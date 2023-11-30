from dataclasses import asdict, field
from pydantic.v1.dataclasses import dataclass
from enum import Enum
from uuid import uuid4
from typing import Dict, List, Union
from .bedlayout import LHBedLayout
from .items import StageName, MethodError
from .methods import MethodsType, BaseMethod, method_manager, Sleep
from datetime import datetime

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

# =============== Sample list handling =================

class SampleStatus(str, Enum):
    INACTIVE = 'inactive'
    PENDING = 'pending'
    ACTIVE = 'active'
    PARTIAL = 'partially complete'
    COMPLETED = 'completed'

@dataclass
class SampleList:
    """Class representing a sample list in JSON
        serializable format for Gilson Trilution LH Web Service """
    name: str
    id: str
    createdBy: str
    description: str
    createDate: str
    startDate: str
    endDate: str
    columns: list[BaseMethod.lh_method] | None

@dataclass
class MethodList:
    """Class representing a list of methods representing one LH job. Can be nested
        in a single stage"""
    LH_id: int | None = None
    createdDate: str | None = None
    methods: List[MethodsType] = field(default_factory=list)
    run_methods: List[MethodsType] | None = None
    run_methods_complete: List[bool] | None = None
    status: SampleStatus = SampleStatus.INACTIVE

    def __post_init__(self):

        for i, method in enumerate(self.methods):
            if isinstance(method, dict):
                self.methods[i] = method_manager.get_method_by_name(method['method_name'])(**method)

    def addMethod(self, method: MethodsType) -> None:
        """Adds new method"""
        self.methods.append(method)

    def estimated_time(self, layout: LHBedLayout) -> float:
        """Generates estimated time of all methods in list. If list has been prepared for run,
            use estimated time only from those methods that have not completed

        Returns:
            float: total estimated time in default time units
        """

        if self.run_methods is None:
            return sum(m.estimated_time(layout) for m in self.methods)
        else:
            return sum(m.estimated_time(layout) if not complete else 0.0 for m, complete in zip(self.run_methods, self.run_methods_complete))

    def prepare_run_methods(self, layout: LHBedLayout):
        """Prepares the method list for running by populating run_methods and run_methods_complete.
            List can then be used for dry or wet runs
        """

        # Generate real-time LH methods based on layout
        self.run_methods = []
        for m in self.methods:
            self.run_methods += m.get_methods(layout)

        # Generate one entry for each method.
        self.run_methods_complete = [False for _ in self.run_methods]

    def explode(self, layout: LHBedLayout):
        """Permanently replaces the original methods with "exploded" methods, i.e. rendered methods
            based on the provided layout. Cannot be undone.

        Args:
            layout (LHBedLayout): layout to use to generate exploded methods
        """

        self.prepare_run_methods(layout)
        self.methods = self.run_methods

    def execute(self, layout: LHBedLayout) -> List[MethodError | None]:
        """Executes all methods. Used for dry running. Returns list of
            errors, one for each method, or None if no error"""

        errors = []
        for m in self.methods:
            print(f'Executing {m}')
            errors += [m.execute(layout)]

        return errors

    def undo_prepare(self):
        """Undoes the prepare steps"""

        self.run_methods = None
        self.run_methods_complete = None
    
    def get_method_completion(self) -> bool:
        """Returns list of method completion status. If prepare_run_methods has not been
            run (i.e. run_methods is None), returns False

        Returns:
            bool: Method completion status, one for each method in methods
        """

        if self.run_methods_complete is not None:
            return all(self.run_methods_complete)
        
        return False

@dataclass
class Sample:
    """Class representing a sample to be created by Gilson LH"""
    name: str
    description: str
    id: str | None = None
    stages: Dict[StageName, MethodList] = field(default_factory=lambda: {StageName.PREP: MethodList(), StageName.INJECT: MethodList()})
    NICE_uuid: str | None = None
    NICE_slotID: int | None = None
    current_contents: str = ''

    def __post_init__(self) -> None:

        if self.id is None:
            self.id = str(uuid4())

    def get_LH_ids(self) -> list[int | None]:

        return [methodlist.LH_id for methodlist in self.stages.values()]

    def getMethodListbyID(self, id: int) -> Union[MethodList, None]:

        return next((methodlist for methodlist in self.stages.values() if methodlist.LH_id == id), None)

    def getStageByID(self, id: int) -> StageName | None:
        return next((stage_name for (stage_name, methodlist) in self.stages.items() if methodlist.LH_id == id), None)

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

    def toSampleList(self, stage_name: StageName, layout: LHBedLayout, entry=False) -> dict:
        """Generates dictionary for LH sample list
        
            stage_name (StageName): Name of stage containing methods to be included
            layout (LHBedLayout): Name of bed layout to use for validation
            entry: if a list of sample lists entry, SampleList columns field is null; otherwise,
                    if a full sample list, expose all methods 

            Note:
            1. Before calling this, MethodList.LH_id and Methodlist.createdDate must be set.
        """

        assert stage_name in self.stages, "Must use stage from calling sample!"

        stage = self.stages[stage_name]
        if entry:
            expose_methods = None
        else:
            stage.prepare_run_methods(layout)
            expose_methods: List[BaseMethod.lh_method] = []
            for m in stage.run_methods:
                expose_methods += [m2.to_dict()
                                   for m2 in m.render_lh_method(sample_name=self.name,
                                              sample_description=self.description,
                                              layout=layout)]
        
        d = asdict(SampleList(
            name=self.name,
            id=f'{stage.LH_id}',
            createdBy='System',
            description=self.description,
            createDate=str(stage.createdDate),
            startDate=str(stage.createdDate),
            endDate=str(stage.createdDate),
            columns=None
        ))
        
        # This is necessary so field names with hashes do not get stripped.
        d.update(columns=expose_methods)

        return d

#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
Sample.__pydantic_model__.update_forward_refs()  # type: ignore
example_method = Sleep(Time=0.1)
example_sample_list: List[Sample] = []
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
#example_sample = Sample('12', 'testsample12', 'test sample description')
#example_sample.methods.append(example_method)
#print(methods)

