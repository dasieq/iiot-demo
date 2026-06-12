import os
import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from awscrt import io, mqtt as aws_mqtt
from awsiot import mqtt_connection_builder


# -----------------------------
# Local MQTT configuration
# -----------------------------
LOCAL_MQTT_HOST = os.getenv("LOCAL_MQTT_HOST", "localhost")
LOCAL_MQTT_PORT = int(os.getenv("LOCAL_MQTT_PORT", "1883"))

LOCAL_SUBSCRIBE_TOPIC = os.getenv(
    "LOCAL_SUBSCRIBE_TOPIC",
    "plain-uns/v1/house-factory/line-01/#"
)

LOCAL_BASE_TOPIC = os.getenv(
    "LOCAL_BASE_TOPIC",
    "plain-uns/v1/house-factory/line-01"
)


# -----------------------------
# Cloud publish configuration
# -----------------------------
CLOUD_PUBLISH_INTERVAL_SECONDS = float(
    os.getenv("CLOUD_PUBLISH_INTERVAL_SECONDS", "5")
)

last_publish_time = {}


# -----------------------------
# AWS IoT configuration
# -----------------------------
AWS_IOT_ENDPOINT = os.getenv(
    "AWS_IOT_ENDPOINT",
    "a39fq8pk1n1f0l-ats.iot.eu-north-1.amazonaws.com"
)

AWS_CLIENT_ID = os.getenv("AWS_CLIENT_ID", "basicPubSub")

AWS_CERT_FILE = os.getenv(
    "AWS_CERT_FILE",
    "aws/raspberry-iiot-demo.cert.pem"
)

AWS_KEY_FILE = os.getenv(
    "AWS_KEY_FILE",
    "aws/raspberry-iiot-demo.private.key"
)

AWS_ROOT_CA_FILE = os.getenv(
    "AWS_ROOT_CA_FILE",
    "aws/root-CA.crt"
)

AWS_TOPIC_PREFIX = os.getenv(
    "AWS_TOPIC_PREFIX",
    "iiot/house-factory/line-01"
)

PUBLISH_QOS = aws_mqtt.QoS.AT_LEAST_ONCE


aws_connection = None


def build_aws_connection():
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    return mqtt_connection_builder.mtls_from_path(
        endpoint=AWS_IOT_ENDPOINT,
        cert_filepath=AWS_CERT_FILE,
        pri_key_filepath=AWS_KEY_FILE,
        ca_filepath=AWS_ROOT_CA_FILE,
        client_bootstrap=client_bootstrap,
        client_id=AWS_CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30,
    )


def local_topic_to_aws_topic(local_topic: str) -> str:
    suffix = local_topic.replace(LOCAL_BASE_TOPIC, "", 1).strip("/")
    return f"{AWS_TOPIC_PREFIX}/{suffix}"


def should_publish(topic: str) -> bool:
    now = time.time()
    last_time = last_publish_time.get(topic, 0)

    if now - last_time < CLOUD_PUBLISH_INTERVAL_SECONDS:
        return False

    last_publish_time[topic] = now
    return True


def on_local_message(client, userdata, msg):
    try:
        if not should_publish(msg.topic):
            return

        payload_text = msg.payload.decode("utf-8")
        payload = json.loads(payload_text)

        cloud_payload = {
            "source": "raspberry-edge",
            "local_topic": msg.topic,
            "cloud_topic": local_topic_to_aws_topic(msg.topic),
            "value": payload.get("value"),
            "unit": payload.get("unit", ""),
            "quality": payload.get("quality", "UNKNOWN"),
            "timestamp": payload.get("timestamp"),
            "cloud_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        aws_topic = cloud_payload["cloud_topic"]

        publish_future, packet_id = aws_connection.publish(
            topic=aws_topic,
            payload=json.dumps(cloud_payload),
            qos=PUBLISH_QOS,
        )

        publish_future.result()

        print(f"Forwarded: {msg.topic} -> {aws_topic}")

    except Exception as exc:
        print(f"ERROR processing MQTT message from {msg.topic}: {exc}")


def main():
    global aws_connection

    print("Starting House Factory AWS IoT publisher")
    print(f"Local MQTT: {LOCAL_MQTT_HOST}:{LOCAL_MQTT_PORT}")
    print(f"Local subscribe topic: {LOCAL_SUBSCRIBE_TOPIC}")
    print(f"Cloud publish interval: {CLOUD_PUBLISH_INTERVAL_SECONDS} s")
    print(f"AWS endpoint: {AWS_IOT_ENDPOINT}")
    print(f"AWS client ID: {AWS_CLIENT_ID}")
    print(f"AWS topic prefix: {AWS_TOPIC_PREFIX}")

    aws_connection = build_aws_connection()

    print("Connecting to AWS IoT Core...")
    aws_connection.connect().result()
    print("Connected to AWS IoT Core")

    local_client = mqtt.Client()
    local_client.on_message = on_local_message

    print("Connecting to local MQTT broker...")
    local_client.connect(LOCAL_MQTT_HOST, LOCAL_MQTT_PORT, 60)
    local_client.subscribe(LOCAL_SUBSCRIBE_TOPIC)
    print("Connected to local MQTT broker")

    try:
        local_client.loop_forever()
    except KeyboardInterrupt:
        print("Stopping AWS IoT publisher...")
    finally:
        local_client.disconnect()
        aws_connection.disconnect().result()


if __name__ == "__main__":
    main()