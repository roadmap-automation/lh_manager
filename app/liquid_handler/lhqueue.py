"""Internal queue for feeding LH operations one at a time"""
from queue import Queue
from datetime import datetime

from .state import samples
from .samplelist import SampleStatus, DATE_FORMAT, StageName, example_sample_list

def validate_format(data: dict) -> bool:
    """Checks format of data input"""

    return all(val in data.keys() for val in ('name', 'uuid', 'slotID', 'stage'))

class LHSimpleQueue(Queue):
    """Derived queue class for keeping track of LH status"""
    busy = False

    def put_safe(self, data) -> None:
        """Safe put that ignores duplicate requests.
        
            Important for handling NICE stop/pause/restart requests"""

        if data not in self.queue:
            self.put(data)

    def stop(self) -> int:
        """Empties queue and resets status of incomplete methods to INACTIVE"""

        while not self.empty():
            data = self.get()
            sample = samples.getSamplebyName(data['name'])
            
            # should only ever be one stage
            for stage in data['stage']:
                # reset status of sample stage to INACTIVE
                sample.stages[stage].status = SampleStatus.INACTIVE

    def run_next(self) -> None:
        """Runs next item in queue if queue is not busy and there are items to run.
        Otherwise, does nothing"""

        if (self.qsize() > 0) & (not self.busy):
            # get next item in queue
            data = self.get()
            self.busy = True

            # get sample name
            # NOTE: checks for inactivity, etc. are done when the sample is enqueued.
            # If anything has changed in the meantime, it will not be captured here
            sample = samples.getSamplebyName(data['name'])

            # Note: by construction of the queue there should only ever be one item in stage
            for stage in data['stage']:
                # set stage status to active, set date activated, give LH_id
                methodlist = sample.stages[stage]
                methodlist.status = SampleStatus.ACTIVE
                methodlist.createdDate = datetime.now().strftime(DATE_FORMAT)
                methodlist.LH_id = samples.getMaxLH_id() + 1

                # only if an injection operation, set sample NICE_uuid and NICE_slotID
                if stage == StageName.INJECT:
                    sample.NICE_uuid = data['uuid']
                    sample.NICE_slotID = int(data['slotID'])

    def repr_queue(self):
        """Provides a string representation of the queue"""

        return '\n'.join(str(item) for item in self.queue)

## ========== Liquid handler queue initialization ============

LHqueue = LHSimpleQueue()

# TODO: remove for production (though having a dummy method first 
# might be useful before pushing "auto run" on Trilution)
LHqueue.put_safe({'name': example_sample_list[0].name, 'uuid': '0', 'slotID': '1', 'stage': ['prep']})
LHqueue.run_next()
