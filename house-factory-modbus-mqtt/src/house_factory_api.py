import os
import sqlite3

from fastapi import FastAPI, Query, HTTPException


# -----------------------------
# SQLite configuration
# -----------------------------
DB_FILE = os.getenv("SQLITE_DB_FILE", "iiot_history.db")


# -----------------------------
# API configuration
# -----------------------------
API_TITLE = os.getenv("API_TITLE", "House Factory IIoT API")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))


app = FastAPI(
    title=API_TITLE,
    description="HTTP API for reading House Factory SQLite historian data.",
    version="1.0.0",
)


def get_connection():
    """
    Open a SQLite connection for one API request.

    WAL + busy_timeout help when the logger writes
    and the API reads at the same time.
    """
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def check_database_exists():
    if not os.path.exists(DB_FILE):
        raise HTTPException(
            status_code=500,
            detail=f"SQLite database file not found: {DB_FILE}",
        )


def check_table_exists():
    """
    Verify that the expected historian table exists.
    """
    check_database_exists()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = 'tag_history'
    """)

    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=500,
            detail="Table 'tag_history' not found in SQLite database.",
        )


@app.get("/")
def root():
    return {
        "service": API_TITLE,
        "database": DB_FILE,
        "endpoints": [
            "/api/health",
            "/api/topics",
            "/api/latest",
            "/api/latest/{topic_path:path}",
            "/api/history?topic=...&limit=100",
            "/api/history/{topic_path:path}?limit=100",
            "/api/raw/latest/{topic_path:path}",
        ],
    }


@app.get("/api/health")
def health():
    """
    Basic health check for the API and SQLite database.
    """
    check_table_exists()

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS count FROM tag_history")
        count = cur.fetchone()["count"]

        cur.execute("SELECT MAX(timestamp) AS last_timestamp FROM tag_history")
        last_timestamp = cur.fetchone()["last_timestamp"]

        conn.close()

        return {
            "status": "ok",
            "database": DB_FILE,
            "rows": count,
            "last_timestamp": last_timestamp,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database health check failed: {exc}",
        )


@app.get("/api/topics")
def topics():
    """
    Return all topics stored in the SQLite historian.
    """
    check_table_exists()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            topic,
            COUNT(*) AS samples,
            MAX(timestamp) AS last_timestamp
        FROM tag_history
        GROUP BY topic
        ORDER BY topic
    """)

    rows = rows_to_dicts(cur.fetchall())
    conn.close()

    return rows


@app.get("/api/latest")
def latest():
    """
    Return the latest value for every topic.
    """
    check_table_exists()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            h.id,
            h.timestamp,
            h.topic,
            h.value,
            h.unit,
            h.quality
        FROM tag_history h
        INNER JOIN (
            SELECT topic, MAX(id) AS max_id
            FROM tag_history
            GROUP BY topic
        ) latest_rows
        ON h.topic = latest_rows.topic
        AND h.id = latest_rows.max_id
        ORDER BY h.topic
    """)

    rows = rows_to_dicts(cur.fetchall())
    conn.close()

    return rows


@app.get("/api/latest/{topic_path:path}")
def latest_for_topic(topic_path: str):
    """
    Return the latest value for one topic.

    Example:
    /api/latest/plain-uns/v1/house-factory/line-01/process/temperature
    """
    check_table_exists()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            timestamp,
            topic,
            value,
            unit,
            quality
        FROM tag_history
        WHERE topic = ?
        ORDER BY id DESC
        LIMIT 1
    """, (topic_path,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for topic: {topic_path}",
        )

    return dict(row)


@app.get("/api/history")
def history(
    topic: str = Query(..., description="Full MQTT topic path"),
    limit: int = Query(100, ge=1, le=5000),
    newest_first: bool = Query(True),
):
    """
    Return historical values for one topic.

    Example:
    /api/history?topic=plain-uns/v1/house-factory/line-01/process/temperature&limit=100
    """
    check_table_exists()

    order = "DESC" if newest_first else "ASC"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT
            id,
            timestamp,
            topic,
            value,
            unit,
            quality
        FROM tag_history
        WHERE topic = ?
        ORDER BY id {order}
        LIMIT ?
    """, (topic, limit))

    rows = rows_to_dicts(cur.fetchall())
    conn.close()

    return rows


@app.get("/api/history/{topic_path:path}")
def history_for_topic_path(
    topic_path: str,
    limit: int = Query(100, ge=1, le=5000),
    newest_first: bool = Query(True),
):
    """
    Return historical values for one topic using path syntax.

    Example:
    /api/history/plain-uns/v1/house-factory/line-01/process/temperature?limit=100
    """
    check_table_exists()

    order = "DESC" if newest_first else "ASC"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        SELECT
            id,
            timestamp,
            topic,
            value,
            unit,
            quality
        FROM tag_history
        WHERE topic = ?
        ORDER BY id {order}
        LIMIT ?
    """, (topic_path, limit))

    rows = rows_to_dicts(cur.fetchall())
    conn.close()

    return rows


@app.get("/api/raw/latest/{topic_path:path}")
def latest_raw_for_topic(topic_path: str):
    """
    Return the latest raw JSON payload for one topic.
    """
    check_table_exists()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            timestamp,
            topic,
            value,
            unit,
            quality,
            raw_json
        FROM tag_history
        WHERE topic = ?
        ORDER BY id DESC
        LIMIT 1
    """, (topic_path,))

    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for topic: {topic_path}",
        )

    return dict(row)


def main():
    import uvicorn

    print("Starting House Factory IIoT API")
    print(f"API title:   {API_TITLE}")
    print(f"API address: http://{API_HOST}:{API_PORT}")
    print(f"SQLite file: {DB_FILE}")
    print()
    print("Useful endpoints:")
    print(f"  http://{API_HOST}:{API_PORT}/api/health")
    print(f"  http://{API_HOST}:{API_PORT}/api/topics")
    print(f"  http://{API_HOST}:{API_PORT}/api/latest")
    print(f"  http://{API_HOST}:{API_PORT}/docs")

    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
    )


if __name__ == "__main__":
    main()
