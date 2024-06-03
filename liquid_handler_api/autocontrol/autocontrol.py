"""Interface for autocontrol"""

from typing import List, Dict
import requests
import threading
import time
import copy
import json
from uuid import uuid4

from autocontrol.task_struct import Task, TaskData, TaskType
from autocontrol.status import Status

from ..gui_api.events import trigger_sample_status_update

from ..liquid_handler.devices import device_manager
from ..liquid_handler.lhqueue import submit_handler
from ..liquid_handler.methods import MethodsType
from ..liquid_handler.bedlayout import LHBedLayout
from ..liquid_handler.samplelist import Sample, StageName
from ..liquid_handler.state import samples, layout
from ..liquid_handler.items import Item
from ..liquid_handler.samplecontainer import SampleStatus
from ..liquid_handler.lhinterface import lh_interface, LHJob, ResultStatus
from ..liquid_handler.lhqueue import ActiveTasks

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
            if sample.stages[stage].status != SampleStatus.INACTIVE:
                return f'stage {stage} of sample {data["name"]} is not inactive'
            
            sample.stages[stage].status = SampleStatus.PENDING
            prepare_and_submit(sample, stage, layout)

        return

    return 'sample not found'

@trigger_sample_status_update
def results_callback(job: LHJob, *args, **kwargs):
    # this doesn't work now that we're using the parent task to update things
    if job.get_result_status() == ResultStatus.SUCCESS:
        parent_item = active_tasks.active.pop(job.id)
        _, sample = samples.getSampleById(parent_item.id)
        sample.stages[parent_item.stage].run_jobs.pop(sample.stages[parent_item.stage].run_jobs.index(str(job.id)))
        sample.stages[parent_item.stage].update_status()

#lh_interface.results_callbacks.append(results_callback)

def prepare_and_submit(sample: Sample, stage: StageName, layout: LHBedLayout) -> List[Task]:
    """Prepares a method list for running by populating run_methods and run_methods_complete.
        List can then be used for dry or wet runs
    """
   
    # Generate real-time tasks based on layout
    all_methods: List[MethodsType] = []
    for m in sample.stages[stage].methods:
        all_methods += m.get_methods(layout)

    # render all the methods
    rendered_methods: List[dict] = [m2
                                    for m in all_methods
                                    for m2 in m.render_lh_method(sample_name=sample.name,
                                                    sample_description=sample.description,
                                                    layout=layout)]

    # create tasks, one per method
    tasks: List[Task] = []
    sample.stages[stage].run_jobs = []
    for method in rendered_methods:
        new_task = Task(id=str(uuid4()),
                        sample_id=sample.id,
                        task_type=TaskType.NOCHANNEL,
                        tasks=[TaskData(id=uuid4(),
                                        device=device_name,
                                        channel=(sample.channel if device_manager.get_device_by_name(device_name).is_multichannel() else None),
                                        method_data=device_manager.get_device_by_name(device_name).create_job_data(method[device_name]))
                                for device_name in method.keys()])
        
        # detect transfer tasks
        if len(new_task.tasks) > 1:
            new_task.task_type = TaskType.TRANSFER
        elif new_task.tasks[0].channel is not None:
            new_task.task_type = TaskType.MEASURE

        # reserve active_tasks (and sample.stages[stage])
        with active_tasks.lock:
            sample.stages[stage].run_jobs += [str(new_task.id)]
            active_tasks.pending.update({str(new_task.id): Item(sample.id, stage)})

        tasks.append(new_task)
    
    submit_tasks(tasks)

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
                                       number_of_channels=(samples.n_channels if device.is_multichannel() else None))])
                  for device in device_manager.device_list]

    submit_tasks(init_tasks)

@to_thread(daemon=True)
def synchronize_status(poll_delay: int = 5):
    """Thread to periodically query sample status and update

    Args:
        poll_delay (Optional, int): Poll delay in seconds. Default 5
    """

    def check_status_completion(id: str) -> bool:
        # send task id to autocontrol to get status
        try:
            response = requests.get(AUTOCONTROL_URL + '/get_task_status/' + id)
        except ConnectionError:
            print(f'Warning: Autocontrol not connected')
            return False

        if response.ok:
            if response.json()['queue'] == 'history':
                return True
        else:
            print(f'Warning: status completion fail for id {id} with code {response.status_code}: {response.text}')
        
        return False

    @trigger_sample_status_update
    def mark_complete(id: str) -> None:
        parent_item = active_tasks.active.pop(id)
        _, sample = samples.getSampleById(parent_item.id)
        sample.stages[parent_item.stage].run_jobs.pop(sample.stages[parent_item.stage].run_jobs.index(id))
        sample.stages[parent_item.stage].status = SampleStatus.PARTIAL
        sample.stages[parent_item.stage].update_status()

    while True:

        # reserve active_tasks (and samples)
        with active_tasks.lock:
            for task_id in copy.copy(list(active_tasks.active.keys())):
                if check_status_completion(task_id):
                    mark_complete(task_id)

        time.sleep(poll_delay)

