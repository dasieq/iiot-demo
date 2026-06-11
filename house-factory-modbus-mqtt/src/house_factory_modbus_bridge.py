import os
import json
from threading import Thread, Lock

import paho.mqtt.client as mqtt

try:
    from pymodbus.server import StartTcpServer
except ImportError:
    from pymodbus.server.sync import StartTcpServer
    
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)


# -----------------------------
# MQTT source configuration
# -----------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

SOURCE_BASE_TOPIC = os.getenv(
    "SOURCE_BASE_TOPIC",
    os.getenv("BASE_TOPIC", "plain-uns/v1/house-factory/line-01")
)

SOURCE_SUBSCRIBE_TOPIC = os.getenv(
    "SOURCE_SUBSCRIBE_TOPIC",
    SOURCE_BASE_TOPIC + "/#"
)


# -----------------------------
# Modbus TCP configuration
# -----------------------------
MODBUS_HOST = os.getenv("MODBUS_HOST", "0.0.0.0")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "5021"))


# -----------------------------
# Holding register map
# -----------------------------
REGISTER_MAP = {
    "process/temperature": {
        "address": 0,
        "scale": 10,
        "type": "float",
        "name": "Temperature x10 degC",
    },
    "process/pressure": {
        "address": 1,
        "scale": 10,
        "type": "float",
        "name": "Pressure x10 kPa",
    },
    "process/motor_speed": {
        "address": 2,
        "scale": 1,
        "type": "int",
        "name": "Motor speed rpm",
    },
    "process/tank_level": {
        "address": 3,
        "scale": 10,
        "type": "float",
        "name": "Tank level x10 percent",
    },
    "process/valve_position": {
        "address": 4,
        "scale": 1,
        "type": "int",
        "name": "Valve position percent",
    },
    "process/flow": {
        "address": 5,
        "scale": 1,
        "type": "int",
        "name": "Flow l/min",
    },
    "status/alarm": {
        "address": 6,
        "scale": 1,
        "type": "bool",
        "name": "Alarm",
    },
    "status/operation": {
        "address": 7,
        "scale": 1,
        "type": "bool",
        "name": "Operation",
    },
    "status/connection": {
        "address": 8,
        "scale": 1,
        "type": "bool",
        "name": "Connection",
    },
    "status/heartbeat": {
        "address": 9,
        "scale": 1,
        "type": "int",
        "name": "Heartbeat",
    },
}


lock = Lock()


# -----------------------------
# Modbus datastore
# -----------------------------
# 100 holding registers, initialized to zero
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 100)
)

context = ModbusServerContext(
    slaves=store,
    single=True
)


def value_to_register(value, info):
    value_type = info["type"]
    scale = info["scale"]

    if value_type == "bool":
        return 1 if bool(value) else 0

    if value_type == "float":
        return int(round(float(value) * scale))

    if value_type == "int":
        return int(value)

    return int(value)


def write_holding_register(address, value):
    with lock:
        # Function code 3 = holding registers
        store.setValues(3, address, [value])


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker, rc={rc}")

    if rc == 0:
        client.subscribe(SOURCE_SUBSCRIBE_TOPIC)
        print(f"Subscribed to MQTT source: {SOURCE_SUBSCRIBE_TOPIC}")
    else:
        print("MQTT connection failed")


def on_message(client, userdata, message):
    topic = message.topic

    if not topic.startswith(SOURCE_BASE_TOPIC + "/"):
        return

    relative_topic = topic[len(SOURCE_BASE_TOPIC) + 1:]

    if relative_topic not in REGISTER_MAP:
        return

    try:
        payload = json.loads(message.payload.decode("utf-8"))
        mqtt_value = payload["value"]

        info = REGISTER_MAP[relative_topic]
        address = info["address"]
        register_value = value_to_register(mqtt_value, info)

        write_holding_register(address, register_value)

        print(
            f"{relative_topic:24s} MQTT={str(mqtt_value):8s} "
            f"-> HR{address + 1} / 4x{40001 + address} = {register_value}"
        )

    except Exception as exc:
        print(f"Bad MQTT message on {topic}: {exc}")


def start_mqtt_client():
    client = mqtt.Client(client_id="plain-uns-to-modbus-bridge")
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to MQTT broker: {MQTT_HOST}:{MQTT_PORT}")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


def print_register_map():
    print()
    print("Modbus TCP register map")
    print("-----------------------")
    print("Holding Registers, Unit ID 1")
    print()
    print(f"{'Address':>7s}  {'Modbus':>8s}  {'Source topic':30s}  {'Description'}")
    print("-" * 90)

    for topic, info in sorted(
        REGISTER_MAP.items(),
        key=lambda item: item[1]["address"]
    ):
        address = info["address"]
        print(
            f"{address:7d}  "
            f"4x{40001 + address:<5d}  "
            f"{topic:30s}  "
            f"{info['name']}"
        )

    print()


def main():
    print("Starting House Factory MQTT -> Modbus TCP bridge")
    print(f"MQTT broker:         {MQTT_HOST}:{MQTT_PORT}")
    print(f"Reading MQTT from:   {SOURCE_SUBSCRIBE_TOPIC}")
    print(f"Serving Modbus TCP:  {MODBUS_HOST}:{MODBUS_PORT}")

    print_register_map()

    mqtt_thread = Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()

    print("Starting Modbus TCP server...")

    StartTcpServer(
        context=context,
        address=(MODBUS_HOST, MODBUS_PORT),
    )


if __name__ == "__main__":
    main()