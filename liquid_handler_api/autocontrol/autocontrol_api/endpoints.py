"""Gilson Trilution LH 4.0 Endpoints

    Designed to operate as an independent web interface; does not depend on sample list state"""
from dataclasses import asdict
from flask import make_response, Response, request

from . import autocontrol_blueprint
from autocontrol.status import Status
from autocontrol.task_struct import TaskData
from ...liquid_handler.lhinterface import InterfaceStatus, lh_interface

@autocontrol_blueprint.route('/autocontrol/GetStatus', methods=['GET'])
def GetStatus() -> Response:
    """Gets Autocontrol status code"""

    status_map = {InterfaceStatus.BUSY: Status.BUSY,
                 InterfaceStatus.DOWN: Status.DOWN,
                 InterfaceStatus.UP: Status.IDLE}
    
    print(lh_interface.get_status())

    return make_response(dict(status=status_map[lh_interface.get_status()],
                              channel_status=[])
                              , 200)