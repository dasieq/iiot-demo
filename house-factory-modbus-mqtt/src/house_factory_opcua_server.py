import os
import asyncio
import json
from threading import Lock

import paho.mqtt.client as mqtt
from asyncua import Server


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
# OPC UA configuration
# -----------------------------
OPCUA_HOST = os.getenv("OPCUA_HOST", "0.0.0.0")
OPCUA_PORT = int(os.getenv("OPCUA_PORT", "4840"))

OPCUA_ENDPOINT = os.getenv(
    "OPCUA_ENDPOINT",
    f"opc.tcp://{OPCUA_HOST}:{OPCUA_PORT}/house-factory/server/"
)

OPCUA_NAMESPACE_URI = os.getenv(
    "OPCUA_NAMESPACE_URI",
    "urn:house-factory:line-01"
)

OPCUA_SERVER_NAME = os.getenv(
    "OPCUA_SERVER_NAME",
    "House Factory OPC UA Server"
)

OPCUA_UPDATE_INTERVAL_SECONDS = float(
    os.getenv("OPCUA_UPDATE_INTERVAL_SECONDS", "0.2")
)


# -----------------------------
# MQTT topic -> OPC UA variable mapping
# -----------------------------
TOPIC_TO_VARIABLE = {
    "process/temperature": {
        "folder": "Process",
        "name": "Temperature",
        "type": "float",
        "default": 0.0,
    },
    "process/pressure": {
        "folder": "Process",
        "name": "Pressure",
        "type": "float",
        "default": 0.0,
    },
    "process/motor_speed": {
        "folder": "Process",
        "name": "MotorSpeed",
        "type": "int",
        "default": 0,
    },
    "process/tank_level": {
        "folder": "Process",
        "name": "TankLevel",
        "type": "float",
        "default": 0.0,
    },
    "process/valve_position": {
        "folder": "Process",
        "name": "ValvePosition",
        "type": "int",
        "default": 0,
    },
    "process/flow": {
        "folder": "Process",
        "name": "Flow",
        "type": "int",
        "default": 0,
    },
    "status/alarm": {
        "folder": "Status",
        "name": "Alarm",
        "type": "bool",
        "default": False,
    },
    "status/operation": {
        "folder": "Status",
        "name": "Operation",
        "type": "bool",
        "default": False,
    },
    "status/connection": {
        "folder": "Status",
        "name": "Connection",
        "type": "bool",
        "default": False,
    },
    "status/heartbeat": {
        "folder": "Status",
        "name": "Heartbeat",
        "type": "int",
        "default": 0,
    },
}


# -----------------------------
# Runtime state
# -----------------------------
lock = Lock()

latest_values = {}
changed_variables = set()


def cast_value(value, value_type):
    if value_type == "bool":
        return bool(value)

    if value_type == "int":
        return int(value)

    if value_type == "float":
        return float(value)

    return value


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

    if relative_topic not in TOPIC_TO_VARIABLE:
        return

    try:
        payload = json.loads(message.payload.decode("utf-8"))
        mqtt_value = payload["value"]

        info = TOPIC_TO_VARIABLE[relative_topic]
        variable_name = info["name"]
        value_type = info["type"]

        value = cast_value(mqtt_value, value_type)

        with lock:
            latest_values[variable_name] = value
            changed_variables.add(variable_name)

        print(
            f"{relative_topic:24s} "
            f"MQTT={str(mqtt_value):8s} "
            f"-> OPCUA {variable_name}={value}"
        )

    except Exception as exc:
        print(f"Bad MQTT message on {topic}: {exc}")


def start_mqtt_client():
    client = mqtt.Client(client_id="plain-uns-to-opcua-server")
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to MQTT broker: {MQTT_HOST}:{MQTT_PORT}")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    return client


async def create_opcua_server():
    server = Server()
    await server.init()

    server.set_endpoint(OPCUA_ENDPOINT)
    server.set_server_name(OPCUA_SERVER_NAME)

    idx = await server.register_namespace(OPCUA_NAMESPACE_URI)

    objects = server.nodes.objects

    house_factory = await objects.add_object(idx, "HouseFactory")
    line_01 = await house_factory.add_object(idx, "Line01")

    process_folder = await line_01.add_object(idx, "Process")
    status_folder = await line_01.add_object(idx, "Status")

    opcua_variables = {}

    for topic, info in TOPIC_TO_VARIABLE.items():
        folder_name = info["folder"]
        variable_name = info["name"]
        default_value = info["default"]

        parent = process_folder if folder_name == "Process" else status_folder

        var = await parent.add_variable(idx, variable_name, default_value)
        opcua_variables[variable_name] = var

        with lock:
            latest_values[variable_name] = default_value

    return server, opcua_variables


async def update_opcua_variables(opcua_variables):
    with lock:
        variables_to_update = list(changed_variables)
        changed_variables.clear()

        values_snapshot = {
            name: latest_values[name]
            for name in variables_to_update
            if name in latest_values
        }

    for variable_name, value in values_snapshot.items():
        var = opcua_variables.get(variable_name)

        if var is not None:
            await var.write_value(value)


async def main():
    print("Starting House Factory OPC UA server")
    print(f"MQTT broker:        {MQTT_HOST}:{MQTT_PORT}")
    print(f"Reading MQTT from:  {SOURCE_SUBSCRIBE_TOPIC}")
    print(f"OPC UA endpoint:   {OPCUA_ENDPOINT}")
    print(f"Namespace URI:      {OPCUA_NAMESPACE_URI}")
    print(f"Update interval:    {OPCUA_UPDATE_INTERVAL_SECONDS} s")

    mqtt_client = start_mqtt_client()

    try:
        server, opcua_variables = await create_opcua_server()

        async with server:
            print("OPC UA server is running")

            while True:
                await update_opcua_variables(opcua_variables)
                await asyncio.sleep(OPCUA_UPDATE_INTERVAL_SECONDS)

    finally:
        print("Stopping MQTT client...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("Stopping OPC UA server...")