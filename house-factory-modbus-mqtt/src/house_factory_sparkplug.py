import os
import json
import time
from threading import Lock

import paho.mqtt.client as mqtt
from mqtt_spb_wrapper import spb_protobuf
from mqtt_spb_wrapper.spb_protobuf import MetricDataType


# -----------------------------
# MQTT broker
# -----------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))


# -----------------------------
# Source plain MQTT UNS
# -----------------------------
SOURCE_BASE_TOPIC = os.getenv(
    "SOURCE_BASE_TOPIC",
    "plain-uns/v1/house-factory/line-01"
)

SOURCE_SUBSCRIBE_TOPIC = os.getenv(
    "SOURCE_SUBSCRIBE_TOPIC",
    SOURCE_BASE_TOPIC + "/#"
)


# -----------------------------
# Sparkplug B configuration
# -----------------------------
SPARKPLUG_NAMESPACE = os.getenv("SPARKPLUG_NAMESPACE", "spBv1.0")
GROUP_ID = os.getenv("SPARKPLUG_GROUP_ID", "house-factory")
EDGE_NODE_ID = os.getenv("SPARKPLUG_EDGE_NODE_ID", "line-01")

SPARKPLUG_CLIENT_ID = os.getenv(
    "SPARKPLUG_CLIENT_ID",
    f"manual-sparkplug-bridge-{EDGE_NODE_ID}"
)

SPARKPLUG_PUBLISH_INTERVAL_SECONDS = float(
    os.getenv("SPARKPLUG_PUBLISH_INTERVAL_SECONDS", "1")
)

INITIAL_WAIT_SECONDS = float(
    os.getenv("SPARKPLUG_INITIAL_WAIT_SECONDS", "5")
)


NBIRTH_TOPIC = f"{SPARKPLUG_NAMESPACE}/{GROUP_ID}/NBIRTH/{EDGE_NODE_ID}"
NDATA_TOPIC = f"{SPARKPLUG_NAMESPACE}/{GROUP_ID}/NDATA/{EDGE_NODE_ID}"
NDEATH_TOPIC = f"{SPARKPLUG_NAMESPACE}/{GROUP_ID}/NDEATH/{EDGE_NODE_ID}"
NCMD_TOPIC = f"{SPARKPLUG_NAMESPACE}/{GROUP_ID}/NCMD/{EDGE_NODE_ID}"


# -----------------------------
# Mapping plain-uns topic -> Sparkplug metric
# -----------------------------
TOPIC_TO_METRIC = {
    "process/temperature": {
        "metric": "Process/Temperature",
        "type": MetricDataType.Double,
        "default": 0.0,
    },
    "process/pressure": {
        "metric": "Process/Pressure",
        "type": MetricDataType.Double,
        "default": 0.0,
    },
    "process/motor_speed": {
        "metric": "Process/Motor_Speed",
        "type": MetricDataType.Int32,
        "default": 0,
    },
    "process/tank_level": {
        "metric": "Process/Tank_Level",
        "type": MetricDataType.Double,
        "default": 0.0,
    },
    "process/valve_position": {
        "metric": "Process/Valve_Position",
        "type": MetricDataType.Int32,
        "default": 0,
    },
    "process/flow": {
        "metric": "Process/Flow",
        "type": MetricDataType.Int32,
        "default": 0,
    },
    "status/alarm": {
        "metric": "Status/Alarm",
        "type": MetricDataType.Boolean,
        "default": False,
    },
    "status/operation": {
        "metric": "Status/Operation",
        "type": MetricDataType.Boolean,
        "default": False,
    },
    "status/connection": {
        "metric": "Status/Connection",
        "type": MetricDataType.Boolean,
        "default": False,
    },
    "status/heartbeat": {
        "metric": "Status/Heartbeat",
        "type": MetricDataType.Int32,
        "default": 0,
    },
}


# -----------------------------
# Runtime state
# -----------------------------
lock = Lock()

latest_values = {
    info["metric"]: info["default"]
    for info in TOPIC_TO_METRIC.values()
}

received_source_topics = set()

data_changed = False
birth_sent = False
rebirth_requested = False

# Sparkplug message sequence.
# Important:
# After every NBIRTH, Ignition expects the next NDATA to have seq = 1.
seq = 0

# Birth/death sequence.
# For this simple demo it stays fixed.
# The same bdSeq is used in NBIRTH and NDEATH.
bdSeq = 0


def current_ms():
    return int(time.time() * 1000)


def next_seq():
    """
    Return current Sparkplug payload sequence number and increment it.

    Expected flow after NBIRTH:
        NBIRTH seq = 0
        first NDATA seq = 1
        next NDATA seq = 2
        ...
    """
    global seq

    value = seq
    seq = (seq + 1) % 256
    return value


def reset_sequence_for_birth():
    """
    Reset Sparkplug sequence before NBIRTH/rebirth.

    Ignition MQTT Engine expects the sequence to restart after a valid birth.
    """
    global seq
    seq = 0


def cast_value(value, metric_type):
    if metric_type == MetricDataType.Boolean:
        return bool(value)

    if metric_type == MetricDataType.Int32:
        return int(value)

    if metric_type == MetricDataType.Double:
        return float(value)

    return value


def add_all_process_metrics(payload, values):
    now = current_ms()

    for info in TOPIC_TO_METRIC.values():
        metric_name = info["metric"]
        metric_type = info["type"]
        metric_value = values.get(metric_name, info["default"])

        spb_protobuf.addMetric(
            payload,
            metric_name,
            None,
            metric_type,
            metric_value,
            timestamp=now,
        )


def create_nbirth_payload(values):
    payload = spb_protobuf.getNodeBirthPayload()
    payload.timestamp = current_ms()
    payload.seq = next_seq()

    spb_protobuf.addMetric(
        payload,
        "bdSeq",
        None,
        MetricDataType.Int64,
        bdSeq,
        timestamp=current_ms(),
    )

    # Required control metric for MQTT Engine rebirth requests.
    spb_protobuf.addMetric(
        payload,
        "Node Control/Rebirth",
        None,
        MetricDataType.Boolean,
        False,
        timestamp=current_ms(),
    )

    add_all_process_metrics(payload, values)

    return payload.SerializeToString()


def create_ndata_payload(values):
    payload = spb_protobuf.getDdataPayload()
    payload.timestamp = current_ms()
    payload.seq = next_seq()

    add_all_process_metrics(payload, values)

    return payload.SerializeToString()


def create_ndeath_payload():
    payload = spb_protobuf.getNodeDeathPayload()
    payload.timestamp = current_ms()

    spb_protobuf.addMetric(
        payload,
        "bdSeq",
        None,
        MetricDataType.Int64,
        bdSeq,
        timestamp=current_ms(),
    )

    return payload.SerializeToString()


def publish_nbirth(client):
    global birth_sent

    with lock:
        values = dict(latest_values)

    # Critical fix:
    # Every birth/rebirth restarts the Sparkplug message sequence.
    reset_sequence_for_birth()

    client.publish(
        NBIRTH_TOPIC,
        create_nbirth_payload(values),
        qos=0,
        retain=False,
    )

    birth_sent = True

    print(f"Published NBIRTH: {NBIRTH_TOPIC}")


def publish_ndata(client):
    with lock:
        values = dict(latest_values)

    client.publish(
        NDATA_TOPIC,
        create_ndata_payload(values),
        qos=0,
        retain=False,
    )

    print(f"Published NDATA: {NDATA_TOPIC}")


def handle_plain_uns_message(message):
    global data_changed

    topic = message.topic

    if not topic.startswith(SOURCE_BASE_TOPIC + "/"):
        return

    relative_topic = topic[len(SOURCE_BASE_TOPIC) + 1:]

    if relative_topic not in TOPIC_TO_METRIC:
        return

    payload = json.loads(message.payload.decode("utf-8"))
    value = payload["value"]

    info = TOPIC_TO_METRIC[relative_topic]
    metric_name = info["metric"]
    metric_type = info["type"]

    value = cast_value(value, metric_type)

    with lock:
        latest_values[metric_name] = value
        received_source_topics.add(relative_topic)
        data_changed = True

    print(f"Received {relative_topic} = {value}")


def handle_ncmd_message(message):
    global rebirth_requested

    try:
        payload = spb_protobuf.sparkplug_b_pb2.Payload()
        payload.ParseFromString(message.payload)

        for metric in payload.metrics:
            name = metric.name

            if name == "Node Control/Rebirth":
                value = spb_protobuf.getMetricValue(metric)
                print(f"Received NCMD Node Control/Rebirth = {value}")

                if value:
                    rebirth_requested = True

    except Exception as exc:
        print(f"Bad NCMD message: {exc}")


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker, rc={rc}")

    client.subscribe(SOURCE_SUBSCRIBE_TOPIC)
    client.subscribe(NCMD_TOPIC)

    print(f"Subscribed to source:  {SOURCE_SUBSCRIBE_TOPIC}")
    print(f"Subscribed to command: {NCMD_TOPIC}")


def on_message(client, userdata, message):
    try:
        if message.topic.startswith(SOURCE_BASE_TOPIC + "/"):
            handle_plain_uns_message(message)

        elif message.topic == NCMD_TOPIC:
            handle_ncmd_message(message)

    except Exception as exc:
        print(f"Message handling error on {message.topic}: {exc}")


def wait_for_initial_values(timeout_seconds):
    print("Waiting for retained plain-uns values...")

    start = time.time()
    expected_count = len(TOPIC_TO_METRIC)
    count = 0

    while time.time() - start < timeout_seconds:
        with lock:
            count = len(received_source_topics)

        if count >= expected_count:
            print("All initial plain-uns values received")
            return

        time.sleep(0.2)

    print(f"Initial wait finished with {count}/{expected_count} values")


def main():
    global data_changed, rebirth_requested

    print("Starting manual Sparkplug B bridge")
    print(f"MQTT broker:    {MQTT_HOST}:{MQTT_PORT}")
    print(f"Reading from:   {SOURCE_SUBSCRIBE_TOPIC}")
    print(f"Publishing to:  {NDATA_TOPIC}")
    print(f"Command topic:  {NCMD_TOPIC}")
    print(f"Client ID:      {SPARKPLUG_CLIENT_ID}")
    print(f"Publish period: {SPARKPLUG_PUBLISH_INTERVAL_SECONDS} s")
    print(f"Initial wait:   {INITIAL_WAIT_SECONDS} s")
    print(f"bdSeq:          {bdSeq}")

    client = mqtt.Client(client_id=SPARKPLUG_CLIENT_ID)

    client.on_connect = on_connect
    client.on_message = on_message

    client.will_set(
        NDEATH_TOPIC,
        create_ndeath_payload(),
        qos=0,
        retain=False,
    )

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    wait_for_initial_values(timeout_seconds=INITIAL_WAIT_SECONDS)

    publish_nbirth(client)

    try:
        while True:
            do_publish = False
            do_rebirth = False

            with lock:
                if data_changed:
                    do_publish = True
                    data_changed = False

                if rebirth_requested:
                    do_rebirth = True
                    rebirth_requested = False

            if do_rebirth:
                print("Handling rebirth request")
                publish_nbirth(client)

                # After a rebirth, skip this loop's normal data publish.
                # The next NDATA should come from the next data update.
                do_publish = False

            if do_publish and birth_sent:
                publish_ndata(client)

            time.sleep(SPARKPLUG_PUBLISH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Stopping manual Sparkplug bridge...")

    finally:
        client.publish(
            NDEATH_TOPIC,
            create_ndeath_payload(),
            qos=0,
            retain=False,
        )
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()