import os
import time
import math
import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


# -----------------------------
# MQTT configuration
# -----------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
BASE_TOPIC = os.getenv(
    "BASE_TOPIC",
    "plain-uns/v1/house-factory/line-01"
)

PUBLISH_INTERVAL_SECONDS = float(os.getenv("PUBLISH_INTERVAL_SECONDS", "1"))


mqtt_client = mqtt.Client()


def connect_mqtt():
    print(f"Connecting to MQTT broker: {MQTT_HOST}:{MQTT_PORT}")
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
        # Simulated raw PLC-like values
        temperature_raw = int(250 + 40 * math.sin(t / 20))      # 25.0–29.0 °C
        pressure_raw = int(1200 + 150 * math.sin(t / 15))       # 120.0–135.0 kPa
        motor_speed = int(1450 + 120 * math.sin(t / 10))        # rpm
        tank_level_raw = int(500 + 300 * math.sin(t / 30))      # 20.0–80.0 %
        valve_position = int(50 + 50 * math.sin(t / 12))        # 0–100 %
        flow = int(250 + 80 * math.sin(t / 8))                  # l/min

        alarm = temperature_raw > 285 or pressure_raw > 1320
        running = True
        heartbeat = t % 2

        # Convert raw values to engineering values
        temperature = round(temperature_raw / 10, 1)
        pressure = round(pressure_raw / 10, 1)
        tank_level = round(tank_level_raw / 10, 1)

        # Publish process values
        publish_mqtt("process/temperature", temperature, "degC")
        publish_mqtt("process/pressure", pressure, "kPa")
        publish_mqtt("process/motor_speed", motor_speed, "rpm")
        publish_mqtt("process/tank_level", tank_level, "%")
        publish_mqtt("process/valve_position", valve_position, "%")
        publish_mqtt("process/flow", flow, "l/min")

        # Publish status values
        publish_mqtt("status/alarm", alarm)
        publish_mqtt("status/operation", running)
        publish_mqtt("status/connection", True)
        publish_mqtt("status/heartbeat", heartbeat)

        print(
            f"Published cycle {t}: "
            f"T={temperature} degC, "
            f"P={pressure} kPa, "
            f"Speed={motor_speed} rpm, "
            f"Tank={tank_level} %, "
            f"Valve={valve_position} %, "
            f"Flow={flow} l/min, "
            f"Alarm={alarm}, "
            f"Heartbeat={heartbeat}"
        )

        t += 1
        time.sleep(PUBLISH_INTERVAL_SECONDS)


def main():
    print("Starting House Factory MQTT simulator")
    print(f"MQTT broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"MQTT base topic: {BASE_TOPIC}")
    print(f"Publish interval: {PUBLISH_INTERVAL_SECONDS} s")

    connect_mqtt()

    try:
        update_values()
    except KeyboardInterrupt:
        print("Stopping MQTT simulator...")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()