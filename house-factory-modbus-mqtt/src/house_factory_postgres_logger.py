import os
import json
import time
from datetime import datetime, timezone, timedelta

import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import execute_batch


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
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "1800"))

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
FLUSH_INTERVAL_SECONDS = float(os.getenv("FLUSH_INTERVAL_SECONDS", "2"))

PRINT_EVERY_BATCH = os.getenv("PRINT_EVERY_BATCH", "true").lower() == "true"


# -----------------------------
# Runtime state
# -----------------------------
conn = None
cur = None
buffer = []

last_flush_time = time.time()
last_cleanup_time = 0
saved_total = 0


def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def ensure_db_connection():
    global conn, cur

    if conn is None or conn.closed:
        conn = get_connection()
        cur = conn.cursor()

    return conn, cur


def init_db():
    conn_init = get_connection()
    cur_init = conn_init.cursor()

    cur_init.execute("""
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

    cur_init.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_history_timestamp
        ON tag_history(timestamp)
    """)

    cur_init.execute("""
        CREATE INDEX IF NOT EXISTS idx_tag_history_topic
        ON tag_history(topic)
    """)

    conn_init.commit()
    cur_init.close()
    conn_init.close()


def add_to_buffer(topic, payload_text):
    try:
        data = json.loads(payload_text)

        timestamp = data.get("timestamp")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        value = data.get("value")
        unit = data.get("unit", "")
        quality = data.get("quality", "")

        buffer.append((
            timestamp,
            topic,
            str(value),
            unit,
            quality,
            payload_text,
        ))

    except Exception as exc:
        print(f"Payload parse error for topic {topic}: {exc}")
        print(f"Payload was: {payload_text}")


def flush_buffer(force=False):
    global buffer, last_flush_time, saved_total, conn, cur

    now = time.time()

    if not buffer:
        return

    if not force:
        if len(buffer) < BATCH_SIZE and (now - last_flush_time) < FLUSH_INTERVAL_SECONDS:
            return

    try:
        db_conn, db_cur = ensure_db_connection()

        execute_batch(db_cur, """
            INSERT INTO tag_history (
                timestamp,
                topic,
                value,
                unit,
                quality,
                raw_json
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """, buffer, page_size=BATCH_SIZE)

        db_conn.commit()

        saved_count = len(buffer)
        saved_total += saved_count

        if PRINT_EVERY_BATCH:
            print(f"Saved batch: {saved_count} rows, total: {saved_total}")

        buffer = []
        last_flush_time = now

    except Exception as exc:
        print(f"DB batch save error: {exc}")

        try:
            if conn:
                conn.rollback()
                conn.close()
        except Exception:
            pass

        conn = None
        cur = None


def cleanup_old_rows():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)

    try:
        db_conn, db_cur = ensure_db_connection()

        db_cur.execute("""
            DELETE FROM tag_history
            WHERE timestamp < %s
        """, (cutoff,))

        deleted = db_cur.rowcount
        db_conn.commit()

        if deleted > 0:
            print(f"Deleted old rows older than {RETENTION_HOURS}h: {deleted}")

    except Exception as exc:
        print(f"Cleanup error: {exc}")
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass


def maybe_cleanup():
    global last_cleanup_time

    now = time.time()

    if now - last_cleanup_time >= CLEANUP_INTERVAL_SECONDS:
        flush_buffer(force=True)
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

        add_to_buffer(msg.topic, payload_text)
        flush_buffer()
        maybe_cleanup()

    except Exception as exc:
        print(f"Message error: {exc}")


def close_db():
    global conn, cur

    try:
        flush_buffer(force=True)
    except Exception:
        pass

    try:
        if cur:
            cur.close()
        if conn:
            conn.close()
    except Exception:
        pass


def main():
    print("Starting PostgreSQL MQTT logger")
    print(f"MQTT broker:         {MQTT_HOST}:{MQTT_PORT}")
    print(f"Subscribed topic:    {SUBSCRIBE_TOPIC}")
    print(f"PostgreSQL host:     {PG_HOST}:{PG_PORT}")
    print(f"PostgreSQL database: {PG_DATABASE}")
    print(f"PostgreSQL user:     {PG_USER}")
    print(f"Retention window:    last {RETENTION_HOURS} hours")
    print(f"Cleanup interval:    {CLEANUP_INTERVAL_SECONDS} seconds")
    print(f"Batch size:          {BATCH_SIZE}")
    print(f"Flush interval:      {FLUSH_INTERVAL_SECONDS} seconds")

    init_db()
    ensure_db_connection()
    cleanup_old_rows()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_forever()
    finally:
        close_db()


if __name__ == "__main__":
    main()