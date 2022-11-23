from datetime import datetime
from dataclasses import asdict
from flask import make_response, Response, request

from lhqueue import LHqueue
from state.state import samples
from liquid_handler.samplelist import SampleStatus, DATE_FORMAT
from gui_api.events import trigger_sample_status_update

from . import nice_blueprint

def _run_sample(data) -> Response:
    """ Generic function for processing a run request"""

    # check that sample name exists
    sample = samples.getSamplebyName(data['name'])
    if sample is not None:
        # check that requested stages are inactive
        for stage in data['stage']:
            if sample.stages[stage].status != SampleStatus.INACTIVE:
                return make_response({'result': 'error', 'message': f'stage {stage} of sample {data["name"]} is not inactive'}, 400)
            
            # create new run command specific to stage and add to queue
            sample.stages[stage].status = SampleStatus.PENDING
            stagedata = {**data, 'stage': [stage]}
            LHqueue.put(stagedata)
            LHqueue.run_next()

        return make_response({'result': 'success', 'message': 'success'}, 200)

    return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/RunSample/<sample_name>/<uuid>/<slotID>/<stage>', methods=['GET'])
@trigger_sample_status_update
def RunSample(sample_name, uuid, slotID, stage) -> Response:
    """Runs a sample by name and stage. For testing only"""

    if stage == 'both':
        stage = ['prep', 'inject']
    else:
        stage = [stage]

    data = {'name': sample_name, 'uuid': uuid, 'slotID': int(slotID), 'stage': stage}

    return _run_sample(data)

@nice_blueprint.route('/NICE/RunSamplewithUUID', methods=['POST'])
@trigger_sample_status_update
def RunSamplewithUUID() -> Response:
    """Runs a sample by name, giving it a UUID. Returns error if sample not found or sample is already active or completed."""
    data = request.get_json(force=True)

    # check for proper format
    if ('name' in data.keys()) & ('uuid' in data.keys() & ('slotID' in data.keys()) & ('stage' in data.keys())):

        return _run_sample(data)
    
    return make_response({'result': 'error', 'message': "bad request format; should be {'name': <sample_name>; 'uuid': <uuid>; 'slotID': <slot_id>; 'stage': ['prep' | 'inject']"}, 400)

def _getActiveSample() -> str:
    """Gets the currently active sample with the earliest createdDate."""

    # find active samples
    active_sample_names = [sample.name for sample in samples.samples if sample.get_status() == SampleStatus.ACTIVE]
    active_name = ''

    if len(active_sample_names):
        # regenerate datetime objects from date strings
        active_sample_dates = [sample.get_earliest_date() for sample in samples.samples if sample.get_status() == SampleStatus.ACTIVE]

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
        return make_response({'name': sample_name, 'status': sample.get_status()}, 200)
    else:
        return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/GetMetaData/<uuid>', methods=['GET'])
def GetMetaData(uuid) -> Response:
    """Gets metadata from all samples with UUID.
        Responses are sorted by createdDate"""

    samples_uuid = [sample for sample in samples.samples if sample.NICE_uuid == uuid]
    
    if len(samples_uuid):
        samples_uuid.sort(key=lambda sample: datetime.strptime(sample.get_earliest_date(), DATE_FORMAT))
        return make_response({'metadata': [asdict(sample) for sample in samples_uuid], 'current contents': samples_uuid[-1].current_contents}, 200)
    else:
        return make_response({}, 200)

@nice_blueprint.route('/NICE/DryRunSamplewithUUID', methods=['POST'])
def DryRunSamplewithUUID() -> Response:
    """Dry runs a sample by name. UUID is ignored. Returns time estimate; otherwise error if sample not found."""
    data = request.get_json(force=True)

    if ('name' in data.keys()) & ('uuid' in data.keys() & ('slotID' in data.keys()) & ('role' in data.keys())):

        sample = samples.getSamplebyName(data['name'])
        if sample is not None:
            totaltime = 0.0
            for role in data['role']:
                methodlist = sample.stages[role]
                if methodlist.status in (SampleStatus.PENDING, SampleStatus.INACTIVE):
                    totaltime += sum(method.estimated_time() if not complete else 0.0
                        for method, complete in zip(methodlist.methods, methodlist.methods_complete))

            return make_response({'result': 'success', 'time estimate': totaltime}, 200)
        else:
            return make_response({'result': 'error', 'message': 'sample not found'}, 400)
    
    else:
        return make_response({'result': "bad request format; should be {'name': <sample_name>; 'uuid': <uuid>; 'slotID': <slot_id>; 'role': ['prep' | 'inject']"}, 400)

@nice_blueprint.route('/NICE/GetInstrumentStatus/', methods=['GET'])
def GetInstrumentStatus() -> Response:
    """Probes instrument status. Busy if any samples are active, otherwise idle"""

    status = 'busy' if any([sample.get_status() == SampleStatus.ACTIVE for sample in samples.samples]) else 'idle'

    return make_response({'status': status, 'active sample': _getActiveSample()}, 200)

@nice_blueprint.route('/NICE/Stop/', methods=['GET'])
def Stop() -> Response:
    """Stops operation by emptying liquid handler queue"""

    # empties queue and resets status of incomplete methods to INACTIVE
    init_size = LHqueue.qsize()

    while not LHqueue.empty():
        data = LHqueue.get()
        sample = samples.getSamplebyName(data['name'])
        
        # should only ever be one stage
        for stage in data['stage']:
            # reset status of sample stage to INACTIVE
            sample.stages[stage].status = SampleStatus.INACTIVE

    return make_response({'result': 'success', 'message': f'{init_size} pending LH operations canceled'}, 200)
