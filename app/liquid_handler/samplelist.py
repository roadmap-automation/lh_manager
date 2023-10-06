from dataclasses import InitVar, asdict, fields, field
from pydantic.dataclasses import dataclass
from enum import Enum
from uuid import uuid4
from typing import Dict, List, Literal, Optional, Union, Tuple
from .bedlayout import Well, LHBedLayout, WellLocation
from .layoutmap import LayoutWell2ZoneWell, Zone
from .items import LHError, Item, StageName, MethodError
from datetime import datetime

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

## ========== Methods specification =============
# methods must also be added to lh_methods list to be used

@dataclass
class BaseMethod:
    """Base class for LH methods"""

    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    @dataclass
    class lh_method:
        """Base class for representation in Trilution LH sample lists"""
        SAMPLENAME: str
        SAMPLEDESCRIPTION: str
        METHODNAME: str

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        return None
    
    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns new sample composition if applicable"""
        
        return ''

    def estimated_time(self, layout: LHBedLayout) -> float:
        """Estimated time for method in default time units"""
        return 0.0
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[lh_method]:
        """Renders the lh_method class to a Gilson LH-compatible format"""
        
        return []
    
@dataclass
class InjectMethod(BaseMethod):
    """Special class for methods that change the sample composition"""

    Source: WellLocation = field(default_factory=WellLocation)

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        return repr(source_well.composition)

@dataclass
class TransferWithRinse(BaseMethod):
    """Transfer with rinse"""

    Source: WellLocation = field(default_factory=WellLocation)
    Target: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0
    Flow_Rate: float = 2.5
    display_name: Literal['Transfer With Rinse'] = 'Transfer With Rinse'
    method_name: Literal['NCNR_TransferWithRinse'] = 'NCNR_TransferWithRinse'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Flow_Rate: str
        Target_Zone: Zone
        Target_Well: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Flow_Rate=f'{self.Flow_Rate}',
            Target_Zone=target_zone,
            Target_Well=target_well
        )]

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        target_well, target_rack = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.Volume > source_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Well {source_well.well_number} in {source_well.rack_id} \
                                      rack contains {source_well.volume} but needs {self.Volume}")

        source_well.volume -= self.Volume

        if (target_well.volume + self.Volume) > target_rack.max_volume:
            return MethodError(name=self.display_name,
                                      error=f"Total volume {target_well.volume + self.Volume} from existing volume {target_well.volume} and transfer volume {self.Volume} exceeds rack maximum volume {target_rack.max_volume}"
                                      )

        # Perform mix. Note that target_well volume is also changed by this operation
        target_well.mix_with(self.Volume, source_well.composition)

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Flow_Rate

@dataclass
class MixWithRinse(BaseMethod):
    """Inject with rinse"""
    Target: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0
    Flow_Rate: float = 2.5
    Number_of_Mixes: int = 3
    display_name: Literal['Mix With Rinse'] = 'Mix With Rinse'
    method_name: Literal['NCNR_MixWithRinse'] = 'NCNR_MixWithRinse'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Volume: str
        Flow_Rate: str
        Number_of_Mixes: str
        Target_Zone: Zone
        Target_Well: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Volume=f'{self.Volume}',
            Flow_Rate=f'{self.Flow_Rate}',
            Number_of_Mixes=f'{self.Number_of_Mixes}',
            Target_Zone=target_zone,
            Target_Well=target_well
        )]
    
    def execute(self, layout: LHBedLayout) -> MethodError | None:

        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.Volume > target_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Mix with volume {self.Volume} requested but well {target_well.well_number} in {target_well.rack_id} rack contains only {target_well.volume}"
                                      )

    def estimated_time(self, layout: LHBedLayout) -> float:
        return 2 * self.Number_of_Mixes * self.Volume / self.Flow_Rate

@dataclass
class InjectWithRinse(InjectMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    Volume: float = 1.0
    Aspirate_Flow_Rate: float = 2.5
    Flow_Rate: float = 2.5
    display_name: Literal['Inject With Rinse'] = 'Inject With Rinse'
    method_name: Literal['NCNR_InjectWithRinse'] = 'NCNR_InjectWithRinse'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Flow_Rate: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Flow_Rate=f'{self.Flow_Rate}'
        )]

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        
        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)

        if self.Volume > source_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Injection of volume {self.Volume} requested but well {source_well.well_number} in {source_well.rack_id} rack contains only {source_well.volume}"
                                      )
            
        source_well.volume -= self.Volume

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate

@dataclass
class Sleep(BaseMethod):
    """Sleep"""
    Time: float = 1.0
    display_name: Literal['Sleep'] = 'Sleep'
    method_name: Literal['NCNR_Sleep'] = 'NCNR_Sleep'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Time: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Time=f'{self.Time}'
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return float(self.Time)

@dataclass
class MethodContainer(BaseMethod):
    """Special method that generates a list of basic methods when rendered"""

    display_name: str = 'MethodContainer'

    def get_methods(self, layout: LHBedLayout) -> List[BaseMethod]:
        """Generates list of methods. Intended to be superceded for specific applications

        Args:
            layout (LHBedLayout): layout to use for generating method list

        Returns:
            List[BaseMethod]: list of base methods
        """

        return []

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Returns the error if any of the submethods give errors"""
        for m in self.get_methods(layout):
            error = m.execute(layout)
            if error is not None:
                return MethodError(f'{self.display_name}.{error.name}', error.error)

    def estimated_time(self, layout: LHBedLayout) -> float:
        return sum(m.estimated_time() for m in self.get_methods(layout))
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        rendered_methods = []
        for m in self.get_methods(layout):
            rendered_methods += m.render_lh_method(sample_name=sample_name,
                                                   sample_description=sample_description,
                                                   layout=layout)
        return rendered_methods


# get "methods" specification of fields
method_list = [TransferWithRinse, MixWithRinse, InjectWithRinse, Sleep]
MethodsType = Union[TransferWithRinse, MixWithRinse, InjectWithRinse, Sleep, MethodContainer]
EXCLUDE_FIELDS = set(["method_name", "display_name", "complete"])
lh_methods = {v.method_name: v for v in method_list}
lh_method_fields = {}
for method in method_list:
    fieldlist = []
    for fi in fields(method):
        if not fi.name in EXCLUDE_FIELDS:
            fieldlist.append(fi.name)
    lh_method_fields[method.method_name] = {'fields': fieldlist, 'display_name': method.display_name, 'schema': method.__pydantic_model__.schema()}

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
                self.methods[i] = lh_methods[method['method_name']](**method)

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

    def prepare_for_run(self, sample_name: str, sample_description: str, layout: LHBedLayout):
        """Prepares the method list for running by populating run_methods and run_methods_complete.
            List can then be used for dry or wet runs
        """

        # Generate real-time LH methods based on layout
        self.run_methods = []
        for m in self.methods:
            self.run_methods += m.render_lh_method(sample_name=sample_name,
                                              sample_description=sample_description,
                                              layout=layout)

        # Generate one entry for each method.
        self.run_methods_complete = [False for _ in self.run_methods]

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
    
    def get_method_completion(self) -> List[bool]:
        """Returns list of method completion status

        Returns:
            List[bool]: List of method completion status, one for each method in methods
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
            stage.prepare_for_run(self.name, self.description, layout)
            expose_methods = stage.run_methods

        return asdict(SampleList(
            name=self.name,
            id=f'{stage.LH_id}',
            createdBy='System',
            description=self.description,
            createDate=str(stage.createdDate),
            startDate=str(stage.createdDate),
            endDate=str(stage.createdDate),
            columns=expose_methods
        ))

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

