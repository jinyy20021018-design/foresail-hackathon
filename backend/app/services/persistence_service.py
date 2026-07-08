import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
UTC = timezone.utc
from pathlib import Path


def database_path() -> Path:
    url = os.getenv("DATABASE_URL", "sqlite:///./foresail.db")
    if url.startswith("sqlite:///"):
        raw_path = url.replace("sqlite:///", "", 1)
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / raw_path
        return path
    return Path(__file__).resolve().parents[2] / "foresail.db"


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    init_db(connection)
    return connection


@contextmanager
def managed_connection():
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def init_db(connection: sqlite3.Connection | None = None) -> None:
    own_connection = connection is None
    connection = connection or sqlite3.connect(database_path())
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS kv_store (
              namespace TEXT NOT NULL,
              item_key TEXT NOT NULL,
              case_id TEXT,
              payload TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(namespace, item_key)
            );
            CREATE INDEX IF NOT EXISTS idx_kv_case ON kv_store(namespace, case_id);
            """
        )
        connection.commit()
    finally:
        if own_connection:
            connection.close()


def save_item(namespace: str, item_key: str, payload: dict | list, case_id: str | None = None) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    with managed_connection() as connection:
        connection.execute(
            """
            INSERT INTO kv_store(namespace, item_key, case_id, payload, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(namespace, item_key)
            DO UPDATE SET case_id=excluded.case_id, payload=excluded.payload, updated_at=excluded.updated_at
            """,
            (namespace, item_key, case_id, json.dumps(payload, ensure_ascii=True), now),
        )
        connection.commit()


def load_item(namespace: str, item_key: str):
    with managed_connection() as connection:
        row = connection.execute(
            "SELECT payload FROM kv_store WHERE namespace=? AND item_key=?",
            (namespace, item_key),
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def list_items(namespace: str, case_id: str | None = None) -> list:
    query = "SELECT payload FROM kv_store WHERE namespace=?"
    params: list[str] = [namespace]
    if case_id is not None:
        query += " AND case_id=?"
        params.append(case_id)
    query += " ORDER BY item_key"
    with managed_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def list_item_records(namespace: str, case_id: str | None = None) -> list[dict]:
    query = "SELECT item_key, case_id, payload, updated_at FROM kv_store WHERE namespace=?"
    params: list[str] = [namespace]
    if case_id is not None:
        query += " AND case_id=?"
        params.append(case_id)
    query += " ORDER BY item_key"
    with managed_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [
        {
            "item_key": row["item_key"],
            "case_id": row["case_id"],
            "payload": json.loads(row["payload"]),
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_item(namespace: str, item_key: str) -> None:
    with managed_connection() as connection:
        connection.execute("DELETE FROM kv_store WHERE namespace=? AND item_key=?", (namespace, item_key))
        connection.commit()


def clear_namespace(namespace: str) -> None:
    with managed_connection() as connection:
        connection.execute("DELETE FROM kv_store WHERE namespace=?", (namespace,))
        connection.commit()


def clear_all() -> None:
    with managed_connection() as connection:
        connection.execute("DELETE FROM kv_store")
        connection.commit()
