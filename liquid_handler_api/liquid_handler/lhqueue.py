"""Internal queue for feeding LH operations one at a time"""
from typing import Dict, Callable, List
from threading import Lock
from dataclasses import field
from pydantic.v1.dataclasses import dataclass
from datetime import datetime

from .job import ResultStatus, ValidationStatus

from .state import samples, layout
from .samplelist import SampleStatus
from .lhinterface import LHJob, lh_interface

def validate_format(data: dict) -> bool:
    """Checks format of data input"""
    print('data in: ', list(data.keys()))
    return all(val in data.keys() for val in ('name', 'uuid', 'slotID', 'stage'))

@dataclass
class JobQueue:
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

# Add appropriate functions to lh_interface callbacks
lh_interface.results_callbacks.append(LHqueue.update_job_result)
lh_interface.validation_callbacks.append(LHqueue.update_job_validation)