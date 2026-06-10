# IIoT Demo Portfolio

This repository contains practical Industrial IoT / OT integration demos.

The main project is:

```text
house-factory-modbus-mqtt/
```

It is a simulated factory data integration stack showing how shopfloor-style process data can be exposed through multiple industrial and IIoT interfaces.

---

## Main demo

### House Factory IIoT Integration Demo

Folder:

```text
house-factory-modbus-mqtt/
```

This demo simulates a small industrial process and publishes live values such as:

```text
Temperature
Pressure
Motor speed
Tank level
Valve position
Flow
Alarm status
Operation status
Connection status
Heartbeat
```

The goal is to demonstrate practical data integration between simulated OT systems, MQTT, OPC UA, Modbus TCP, databases, and Ignition.

---

## Supported integration paths

The current stack includes:

```text
Plain MQTT / UNS-style namespace
Sparkplug B MQTT
OPC UA server
Modbus TCP bridge
PostgreSQL 24h rolling historian
SQLite local historian example
Ignition integration
Docker Compose deployment
```

---

## Architecture overview

```text
House Factory simulator
        |
        +--> Plain MQTT / UNS-style topics
        |       plain-uns/v1/house-factory/line-01/...
        |
        +--> Sparkplug B bridge
        |       spBv1.0/house-factory/...
        |
        +--> OPC UA server
        |       opc.tcp://localhost:4840/house-factory/server/
        |
        +--> Modbus TCP bridge
        |       localhost:5021
        |
        +--> PostgreSQL historian
        |       localhost:5432
        |
        +--> SQLite logger
                local Docker volume
```

Ignition can consume the demo data through:

```text
OPC UA connection
Modbus TCP device
MQTT Engine / Sparkplug B
PostgreSQL JDBC connection
Named Queries
Perspective dashboard
```

---

## Docker services

The demo is started with Docker Compose and contains the following services:

```text
house-factory-mosquitto
house-factory-simulator
house-factory-sparkplug
house-factory-opcua
house-factory-modbus-bridge
house-factory-postgres
house-factory-postgres-logger
house-factory-sqlite-logger
```

Useful commands:

```bash
cd house-factory-modbus-mqtt
docker compose up -d --build
docker compose ps
docker compose logs -f
```

Stop the stack:

```bash
docker compose down
```

Remove volumes as well:

```bash
docker compose down -v
```

---

## Main external endpoints

When the stack is running locally, the main endpoints are:

```text
MQTT broker:        localhost:1883
OPC UA server:     opc.tcp://localhost:4840/house-factory/server/
Modbus TCP:        localhost:5021
PostgreSQL:        localhost:5432
```

PostgreSQL demo credentials:

```text
Database: iiot_history
User:     iiot_user
Password: iiot_password
```

These credentials are for local demo use only.

---

## Ignition integration

The Ignition resources are stored inside:

```text
house-factory-modbus-mqtt/ignition/
```

This folder contains:

```text
project-export/
tag-export/
screenshots/
```

The Ignition part demonstrates:

```text
OPC UA tags
Modbus TCP tags
MQTT Engine / Sparkplug tags
PostgreSQL database connection
Named Queries
Perspective dashboard
```

---

## Screenshots

Example screenshots are stored in:

```text
house-factory-modbus-mqtt/screenshots/
house-factory-modbus-mqtt/ignition/screenshots/
```

They show the MQTT namespace, Ignition tag browser, and Perspective dashboard.

---

## Purpose

This demo is intended as a compact IIoT portfolio project.

It shows practical understanding of:

```text
industrial connectivity
OT / IT data flow
MQTT topic design
UNS-style namespace structure
Sparkplug B
OPC UA
Modbus TCP
SQL historian concepts
Ignition integration
Dockerized deployment
```

The project is not intended for production use. It is a local lab environment for learning, testing, and demonstrating IIoT integration concepts.

---

## Security note

Do not expose this stack directly to the internet.

For real deployments, use:

```text
authentication
TLS
firewall rules
VPN access
network segmentation
least-privilege users
secure credential management
proper OT/IT security design
```
