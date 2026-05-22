"""Interface for autocontrol"""

import logging
import threading

from typing import List, Dict
from uuid import uuid4

from autocontrol.task_struct import Task, TaskData, TaskType
from autocontrol.status import Status

from ..gui_api.events import trigger_samples_update, trigger_layout_update

from ..liquid_handler.devices import device_manager
from ..liquid_handler.lhqueue import submit_handler, ActiveTasks
from ..liquid_handler.methods import MethodsType, MethodType, TaskContainer, BaseMethod, RawMethod, EXCLUDE_FIELDS, method_manager
from ..liquid_handler.bedlayout import LHBedLayout
from ..liquid_handler.samplelist import Sample
from ..liquid_handler.state import samples
from ..liquid_handler.items import Item
from ..liquid_handler.samplecontainer import SampleStatus, SampleContainer

COMPLETED_STATUS = [SampleStatus.COMPLETED, SampleStatus.FAILED, SampleStatus.CANCELLED, SampleStatus.UNKNOWN]

active_tasks = ActiveTasks()

# Broker worker reference — set by app.py via set_broker_worker() before
# launch_autocontrol_interface() is called.
_broker_worker = None

def set_broker_worker(worker) -> None:
    global _broker_worker
    _broker_worker = worker


def launch_autocontrol_interface():
    """Register submission/cancel callbacks and send device INIT tasks."""
    submit_handler.submit_callbacks.append(submission_callback)
    submit_handler.cancel_callbacks.append(cancel_callback)

def submission_callback(data: dict):
    """Submission handler callback

    Args:
        data (dict): dictionary of submission data
    """

    if 'tasks' in data:

        submit_tasks(tasks=[AutocontrolTaskContainer(task=Task(**d), status=SampleStatus.PENDING) for d in data['tasks']], resubmit=True)

    else:

        if 'id' in data:
            _, sample = samples.getSampleById(data['id'])
        else:
            sample = samples.getSamplebyName(data['name'])

        # check that sample name exists
        if sample is not None:
            # check if running a single method or an entire stage
            if 'method_id' in data.keys():
                prepare_and_submit_method(sample=sample,
                                        stage=data['stage'],
                                        method_index=[m.id for m in sample.stages[data['stage']].methods].index(data['method_id']))

            else:
                for stage in data['stage']:
                    prepare_and_submit_stage(sample, stage)

            return

        return 'sample not found'

def cancel_callback(data: dict):
    """Submission handler callback

    Args:
        data (dict): dictionary of cancellation data
    """

    return cancel_tasks(tasks=[Task(**d) for d in data['tasks']],
                        include_active_queue=data.get('include_active_queue', False),
                        drop_material=data.get('drop_material', False))

class AutocontrolTaskContainer(TaskContainer):
    id: str | None = None
    task: Task | None = None
    status: SampleStatus | None = None

    def model_post_init(self, __context):

        if self.id is None:
            self.id = self.task.id

class AutocontrolItem(Item):
    method_id: str | None = None

def _submit_raw_method(sample: Sample, stage: str, method_index: int, m: RawMethod) -> None:
    """Broker-path submission for RawMethod — bypasses legacy render/render_method pipeline."""
    raw_method_name = m.method_data.get('method_name')
    schema = method_manager._remote_schemas.get(raw_method_name)
    if schema is None:
        logging.error(
            "Cannot submit RawMethod '%s': no remote schema registered. "
            "Ensure the device is running and has published device.registered.",
            raw_method_name,
        )
        return

    device_id = schema.get('device_id')
    if not device_id:
        logging.error(
            "Cannot submit RawMethod '%s': schema is missing device_id "
            "(re-start the device to trigger a fresh device.registered event).",
            raw_method_name,
        )
        return

    device = device_manager.get_device_by_name(device_id)
    channel = sample.channel if (device is not None and device.multichannel) else None

    # Strip lh_manager tracking / metadata fields — device only needs user parameters.
    params = {k: v for k, v in m.method_data.items() if k not in EXCLUDE_FIELDS}

    task_data = TaskData(
        device=device_id,
        channel=channel,
        method_data={'method_list': [{'method_name': raw_method_name, 'method_data': params}]},
    )

    if m.method_type == MethodType.MEASURE:
        tasktype = TaskType.MEASURE
    elif m.method_type == MethodType.PREPARE:
        tasktype = TaskType.PREPARE
    else:
        tasktype = TaskType.NOCHANNEL

    new_task = AutocontrolTaskContainer(
        task=Task(sample_id=sample.id, task_type=tasktype, tasks=[task_data]),
        status=SampleStatus.INACTIVE,
    )

    with active_tasks.lock:
        m.tasks.append(new_task)
        active_tasks.pending[str(new_task.task.id)] = AutocontrolItem(
            id=sample.id, stage=stage, method_id=m.id,
        )

    sample.stages[stage].activate(method_index)
    submit_tasks([new_task])


def prepare_and_submit_stage(sample: Sample, stage: str, layout: LHBedLayout | None = None) -> List[Task]:
    """Runs all draft methods in an entire stage
    """

    # Generate real-time tasks based on layout
    for _ in range(len(sample.stages[stage].methods)):
        prepare_and_submit_method(sample, stage, 0, layout)

def _submit_raw_method_group(sample: Sample, stage: str, method_index: int, m: RawMethod) -> None:
    """Broker-path submission for a parallel method group — one Task, multiple TaskData."""
    method_group = m.method_data["method_group"]
    taskdata = []
    for sub in method_group:
        method_name = sub["method_name"]
        schema = method_manager._remote_schemas.get(method_name)
        if schema is None:
            logging.error(
                "Cannot submit method group: no remote schema for '%s'. "
                "Ensure the device is running and has published device.registered.",
                method_name,
            )
            return
        device_id = schema.get("device_id")
        if not device_id:
            logging.error(
                "Cannot submit method group: schema for '%s' is missing device_id.",
                method_name,
            )
            return
        device = device_manager.get_device_by_name(device_id)
        channel = sample.channel if (device is not None and device.multichannel) else None
        params = {k: v for k, v in sub.items() if k not in ("method_name",) and k not in EXCLUDE_FIELDS}
        taskdata.append(TaskData(
            id=str(uuid4()),
            device=device_id,
            channel=channel,
            method_data={"method_list": [{"method_name": method_name, "method_data": params}]},
            non_channel_storage="vial" if channel is None else None,
        ))

    new_task = AutocontrolTaskContainer(
        task=Task(sample_id=sample.id, task_type=TaskType.TRANSFER, tasks=taskdata),
        status=SampleStatus.INACTIVE,
    )
    with active_tasks.lock:
        m.tasks.append(new_task)
        active_tasks.pending[str(new_task.task.id)] = AutocontrolItem(
            id=sample.id, stage=stage, method_id=m.id,
        )
    sample.stages[stage].activate(method_index)
    submit_tasks([new_task])


def prepare_and_submit_method(sample: Sample, stage: str, method_index: int, layout: LHBedLayout | None = None) -> List[Task]:
    """Runs a specific method by index
    """

    # Generate real-time tasks based on layout
    m: MethodsType = sample.stages[stage].methods[method_index]

    if isinstance(m, RawMethod):
        if m.method_data.get("method_group"):
            _submit_raw_method_group(sample, stage, method_index, m)
        else:
            _submit_raw_method(sample, stage, method_index, m)
        return []

    all_methods: List[MethodsType] = m.get_methods(layout)

    # render all the methods. Can be multiple rendered submethod per main method
    rendered_methods: List[List[dict]] = [m.render_method(sample_name=sample.name,
                                                    sample_description=sample.description,
                                                    layout=layout)
                                            for m in all_methods]

    method_types: List[MethodType] = [m.method_type
                                    for m in all_methods]

    # create tasks, one per method
    tasks: List[AutocontrolTaskContainer] = []
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
            if method_type == MethodType.NONE:
                tasktype = TaskType.NOCHANNEL
            elif len(method.keys()) > 1:
                tasktype = TaskType.TRANSFER
            elif method_type == MethodType.PREPARE:
                tasktype = TaskType.PREPARE
            elif method_type == MethodType.MEASURE:
                tasktype = TaskType.MEASURE
            else:
                tasktype = TaskType.NOCHANNEL

            new_task = AutocontrolTaskContainer(task=Task(sample_id=sample.id,
                                                          task_type=tasktype,
                                                          tasks=taskdata),
                                                status=SampleStatus.INACTIVE)

            # reserve active_tasks (and sample.stages[stage])
            with active_tasks.lock:
                m.tasks.append(new_task)
                active_tasks.pending.update({str(new_task.task.id): AutocontrolItem(id=sample.id, stage=stage, method_id=m.id)})

            tasks.append(new_task)

    sample.stages[stage].activate(method_index)
    submit_tasks(tasks)

def to_thread(**thread_kwargs):
    def decorator_to_thread(f):
        """Decorator that starts target function in a new thread"""
        def wrap(*args, **kwargs):
            threading.Thread(target=f, args=args, kwargs=kwargs, **thread_kwargs).start()
        wrap.__name__ = f.__name__
        return wrap
    return decorator_to_thread

submission_lock = threading.Lock()

@to_thread()
def submit_tasks(tasks: List[AutocontrolTaskContainer], resubmit=False):
    # submission lock prevents multiple methods from being submitted at the same time
    with submission_lock:
        for taskcontainer in tasks:
            task = taskcontainer.task
            logging.info('Submitting Task: ' + task.tasks[0].device + ' ' + task.task_type + '\n')
            if _broker_worker is None:
                logging.error('Broker worker not set — cannot submit task %s', task.id)
                if task.task_type != TaskType.INIT:
                    taskcontainer.status = SampleStatus.FAILED
                continue
            if resubmit:
                _broker_worker.resubmit_task(task)
            else:
                _broker_worker.submit_task(task)
            if task.task_type != TaskType.INIT:
                with active_tasks.lock:
                    if str(task.id) in active_tasks.pending:
                        taskcontainer.status = SampleStatus.PENDING
                        active_tasks.active.update({str(task.id): active_tasks.pending.pop(str(task.id))})

@to_thread()
def cancel_tasks(tasks: List[Task], include_active_queue: bool = False, drop_material: bool = True):
    for task in tasks:
        logging.info('Cancelling task: ' + str(task.id))
        if _broker_worker is None:
            logging.error('Broker worker not set — cannot cancel task %s', task.id)
            continue
        _broker_worker.cancel_task(str(task.id),
                                   include_active_queue=include_active_queue,
                                   drop_material=drop_material)
        with active_tasks.lock:
            if str(task.id) in active_tasks.active:
                mark_cancelled(str(task.id))

@trigger_samples_update
def mark_cancelled(id: str) -> None:
    """Mark a task cancelled in the active method tree.

    Must be called with active_tasks.lock held by the caller.
    """
    parent_item = active_tasks.active.pop(id)
    _, sample = samples.getSampleById(parent_item.id)
    if sample is None:
        return
    active_methods: List[BaseMethod] = sample.stages[parent_item.stage].active
    for m in active_methods:
        if m.status != SampleStatus.COMPLETED:
            for t in m.tasks:
                if str(t.id) == id:
                    t.status = SampleStatus.CANCELLED

            if all(t.status == SampleStatus.COMPLETED for t in m.tasks):
                m.status = SampleStatus.COMPLETED
            elif any(t.status == SampleStatus.ACTIVE for t in m.tasks):
                m.status = SampleStatus.ACTIVE
            elif any(t.status == SampleStatus.ERROR for t in m.tasks):
                m.status = SampleStatus.ERROR
            else:
                m.status = SampleStatus.PENDING

@trigger_samples_update
def mark_status(id: str, status: SampleStatus) -> None:
    """Update task status in the active method tree.

    Must be called with active_tasks.lock held by the caller.
    Decorated with @trigger_samples_update so the GUI is notified automatically.
    """
    parent_item = active_tasks.active.pop(id)
    _, sample = samples.getSampleById(parent_item.id)

    # check that sample still exists (not yet archived)
    if sample is not None:
        active_methods: List[BaseMethod] = sample.stages[parent_item.stage].active
        for m in active_methods:
            if m.status != SampleStatus.COMPLETED:
                for t in m.tasks:
                    # coerce to str because t.id can be UUID
                    if str(t.id) == id:
                        t.status = status

                if all(t.status == SampleStatus.COMPLETED for t in m.tasks):
                    m.status = SampleStatus.COMPLETED
                elif any(t.status == SampleStatus.ACTIVE for t in m.tasks):
                    m.status = SampleStatus.ACTIVE
                elif any(t.status == SampleStatus.ERROR for t in m.tasks):
                    m.status = SampleStatus.ERROR
                else:
                    m.status = SampleStatus.PENDING

        if status not in COMPLETED_STATUS:
            # put it back if not marking complete
            active_tasks.active.update({id: parent_item})
