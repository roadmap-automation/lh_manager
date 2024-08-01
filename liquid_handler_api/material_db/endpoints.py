"""Material Database Endpoints"""
from dataclasses import asdict
from flask import g, make_response, Response, request, Blueprint
from ..sio import socketio

from . import db

blueprint = Blueprint('material_db', __name__)

@blueprint.route('/Materials/update/', methods=['GET', 'POST'])
def update() -> Response:
    """Update material in the database"""
    data = request.get_json(force=True)
    material = db.Material(**data)
    with db.MaterialDB() as database:
        database.smart_insert(material)
    socketio.emit('update_materials', {'msg': 'update_materials'}, include_self=True)
    return make_response({'material': asdict(material)}, 200)

@blueprint.route('/Materials/get_uuid/', methods=['GET', 'POST'])
def get_uuid(uuid: str) -> Response:
    """Get material from the database"""
    with db.MaterialDB() as database:
        material = database.get_material_by_uuid(uuid)
    return make_response({'material': asdict(material)}, 200)

@blueprint.route('/Materials/get_pubchem_cid/', methods=['GET', 'POST'])
def get_pubchem_cid(pubchem_cid: int) -> Response:
    """Get material from the database"""
    with db.MaterialDB() as database:
        material = database.get_material_by_pubchem_cid(pubchem_cid)
    return make_response({'material': asdict(material)}, 200)

@blueprint.route('/Materials/search_name/', methods=['GET', 'POST'])
def search_name(query: str) -> Response:
    """Search for materials in the database"""
    with db.MaterialDB() as database:
        results = database.search_name(query)
    return make_response({'materials': [asdict(material) for material in results]}, 200)

@blueprint.route('/Materials/all/', methods=['GET'])
def get_all() -> Response:
    """Get all materials from the database"""
    with db.MaterialDB() as database:
        materials = database.get_all_materials()
    return make_response({'materials': [asdict(material) for material in materials]}, 200)

@blueprint.route('/Materials/delete/', methods=['GET', 'POST'])
def delete() -> Response:
    """Delete material from the database"""
    data = request.get_json(force=True)
    material = db.Material(**data)
    with db.MaterialDB() as database:
        database.delete_material(material)
    socketio.emit('update_materials', {'msg': 'update_materials'}, include_self=True)
    return make_response({'deleted': material.name}, 200)