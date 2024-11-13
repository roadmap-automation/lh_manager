"""Interface for NICE"""

from datetime import datetime
from typing import List, Dict, Callable
from uuid import uuid4
from dataclasses import field
from pydantic import BaseModel
from threading import Lock

from ..gui_api.events import trigger_sample_status_update, trigger_layout_update

from ..liquid_handler.lhqueue import submit_handler, ActiveTasks
from ..liquid_handler.lhmethods import LHDevice
from ..liquid_handler.methods import MethodsType
from ..liquid_handler.bedlayout import LHBedLayout
from ..liquid_handler.samplelist import Sample, StageName
from ..liquid_handler.state import samples, layout
from ..liquid_handler.items import Item
from ..liquid_handler.samplecontainer import SampleStatus
from ..liquid_handler.lhinterface import lh_interface, LHJob, ResultStatus, ValidationStatus

active_tasks = ActiveTasks()

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
            print(data, data['stage'])
            if sample.stages[stage].status != SampleStatus.INACTIVE:
                return f'stage {stage} of sample {data["name"]} is not inactive'
            
            # only if an injection operation, set sample NICE_uuid and NICE_slotID
            if stage == StageName.INJECT:
                sample.NICE_uuid = data.get('uuid', None)
                slot_id = data.get('slotID', 0)
                sample.NICE_slotID = int(slot_id) if slot_id is not None else None

            # prepare methods
            all_methods: List[MethodsType] = []
            for m in sample.stages[stage].methods:
                all_methods += m.get_methods(layout)

            # render all the methods
            rendered_methods: List[dict] = [m2
                                            for m in all_methods
                                            for m2 in m.render_method(sample_name=sample.name,
                                                            sample_description=sample.description,
                                                            layout=layout)]
            
            # create job (should generally be only one)
            sample.stages[stage].run_jobs = []
            for m in rendered_methods:
                job = LHJob(id=str(uuid4()),
                            method_data=LHDevice.create_job_data(m[LHDevice.device_name]),
                            parent=Item(sample.id, stage))
            
                # register job
                sample.stages[stage].run_jobs += [job.id]
                active_tasks.pending.update({job.id: job.parent})

                # submit to LHqueue (marks status as pending)
                LHqueue.submit(job)
        
        return
    
    return 'sample not found'

submit_handler.submit_callbacks.append(submission_callback)

@trigger_layout_update
@trigger_sample_status_update
def mark_complete(job: LHJob):
    # find parent sample
    parent_item = active_tasks.active.pop(job.id)
    _, sample = samples.getSampleById(parent_item.id)

    # remove completed job from running jobs and update status
    sample.stages[parent_item.stage].run_jobs.pop(sample.stages[parent_item.stage].run_jobs.index(str(job.id)))
    sample.stages[parent_item.stage].update_status()

    # if sample stage is complete, execute all methods
    if sample.stages[parent_item.stage].status == SampleStatus.COMPLETED:
        for method in sample.stages[parent_item.stage].methods:
            method.execute(layout)

class JobQueue(BaseModel):
    """Hub for interfacing (upstream) samples object to (downstream) running of jobs.
        Use submit_callbacks to link submission to downstream activities. Also provides
        an interface for the upstream objects based on validation and run results"""

    jobs: List[LHJob] = field(default_factory=list)
    # all jobs that have been submitted

    def __post_init__(self) -> None:
        
        self.running = True
        self.lock = Lock()
        self.active_job: LHJob | None = None
        self.submit_callbacks: List[Callable] = []

        # TODO: Reconstruct from history (find all pending samples??)

    def job_exists(self, id: str) -> bool:
        """Check whether job with id is already in the job queue

        Args:
            id (str): id to check

        Returns:
            bool: True if job exists, False otherwise
        """

        return True if id in [job.id for job in self.jobs] else False

    def submit(self, job: LHJob, force=False) -> None:
        """Safe put that ignores duplicate requests unless force is False
        
            Important for handling NICE stop/pause/restart requests"""

        if self.running:
            with self.lock:
                if not self.job_exists(job.id) | force:

                    self.jobs.append(job)

                    _, sample = samples.getSampleById(job.parent.id)
                    sample.stages[job.parent.stage].status = SampleStatus.PENDING
                    active_tasks.active.update({str(job.id): active_tasks.pending.pop(str(job.id))})

                    # route the job appropriately, e.g. self.submit_callbacks.append(lh_interface.activate_job)
                    for callback in self.submit_callbacks:
                        callback(job)

                    # run immediately if no active jobs
                else:
                    print(f'Warning: job id {job.id} exists')
                    return
            
            self.run_next()

    def update_job_validation(self, job: LHJob, result: ValidationStatus) -> None:
        """Handles an update to job validation

        Args:
            job (LHJob): job validated
            result (ValidationStatus): result of validation
        """

        pass

    def update_job_result(self, job: LHJob, method_number: int, method_name: str, result: ResultStatus) -> None:
        """Update job; if it's successful, remove from active list and run next

        Args:
            job (LHJob): job to update
        """

        if job.id != self.active_job.id:
            print(f'Warning: received update on id {job.id} but active job id is {self.active_job.id})')
            return

        if job.get_result_status() == ResultStatus.SUCCESS:
            mark_complete(job)
            self.clear_active_job()
            self.run_next()


    def run_next(self) -> None:
        """Submits the next job to lh_interface. Does not wait for lh_interface
            to go idle; should be called at any point when an idle state may occur,
            e.g. after submitting a job or after a job has finished.
        """

        if self.running:
            with self.lock:
                if (self.active_job is None) & (len(self.jobs) > 0):
                    self.active_job = self.jobs.pop(0)
                    _, sample = samples.getSampleById(self.active_job.parent.id)
                    sample.stages[self.active_job.parent.stage].status = SampleStatus.ACTIVE
                    lh_interface.activate_job(self.active_job)

    def clear_active_job(self) -> None:
        """Clears the active job
        """

        self.active_job = None

    def stop(self) -> None:
        """Clears the queue. Does not clear active job
        """

        with self.lock:
            # reset status of each stage
            while len(self.jobs):
                job = self.jobs.pop(0)
                _, sample = samples.getSampleById(job.parent.id)
                sample.stages[job.parent.stage].status = SampleStatus.INACTIVE


    def pause(self) -> None:
        """Pauses queue after current job completes
        """
        self.running = False

    def resume(self) -> None:
        """Resumes queue"""
        self.running = True
        self.run_next()

    def repr_queue(self) -> str:
        """Provides a string representation of the queue"""

        return '\n'.join(': '.join((str(i), repr(item))) for i, item in enumerate(self.jobs))

LHqueue = JobQueue()
lh_interface.results_callbacks.append(LHqueue.update_job_result)