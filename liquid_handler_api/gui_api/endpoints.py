"""HTTP Endpoints for GUI API"""
import warnings
from dataclasses import asdict, replace
from copy import deepcopy
from flask import make_response, request, Response
from typing import List, Tuple, Optional

from ..liquid_handler.state import samples, layout
from ..liquid_handler.samplelist import Sample, StageName, SampleStatus, MethodList
from ..liquid_handler.methods import method_manager
from ..liquid_handler.bedlayout import Well, WellLocation
from ..liquid_handler.layoutmap import Zone, LayoutWell2ZoneWell
from ..liquid_handler.dryrun import DryRunQueue
from ..liquid_handler.lhqueue import LHqueue, RunQueue
from .events import trigger_samples_update, trigger_sample_status_update, trigger_layout_update
from . import gui_blueprint

@gui_blueprint.route('/webform/AddSample/', methods=['POST'])
@trigger_samples_update
def AddSample() -> Response:
    """Adds a single-method sample to the sample list (testing only)"""
    data = request.get_json(force=True)
    assert isinstance(data, dict)
    #new_sample = Sample(id=samples.getMaxID() + 1, name=data['SAMPLENAME'], description=data['SAMPLEDESCRIPTION'], methods=[new_method])
    new_sample = Sample(**data)
    samples.addSample(new_sample)

    # dry run (testing only)
    test_layout = deepcopy(layout)
    for method in new_sample.stages[StageName.PREP].get_methods(test_layout):
        method.execute(test_layout)

    return make_response({'new sample': new_sample.toSampleList(StageName.PREP, test_layout), 'layout': asdict(test_layout)}, 200)

@gui_blueprint.route('/GUI/UpdateSample/', methods=['POST'])
@trigger_samples_update
@trigger_sample_status_update
def UpdateSample() -> Response:
    """Modifies an existing sample"""
    data = request.get_json(force=True)
    assert isinstance(data, dict)
    id = data.get("id", None)
    if id is None:
        warnings.warn("no id attached to sample, can't update or add")
        return make_response({'error': "no id in sample, can't update or add"}, 200)

    sample_index, sample = samples.getSampleById(id)
    print(data, sample)
    if sample is None or sample_index is None:
        """ adding a new sample """
        new_sample = Sample(**data)
        samples.addSample(new_sample)
        return make_response({'sample added': id}, 200)
    else:
        """ replacing sample """
        new_sample = replace(sample, **data)
        samples.samples[sample_index] = new_sample
        return make_response({'sample updated': id}, 200)

@gui_blueprint.route('/GUI/ExplodeSample/', methods=['POST'])
@trigger_samples_update
def ExplodeSample() -> Response:
    """Explodes an existing sample"""
    data = request.get_json(force=True)
    assert isinstance(data, dict)
    id = data.get("id", None)
    if id is None:
        warnings.warn("no id attached to sample, can't explode")
        return make_response({'error': "no id in sample, can't explode"}, 200)
    
    stage = data.get("stage", None)
    if stage is None:
        warnings.warn("no stage specified, can't explode")
        return make_response({'error': "no stage specified, can't explode"}, 200)

    _, sample = samples.getSampleById(id)
    print(data, sample)
    """ exploding sample """
    sample.stages[stage].explode(layout)
    return make_response({'sample exploded': id}, 200)

@gui_blueprint.route('/GUI/DuplicateSample/', methods=['POST'])
@trigger_samples_update
@trigger_sample_status_update
def DuplicateSample() -> Response:
    """Duplicates an existing sample"""
    data = request.get_json(force=True)
    assert isinstance(data, dict)
    id = data.get("id", None)
    if id is None:
        warnings.warn("no id attached to sample, can't duplicate")
        return make_response({'error': "no id in sample, can't duplicate"}, 200)

    sample_index, sample = samples.getSampleById(id)
    print(data, sample)
    if sample is None or sample_index is None:
        """ sample not found """
        return make_response({'error': "sample not found, can't duplicate"}, 200)
    else:
        """ duplicate sample, resetting all statuses """
        new_sample = deepcopy(sample)

        # generate new unique ID
        new_sample.generate_new_id()

        # make sure sample name is unique
        while samples.getSamplebyName(new_sample.name) is not None:
            new_sample.name = new_sample.name + ' copy'

        # reset method lists and statuses
        for key, mlist in new_sample.stages.items():
            new_sample.stages[key] = MethodList(methods=mlist.methods)

        # add to sample list immediately after the duplicated sample
        samples.samples.insert(sample_index + 1, new_sample)

        return make_response({'sample duplicated': new_sample.id}, 200)

@gui_blueprint.route('/GUI/RemoveSample/', methods=['POST'])
@trigger_samples_update
def RemoveSample() -> Response:
    """Deletes an existing sample"""
    data = request.get_json(force=True)
    assert isinstance(data, dict)
    id = data.get("id", None)
    if id is None:
        warnings.warn("no id attached to sample, can't delete")
        return make_response({'error': "no id in sample, can't delete"}, 200)

    sample_index, sample = samples.getSampleById(id)
    print(data, sample)
    if sample is None or sample_index is None:
        """ sample not found """
        return make_response({'error': "sample not found, can't delete"}, 200)
    else:
        """ archive sample """
        samples.deleteSample(sample)
        return make_response({'sample removed': id}, 200)

@gui_blueprint.route('/GUI/ArchiveandRemoveSample/', methods=['POST'])
@trigger_samples_update
def ArchiveandRemoveSample() -> Response:
    """Archives an existing sample and deletes"""
    data = request.get_json(force=True)
    assert isinstance(data, dict)
    id = data.get("id", None)
    if id is None:
        warnings.warn("no id attached to sample, can't archive")
        return make_response({'error': "no id in sample, can't archive"}, 200)

    sample_index, sample = samples.getSampleById(id)
    print(data, sample)
    if sample is None or sample_index is None:
        """ sample not found """
        return make_response({'error': "sample not found, can't archive"}, 200)
    else:
        """ archive sample """
        samples.archiveSample(sample)
        samples.deleteSample(sample)
        return make_response({'sample archived and removed': id}, 200)

@gui_blueprint.route('/GUI/UpdateDryRunQueue/', methods=['POST'])
@trigger_samples_update
def UpdateDryRunQueue() -> Response:
    """Updates the dry run queue
    """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    samples.dryrun_queue = DryRunQueue(**data)
    samples.validate_queue(samples.dryrun_queue)

    return make_response({'dry run queue updated': None}, 200)

@gui_blueprint.route('/GUI/DryRun/', methods=['POST'])
def DryRun() -> Response:
    """Performs dry run and returns list of errors
    """
    test_layout = deepcopy(layout)
    errors = samples.dryrun(test_layout)

    return make_response({'dry run errors': errors}, 200)

@gui_blueprint.route('/GUI/UpdateRunQueue/', methods=['POST'])
def UpdateRunQueue() -> Response:
    """Updates the dry run queue
    """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    new_queue = RunQueue(**data)
    with LHqueue.lock:
        LHqueue.stages = new_queue.stages

    return make_response({'run queue updated': None}, 200)

@gui_blueprint.route('/GUI/GetRunQueue/', methods=['GET'])
def GetRunQueue() -> Response:
    """Gets run queue as dict"""

    return make_response({'run_queue': asdict(LHqueue)}, 200)

@gui_blueprint.route('/GUI/GetSamples/', methods=['GET'])
def GetSamples() -> Response:
    """Gets sample list as dict"""

    return make_response({'samples': asdict(samples)}, 200)

@gui_blueprint.route('/GUI/GetSampleStatus/', methods=['GET'])
def GetSamplesStatus() -> Response:
    """Gets sample list statuses"""

    status_dict = {}
    for sample in samples.samples:
        status = {"status": sample.get_status()}
        stages = {}
        for stage_name, stage in sample.stages.items():
            stage_status = {"status": stage.status}
            stage_status["methods_complete"] = stage.get_method_completion()
            stages[stage_name] = stage_status
        status["stages"] = stages
        status_dict[sample.id] = status

    return make_response(status_dict, 200)

@gui_blueprint.route('/GUI/GetAllMethods/', methods=['GET'])
def GetAllMethodSchema() -> Response:
    """Gets method fields and pydantic schema of all methods"""

    return make_response({'methods': method_manager.get_all_schema()}, 200)

@gui_blueprint.route('/GUI/GetLayout/', methods=['GET'])
def GetLayout() -> Response:
    """Gets list of sample names, IDs, and status"""

    return make_response(asdict(layout), 200)

def _get_component_zones(wells: List[Well]) -> Tuple[List[Tuple[str, Zone]], List[Tuple[str, Zone]]]:
    """Gets lists of all solvents and solutes in the specified wells

    Args:
        wells (List[Well]): list of wells to inspect

    Returns:
        Tuple[
            List[Tuple[str, Zone]]: list of tuples with unique solvent names and zones
            List[Tuple[str, Zone]]]: list of tuples with unique solute names and zones
            ]
    """

    all_solvents = set()
    all_solutes = set()
    for well in wells:
        zone, _ = LayoutWell2ZoneWell(well.rack_id, well.well_number)
        for solvent in well.composition.solvents:
            all_solvents.add((solvent.name, zone))
        for solute in well.composition.solutes:
            all_solutes.add((solute.name, zone))

    return list(all_solvents), list(all_solutes)

@gui_blueprint.route('/GUI/GetComponents/', methods=['GET'])
def GetComponents() -> Response:
    """Gets list of components and what zone they're in"""

    solvents, solutes = _get_component_zones(layout.get_all_wells())

    return make_response({'solvents': solvents, 'solutes': solutes}, 200)

@gui_blueprint.route('/GUI/GetWells/', methods=['GET'])
def GetWells(well_locations: Optional[List[WellLocation]] = None) -> Response:
    """ Gets a list of all filled wells """
    wells: List[Well]
    if well_locations is None:
        wells = layout.get_all_wells()
    else:
        wells = []
        for loc in well_locations:
            well, rack = layout.get_well_and_rack(loc.rack_id, loc.well_number)
            wells.append(well)
    wells_dict = [asdict(well) for well in wells]
    for wd in wells_dict:
        zone, _ = LayoutWell2ZoneWell(wd['rack_id'], wd['well_number'])
        wd['zone'] = zone
    return make_response(wells_dict, 200)

@gui_blueprint.route('/GUI/UpdateWell/', methods=['POST'])
@trigger_layout_update
def UpdateWell() -> Response:
    """ Replaces any existing well definition weith the same rack_id, well_number
    (or creates a new well definition if none already exists) """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    well = Well(**data)
    layout.update_well(well)
    return make_response(asdict(well), 200)

@gui_blueprint.route('/GUI/RemoveWellDefinition/', methods=['POST'])
@trigger_layout_update
def RemoveWellDefinition() -> Response:
    """ Replaces any existing well definition weith the same rack_id, well_number
    (or creates a new well definition if none already exists) """

    data = request.get_json(force=True)
    assert isinstance(data, dict)
    layout.remove_well_definition(data["rack_id"], data["well_number"])
    return make_response({"well definition removed": data}, 200)