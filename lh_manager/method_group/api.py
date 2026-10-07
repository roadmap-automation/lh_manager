"""Flask blueprint for MethodGroup CRUD in lh_manager.

Exposes the MethodGroup library so the GUI editor and Protocol Studio can
list, create, update, and delete method group definitions.
"""

import json

from flask import Blueprint, jsonify, request

from . import db
from ..subprotocol import db as sp_db
from ..liquid_handler.methods import method_manager
from ..validation import compute_availability

blueprint = Blueprint("method_group", __name__, url_prefix="/method_groups")

db.init_db()


@blueprint.get("/")
def list_method_groups():
    mgs = db.list_method_groups()
    sps = sp_db.list_subprotocols()
    mgs_parsed = [{**mg, "steps": json.loads(mg.get("steps") or "[]")} for mg in mgs]
    sps_parsed = [{**sp, "steps": json.loads(sp.get("steps") or "[]")} for sp in sps]
    _, mg_avail = compute_availability(sps_parsed, mgs_parsed, method_manager.available_method_names())
    result = []
    for mg in mgs_parsed:
        row = {k: v for k, v in mg.items() if k != "steps"}
        row["available"] = mg_avail.get(mg["name"], True)
        result.append(row)
    return jsonify({"method_groups": result})


@blueprint.post("/")
def create_method_group():
    body = request.get_json(force=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    steps = body.get("steps", [])
    mg_id = db.create_method_group(
        name=name,
        steps=steps,
        description=body.get("description"),
        exposed_fields=body.get("exposed_fields"),
        method_type=body.get("method_type"),
    )
    return jsonify({"id": mg_id}), 201


@blueprint.get("/<mg_id>")
def get_method_group(mg_id: str):
    mg = db.get_method_group(mg_id)
    if mg is None:
        return jsonify({"error": "not found"}), 404
    mg["steps"] = json.loads(mg["steps"])
    mg["exposed_fields"] = json.loads(mg.get("exposed_fields") or "[]")
    return jsonify(mg)


@blueprint.put("/<mg_id>")
def update_method_group(mg_id: str):
    if db.get_method_group(mg_id) is None:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    db.update_method_group(
        mg_id=mg_id,
        name=name,
        steps=body.get("steps", []),
        description=body.get("description"),
        exposed_fields=body.get("exposed_fields"),
        method_type=body.get("method_type"),
    )
    return jsonify({"ok": True})


@blueprint.delete("/<mg_id>")
def delete_method_group(mg_id: str):
    if db.get_method_group(mg_id) is None:
        return jsonify({"error": "not found"}), 404
    db.delete_method_group(mg_id)
    return jsonify({"ok": True})
