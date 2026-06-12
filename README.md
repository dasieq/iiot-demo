# IIoT Demo Portfolio

Practical Industrial IoT / OT integration demo built around a simulated factory line.

The main project is:

```text
house-factory-modbus-mqtt/
```

It demonstrates how shopfloor-style process data can be generated, published, transformed, stored and exposed through common industrial and IT interfaces: MQTT, UNS-style topics, Sparkplug B, OPC UA, Modbus TCP, PostgreSQL, SQLite, HTTP API, Docker Compose and Ignition.

---

## What the demo simulates

The simulator publishes live process and status values for a small factory line:

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

The values are published every second to a plain MQTT namespace that follows a simple Unified Namespace-style structure.

Base topic:

```text
plain-uns/v1/house-factory/line-01
```

Example topics:

```text
plain-uns/v1/house-factory/line-01/process/temperature
plain-uns/v1/house-factory/line-01/process/pressure
plain-uns/v1/house-factory/line-01/status/alarm
plain-uns/v1/house-factory/line-01/status/heartbeat
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
        +--> SQLite historian
        |       Docker volume: sqlite_data
        |
        +--> FastAPI HTTP API
                http://localhost:8000
```

Ignition can consume the same demo data through:

```text
OPC UA connection
Modbus TCP device
MQTT Engine / Sparkplug B
PostgreSQL JDBC connection
Named Queries
Perspective dashboard
```

---

## Project structure

```text
iiot-demo/
├── README.md
└── house-factory-modbus-mqtt/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── mosquitto/
    │   └── house-factory.conf
    ├── src/
    │   ├── house_factory_simulator.py
    │   ├── house_factory_sparkplug.py
    │   ├── house_factory_opcua_server.py
    │   ├── house_factory_modbus_bridge.py
    │   ├── house_factory_postgres_logger.py
    │   ├── house_factory_sql_logger.py
    │   └── house_factory_api.py
    ├── screenshots/
    │   └── mqtt-explorer-topics.png
    └── ignition/
        ├── project-export/
        ├── screenshots/
        └── tag-export/
```

---

## Quick start with Docker Compose

From the project folder:

```bash
cd house-factory-modbus-mqtt
```

Build and start the full stack:

```bash
docker compose up -d --build
```

Check running services:

```bash
docker compose ps
```

Expected result: all containers should be running. PostgreSQL should become `healthy` after startup.

Stop the stack:

```bash
docker compose down
```

Stop the stack and remove stored database volumes:

```bash
docker compose down -v
```

---

## Docker services

The Docker Compose stack contains these services:

```text
mosquitto          MQTT broker
simulator          Process data simulator publishing plain MQTT / UNS-style topics
sparkplug          Plain MQTT to Sparkplug B bridge
opcua-server       OPC UA server exposing the latest simulated values
modbus-bridge      Modbus TCP bridge exposing selected values as holding registers
postgres           PostgreSQL database for historian data
postgres-logger    MQTT to PostgreSQL historian logger
sqlite-logger      MQTT to SQLite historian logger
api                FastAPI HTTP API reading data from the SQLite historian
```

Container names:

```text
house-factory-mosquitto
house-factory-simulator
house-factory-sparkplug
house-factory-opcua
house-factory-modbus-bridge
house-factory-postgres
house-factory-postgres-logger
house-factory-sqlite-logger
house-factory-api
```

Useful log commands:

```bash
docker compose logs -f
docker compose logs -f simulator
docker compose logs -f sparkplug
docker compose logs -f opcua-server
docker compose logs -f modbus-bridge
docker compose logs -f postgres-logger
docker compose logs -f sqlite-logger
docker compose logs -f api
```

Start only the minimum stack needed for the HTTP API:

```bash
docker compose up -d --build mosquitto simulator sqlite-logger api
```

---

## External endpoints

When the stack is running locally:

```text
MQTT broker:        localhost:1883
OPC UA server:     opc.tcp://localhost:4840/house-factory/server/
Modbus TCP:        localhost:5021
PostgreSQL:        localhost:5432
HTTP API:          http://localhost:8000
API docs:          http://localhost:8000/docs
```

When running on a Raspberry Pi, replace `localhost` with the Raspberry Pi IP address, for example:

```text
http://192.168.1.117:8000/docs
opc.tcp://192.168.1.117:4840/house-factory/server/
192.168.1.117:5021
```

---

## HTTP API service

The API service is implemented in:

```text
src/house_factory_api.py
```

It reads from the same SQLite database volume used by `sqlite-logger`:

```text
/data/iiot_history.db
```

Docker Compose service:

```text
api
```

Port mapping:

```text
8000:8000
```

Main endpoints:

```text
GET /                         Service overview
GET /api/health               API and SQLite health check
GET /api/topics               List stored MQTT topics
GET /api/latest               Latest value for every topic
GET /api/latest/{topic_path}  Latest value for one topic
GET /api/history?topic=...    History for one full topic path
GET /api/history/{topic_path} History for one topic using path syntax
GET /api/raw/latest/{topic_path} Latest row including raw JSON payload
GET /docs                     Swagger / OpenAPI documentation
```

Example API calls:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/topics
curl http://localhost:8000/api/latest
```

Latest value for one topic:

```bash
curl "http://localhost:8000/api/latest/plain-uns/v1/house-factory/line-01/process/temperature"
```

History for one topic:

```bash
curl "http://localhost:8000/api/history?topic=plain-uns/v1/house-factory/line-01/process/temperature&limit=20"
```

Alternative path-style history endpoint:

```bash
curl "http://localhost:8000/api/history/plain-uns/v1/house-factory/line-01/process/temperature?limit=20"
```

If `/api/health` returns a database or table error immediately after startup, wait a few seconds until `sqlite-logger` creates the SQLite file and begins writing MQTT samples.

---

## MQTT validation

Subscribe to all plain UNS-style topics:

```bash
docker compose exec mosquitto mosquitto_sub -t 'plain-uns/v1/house-factory/line-01/#' -v
```

Expected payload format:

```json
{
  "timestamp": "2026-06-10T20:00:00.000000+00:00",
  "value": 23.4,
  "unit": "degC",
  "quality": "GOOD"
}
```

---

## PostgreSQL historian

PostgreSQL demo credentials:

```text
Database: iiot_history
User:     iiot_user
Password: iiot_password
```

These credentials are for local demo use only.

Open PostgreSQL shell:

```bash
docker compose exec postgres psql -U iiot_user -d iiot_history
```

Check the latest rows:

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

---

## SQLite historian

The SQLite logger stores local historian data in the Docker volume `sqlite_data`.

Database path inside the container:

```text
/data/iiot_history.db
```

Check SQLite row count and latest rows:

```bash
docker compose exec -T sqlite-logger python - <<'PY'
import sqlite3

conn = sqlite3.connect('/data/iiot_history.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM tag_history')
print('Rows:', cur.fetchone()[0])

cur.execute('''
SELECT id, timestamp, topic, value, unit, quality
FROM tag_history
ORDER BY id DESC
LIMIT 10
''')

for row in cur.fetchall():
    print(row)

conn.close()
PY
```

---

## OPC UA

OPC UA server endpoint:

```text
opc.tcp://localhost:4840/house-factory/server/
```

From another machine or Ignition gateway, use the host IP address instead of `localhost`:

```text
opc.tcp://<host-ip>:4840/house-factory/server/
```

The OPC UA server subscribes to the plain MQTT topics and exposes the latest values as OPC UA variables.

---

## Modbus TCP

The Modbus bridge subscribes to the plain MQTT topics and writes selected values into holding registers.

Endpoint:

```text
localhost:5021
```

Register map:

```text
HR1 / 40001   Temperature x10 degC
HR2 / 40002   Pressure x10 kPa
HR3 / 40003   Motor speed rpm
HR4 / 40004   Tank level x10 percent
HR5 / 40005   Valve position percent
HR6 / 40006   Flow l/min
HR7 / 40007   Alarm
HR8 / 40008   Operation
HR9 / 40009   Connection
HR10 / 40010  Heartbeat
```

The first holding register has zero-based internal address `0`, which is commonly displayed as `40001` by Modbus clients.

---

## Sparkplug B

The Sparkplug bridge converts the plain MQTT / UNS-style values into Sparkplug B node birth and node data messages.

Main Sparkplug settings:

```text
Namespace:     spBv1.0
Group ID:      house-factory
Edge Node ID:  line-01
```

Main topics:

```text
spBv1.0/house-factory/NBIRTH/line-01
spBv1.0/house-factory/NDATA/line-01
spBv1.0/house-factory/NDEATH/line-01
spBv1.0/house-factory/NCMD/line-01
```

The bridge includes a `Node Control/Rebirth` metric so Ignition MQTT Engine can request a rebirth.

---

## Ignition integration

Ignition resources are stored in:

```text
house-factory-modbus-mqtt/ignition/
```

Included resources:

```text
ignition/project-export/    Ignition project export ZIP
ignition/tag-export/        Tag export JSON
ignition/screenshots/       Designer and Perspective screenshots
```

The demo can be connected to Ignition through OPC UA, Modbus TCP, Sparkplug B / MQTT Engine, and PostgreSQL.

---

## Python dependencies

Python dependencies are stored in:

```text
house-factory-modbus-mqtt/requirements.txt
```

Current external Python packages:

```text
paho-mqtt<3
pymodbus==2.5.3
asyncua
mqtt-spb-wrapper
psycopg2-binary
fastapi
uvicorn[standard]
```

Notes:

- `paho-mqtt` is used by the simulator, bridges and loggers.
- `pymodbus==2.5.3` is pinned because the current Modbus bridge is written for the 2.x API style.
- `asyncua` is used by the OPC UA server.
- `mqtt-spb-wrapper` is used by the Sparkplug B bridge.
- `psycopg2-binary` is used by the PostgreSQL logger.
- `fastapi` and `uvicorn` are used by the HTTP API service.
- `sqlite3` is part of the Python standard library and does not need to be installed separately.

---

## Rebuild after changing code

After changing Python files, rebuild the Docker image:

```bash
docker compose up -d --build
```

Restart a single service:

```bash
docker compose restart api
docker compose restart simulator
```

Rebuild and restart only the API:

```bash
docker compose up -d --build api
```

---

## Purpose of the demo

This repository is intended as a compact portfolio example of practical IIoT / OT integration work:

```text
industrial data simulation
MQTT publishing
UNS-style topic structure
Sparkplug B bridge
OPC UA exposure
Modbus TCP bridge
historian logging
SQL access
HTTP API access
Dockerized deployment
Ignition integration
```

It is not intended to be a production-ready industrial control system. It is a readable and testable demonstration of integration patterns used in modern IT/OT environments.
