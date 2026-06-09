"""MethodGroup definition store for lh_manager.

A MethodGroup is a set of device methods dispatched as a single autocontrol
Task with multiple TaskData entries (one per device).  All participating
devices must be available before autocontrol dispatches any part of the group.

Schema:
  steps — ordered list of:
    {
      "method_name": str,
      "parameters": dict,          # parameter bindings; may use $ref/$alloc
      "composition_source": bool,  # True for the step that produces the composition
                                   # (e.g. GilsonFormulation); triggers composition
                                   # transfer event on task completion
    }
  exposed_fields — fields from device method schemas that surface to SubProtocol
    level; used by the GUI editor to build the parameter form:
    [{"field_name": str, "type": str, "display_name": str, "step_index": int}]
  method_type — autocontrol TaskType string ("prepare", "measure", etc.)
"""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from lh_manager.app_config import METHOD_GROUPS_DB


def get_db_path() -> str:
    METHOD_GROUPS_DB.parent.mkdir(parents=True, exist_ok=True)
    return str(METHOD_GROUPS_DB)


def init_db() -> None:
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS method_groups (
            id             TEXT PRIMARY KEY,
            name           TEXT NOT NULL UNIQUE,
            description    TEXT,
            steps          TEXT NOT NULL,
            exposed_fields TEXT,
            method_type    TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def create_method_group(
    name: str,
    steps: list,
    description: Optional[str] = None,
    exposed_fields: Optional[list] = None,
    method_type: Optional[str] = None,
) -> str:
    mg_id = str(uuid.uuid4())
    now = datetime.now()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO method_groups "
        "(id, name, description, steps, exposed_fields, method_type, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            mg_id, name, description,
            json.dumps(steps),
            json.dumps(exposed_fields or []),
            method_type,
            now, now,
        ),
    )
    conn.commit()
    conn.close()
    return mg_id


def get_method_group(mg_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM method_groups WHERE id = ?", (mg_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_method_group_by_name(name: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM method_groups WHERE name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def list_method_groups() -> List[Dict[str, Any]]:
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, name, description, method_type, created_at, updated_at "
        "FROM method_groups ORDER BY updated_at DESC"
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_method_group(
    mg_id: str,
    name: str,
    steps: list,
    description: Optional[str] = None,
    exposed_fields: Optional[list] = None,
    method_type: Optional[str] = None,
) -> None:
    now = datetime.now()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE method_groups "
        "SET name=?, description=?, steps=?, exposed_fields=?, method_type=?, updated_at=? "
        "WHERE id=?",
        (
            name, description,
            json.dumps(steps),
            json.dumps(exposed_fields or []),
            method_type,
            now,
            mg_id,
        ),
    )
    conn.commit()
    conn.close()


def delete_method_group(mg_id: str) -> None:
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM method_groups WHERE id = ?", (mg_id,))
    conn.commit()
    conn.close()
