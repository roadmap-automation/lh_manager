"""Waste Manager Endpoints"""
from typing import List, Optional
from flask import make_response, Response, request, Blueprint

from ...liquid_handler.bedlayout import Well, WellLocation
from .waste import waste_layout
from ..wastedata import WasteItem
from .events import trigger_waste_update

from . import blueprint

@blueprint.route('/Waste/GUI/GetLayout', methods=['GET'])
def GetWasteLayout() -> Response:
    """Gets list of waste bottles"""

    return make_response(waste_layout.model_dump(), 200)

@blueprint.route('/Waste/AddWaste/', methods=['POST'])
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

@blueprint.route('/Waste/EmptyWaste/', methods=['POST'])
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