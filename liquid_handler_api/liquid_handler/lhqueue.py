"""Internal queue for feeding LH operations one at a time"""
from flask import make_response, Response
from typing import Dict, Callable, List
from threading import Lock
from dataclasses import field
from pydantic import BaseModel
from datetime import datetime

from .job import ResultStatus, ValidationStatus
from .items import Item

from .state import samples, layout
from .samplelist import SampleStatus
from .lhinterface import LHJob, lh_interface

def validate_format(data: dict, fields: list[str]) -> bool:
    """Checks format of data input"""
    print('data in: ', list(data.keys()))
    return all(val in data.keys() for val in fields)

class JobRunner:
    """Routes jobs to submission callbacks. Serves to enable plugins for various interfaces.
        Callbacks should accept data of the validate_format variety and be non-blocking.
    """

    def __init__(self, submit_callbacks: List[Callable] = []) -> None:
        self.submit_callbacks = submit_callbacks

    def submit(self, data: dict, *args, **kwargs) -> Response:
        """Runs submission callbacks and returns any errors
        """

        results = []
        for callback in self.submit_callbacks:
            results.append(callback(data, *args, **kwargs))
        
        return results

class ActiveTasks:
    """Active tasks, used for communication with threads. Structure is
        active_tasks: {task_data_id: Item(sample_id, stage_name)}
        pending_tasks: <same>
        rejected_tasks: <same>

    This is essentially a lookup table to keep track of MethodList.run_jobs for completion status
    """

    def __init__(self) -> None:
        self.lock: Lock = Lock()
        self.pending: Dict[str, Item] = {}
        self.active: Dict[str, Item] = {}
        self.rejected: Dict[str, Item] = {}

        self.populate()

    def populate(self) -> None:
        """Populates list of active jobs from SampleContainer
        """

#        self.active.update({
#            id: Item(sample.id, stagename)
#                for sample in samples.samples
#                for stagename, stage in sample.stages.items()
#                for id in stage.run_jobs if stage.run_jobs is not None
#        })
        for sample in samples.samples:
            for stagename, stage in sample.stages.items():
                for m in stage.methods:
                    for t in m.tasks:
                        if t.status != SampleStatus.COMPLETED:
                            self.active.update({t.id: Item(id=sample.id, stage=stagename)})


class JobQueue(BaseModel):
    """Hub for interfacing (upstream) samples object to (downstream) running of jobs.
        Use submit_callbacks to link submission to downstream activities. Also provides
        an interface for the upstream objects based on validation and run results"""

    jobs: Dict[str, LHJob] = field(default_factory=dict)
    # all jobs that have been submitted

    def __post_init__(self) -> None:
        
        self.lock = Lock()
        self.active_job: LHJob | None = None
        self.submit_callbacks: List[Callable] = []

        # TODO: Reconstruct from history (find all pending samples??)

    def submit(self, job: LHJob, force=False) -> None:
        """Safe put that ignores duplicate requests unless force is False
        
            Important for handling NICE stop/pause/restart requests"""

        with self.lock:
            if not (job.id in self.jobs.keys()) | force:

                self.jobs[job.id] = job

                # route the job appropriately, e.g. self.submit_callbacks.append(lh_interface.activate_job)
                for callback in self.submit_callbacks:
                    callback(job)

    def update_job_validation(self, job: LHJob, result: ValidationStatus) -> None:
        """Handles an update to job validation

        Args:
            job (LHJob): job validated
            result (ValidationStatus): result of validation
        """

        with self.lock:
            _, sample = samples.getSampleById(job.parent.id)
            self.jobs[job.id] = job
            sample.stages[job.parent.stage].run_jobs[job.id].job = job

            if result == ValidationStatus.SUCCESS:
                sample.stages[job.parent.stage].status = SampleStatus.ACTIVE
                self.active_job = job
            elif result == ValidationStatus.FAIL:
                sample.stages[job.parent.stage].status = SampleStatus.FAILED
                # TODO: Handle error condition
            elif result == ValidationStatus.UNVALIDATED:
                print('Received ValidationStatus.UNVALIDATED; this should not happen')
            else:
                print(f'Received ValidationStatus {result}; this should not happen')

    def update_job_result(self, job: LHJob, method_number: int, method_name: str, result: ResultStatus) -> None:
        """Update job; if it's successful, remove from active list; otherwise,
            update sample stage status

        Args:
            job (LHJob): job to update
        """
        with self.lock:
            _, sample = samples.getSampleById(job.parent.id)
            jobcontainer = sample.stages[job.parent.stage].run_jobs[job.id]
            method = jobcontainer.methods[method_number]

            assert method_name == method.method_name, f'Wrong method name {method_name} in result, expected {method.method_name}, full output {job}'

            # update local copies
            jobcontainer.job = job

            if result == ResultStatus.SUCCESS:
                # if successful, remove from jobs and execute the method (thereby updating layout)
                self.jobs.pop(job.id)
                sample.stages[job.parent.stage].update_status()
                method.execute(layout)
                self.clear_active_job()
                return
            elif job.get_result_status() == ResultStatus.FAIL:
                # if failed, remove from jobs and updated parent status
                # TODO: Handle errors here
                self.jobs.pop(job.id)
                sample.stages[job.parent.stage].status = SampleStatus.FAILED
                self.clear_active_job()
                return
            else:
                self.jobs[job.id] = job

    def clear_active_job(self) -> None:
        """Clears the active job
        """

        self.active_job = None

    def repr_queue(self) -> str:
        """Provides a string representation of the queue"""

        return '\n'.join(': '.join((str(i), repr(item))) for i, item in enumerate(self.jobs))


## ========== Liquid handler queue initialization ============

LHqueue = JobQueue()

submit_handler = JobRunner()

# Add appropriate functions to lh_interface callbacks
lh_interface.results_callbacks.append(print)
lh_interface.validation_callbacks.append(print)
lh_interface.validation_callbacks.append(print)