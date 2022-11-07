from flask import make_response, Response, request
from . import nice_blueprint
from state.state import samples
from liquid_handler.samplelist import SampleStatus, DATE_FORMAT
from datetime import datetime
from dataclasses import asdict
from gui_api.events import trigger_samples_update

@nice_blueprint.route('/NICE/RunSample/<sample_name>', methods=['GET'])
@trigger_samples_update
def RunSample(sample_name) -> Response:
    """Runs a sample by name"""
    sample = samples.getSamplebyName(sample_name, status=SampleStatus.PENDING)
    if sample is not None:
        sample.status = SampleStatus.ACTIVE
        sample.createdDate = datetime.now().strftime(DATE_FORMAT)
        return make_response({'result': 'success', 'message': 'success'}, 200)
    else:
        return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/RunSamplewithUUID', methods=['POST'])
@trigger_samples_update
def RunSamplewithUUID() -> Response:
    """Runs a sample by name, giving it a UUID. Returns error if sample not found or sample is already active or completed."""
    data = request.get_json(force=True)

    if ('name' in data.keys()) & ('uuid' in data.keys()):

        sample = samples.getSamplebyName(data['name'], status=SampleStatus.PENDING)
        if sample is not None:
            sample.status = SampleStatus.ACTIVE
            sample.createdDate = datetime.now().strftime(DATE_FORMAT)
            sample.NICE_uuid = data['uuid']
            return make_response({'result': 'success', 'message': 'success'}, 200)
        else:
            return make_response({'result': 'error', 'message': 'sample not found'}, 400)
    
    else:
        return make_response({'result': "bad request format; should be {'name': <sample_name>; 'uuid': <uuid>"}, 400)

def _getActiveSample() -> str:
    """Gets the currently active sample with the earliest createdDate."""

    # find active samples
    active_sample_names = [sample.name for sample in samples.samples if sample.status == SampleStatus.ACTIVE]
    active_name = ''

    if len(active_sample_names):
        # regenerate datetime objects from date strings
        active_sample_dates = [datetime.strptime(sample.createdDate, DATE_FORMAT) for sample in samples.samples if sample.status == SampleStatus.ACTIVE]

        # select name of sample with earliest createdDate
        active_name = active_sample_names[active_sample_dates.index(min(active_sample_dates))]
    
    return active_name

@nice_blueprint.route('/NICE/GetActiveSample/', methods=['GET'])
def GetActiveSample() -> Response:
    """Gets the currently active sample with the earliest createdDate."""
        
    return make_response({'name': _getActiveSample()}, 200)

@nice_blueprint.route('/NICE/GetSampleStatus/<sample_name>', methods=['GET'])
def GetSampleStatus(sample_name) -> Response:
    """Gets status of a sample by name"""

    sample = samples.getSamplebyName(sample_name)
    
    if sample is not None:
        return make_response({'name': sample_name, 'status': sample.status}, 200)
    else:
        return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/GetMetaData/<uuid>', methods=['GET'])
def GetMetaData(uuid) -> Response:
    """Gets metadata from all samples with UUID.
        Responses are sorted by createdDate"""

    samples_uuid = [sample for sample in samples.samples if sample.NICE_uuid == uuid]
    
    if len(samples_uuid):
        samples_uuid.sort(key=lambda sample: datetime.strptime(sample.createdDate, DATE_FORMAT))
        return make_response({'metadata': [asdict(sample) for sample in samples_uuid]}, 200)
    else:
        return make_response({}, 200)

@nice_blueprint.route('/NICE/GetSampleTimeEstimate/<sample_name>', methods=['GET'])
def GetSampleTimeEstimate(sample_name) -> Response:
    """Gets time estimate for a given sample."""

    sample = samples.getSamplebyName(sample_name)
    
    if sample is not None:
        totaltime = sum([method.estimated_time() if not complete else 0.0
                        for method, complete in zip(sample.methods, sample.methods_complete)])

        return make_response({'name': sample_name, 'time estimate': totaltime}, 200)
    else:
        return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/GetInstrumentStatus/', methods=['GET'])
def GetInstrumentStatus() -> Response:
    """Probes instrument status. Busy if any samples are active, otherwise idle"""

    status = 'busy' if any([sample.status == SampleStatus.ACTIVE for sample in samples.samples]) else 'idle'

    return make_response({'status': status, 'active sample': _getActiveSample()}, 200)
