"""Gilson Trilution LH 4.0 Endpoints

    Designed to operate as an independent web interface; does not depend on sample list state"""
from flask import make_response, Response, request, redirect

from . import autocontrol_blueprint
from autocontrol.status import Status
from ..autocontrol import init_devices, AUTOCONTROL_URL
from ...liquid_handler.lhinterface import InterfaceStatus, lh_interface
from ...liquid_handler.state import samples

@autocontrol_blueprint.route('/autocontrol/GetStatus', methods=['GET'])
def GetStatus() -> Response:
    """Gets Autocontrol status code"""

    status_map = {InterfaceStatus.BUSY: Status.BUSY,
                 InterfaceStatus.DOWN: Status.DOWN,
                 InterfaceStatus.ERROR: Status.ERROR,
                 InterfaceStatus.UP: Status.IDLE}
    
    status = status_map[lh_interface.get_status()]

    return make_response(dict(status=status,
                              channel_status=[status] * samples.n_channels)
                              , 200)

@autocontrol_blueprint.route('/autocontrol/InitializeDevices/', methods=['POST'])
def InitializeDevices() -> Response:
    """Triggers initialization of devices
        NOTE: Could use JobRunner to do this, but this is much simpler"""
    #data: dict = request.get_json(force=True)

    init_devices()

    return make_response({'result': 'success'}, 200)

@autocontrol_blueprint.route('/autocontrol/GetTaskResult', methods=['GET'])
def GetTaskResult() -> Response:
    """Redirects task result requests to autocontrol server
    """

    data: dict = request.get_json(force=True)

    task_id = data.get('task_id', None)
    subtask_id = data.get('subtask_id', None)

    if task_id is not None:
        if subtask_id is not None:
            return redirect(AUTOCONTROL_URL + f'/get_subtask_results/{task_id}/{subtask_id}')
        return make_response({'error': 'subtask_id required'})
    return make_response({'error': 'task_id required'})

@autocontrol_blueprint.route('/autocontrol/GetTaskStatus', methods=['GET'])
def GetTaskStatus() -> Response:
    """Redirects task result requests to autocontrol server
    """

    data: dict = request.get_json(force=True)

    task_id = data.get('task_id', None)

    if task_id is not None:
        return redirect(AUTOCONTROL_URL + f'/get_task_status/{task_id}')
    else:
        return make_response({'error': 'task_id required'})


