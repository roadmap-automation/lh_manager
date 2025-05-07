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

@blueprint.route('/Materials/MaterialFromSequence/', methods=['GET', 'POST'])
def material_from_sequence() -> Response:
    """Produce a material from an amino acid sequence. Fields:
        'sequence': string representing sequence
        'type': 'aa' (default) or 'dna' or 'rna'
        'name': Optional, defaults to ''
    """

    import periodictable.fasta

    data: dict = request.get_json(force=True)
    sequence = data.get('sequence')

    try:
        seq = periodictable.fasta.Sequence(name=data.get('name', ''),
                                        sequence=sequence,
                                        type=data.get('type', 'aa'))
    except KeyError:
        # usually because there's a problem with the sequence
        print(f'Bad sequence {sequence} from {data}')
        return make_response({'material': None}, 400)
    
    mat = db.Material(name=seq.name,
                      pubchem_cid=None,
                      full_name=sequence,
                      iupac_name=sequence,
                      molecular_weight=seq.mass,
                      density=round(seq.formula.density, 3),
                      concentration_units='mg/mL',
                      type='protein')
    
    return make_response({'material': asdict(mat)}, 200)
    