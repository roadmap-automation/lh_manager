"""Flask blueprint exposing lh_manager's subprotocol definitions to external consumers.

Protocol Studio fetches this list so the protocol editor can show available
subprotocols without maintaining its own subprotocol database.
"""

import json

from flask import Blueprint, jsonify, request

from . import db

blueprint = Blueprint("subprotocol", __name__, url_prefix="/subprotocols")

db.init_db()


@blueprint.get("/")
def list_subprotocols():
    return jsonify({"subprotocols": db.list_subprotocols()})


@blueprint.post("/")
def create_subprotocol():
    body = request.get_json(force=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    sub_id = db.create_subprotocol(
        name=name,
        steps=body.get("steps", []),
        parameter_wiring=body.get("parameter_wiring"),
        inputs=body.get("inputs"),
        outputs=body.get("outputs"),
        execution=body.get("execution"),
        allocations=body.get("allocations"),
        method_type=body.get("method_type"),
    )
    return jsonify({"id": sub_id}), 201


@blueprint.get("/<sub_id>")
def get_subprotocol(sub_id: str):
    sp = db.get_subprotocol(sub_id)
    if sp is None:
        return jsonify({"error": "not found"}), 404
    sp["steps"] = json.loads(sp["steps"])
    sp["allocations"] = json.loads(sp.get("allocations") or "[]")
    sp["inputs"] = json.loads(sp.get("inputs") or "{}")
    sp["outputs"] = json.loads(sp.get("outputs") or "{}")
    sp["parameter_wiring"] = json.loads(sp.get("parameter_wiring") or "[]")
    return jsonify(sp)


@blueprint.put("/<sub_id>")
def update_subprotocol(sub_id: str):
    if db.get_subprotocol(sub_id) is None:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    db.update_subprotocol(
        sub_id=sub_id,
        name=name,
        steps=body.get("steps", []),
        parameter_wiring=body.get("parameter_wiring"),
        inputs=body.get("inputs"),
        outputs=body.get("outputs"),
        execution=body.get("execution"),
        allocations=body.get("allocations"),
        method_type=body.get("method_type"),
    )
    return jsonify({"ok": True})


@blueprint.delete("/<sub_id>")
def delete_subprotocol_route(sub_id: str):
    if db.get_subprotocol(sub_id) is None:
        return jsonify({"error": "not found"}), 404
    db.delete_subprotocol(sub_id)
    return jsonify({"ok": True})
