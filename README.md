# IIoT Demo

A small portfolio repository for Industrial IoT / OT connectivity experiments.

This repository contains demo projects focused on industrial data acquisition, protocol conversion, MQTT publishing, UNS-style topic structures, containerized workloads, and integration with tools such as Ignition, OPC UA, databases, and dashboards.

The purpose is to build a practical, understandable IIoT learning environment using Raspberry Pi / Linux, Docker, Python, MQTT, Modbus TCP, and open-source tools.

## Current project

### House Factory Modbus MQTT Demo

A small factory-line simulator that exposes process values over **Modbus TCP** and publishes the same values to an **MQTT broker** using a UNS-style topic structure.

The project also includes:

* Docker Compose deployment
* Mosquitto MQTT broker configuration
* MQTT Explorer verification
* Ignition tag export
* Ignition Perspective project resources
* basic SCADA / IIoT dashboard concept

Project folder:

```text
house-factory-modbus-mqtt/
```

## Data flow

```text
Python factory simulator
        |
        | Modbus TCP
        v
Ignition OPC tags
        |
        v
Perspective dashboard
```

```text
Python factory simulator
        |
        | MQTT
        v
Mosquitto broker
        |
        v
UNS-style topic structure
```

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
    ├── ignition/
    │   ├── README.md
    │   ├── project-export/
    │   ├── tag-export/
    │   └── screenshots/
    ├── screenshots/
    ├── requirements.txt
    ├── Dockerfile
    ├── docker-compose.yml
    └── .dockerignore
```

## Technologies used

* Python 3
* Modbus TCP
* MQTT
* Mosquitto
* Docker
* Docker Compose
* Raspberry Pi / Linux
* Windows + WSL2 test environment
* Ignition
* Ignition Perspective
* UNS-style topic structure
* JSON payloads

## Quick start with Docker

Open the House Factory project:

```bash
cd house-factory-modbus-mqtt
```

Start the demo stack:

```bash
docker compose up --build
```

This starts:

```text
Mosquitto MQTT broker  -> localhost:1883
Modbus TCP simulator   -> localhost:5020
```

Subscribe to MQTT messages:

```bash
docker exec -it house-factory-mosquitto mosquitto_sub -h localhost -t "uns/v1/house-factory/#" -v
```

Stop the demo:

```bash
docker compose down
```

## Local run without Docker

The project can also be run directly on Raspberry Pi / Linux with Python and Mosquitto installed.

See the detailed project instructions here:

```text
house-factory-modbus-mqtt/README.md
```

## Security note

This repository is intended for local lab and portfolio demonstration use.

The example Mosquitto configuration may allow anonymous access for simplicity. Do not expose the MQTT broker, Modbus TCP server, or Ignition Gateway directly to the internet.

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
Industrial-style data source
        -> Raspberry Pi / Linux / Docker
        -> MQTT / Modbus TCP
        -> UNS-style namespace
        -> Ignition / SCADA / dashboard / analytics
```

It is designed as a small but expandable foundation for learning and demonstrating industrial connectivity concepts.
