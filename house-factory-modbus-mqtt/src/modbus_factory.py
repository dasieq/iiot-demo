import time
import math
import json
from datetime import datetime, timezone
from threading import Thread

import paho.mqtt.client as mqtt

from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext
)


# -----------------------------
# Modbus configuration
# -----------------------------
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 100)
)
context = ModbusServerContext(slaves=store, single=True)


# -----------------------------
# MQTT configuration
# -----------------------------
MQTT_HOST = "localhost"
MQTT_PORT = 1883
BASE_TOPIC = "uns/v1/house-factory/line-01"

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()


def publish_mqtt(path, value, unit="", quality="GOOD"):
    payload = {
        "value": value,
        "unit": unit,
        "quality": quality,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    topic = f"{BASE_TOPIC}/{path}"
    mqtt_client.publish(topic, json.dumps(payload), retain=True)


def update_values():
    t = 0

    while True:
        # Raw Modbus values, scaled as integers
        temperature_raw = int(250 + 40 * math.sin(t / 20))      # 25.0–29.0 °C
        pressure_raw = int(1200 + 150 * math.sin(t / 15))       # 120.0–135.0 kPa
        motor_speed = int(1450 + 120 * math.sin(t / 10))        # rpm
        tank_level_raw = int(500 + 300 * math.sin(t / 30))      # 20.0–80.0 %
        valve_position = int(50 + 50 * math.sin(t / 12))        # 0–100 %
        flow = int(250 + 80 * math.sin(t / 8))                  # l/min

        alarm = 1 if temperature_raw > 285 or pressure_raw > 1320 else 0
        running = 1
        heartbeat = t % 2

        values = [
            temperature_raw,   # HR 40001
            pressure_raw,      # HR 40002
            motor_speed,       # HR 40003
            tank_level_raw,    # HR 40004
            valve_position,    # HR 40005
            flow,              # HR 40006
            alarm,             # HR 40007
            running,           # HR 40008
            heartbeat          # HR 40009
        ]

        # Write values to Modbus holding registers
        context[0].setValues(3, 0, values)

        # Convert raw Modbus values to engineering values for MQTT
        temperature = round(temperature_raw / 10, 1)
        pressure = round(pressure_raw / 10, 1)
        tank_level = round(tank_level_raw / 10, 1)

        # Publish values to MQTT / UNS
        publish_mqtt("process/temperature", temperature, "degC")
        publish_mqtt("process/pressure", pressure, "kPa")
        publish_mqtt("process/motor_speed", motor_speed, "rpm")
        publish_mqtt("process/tank_level", tank_level, "%")
        publish_mqtt("process/valve_position", valve_position, "%")
        publish_mqtt("process/flow", flow, "l/min")

        publish_mqtt("status/alarm", bool(alarm))
        publish_mqtt("status/operation", bool(running))
        publish_mqtt("status/connection", True)
        publish_mqtt("status/heartbeat", heartbeat)

        t += 1
        time.sleep(1)


Thread(target=update_values, daemon=True).start()

print("Modbus TCP factory simulator running on port 5020")
print("Publishing MQTT values to Mosquitto on localhost:1883")
print(f"MQTT base topic: {BASE_TOPIC}")

StartTcpServer(context, address=("0.0.0.0", 5020))
