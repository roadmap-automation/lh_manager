"""Flask blueprint for MethodGroup CRUD in lh_manager.

Exposes the MethodGroup library so the GUI editor and Protocol Studio can
list, create, update, and delete method group definitions.
"""

import json

from flask import Blueprint, jsonify, request

from . import db

blueprint = Blueprint("method_group", __name__, url_prefix="/method_groups")

db.init_db()


@blueprint.get("/")
def list_method_groups():
    return jsonify({"method_groups": db.list_method_groups()})


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
