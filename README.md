# IIoT Demo Portfolio

This repository contains a practical Industrial IoT / OT integration demo.

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

The goal is to demonstrate practical OT/IT data integration between simulated shopfloor systems, MQTT, OPC UA, Modbus TCP, databases, Docker and Ignition.

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

## Quick start

From the project folder:

```bash
cd house-factory-modbus-mqtt
docker compose up -d --build
docker compose ps
```

Expected result: all services should be `Up`, and PostgreSQL should be `healthy`.

Stop the stack:

```bash
docker compose down
```

Remove containers and stored database volumes:

```bash
docker compose down -v
```

---

## Docker services

The Docker Compose stack contains:

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
docker compose ps
docker compose logs -f
docker compose logs -f simulator
docker compose logs -f postgres-logger
docker compose logs -f sparkplug
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

## Basic validation

Check live MQTT data:

```bash
docker compose exec mosquitto mosquitto_sub -t 'plain-uns/v1/house-factory/line-01/#' -v
```

Check PostgreSQL historian data:

```bash
docker compose exec postgres psql -U iiot_user -d iiot_history
```

Then run:

```sql
SELECT id, timestamp, topic, value, unit, quality
FROM tag_history
ORDER BY id DESC
LIMIT 10;
```

Exit PostgreSQL:

```sql
\q
```

Check SQLite historian data:

```bash
docker compose exec -T sqlite-logger python - <<'EOF'
import sqlite3

db = "/data/iiot_history.db"
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM tag_history;")
print("Rows:", cur.fetchone()[0])

cur.execute("""
SELECT id, timestamp, topic, value, unit, quality
FROM tag_history
ORDER BY id DESC
LIMIT 10
""")

for row in cur.fetchall():
    print(row)

conn.close()
EOF
```

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

They show the MQTT namespace, Ignition tag browser, database connection, Docker services and Perspective dashboard.

---

## Tested environment

The stack has been tested with Docker Compose on:

```text
Windows / Docker Desktop
WSL Ubuntu
```

The main external services were verified locally:

```text
MQTT
OPC UA
Modbus TCP
PostgreSQL
SQLite logger
Sparkplug B MQTT
Ignition integration
```

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

The project is not intended for production use. It is a local lab environment for learning, testing and demonstrating IIoT integration concepts.

---

## Roadmap

Possible next steps:

```text
HTTP API over SQLite / PostgreSQL historian
Optional cloud telemetry bridge
Databricks / cloud analytics concept
Improved Ignition Perspective dashboard
Additional screenshots and setup documentation
```

The local OT layer remains responsible for live data access. Cloud or analytics extensions are intended for selected telemetry, reporting, long-term storage and analysis.

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

The default database credentials are local demo credentials only and must not be used in production.
