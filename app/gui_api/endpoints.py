"""HTTP Endpoints for GUI API"""
import warnings
from dataclasses import asdict, replace
from copy import deepcopy
from flask import make_response, request, Response

from liquid_handler.state import samples, layout
from liquid_handler.samplelist import Sample, lh_method_fields, StageName
from .events import trigger_samples_update
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

    

@gui_blueprint.route('/GUI/GetSamples/', methods=['GET'])
def GetSamples() -> Response:
    """Gets sample list as dict"""

    return make_response({'samples': asdict(samples)}, 200)

@gui_blueprint.route('/GUI/GetAllMethods/', methods=['GET'])
def GetAllMethodSchema() -> Response:
    """Gets method fields and pydantic schema of all methods"""

    return make_response({'methods': lh_method_fields}, 200)

@gui_blueprint.route('/GUI/GetLayout/', methods=['GET'])
def GetLayout() -> Response:
    """Gets list of sample names, IDs, and status"""

    return make_response(asdict(layout), 200)

