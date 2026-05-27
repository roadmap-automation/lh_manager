"""Subprotocol definition store for lh_manager.

Subprotocols are ROADMAP business logic owned by lh_manager (the Interface Layer).
This module provides SQLite-backed CRUD.  The DB lives alongside lh_manager's
other persistent state in the history/ folder.

Schema is identical to the prototype tables in lh-protocol-studio so existing
seed data can be re-used without changes.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_FOLDER = os.path.join(os.getcwd(), "persistent_state")
DB_FILE = "lh_manager_subprotocols.db"


def get_db_path() -> str:
    os.makedirs(DB_FOLDER, exist_ok=True)
    return os.path.join(DB_FOLDER, DB_FILE)


def init_db() -> None:
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS subprotocols (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            steps         TEXT NOT NULL,
            parameter_wiring TEXT,
            inputs        TEXT,
            outputs       TEXT,
            execution     TEXT,
            allocations   TEXT,
            method_type   TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Forward-compatible migrations for columns added after initial creation.
    for col in ("inputs TEXT", "outputs TEXT", "execution TEXT",
                "allocations TEXT", "method_type TEXT"):
        try:
            c.execute(f"ALTER TABLE subprotocols ADD COLUMN {col}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def create_subprotocol(
    name: str,
    steps: list,
    parameter_wiring: Optional[list] = None,
    inputs: Optional[dict] = None,
    outputs: Optional[dict] = None,
    execution: Optional[str] = None,
    allocations: Optional[list] = None,
    method_type: Optional[str] = None,
) -> str:
    sub_id = str(uuid.uuid4())
    now = datetime.now()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO subprotocols "
        "(id, name, steps, parameter_wiring, inputs, outputs, "
        " execution, allocations, method_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sub_id, name,
            json.dumps(steps),
            json.dumps(parameter_wiring or []),
            json.dumps(inputs or {}),
            json.dumps(outputs or {}),
            execution,
            json.dumps(allocations or []),
            method_type,
            now, now,
        ),
    )
    conn.commit()
    conn.close()
    return sub_id


def get_subprotocol(sub_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM subprotocols WHERE id = ?", (sub_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_subprotocol_by_name(name: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM subprotocols WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def list_subprotocols() -> List[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, name, inputs, created_at, updated_at "
        "FROM subprotocols ORDER BY updated_at DESC"
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_subprotocol(
    sub_id: str,
    name: str,
    steps: list,
    parameter_wiring: Optional[list] = None,
    inputs: Optional[dict] = None,
    outputs: Optional[dict] = None,
    execution: Optional[str] = None,
    allocations: Optional[list] = None,
    method_type: Optional[str] = None,
) -> None:
    now = datetime.now()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE subprotocols "
        "SET name=?, steps=?, parameter_wiring=?, inputs=?, outputs=?, "
        "    execution=?, allocations=?, method_type=?, updated_at=? "
        "WHERE id=?",
        (
            name,
            json.dumps(steps),
            json.dumps(parameter_wiring or []),
            json.dumps(inputs or {}),
            json.dumps(outputs or {}),
            execution,
            json.dumps(allocations or []),
            method_type,
            now,
            sub_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_subprotocol(sub_id: str) -> None:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM subprotocols WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()
