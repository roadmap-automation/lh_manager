from typing import List, Tuple
from dataclasses import field
from pydantic.dataclasses import dataclass
from .samplelist import Sample, StageName, SampleStatus
from .bedlayout import LHBedLayout
from .dryrun import DryRunQueue, DryRunError

@dataclass
class SampleContainer:
    """Specialized sample dictionary allowing convenient referencing by sample ID or sample name"""

    samples: list[Sample] = field(default_factory=list)
    dryrun_queue: DryRunQueue = field(default_factory=DryRunQueue)

    def _getIDs(self) -> list[str]:

        return [s.id for s in self.samples]

    def _getNames(self) -> list[str]:

        return [s.name for s in self.samples]

    def getSampleStagebyLH_ID(self, id: int) -> Tuple[Sample | None, StageName | None]:
        """Return sample with specific id"""

        for sample in self.samples:
            if id in sample.get_LH_ids():
                return sample, sample.getStageByID(id)

        return None, None
        #raise ValueError(f"Sample ID {id} not found!")

    def getSampleById(self, id: str) -> Tuple[int, Sample] | Tuple[None, None]:
        return next(((i,s) for i,s in enumerate(self.samples) if s.id == id), (None, None))

    def getSamplebyName(self, name: str, status: SampleStatus | None = None) -> Sample | None:
        """Return sample with specific name"""
        names = self._getNames()
        if name in names:
            sample = self.samples[names.index(name)]
            return sample if (sample.get_status() == status) | (status is None) else None
        else:
            return None
            #raise ValueError(f"Sample name {name} not found!")

    def addSample(self, sample: Sample) -> None:
        """Sample appender that checks for proper ID value"""
        if sample.id in self._getIDs():
            print(f'Warning: id {sample.id} already taken. Sample not added.')
        else:
            self.samples.append(sample)
        
    def deleteSample(self, sample: Sample) -> None:
        """Special remover that also updates index object"""
        
        self.samples.pop(self.samples.index(sample))

    def getMaxLH_id(self) -> int:
        """ Returns maximum index value for Sample.MethodList.LH_id. If no LH_ids are defined,
            returns -1."""
        
        lh_ids = []
        for sample in self.samples:
            for lh_id in sample.get_LH_ids():
                lh_ids.append(lh_id)

        return max([lh_id if lh_id is not None else -1 for lh_id in lh_ids])
    
    def dryrun(self, layout: LHBedLayout) -> List[DryRunError]:
        """Executes dry run of everything in the queue by copying the layout and
            executing all methods in the queue

        Args:
            layout (LHBedLayout): bed layout on which to dry run

        Returns:
            List[DryRunError]: list of errors
        """
        errors: List[DryRunError] = []
        self.validate_queue(self.dryrun_queue)
        for item in self.dryrun_queue.stages:
            _, sample = self.getSampleById(item.id)
            sample.stages[item.stage].execute(layout)

        # TODO: figure out how to catch errors
        return errors
    
    def validate_queue(self, q: DryRunQueue) -> None:
        """Checks that all items in the queue are actually present in the sample list;
            if not, removes them from the queue

        Args:
            q (DryRunQueue): Queue to check
        """

        for item in q.stages:
            _, sample = self.getSampleById(item.id)
            if sample is None:
                q.stages.pop(q.stages.index(item))
