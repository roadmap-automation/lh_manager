"""Interface for autocontrol"""

from typing import List
import requests
import threading
from autocontrol.task_struct import Task, TaskData, TaskType

from .devices import device_manager
from .state import samples

port = 5004

def to_thread(f):
    """Decorator that starts target function in a new thread"""
    def wrap(*args, **kwargs):
        threading.Thread(target=f, args=args, kwargs=kwargs).start()
    wrap.__name__ = f.__name__
    return wrap

@to_thread
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
                                       number_of_channels=(samples.n_channels if device.is_multichannel() else 0))])
                  for device in device_manager.device_list]
    
    submit_tasks(init_tasks)
