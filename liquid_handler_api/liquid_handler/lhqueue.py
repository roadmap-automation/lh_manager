"""Internal queue for feeding LH operations one at a time"""
from typing import Dict, Callable, List
from threading import Lock
from dataclasses import field
from pydantic.v1.dataclasses import dataclass
from datetime import datetime

from .state import samples
from .samplelist import SampleStatus
from .lhinterface import LHJob, ResultStatus, ValidationStatus, lh_interface

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

                #lh_interface.activate_job(job)

    def update_job(self, job: LHJob) -> None:
        """Update job; if it's successful, remove from active list; otherwise,
            update sample stage status

        Args:
            job (LHJob): job to update
        """
        with self.lock:
            # update local copy
            self.jobs[job.id] = job

            # update samples copy
            _, sample = samples.getSampleById(job.id)
            sample.stages[job.parent.stage].run_methods[job.id] = job

            if job.get_result_status() == ResultStatus.SUCCESS:
                self.jobs.pop(job.id)
                sample.stages[job.parent.stage].update_status()
                self.clear_active_job()
                return
            elif job.get_result_status() == ResultStatus.FAIL:
                self.jobs.pop(job.id)
                sample.stages[job.parent.stage].status = SampleStatus.FAILED
                self.clear_active_job()
                return
            # NOTE: if ResultStatus.INCOMPLETE, don't do anything
            elif job.get_result_status() == ResultStatus.EMPTY:
                if job.get_validation_status() == ValidationStatus.SUCCESS:
                    sample.stages[job.parent.stage].status = SampleStatus.ACTIVE
                    self.active_job = job
                elif job.get_validation_status() == ValidationStatus.FAIL:
                    sample.stages[job.parent.stage].status = SampleStatus.FAILED
                else:
                    print('Received ValidationStatus.UNVALIDATED; this should not happen')

    def clear_active_job(self) -> None:
        """Clears the active job
        """

        self.active_job = None

    def repr_queue(self) -> str:
        """Provides a string representation of the queue"""

        return '\n'.join(': '.join((str(i), repr(item))) for i, item in enumerate(self.jobs))


## ========== Liquid handler queue initialization ============

LHqueue = JobQueue()