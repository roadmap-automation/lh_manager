"""Internal queue for feeding LH operations one at a time"""
from threading import Lock
from pydantic.v1.dataclasses import dataclass
from datetime import datetime

from .state import samples
from .samplelist import SampleStatus, DATE_FORMAT, StageName, example_sample_list
from .dryrun import DryRunQueue
from .items import Item

def validate_format(data: dict) -> bool:
    """Checks format of data input"""
    print('data in: ', list(data.keys()))
    return all(val in data.keys() for val in ('name', 'uuid', 'slotID', 'stage'))

@dataclass
class RunQueue(DryRunQueue):

    running: bool = True
    active_sample: Item | None = None

    def __post_init__(self) -> None:

        self.lock = Lock()

    def pause(self):
        """Pauses operations
        """

        self.running = False

    def resume(self):
        """Resumes operations"""

        self.running = True

    def put_safe(self, item: Item) -> None:
        """Safe put that ignores duplicate requests.
        
            Important for handling NICE stop/pause/restart requests"""

        with self.lock:
            if item not in self.stages:
                _, sample = samples.getSampleById(item.id)
                sample.stages[item.stage].status = SampleStatus.PENDING
                self.stages.append(item)

    def put_first(self, item: Item) -> None:
        """Safe put that ignores duplicate requests.
        
            Important for handling NICE stop/pause/restart requests"""

        with self.lock:
            if item not in self.stages:
                _, sample = samples.getSampleById(item.id)
                sample.stages[item.stage].status = SampleStatus.PENDING
                self.stages.insert(0, item)

    def stop(self) -> int:
        """Empties queue and resets status of incomplete methods to INACTIVE"""

        with self.lock:
            while not len(self.stages):
                data = self.stages.pop(0)
                _, sample = samples.getSampleById(data.id)
                
                # reset status of sample stage to INACTIVE
                sample.stages[data.stage].status = SampleStatus.INACTIVE

    def run_next(self) -> None:
        """Runs next item in queue if queue is not busy and there are items to run.
        Otherwise, does nothing"""

        if self.running:
            with self.lock:
                # if there is something to run and there is no active sample
                if len(self.stages) & (self.active_sample is None):
                    # get next item in queue
                    item = self.stages.pop(0)

                    # get sample name
                    # NOTE: checks for inactivity, etc. are done when the sample is enqueued.
                    # If anything has changed in the meantime, it will not be captured here
                    _, sample = samples.getSampleById(item.id)

                    # set stage status to active, set date activated, give LH_id
                    methodlist = sample.stages[item.stage]
                    methodlist.status = SampleStatus.ACTIVE
                    methodlist.createdDate = datetime.now().strftime(DATE_FORMAT)

                    # set ID equal to max id and increment by 1
                    methodlist.LH_id = samples.max_LH_id + 1
                    samples.max_LH_id += 1

                    # only if an injection operation, set sample NICE_uuid and NICE_slotID
                    if item.stage == StageName.INJECT:
                        sample.NICE_uuid = item.data.get('uuid', None)
                        slot_id = item.data.get('slotID', 0)
                        sample.NICE_slotID = int(slot_id) if slot_id is not None else None

                    self.active_sample = item

    def clear_active_sample(self) -> None:
        """Clears the active sample
        """

        self.active_sample = None

    def repr_queue(self) -> str:
        """Provides a string representation of the queue"""

        return '\n'.join(': '.join((str(i), repr(item))) for i, item in enumerate(self.stages))


## ========== Liquid handler queue initialization ============

LHqueue = RunQueue()