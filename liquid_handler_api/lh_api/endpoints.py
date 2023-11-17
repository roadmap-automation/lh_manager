"""Gilson Trilution LH 4.0 Endpoints"""
from flask import make_response, Response, request

from ..liquid_handler.state import samples, layout
from ..liquid_handler.lhqueue import LHqueue
from ..liquid_handler.samplelist import SampleStatus, Sample
from ..gui_api.events import trigger_layout_update, trigger_run_queue_update, \
                            trigger_sample_status_update, trigger_samples_update

from . import lh_blueprint

@lh_blueprint.route('/LH/GetListofSampleLists/', methods=['GET'])
def GetListofSampleLists() -> Response:
    sample_list = [sample.toSampleList(stage_name, layout, entry=True) for sample in samples.samples for stage_name in sample.stages if sample.stages[stage_name].status==SampleStatus.ACTIVE]

    return make_response({'sampleLists': sample_list}, 200)

@lh_blueprint.route('/LH/GetSampleList/<sample_list_id>', methods=['GET'])
def GetSampleList(sample_list_id) -> Response:
    sample, stage_name = samples.getSampleStagebyLH_ID(int(sample_list_id))
    sampleList = sample.toSampleList(stage_name, layout) if sample is not None and stage_name is not None else []

    return make_response({'sampleList': sampleList}, 200)

@lh_blueprint.route('/LH/PutSampleListValidation/<sample_list_id>', methods=['POST'])
def PutSampleListValidation(sample_list_id):
    data = request.get_json(force=True)

    # check validation (SUCCESS or ERROR)
    validation = data['validation']['validationType']
    error = None
    
    # TODO: Actual error handling flow, sample activation/inactivation methods
    if not validation == 'SUCCESS':
        error = f'Error in validation. Full message: ' + data['validation']['message']
        sample, stage_name = samples.getSampleStagebyLH_ID(int(sample_list_id))
        sample.stages[stage_name].status = SampleStatus.INACTIVE
        trigger_sample_status_update(lambda: 1)

    return make_response({sample_list_id: validation, 'error': error}, 200)

@trigger_samples_update
def _delete_sample(sample: Sample) -> None:
    """Deletes sample with decorator that triggers update"""
    samples.deleteSample(sample)

@lh_blueprint.route('/LH/PutSampleData/', methods=['POST'])
@trigger_sample_status_update
@trigger_layout_update
@trigger_run_queue_update
def PutSampleData():
    data = request.get_json(force=True)
    assert isinstance(data, dict)

    # Get ID, method number, and method name from returned data
    sample_id = int(data['sampleData']['runData'][0]['sampleListID'])
    method_number = int(data['sampleData']['runData'][0]['iteration']) - 1
    method_name = data['sampleData']['runData'][0]['methodName']
    #print(sample_id, method_number, method_name)

    # check that run was successful
    if any([('completed successfully' in notification) for notification in data['sampleData']['resultNotifications']['notifications'].values()]):
        # find relevant sample by ID
        sample, stage_name = samples.getSampleStagebyLH_ID(sample_id)
        assert sample is not None and stage_name is not None, "unknown sample"
        methodlist = sample.stages[stage_name]
        #print(methodlist.__dict__)
        method = methodlist.run_methods[method_number]

        # double check that correct method is being referenced
        assert method_name == method.method_name, f'Wrong method name {method_name} in result, expected {method.method_name}, full output {data}'

        # mark method complete
        methodlist.run_methods_complete[method_number] = True

        # Change layout state:
        method.execute(layout)

        # Change sample state if the method does this:
        new_state = method.new_sample_composition(layout)
        if len(new_state):
            sample.current_contents = new_state

        # if all methods complete, change status of method list to completed, flag LH as no longer busy, and run the next queue item
        if methodlist.get_method_completion():
            methodlist.status = SampleStatus.COMPLETED

            # activate next queue item
            LHqueue.active_sample = None
            LHqueue.run_next()

        # archive the sample and remove it from active samples if all stages are complete
        samples.archiveSample(sample)
        if sample.get_status() == SampleStatus.COMPLETED:
            _delete_sample(sample)

    # TODO: ELSE: Throw error

    return make_response({'data': data}, 200)