"""Waste Manager Endpoints"""
from typing import List, Optional
from flask import make_response, Response, request

from ...liquid_handler.bedlayout import Well, WellLocation
from ...material_db.db import Material, MaterialDB
from .waste import waste_layout, WasteHistory
from ..wastedata import WasteItem
from .events import trigger_waste_update

from . import blueprint

@blueprint.route('/Waste/GUI/GetLayout', methods=['GET'])
def GetWasteLayout() -> Response:
    """Gets list of waste bottles"""

    return make_response(waste_layout.model_dump(), 200)

@blueprint.route('/Waste/AddWaste', methods=['POST'])
@trigger_waste_update
def AddWaste() -> Response:
    """Adds waste. Data format:
        {'volume': <float (mL)>,
         'composition': <Composition>}
    """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    waste_item = WasteItem(**data)
    waste_layout.add_waste(waste_item)
    return make_response(waste_item.model_dump(), 200)

@blueprint.route('/Waste/EmptyWaste', methods=['POST'])
@trigger_waste_update
def EmptyWaste() -> Response:
    """Empties waste (resets volume to zero)
    """

    waste_layout.empty_waste()

    return make_response(waste_layout.carboy.model_dump(), 200)

@blueprint.route('/Waste/GUI/GetWells', methods=['GET'])
def GetWells(well_locations: Optional[List[WellLocation]] = None) -> Response:
    """ Gets a list of all filled wells """
    wells: List[Well]
    if well_locations is None:
        wells = waste_layout.get_all_wells()
    else:
        wells = []
        for loc in well_locations:
            well, rack = waste_layout.get_well_and_rack(loc.rack_id, loc.well_number)
            wells.append(well)
    wells_dict = [well.model_dump() for well in wells]
    for wd in wells_dict:
        wd['zone'] = wd['rack_id']
    return make_response(wells_dict, 200)

@blueprint.route('/Waste/GUI/UpdateWell', methods=['POST'])
@trigger_waste_update
def UpdateWell() -> Response:
    """ Replaces any existing well definition weith the same rack_id, well_number
    (or creates a new well definition if none already exists) """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    well = Well(**data)
    waste_layout.update_well(well)
    return make_response(well.model_dump(), 200)

@blueprint.route('/Waste/GUI/RemoveWellDefinition', methods=['POST'])
@trigger_waste_update
def RemoveWellDefinition() -> Response:
    """ Replaces any existing well definition weith the same rack_id, well_number
    (or creates a new well definition if none already exists) """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    waste_layout.remove_well_definition(data["rack_id"], data["well_number"])
    return make_response({"well definition removed": data}, 200)

@blueprint.route('/Waste/GUI/GetTimestampTable', methods=['GET'])
def GetTimestampTable() -> Response:
    """Gets list of waste bottles"""

    with WasteHistory(waste_layout._database_path) as waste_history:
        timestamp_table = waste_history.get_timestamp_table()

    return make_response({'timestamp_table': timestamp_table}, 200)


@blueprint.route('/Waste/GUI/GenerateWasteReport', methods=['POST'])
def GetWasteReport() -> Response:
    """Gets list of waste bottles"""

    data = request.get_json(force=True)
    assert isinstance(data, dict)

    with WasteHistory(waste_layout._database_path) as waste_history:
        wasteitems = waste_history.get_waste_by_bottle_id(data['bottle_id'])
        timestamp_table = waste_history.get_timestamp_table()

    total_waste = WasteItem()
    for item in wasteitems:
        total_waste.mix_with(item.volume, item.composition)

    # nicely formatted report. Converts solutes into g/mL
    first_time, last_time = next((b[1], b[2]) for b in timestamp_table if b[0] == data['bottle_id'])
    bottle_id = data['bottle_id']
    report = f'Carboy ID: {bottle_id}\nFirst entry: {first_time}\nLast entry: {last_time}\n'
    report += 'Percent\tChemical name\n'

    with MaterialDB() as db:
        components = ['protein']
        component_fractions = [0]
        for solvent in total_waste.composition.solvents:
            full_name = db.get_material_by_name(solvent.name).full_name
            components.append(full_name)
            component_fractions.append(solvent.fraction)

        for solute in total_waste.composition.solutes:
            material = db.get_material_by_name(solute.name)
            amount = solute.convert_units('mg/mL') * 1e-3
            if material.type == 'protein':
                # convert to g/mL units (assume density of 1)
                component_fractions[components.index('protein')] += amount
           
            else:
                components.append(material.full_name)
                # convert to g/mL units (assume density of 1)
                component_fractions.append(amount)


    # normalize all fractions and convert to percent
    sum_cf = sum(component_fractions)
    component_fractions = [cf / sum_cf * 100 for cf in component_fractions]

    # sort and generate report
    component_fractions, components = zip(*sorted(zip(component_fractions, components)))
    for cf, c in zip(component_fractions[::-1], components[::-1]):
        cf_text = f'{cf: 0.1f}' if cf >= 0.1 else '<0.1'
        report += f'{cf_text}\t{c}\n'

    return make_response({'report': report}, 200)