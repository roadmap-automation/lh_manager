"""Interface for autocontrol"""

from typing import List, Dict
import requests
import threading
import time
from autocontrol.task_struct import Task, TaskData, TaskType

from .devices import device_manager
from .state import samples
from .samplecontainer import SampleStatus

ACTIVE_STATUS = [SampleStatus.PENDING, SampleStatus.PARTIAL, SampleStatus.ACTIVE]
active_tasks: Dict[str, List[str]] = {'active_tasks': []}

port = 5004

def to_thread(**thread_kwargs):
    def decorator_to_thread(f):
        """Decorator that starts target function in a new thread"""
        def wrap(*args, **kwargs):
            threading.Thread(target=f, args=args, kwargs=kwargs, **thread_kwargs).start()
        wrap.__name__ = f.__name__
        return wrap
    return decorator_to_thread

@to_thread()
def submit_tasks(tasks: List[Task]):
    #print('Submitting Task: ' + task.tasks[0].device + ' ' + task.task_type + 'Sample: ' + str(task.sample_id) + '\n')
    for task in tasks:
        print('Submitting Task: ' + task.tasks[0].device + ' ' + task.task_type + '\n')
        url = 'http://localhost:' + str(port) + '/put'
        headers = {'Content-Type': 'application/json'}
        data = task.model_dump_json()
        response = requests.post(url, headers=headers, data=data)
        print('Autocontrol response: ', response)

    # TODO: keep track of unsuccessfully submitted tasks and re-expose them in the gui. Requires a callback function somewhere.

def init_devices():
    init_tasks = [Task(task_type=TaskType.INIT,
                       tasks=[TaskData(device=device.device_name,
                                       device_type=device.device_type,
                                       device_address=device.address,
                                       number_of_channels=(samples.n_channels if device.is_multichannel() else None))])
                  for device in device_manager.device_list]
    
    submit_tasks(init_tasks)

@to_thread(daemon=True)
def synchronize_status(poll_delay: 5, active_tasks: Dict[str, List[str]]):

    def check_status_completion(task) -> bool:
        # send task id to autocontrol to get status
        pass

    while True:

        for task in active_tasks['active_tasks']:
            if check_status_completion(task):
                active_tasks['active_tasks'].pop(task)

        time.sleep(poll_delay)
