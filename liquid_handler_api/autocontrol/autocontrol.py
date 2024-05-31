"""Interface for autocontrol"""

from typing import List, Dict
import requests
import threading
import time
from uuid import uuid4
from autocontrol.task_struct import Task, TaskData, TaskType

from ..liquid_handler.devices import device_manager
from ..liquid_handler.methods import MethodsType
from ..liquid_handler.bedlayout import LHBedLayout
from ..liquid_handler.samplelist import MethodList
from ..liquid_handler.state import samples
from ..liquid_handler.samplecontainer import SampleStatus

AUTOCONTROL_PORT = 5004
ACTIVE_STATUS = [SampleStatus.PENDING, SampleStatus.PARTIAL, SampleStatus.ACTIVE]

active_tasks: Dict[str, List[str]] = {'active_tasks': []}

def prepare_run_methods(stage: MethodList, layout: LHBedLayout) -> List[Task]:
    """Prepares a method list for running by populating run_methods and run_methods_complete.
        List can then be used for dry or wet runs
    """

    # Generate real-time tasks based on layout
    all_methods: List[MethodsType] = []
    for m in stage.methods:
        all_methods += m.get_methods(layout)

    # render all the methods
    rendered_methods: List[dict] = [m2
                                    for m in all_methods
                                    for m2 in m.render_lh_method(sample_name=self.name,
                                                    sample_description=self.description,
                                                    layout=layout)]

    # create tasks, one per method
    tasks: List[Task] = []
    stage.run_jobs = []
    for method in rendered_methods:
        new_task = Task(id=str(uuid4()),
                        task_type=TaskType.NOCHANNEL,
                        tasks=[TaskData(id=uuid4(),
                                        device=device_name,
                                        channel=(self.channel if device_manager.get_device_by_name(device_name).is_multichannel() else None),
                                        method_data=device_manager.get_device_by_name(device_name).create_job_data(method[device_name]))
                                for device_name in method.keys()])
        
        # detect transfer tasks
        if len(new_task.tasks) > 1:
            new_task.task_type = TaskType.TRANSFER
        elif new_task.tasks[0].channel is not None:
            new_task.task_type = TaskType.MEASURE

        stage.run_jobs += [str(task.id) for task in new_task.tasks]

        tasks.append(new_task)
    
    return tasks

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
def synchronize_status(poll_delay: 5):

    def check_status_completion(task) -> bool:
        # send task id to autocontrol to get status
        pass

    while True:

        for task in active_tasks['active_tasks']:
            if check_status_completion(task):
                active_tasks['active_tasks'].pop(task)

        time.sleep(poll_delay)
