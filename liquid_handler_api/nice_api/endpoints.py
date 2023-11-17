"""NICE API Endpoints"""
from dataclasses import asdict
from flask import make_response, Response, request

from ..liquid_handler.lhqueue import LHqueue, validate_format
from ..liquid_handler.samplelist import SampleStatus
from ..liquid_handler.state import samples, layout
from ..liquid_handler.items import Item
from ..liquid_handler.history import History
from ..gui_api.events import trigger_sample_status_update, trigger_run_queue_update

from . import nice_blueprint

def _run_sample(data) -> Response:
    """ Generic function for processing a run request"""

    if 'id' in data:
        _, sample = samples.getSampleById(data['id'])
    else:
        sample = samples.getSamplebyName(data['name'])

    # check that sample name exists
    if sample is not None:
        # check that requested stages are inactive
        for stage in data['stage']:
            if sample.stages[stage].status != SampleStatus.INACTIVE:
                return make_response({'result': 'error', 'message': f'stage {stage} of sample {data["name"]} is not inactive'}, 400)
            
            # create new run command specific to stage and add to queue
            #stagedata = {**data, 'stage': [stage]}
            LHqueue.put_safe(Item(sample.id, stage, data))
            LHqueue.run_next()

        return make_response({'result': 'success', 'message': 'success'}, 200)

    return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/RunSample/<sample_name>/<uuid>/<slotID>/<stage>/', methods=['GET'])
@trigger_run_queue_update
@trigger_sample_status_update
def RunSample(sample_name, uuid, slotID, stage) -> Response:
    """Runs a sample by name and stage. For testing only"""

    if stage == 'both':
        stage = ['prep', 'inject']
    else:
        stage = [stage]

    data = {'name': sample_name, 'uuid': uuid, 'slotID': int(slotID), 'stage': stage}

    return _run_sample(data)

@nice_blueprint.route('/NICE/RunSamplewithUUID/', methods=['POST'])
@trigger_run_queue_update
@trigger_sample_status_update
def RunSamplewithUUID() -> Response:
    """Runs a sample by name, giving it a UUID. Returns error if sample not found or sample is already active or completed."""
    data = request.get_json(force=True)
    #print(data)
    # check for proper format
    if validate_format(data):

        # catch null UUID
        if (data['uuid'] == chr(0)) | (data['uuid'] == '%00'):
            data['uuid'] = None

        return _run_sample(data)
    
    return make_response({'result': 'error', 'message': "bad request format; should be {'name': <sample_name>; 'uuid': <uuid>; 'slotID': <slot_id>; 'stage': ['prep' | 'inject']"}, 400)

def _getActiveSample() -> str:
    """Gets the currently active sample with the earliest createdDate."""

    active_sample = LHqueue.active_sample

    if active_sample is not None:
        return samples.getSampleById(active_sample.id)[1].name

    return ''

@nice_blueprint.route('/NICE/GetActiveSample/', methods=['GET'])
def GetActiveSample() -> Response:
    """Gets the currently active sample with the earliest createdDate."""
        
    return make_response({'name': _getActiveSample()}, 200)

@nice_blueprint.route('/NICE/GetSampleStatus/<sample_name>/', methods=['GET'])
def GetSampleStatus(sample_name) -> Response:
    """Gets status of a sample by name"""

    sample = samples.getSamplebyName(sample_name)
    
    if sample is not None:
        return make_response({'name': sample_name, 'status': sample.get_status()}, 200)
    else:
        return make_response({'result': 'error', 'message': 'sample not found'}, 400)

@nice_blueprint.route('/NICE/GetMetaData/<uuid>/', methods=['GET'])
def GetMetaData(uuid) -> Response:
    """Gets metadata from all samples with UUID. %00 (null character)
        is interpreted as None.
        Responses are sorted by createdDate"""

    if uuid != chr(0):
        # Get samples from history
        # NOTE: it may not be necessary to re-initialize historical data into Sample objects but
        # it makes the code cleaner.
        history = History()
        samples_history = history.get_samples_by_NICE_uuid(uuid)
        history.close()

        # get currently active samples
        samples_uuid = [sample for sample in samples.samples if sample.NICE_uuid == uuid]

        # remove duplicates from history (if active in memory, should use that one). This should
        # never happen
        sample_ids = [s.id for s in samples_uuid]
        samples_history = [s for s in samples_history if s.id not in sample_ids]

        # concatenate the historical and current lists
        samples_uuid += samples_history
        
        if len(samples_uuid):
            samples_uuid.sort(key=lambda sample: sample.get_earliest_date())
            return make_response({'metadata': [asdict(sample) for sample in samples_uuid], 'current contents': samples_uuid[-1].current_contents}, 200)

    return make_response({}, 200)

@nice_blueprint.route('/NICE/DryRunSamplewithUUID', methods=['POST'])
def DryRunSamplewithUUID() -> Response:
    """Dry runs a sample by name. UUID is ignored. Returns time estimate; otherwise error if sample not found."""
    data = request.get_json(force=True)

    if validate_format(data):

        sample = samples.getSamplebyName(data['name'])
        if sample is not None:
            totaltime = 0.0
            for stage in data['stage']:
                methodlist = sample.stages[stage]
                if methodlist.status in (SampleStatus.PENDING, SampleStatus.INACTIVE):
                    # NOTE: Formulation methods will return zero for this, leading to inaccurate estimates
                    totaltime = methodlist.estimated_time(layout)

            return make_response({'result': 'success', 'time estimate': totaltime}, 200)
        else:
            return make_response({'result': 'error', 'message': 'sample not found'}, 400)
    
    else:
        return make_response({'result': "bad request format; should be {'name': <sample_name>; 'uuid': <uuid>; 'slotID': <slot_id>; 'role': ['prep' | 'inject']"}, 400)

@nice_blueprint.route('/NICE/GetInstrumentStatus/', methods=['GET'])
def GetInstrumentStatus() -> Response:
    """Probes instrument status. Busy if any samples are active, otherwise idle"""

    #all_method_statuses = [methodlist.status in (SampleStatus.ACTIVE, SampleStatus.PENDING) for sample in samples.samples for methodlist in sample.stages.values()]
    #print(all_method_statuses)
    status = 'busy' if any(methodlist.status in (SampleStatus.ACTIVE, SampleStatus.PENDING) for sample in samples.samples for methodlist in sample.stages.values()) else 'idle'
    #print(status)
    return make_response({'status': status, 'active sample': _getActiveSample()}, 200)

@nice_blueprint.route('/NICE/GetLHQueue/', methods=['GET'])
def GetLHQueue() -> Response:
    """Probes instrument status. Busy if any samples are active, otherwise idle"""

    return make_response({'LHQueue': LHqueue.repr_queue()}, 200)

@nice_blueprint.route('/NICE/Stop/', methods=['GET', 'POST'])
@trigger_run_queue_update
@trigger_sample_status_update
def Stop() -> Response:
    """Stops operation by emptying liquid handler queue.
    
        Ignores request data.
        
        TODO: Remove GET for production"""

    with LHqueue.lock:
        init_size = len(LHqueue.stages)

    LHqueue.stop()

    return make_response({'result': 'success', 'number_operations_canceled': init_size, 'message': f'{init_size} pending LH operations canceled'}, 200)

@nice_blueprint.route('/NICE/Inactivate/', methods=['GET', 'POST'])
@trigger_run_queue_update
@trigger_sample_status_update
def Inactivate() -> Response:
    """Stops operation by emptying liquid handler queue.
    
        Ignores request data."""

    active_stage_list = [sample.stages[stage_name] for sample in samples.samples for stage_name in sample.stages if sample.stages[stage_name].status in (SampleStatus.ACTIVE, SampleStatus.PENDING)]
    for stage in active_stage_list:
        stage.status = SampleStatus.INACTIVE

    return make_response({'result': 'success', 'number_operations_inactivated': len(active_stage_list), 'message': f'{len(active_stage_list)} pending LH operations canceled'}, 200)

@nice_blueprint.route('/NICE/Pause/', methods=['GET', 'POST'])
def Pause() -> Response:
    """Pauses liquid handler queue.
    
        Ignores request data.
        
        TODO: Remove GET for production"""

    LHqueue.pause()

    return make_response({'result': 'success'}, 200)

@nice_blueprint.route('/NICE/Resume/', methods=['GET', 'POST'])
@trigger_run_queue_update
@trigger_sample_status_update
def Resume() -> Response:
    """Pauses liquid handler queue.
    
        Ignores request data.
        
        TODO: Remove GET for production"""

    LHqueue.resume()
    LHqueue.run_next()

    return make_response({'result': 'success'}, 200)