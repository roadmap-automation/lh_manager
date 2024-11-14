from pydantic import BaseModel, validator, Field
from enum import Enum
from uuid import uuid4
from typing import Dict, List, Union, Any

from .lhmethods import Sleep
from .bedlayout import LHBedLayout
from .lhinterface import DATE_FORMAT
from .items import StageName
from .status import MethodError, SampleStatus
from .methods import MethodsType, BaseMethod, method_manager, TaskContainer
from datetime import datetime

class MethodList(BaseModel):
    """Class representing a list of methods representing one LH job. Can be nested
        in a single stage"""
    createdDate: str | None = None
    methods: list = Field(default_factory=list)
    active: list = Field(default_factory=list)
    status: SampleStatus = SampleStatus.INACTIVE

    @validator('methods', 'active')
    def validate_methods(cls, v):

        if not isinstance(v, list):
            raise ValueError(f"{v} must be a list")

        for i, iv in enumerate(v):
            if isinstance(iv, dict):
                v[i] = method_manager.get_method_by_name(iv['method_name'])(**iv)
            else:
                if not (isinstance(iv, BaseMethod)):
                    raise ValueError(f"{iv} must be derived from BaseMethod")

        return v

    @property
    def run_jobs(self) -> List[str]:

        return [task.id for m in self.active for task in m.tasks]

    def add(self, method: MethodsType) -> None:
        """Adds new method"""
        self.methods.append(method)

    def activate(self, index: int) -> None:
        """Moves method to active category

        Args:
            index (int): index of method to move
        """

        self.active.append(self.methods.pop(index))

    def estimated_time(self, layout: LHBedLayout) -> float:
        """Generates estimated time of all methods in list. Does not track method completion

        Returns:
            float: total estimated time in default time units
        """

        # NOTE: Does not currently update estimated time based on completion
        return sum(m.estimated_time(layout) for m in self.methods)

    def explode(self, layout: LHBedLayout):
        """Permanently replaces the original methods with "exploded" methods, i.e. rendered methods
            based on the provided layout. Cannot be undone. Two layers of recursion to account for
            LHMethodClusters.

        Args:
            layout (LHBedLayout): layout to use to generate exploded methods
        """

        #self.prepare_run_methods(layout)
        new_methods = []
        for m in self.methods:
            print('m', type(m))
            print('m exploded', m.explode(layout))
            for im in m.explode(layout):
                print('im', type(im))
                #print(im.explode(layout))
                for iim in im.explode(layout):
                    new_methods.append(iim)
        self.methods = new_methods

    def execute(self, layout: LHBedLayout) -> List[MethodError | None]:
        """Executes all methods. Used for dry running. Returns list of
            errors, one for each method, or None if no error"""

        errors = []
        for m in self.methods:
            print(f'Executing {m}')
            errors += [m.method.execute(layout)]

        return errors
    
    def get_method_completion(self) -> bool:
        """Method completion is not currently being tracked. Returns False

        Returns:
            bool: False
        """

        return False

class Sample(BaseModel):
    """Class representing a sample to be created by Gilson LH"""
    name: str
    description: str
    id: str | None = None
    channel: int = 0
    stages: Dict[StageName, MethodList] = Field(default_factory=lambda: {StageName.PREP: MethodList(), StageName.INJECT: MethodList()})
    NICE_uuid: str | None = None
    NICE_slotID: int | None = None
    current_contents: str = ''

    def __post_init__(self) -> None:

        if self.id is None:
            self.generate_new_id()

        # back compatibility
        if not hasattr(self, 'channel'):
            setattr(self, 'channel', 0)

    def generate_new_id(self) -> None:

        self.id = str(uuid4())

    def get_created_dates(self) -> list[datetime]:
        """Returns list of MethodList.createdDates from the sample"""

        return [datetime.strptime(methodlist.createdDate, DATE_FORMAT) for methodlist in self.stages.values() if methodlist.createdDate is not None]

    def get_earliest_date(self) -> datetime | None:
        """Gets earliest createdDate in the sample"""

        datelist = self.get_created_dates()

        return None if len(datelist) < 1 else min(datelist)

    def get_status(self) -> SampleStatus:

        method_status = [methodlist.status for methodlist in self.stages.values()]

        # all are inactive
        if all(ms == SampleStatus.INACTIVE for ms in method_status):

            return SampleStatus.INACTIVE

        # any are active
        elif any(ms == SampleStatus.ACTIVE for ms in method_status):

            return SampleStatus.ACTIVE

        # any are pending
        elif any(ms == SampleStatus.PENDING for ms in method_status):

            return SampleStatus.PENDING

        # all are completed
        elif all(ms == SampleStatus.COMPLETED for ms in method_status):

            return SampleStatus.COMPLETED

        elif any(ms == SampleStatus.COMPLETED for ms in method_status) & any(ms == SampleStatus.INACTIVE for ms in method_status):

            return SampleStatus.PARTIAL

        else:

            print('Warning: undefined sample status. This should never happen!')
            return None

#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
Sample.model_rebuild()  # type: ignore
example_sample_list: List[Sample] = []

if False:
    example_method = Sleep(Time=0.1)

    for i in range(10):
        example_sample = Sample(name=f'testsample{i}', description='test sample description')
        example_sample.stages[StageName.PREP].addMethod(Sleep(Time=0.01*float(i)))
        example_sample.stages[StageName.INJECT].addMethod(Sleep(Time=0.011*float(i)))
        example_sample_list.append(example_sample)

    # throw some new statuses in the mix:
    example_sample_list[0].stages[StageName.PREP].status = SampleStatus.INACTIVE
    example_sample_list[1].stages[StageName.PREP].status = SampleStatus.COMPLETED
    example_sample_list[1].stages[StageName.INJECT].status = SampleStatus.COMPLETED
    example_sample_list[2].stages[StageName.PREP].status = SampleStatus.COMPLETED
    example_sample_list[2].stages[StageName.INJECT].status = SampleStatus.INACTIVE
    example_sample_list[5].channel = 1

    #example_sample = Sample('12', 'testsample12', 'test sample description')
    #example_sample.methods.append(example_method)
    #print(methods)

