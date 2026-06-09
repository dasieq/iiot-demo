# IIoT Demo

A small portfolio repository for Industrial IoT / OT connectivity experiments.

This repository contains demo projects focused on industrial data acquisition, protocol conversion, MQTT publishing, UNS-style topic structures, and future integration with tools such as Ignition, OPC UA, databases, and dashboards.

The purpose is to build a practical, understandable IIoT learning environment using a Raspberry Pi / Linux machine and open-source tools.

## Current project

### House Factory Modbus MQTT Demo

A simple factory-line simulator that exposes process values over **Modbus TCP** and publishes the same values to an **MQTT broker** using a UNS-style topic structure.

Project folder:

```text
house-factory-modbus-mqtt/
```

Data flow:

```text
Python simulator
      |
      | Modbus TCP
      v
Modbus clients / SCADA / Ignition
      |
      | MQTT
      v
Mosquitto broker / UNS-style namespace
```

The simulator publishes example process values such as:

* temperature
* pressure
* motor speed
* tank level
* valve position
* flow
* alarm status
* running status
* heartbeat

MQTT base topic:

```text
uns/v1/house-factory/line-01
```

Example MQTT topic:

```text
uns/v1/house-factory/line-01/process/temperature
```

Example payload:

```json
{
  "value": 26.7,
  "unit": "degC",
  "quality": "GOOD",
  "timestamp": "2026-06-09T17:30:00.000000+00:00"
}
```

## Repository structure

```text
iiot-demo/
├── README.md
└── house-factory-modbus-mqtt/
    ├── README.md
    ├── src/
    │   └── modbus_factory.py
    ├── mosquitto/
    │   └── house-factory.conf
    └── requirements.txt
```

## Technologies used

* Python 3
* Modbus TCP
* MQTT
* Mosquitto
* Raspberry Pi / Linux
* UNS-style topic structure
* JSON payloads

Planned future additions may include:

* Ignition Perspective dashboard
* MQTT Engine / MQTT Transmission concepts
* OPC UA integration
* Docker Compose setup
* historical data logging
* Grafana or web dashboard
* systemd service for automatic startup

## Quick start

Open the House Factory project:

```bash
cd house-factory-modbus-mqtt
```

Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the simulator:

```bash
python src/modbus_factory.py
```

Subscribe to MQTT messages:

```bash
mosquitto_sub -h localhost -t "uns/v1/house-factory/#" -v
```

## Security note

This repository is intended for local lab and portfolio demonstration use.

The example Mosquitto configuration may allow anonymous access for simplicity. Do not expose the broker or Modbus TCP server directly to the internet.

For real industrial or production environments, use:

* authentication
* TLS
* firewall rules
* VPN access
* network segmentation
* proper user and permission management
* secure handling of credentials

## Goal

The goal of this repository is to demonstrate a practical IIoT data path:

```text
Industrial-style data source -> Raspberry Pi / Linux -> MQTT -> UNS-style namespace -> SCADA / dashboard / analytics
```

It is designed as a small but expandable foundation for learning and demonstrating industrial connectivity concepts.
