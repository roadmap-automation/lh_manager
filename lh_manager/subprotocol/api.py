"""Flask blueprint exposing lh_manager's subprotocol definitions to external consumers.

Protocol Studio fetches this list so the protocol editor can show available
subprotocols without maintaining its own subprotocol database.
"""

import json

from flask import Blueprint, jsonify, request

from . import db
from ..method_group import db as mg_db
from ..liquid_handler.methods import method_manager
from ..validation import compute_availability

blueprint = Blueprint("subprotocol", __name__, url_prefix="/subprotocols")

db.init_db()


@blueprint.get("/")
def list_subprotocols():
    sps = db.list_subprotocols()
    mgs = mg_db.list_method_groups()
    # Parse steps for the availability walk, then strip before returning.
    sps_parsed = [{**sp, "steps": json.loads(sp.get("steps") or "[]")} for sp in sps]
    mgs_parsed = [{**mg, "steps": json.loads(mg.get("steps") or "[]")} for mg in mgs]
    sp_avail, _ = compute_availability(sps_parsed, mgs_parsed, method_manager.available_method_names())
    result = []
    for sp in sps_parsed:
        row = {k: v for k, v in sp.items() if k != "steps"}
        row["available"] = sp_avail.get(sp["name"], True)
        result.append(row)
    return jsonify({"subprotocols": result})


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
