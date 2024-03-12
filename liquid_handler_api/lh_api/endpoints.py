"""Gilson Trilution LH 4.0 Endpoints

    Designed to operate as an independent web interface; does not depend on sample list state"""
from dataclasses import asdict
from flask import make_response, Response, request

from ..liquid_handler.lhinterface import lh_interface, LHJob, ValidationStatus, ResultStatus, LHJobHistory, InterfaceStatus
from ..sio import socketio

from . import lh_blueprint

def broadcast_job_activation(job: LHJob) -> None:
    """Sends activation signal

    Args:
        job (LHJob): job activated
    """

    socketio.emit('job_activation',
                  {'job_id': job.id},
                  include_self=True)

def broadcast_job_validation(job: LHJob, result: ValidationStatus) -> None:
    """Sends validation signal

    Args:
        job (LHJob): job validated
    """

    socketio.emit('job_validation',
                  {'job_id': job.id,
                   'result': result},
                  include_self=True)

def broadcast_job_result(job: LHJob, method_number: int, method_name: str, result: ResultStatus) -> None:
    """Sends result signal

    Args:
        job (LHJob): job updated
        method_number (int): index of method corresponding to result
        method_name (str): name of method
        result (ResultStatus): nature of result
    """

    socketio.emit('job_validation',
                  {'job_id': job.id,
                   'method_number': method_number,
                   'method_name': method_name,
                   'result': result},
                  include_self=True)


@lh_blueprint.route('/LH/GetJob/<job_id>', methods=['GET'])
def GetJob(job_id: str) -> Response:
    """Gets job object from database"""

    with LHJobHistory() as history:
        job = history.get_job_by_uuid(job_id)

    if job is not None:
        return make_response({'success': asdict(job)}, 200)
    else:
        return make_response({'error': f'job {job_id} does not exist'}, 400)

@lh_blueprint.route('/LH/SubmitJob/', methods=['POST'])
def SubmitJob() -> Response:
    """Submits LHJob to server. Data format should just be a single
        serialized LHJob object"""

    # Ensure lh_interface is ready to receive a job
    if lh_interface.get_status() != InterfaceStatus.UP:
        return make_response({'error': 'job rejected, LH interface busy'}, 400)

    # attempt deserialization, raise error if it fails
    data = request.get_json(force=True)

    try:
        job = LHJob(**data)
    except:
        return make_response({'error': 'job rejected, cannot be deserialized'}, 400)

    # activate the job
    lh_interface.activate_job(job)
    broadcast_job_activation(job)

    return make_response({'success': 'job accepted'}, 200)

@lh_blueprint.route('/LH/GetListofSampleLists/', methods=['GET'])
def GetListofSampleLists() -> Response:
    """Gets list of sample lists for Gilson LH

    Returns:
        Response: format {'sampleLists': sample_list}
    """

    job: LHJob | None = lh_interface.get_active_job()
    sample_list = [] if job is None else [job.get_samplelist(listonly=True)]

    return make_response({'sampleLists': sample_list}, 200)

@lh_blueprint.route('/LH/GetSampleList/<sample_list_id>', methods=['GET'])
def GetSampleList(sample_list_id: str) -> Response:
    """Gets specific sample list by ID

    Args:
        sample_list_id (str): string representation of sample list ID

    Returns:
        Response: sample list, or error if ID does not match active sample
    """
    job = lh_interface.get_active_job()
    if job is None:
        return make_response({'error': 'no active jobs'}, 400)
    if int(sample_list_id) != job.LH_id:
        return make_response({'error': f'requested job ID {sample_list_id} does not match active job ID {job.LH_id}'}, 400)

    sample_list = [job.get_samplelist(listonly=False)]

    return make_response({'sampleLists': sample_list}, 200)

@lh_blueprint.route('/LH/PutSampleListValidation/<sample_list_id>', methods=['POST'])
def PutSampleListValidation(sample_list_id):
    data = request.get_json(force=True)

    job = lh_interface.get_active_job()

    if job is None:
        return make_response({'error': 'no active jobs'}, 400)
    if int(sample_list_id) != job.LH_id:
        return make_response({'error': f'validation job ID {sample_list_id} does not match active job ID {job.LH_id}'}, 400)

    job.validation = data
    lh_interface.update_job(job)
    broadcast_job_validation(job, job.get_validation_status()[0])

    error = None
    if job.get_validation_status() != ValidationStatus.SUCCESS:
        error = f'Error in validation. Full message: ' + data['validation']['message']
        lh_interface.deactivate()

    return make_response({sample_list_id: job.get_validation_status(), 'error': error}, 200)

@lh_blueprint.route('/LH/PutSampleData/', methods=['POST'])
def PutSampleData():
    data = request.get_json(force=True)
    assert isinstance(data, dict)

    # Get ID, method number, and method name from returned data
    sample_id = int(data['sampleData']['runData'][0]['sampleListID'])
    method_number = int(data['sampleData']['runData'][0]['iteration']) - 1
    method_name = data['sampleData']['runData'][0]['methodName']

    job = lh_interface.get_active_job()

    if job is None:
        return make_response({'error': 'no active jobs'}, 400)
    if sample_id != job.LH_id:
        return make_response({'error': f'PutSampleData job ID {sample_id} does not match active job ID {job.LH_id}'}, 400)
    if job.samplelist['columns'][method_number]['METHODNAME'] != method_name:
        return make_response({'error': f'PutSampleData method name {method_name} does not match corresponding method name {job.samplelist['columns']['METHODNAME']}'}, 400)

    job.results.append(data)
    lh_interface.update_job(job)
    broadcast_job_result(job, method_number, method_name, job.get_result_status())

    error = None
    if job.get_result_status() == ResultStatus.FAIL:
        error = f'Error in results. Full message: ' + data
        lh_interface.deactivate()

    return make_response({'data': data}, 200)