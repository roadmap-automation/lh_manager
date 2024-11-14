"""Interface for autocontrol"""

from typing import List, Dict
import requests
import threading
import time
import copy
from uuid import uuid4

from autocontrol.task_struct import Task, TaskData, TaskType
from autocontrol.status import Status

from ..gui_api.events import trigger_samples_update, trigger_layout_update

from ..liquid_handler.devices import device_manager
from ..liquid_handler.lhqueue import submit_handler, ActiveTasks
from ..liquid_handler.methods import MethodsType, MethodType
from ..liquid_handler.bedlayout import LHBedLayout
from ..liquid_handler.samplelist import Sample, StageName, TaskTracker
from ..liquid_handler.state import samples, layout
from ..liquid_handler.items import Item
from ..liquid_handler.samplecontainer import SampleStatus

AUTOCONTROL_PORT = 5004
AUTOCONTROL_URL = 'http://localhost:' + str(AUTOCONTROL_PORT)
DEFAULT_HEADERS = {'Content-Type': 'application/json'}

active_tasks = ActiveTasks()

def verify_connection() -> bool:
    """Verifies that Autocontrol is alive

    Returns:
        bool: False if any issues, otherwise True
    """
    print('Connecting to AutoControl server...')
    try:
        response = requests.get(AUTOCONTROL_URL)
    except requests.ConnectionError:
        print('Autocontrol connection failed')
        return False
    
    if not response.ok:
        print(f'Autocontrol connection error, response code {response.status_code}')
        return False

    return True

def launch_autocontrol_interface(poll_delay: int = 5):
    """Launches autocontrol-based threads
    """

    # check that autocontrol is running
    if verify_connection():

        # register callback
        submit_handler.submit_callbacks.append(submission_callback)

        # initialize devices
        init_devices()

        # start synchronization code
        synchronize_status(poll_delay)

def submission_callback(data: dict):
    """Submission handler callback

    Args:
        data (dict): dictionary of submission data
    """

    if 'id' in data:
        _, sample = samples.getSampleById(data['id'])
    else:
        sample = samples.getSamplebyName(data['name'])

    # check that sample name exists
    if sample is not None:
        # check that requested stages are inactive
        for stage in data['stage']:
            #if sample.stages[stage].status != SampleStatus.INACTIVE:
            #    return f'stage {stage} of sample {data["name"]} is not inactive'
            
            sample.stages[stage].status = SampleStatus.PENDING
            prepare_and_submit(sample, stage, layout)

        return

    return 'sample not found'

class AutocontrolTaskTracker(TaskTracker):
    id: str | None = None
    task: Task | None = None
    status: SampleStatus | None = None

    def model_post_init(self, __context):

        if self.id is None:
            self.id = self.task.id

class AutocontrolItem(Item):
    method_id: str | None = None

def prepare_and_submit(sample: Sample, stage: StageName, layout: LHBedLayout) -> List[Task]:
    """Prepares a method list for running by populating run_methods and run_methods_complete.
        List can then be used for dry or wet runs
    """
   
    # Generate real-time tasks based on layout
    all_tasks: List[Task] = []
    for i in range(len(sample.stages[stage].methods)):
        all_tasks += prepare_method(sample, stage, i, layout)

    # activate the tasks
    for i in range(len(sample.stages[stage].methods)):
        sample.stages[stage].activate(0)

    submit_tasks(all_tasks)

def prepare_method(sample: Sample, stage: StageName, method_index: int, layout: LHBedLayout) -> List[Task]:
    """Prepares a method list for running by populating run_methods and run_methods_complete.
        List can then be used for dry or wet runs
    """
   
    # Generate real-time tasks based on layout
    m = sample.stages[stage].methods[method_index]
    all_methods: List[MethodsType] = m.method.get_methods(layout)

    # render all the methods. Can be multiple rendered submethod per main method
    rendered_methods: List[List[dict]] = [m.render_method(sample_name=sample.name,
                                                    sample_description=sample.description,
                                                    layout=layout)
                                            for m in all_methods]
    
    method_types: List[MethodType] = [m.method_type
                                    for m in all_methods]

    # create tasks, one per method
    tasks: List[Task] = []
    for method_type, method_list in zip(method_types, rendered_methods):
        
        # should typically only ever be one method in method_list
        for method in method_list:
            taskdata: List[TaskData] = []
            max_subtasks = 0
            for device_name, device_data in method.items():
                channel = sample.channel if device_manager.get_device_by_name(device_name).multichannel else None
                max_subtasks = max(max_subtasks, len(device_data))
                newtaskdata = TaskData(id=str(uuid4()),
                                device=device_name,
                                channel=channel,
                                method_data=device_manager.get_device_by_name(device_name).create_job_data(device_data),
                                non_channel_storage='vial' if channel is None else None)
                taskdata.append(newtaskdata)
            
            # transfer if multiple devices are involved
            if len(method.keys()) > 1:
                tasktype = TaskType.TRANSFER
            # prepare if multiple subtasks from a single device are involved
            elif method_type == MethodType.PREPARE:
                tasktype = TaskType.PREPARE
            elif method_type == MethodType.MEASURE:
                tasktype = TaskType.MEASURE
            else:
                tasktype = TaskType.NOCHANNEL
                
            new_task = Task(sample_id=sample.id,
                            task_type=tasktype,
                            tasks=taskdata)

            # reserve active_tasks (and sample.stages[stage])
            with active_tasks.lock:
                m.tasks.append(AutocontrolTaskTracker(task=new_task,
                                                        status=SampleStatus.PENDING))
                active_tasks.pending.update({str(new_task.id): AutocontrolItem(id=sample.id, stage=stage, method_id=m.id)})

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
    for task in tasks:
        print('Submitting Task: ' + task.tasks[0].device + ' ' + task.task_type + '\n')
        data = task.model_dump_json()
        response = requests.post(AUTOCONTROL_URL + '/put', headers=DEFAULT_HEADERS, data=data)
        print('Autocontrol response: ', response.status_code)
        if task.task_type != TaskType.INIT:
            with active_tasks.lock:
                if response.ok:
                    active_tasks.active.update({str(task.id): active_tasks.pending.pop(str(task.id))})
                else:
                    active_tasks.rejected.update({str(task.id): active_tasks.pending.pop(str(task.id))})

def init_devices():
    init_tasks = [Task(task_type=TaskType.INIT,
                       tasks=[TaskData(device=device.device_name,
                                       device_type=device.device_type,
                                       device_address=device.address,
                                       number_of_channels=(samples.n_channels if device.multichannel else None),
                                       sample_mixing=device.allow_sample_mixing)])
                  for device in device_manager.device_list]

    submit_tasks(init_tasks)

@to_thread(daemon=True)
def synchronize_status(poll_delay: int = 5):
    """Thread to periodically query sample status and update

    Args:
        poll_delay (Optional, int): Poll delay in seconds. Default 5
    """

    def check_status_completion(id: str) -> str:
        # send task id to autocontrol to get status
        try:
            response = requests.get(AUTOCONTROL_URL + '/get_task_status/' + id)
        except ConnectionError:
            print(f'Warning: Autocontrol not connected')
            return 'not connected'

        if response.ok:
            if response.json()['queue'] == 'history':
                return 'complete'
        else:
            if 'No task found' in response.text:
                return 'task not found'
            print(f'Warning: status completion fail for id {id} with code {response.status_code}: {response.text}')
        
        return 'uncaught error'

    @trigger_layout_update
    @trigger_samples_update
    def mark_complete(id: str) -> None:
        parent_item = active_tasks.active.pop(id)
        _, sample = samples.getSampleById(parent_item.id)
        stage = sample.stages[parent_item.stage]
        for m in stage.active:
            if m.status != SampleStatus.COMPLETED:
                for t in m.tasks:
                    # coerce to str because t.id can be UUID
                    if str(t.id) == id:
                        t.status = SampleStatus.COMPLETED
            
                if all(t.status == SampleStatus.COMPLETED for t in m.tasks):
                    m.status = SampleStatus.COMPLETED

            #sample.stages[parent_item.stage].update_status()

        # NOTE: this is now done at the LHInterface level. However, GUI is only updated here.
        # if sample stage is complete, execute all methods
        #if sample.stages[parent_item.stage].status == SampleStatus.COMPLETED:
        #    for method in sample.stages[parent_item.stage].methods:
        #        method.execute(layout)

    while True:

        # reserve active_tasks (and samples)
        with active_tasks.lock:
            for task_id in copy.copy(list(active_tasks.active.keys())):
                result = check_status_completion(task_id)
                if result == 'complete':
                    mark_complete(task_id)
                elif result == 'task not found':
                    # Remove item without updating parent
                    print(f'Warning: id {task_id} not found, marking complete anyway')
                    mark_complete(task_id)

        time.sleep(poll_delay)

