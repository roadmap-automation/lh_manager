from flask import make_response, request, jsonify, Response
from . import gui_blueprint
from state.state import samples, layout
from liquid_handler.samplelist import Sample, SampleStatus, lh_method_fields
from dataclasses import asdict
from copy import deepcopy
from .events import trigger_layout_update, trigger_samples_update

@gui_blueprint.route('/webform/AddSample/', methods=['POST'])
@trigger_samples_update
def AddSample() -> Response:
    """Adds a single-method sample to the sample list (testing only)"""
    data = request.get_json(force=True)
    #new_sample = Sample(id=samples.getMaxID() + 1, name=data['SAMPLENAME'], description=data['SAMPLEDESCRIPTION'], methods=[new_method])
    new_sample = Sample(**data)
    samples.addSample(new_sample)

    # dry run (testing only)
    test_layout = deepcopy(layout)
    for method in new_sample.methods:
        method.execute(test_layout)

    return make_response({'new sample': new_sample.toSampleList(), 'layout': asdict(test_layout)}, 200)

# TODO: Make NICE endpoint
@gui_blueprint.route('/test/RunSample/<sample_name>', methods=['GET'])
@trigger_samples_update
def RunSample(sample_name) -> Response:
    """Runs a sample """
    # TODO: Use POST to change status; might be useful for pausing, stopping; as coded this is best as a PUT
    sample = samples.getSamplebyName(sample_name)
    if sample is not None:
        sample.status = SampleStatus.ACTIVE
        return make_response(asdict(sample), 200)
    else:
        return make_response({}, 404)

# GUI URIs
@gui_blueprint.route('/GUI/GetSamples/', methods=['GET'])
def GetSamples() -> Response:
    """Gets list of sample names, IDs, and status"""

    return make_response({'methods': lh_method_fields, 'samples': asdict(samples)}, 200)

@gui_blueprint.route('/GUI/GetLayout/', methods=['GET'])
def GetLayout() -> Response:
    """Gets list of sample names, IDs, and status"""

    return make_response({'layout': asdict(layout)}, 200)

