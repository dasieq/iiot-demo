import os
import json
import time
from datetime import datetime, timezone, timedelta

import paho.mqtt.client as mqtt
import psycopg2


# -----------------------------
# MQTT configuration
# -----------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

SUBSCRIBE_TOPIC = os.getenv(
    "SUBSCRIBE_TOPIC",
    os.getenv("SOURCE_SUBSCRIBE_TOPIC", "plain-uns/v1/house-factory/line-01/#")
)


# -----------------------------
# PostgreSQL configuration
# -----------------------------
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "iiot_history")
PG_USER = os.getenv("PG_USER", "iiot_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "iiot_password")

RETENTION_HOURS = int(os.getenv("RETENTION_HOURS", "24"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))


# -----------------------------
# Runtime state
# -----------------------------
last_cleanup_time = 0


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tag_history (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            topic TEXT NOT NULL,
            value TEXT,
            unit TEXT,
            quality TEXT,
            raw_json JSONB
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_history_timestamp
        ON tag_history(timestamp)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_history_topic
        ON tag_history(topic)
    """)

    conn.commit()
    cur.close()
    conn.close()


def save_to_db(topic, payload_text):
    try:
        data = json.loads(payload_text)

        timestamp = data.get("timestamp")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        value = data.get("value")
        unit = data.get("unit", "")
        quality = data.get("quality", "")

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO tag_history (
                timestamp,
                topic,
                value,
                unit,
                quality,
                raw_json
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """, (
            timestamp,
            topic,
            str(value),
            unit,
            quality,
            payload_text,
        ))

        conn.commit()
        cur.close()
        conn.close()

        print(f"Saved: {topic} = {value} {unit} [{quality}]")

    except Exception as exc:
        print(f"DB save error for topic {topic}: {exc}")
        print(f"Payload was: {payload_text}")


def cleanup_old_rows():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM tag_history
        WHERE timestamp < %s
    """, (cutoff,))

    deleted = cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    if deleted > 0:
        print(f"Deleted old rows older than {RETENTION_HOURS}h: {deleted}")


def maybe_cleanup():
    global last_cleanup_time

    now = time.time()

    if now - last_cleanup_time >= CLEANUP_INTERVAL_SECONDS:
        cleanup_old_rows()
        last_cleanup_time = now


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(SUBSCRIBE_TOPIC)
        print(f"Subscribed to: {SUBSCRIBE_TOPIC}")
    else:
        print(f"MQTT connection failed with code: {rc}")


def on_message(client, userdata, msg):
    try:
        payload_text = msg.payload.decode("utf-8")

        save_to_db(msg.topic, payload_text)
        maybe_cleanup()

    except Exception as exc:
        print(f"Message error: {exc}")


def main():
    print("Starting PostgreSQL MQTT logger")
    print(f"MQTT broker:         {MQTT_HOST}:{MQTT_PORT}")
    print(f"Subscribed topic:    {SUBSCRIBE_TOPIC}")
    print(f"PostgreSQL host:     {PG_HOST}:{PG_PORT}")
    print(f"PostgreSQL database: {PG_DATABASE}")
    print(f"PostgreSQL user:     {PG_USER}")
    print(f"Retention window:    last {RETENTION_HOURS} hours")
    print(f"Cleanup interval:    {CLEANUP_INTERVAL_SECONDS} seconds")

    init_db()
    cleanup_old_rows()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()