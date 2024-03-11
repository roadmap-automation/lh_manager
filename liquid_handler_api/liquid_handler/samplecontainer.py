from typing import List, Tuple, Dict
from dataclasses import field
from pydantic.v1.dataclasses import dataclass
from .history import History
from .samplelist import Sample, StageName, SampleStatus
from .bedlayout import LHBedLayout
from .dryrun import DryRunQueue
from .items import Item
from .error import MethodError

@dataclass
class SampleContainer:
    """Specialized sample dictionary allowing convenient referencing by sample ID or sample name"""

    samples: list[Sample] = field(default_factory=list)
    dryrun_queue: DryRunQueue = field(default_factory=DryRunQueue)
    max_LH_id: int = 1

    def _getIDs(self) -> list[str]:

        return [s.id for s in self.samples]

    def _getNames(self) -> list[str]:

        return [s.name for s in self.samples]

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

    def archiveSample(self, sample: Sample) -> None:
        """Moves sample to history archive

        Args:
            sample (Sample): sample to archive
        """

        with History() as history:
            history.smart_insert(sample)

    def dryrun(self, layout: LHBedLayout) -> List[Tuple[Item, List[MethodError]]]:
        """Executes dry run of everything in the queue by copying the layout and
            executing all methods in the queue

        Args:
            layout (LHBedLayout): bed layout on which to dry run

        Returns:
            List[Tuple[Item, List[MethodError]]]: list of item / error list keys
        """
        errors: List[Tuple[Item, List[MethodError]]] = []
        self.validate_queue(self.dryrun_queue)
        for item in self.dryrun_queue.stages:
            _, sample = self.getSampleById(item.id)
            new_errors = sample.stages[item.stage].execute(layout)
            if not all (v is None for v in new_errors):
                errors.append((item, new_errors))

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
