from dataclasses import InitVar, asdict, fields, field
from pydantic.dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Literal, Optional, Union, Tuple
from .bedlayout import Well, LHBedLayout, WellLocation
from .layoutmap import LayoutWell2ZoneWell, Zone
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

    def execute(self, layout: LHBedLayout) -> None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        pass

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns new sample composition if applicable"""
        
        return ''

    def estimated_time(self) -> float:
        """Estimated time for method in default time units"""
        return 0.0

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

    def render_lh_method(self, sample_name: str, sample_description: str) -> BaseMethod.lh_method:

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Flow_Rate=f'{self.Flow_Rate}',
            Target_Zone=target_zone,
            Target_Well=target_well
        )

    def execute(self, layout: LHBedLayout) -> None:
        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        target_well, target_rack = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)
        
        # TODO: real error reporting
        assert source_well.volume > self.Volume, f"{source_well.well_number} in {source_well.rack_id} rack contains {source_well.volume} but needs {self.Volume}"
        source_well.volume -= self.Volume

        assert (target_well.volume + self.Volume) < target_rack.max_volume, f"{source_well.well_number} in {source_well.rack_id} rack contains {source_well.volume} but needs {self.Volume}"

        # Perform mix. Note that target_well volume is also changed by this operation
        target_well.mix_with(self.Volume, source_well.composition)

    def estimated_time(self) -> float:
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

    def render_lh_method(self, sample_name: str, sample_description: str) -> BaseMethod.lh_method:

        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Volume=f'{self.Volume}',
            Flow_Rate=f'{self.Flow_Rate}',
            Number_of_Mixes=f'{self.Number_of_Mixes}',
            Target_Zone=target_zone,
            Target_Well=target_well
        )

    def estimated_time(self) -> float:
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

    def render_lh_method(self, sample_name: str, sample_description: str) -> BaseMethod.lh_method:

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        return self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Flow_Rate=f'{self.Flow_Rate}'
        )

    def execute(self, layout: LHBedLayout) -> None:
        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        source_well.volume -= self.Volume

    def estimated_time(self) -> float:
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

    def render_lh_method(self, sample_name: str, sample_description: str) -> BaseMethod.lh_method:

        return self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Time=f'{self.Time}'
        )

    def estimated_time(self) -> float:
        return float(self.Time)

# get "methods" specification of fields
method_list = [TransferWithRinse, MixWithRinse, InjectWithRinse, Sleep]
MethodsType = Union[TransferWithRinse, MixWithRinse, InjectWithRinse, Sleep]
lh_methods = {v.method_name: v for v in method_list}
lh_method_fields = {}
for method in method_list:
    fieldlist = []
    for fi in fields(method):
        if (fi.name != 'method_name') & (fi.name != 'display_name'):
            fieldlist.append(fi.name)
    lh_method_fields[method.method_name] = {'fields': fieldlist, 'display_name': method.display_name, 'schema': method.__pydantic_model__.schema()}

# =============== Sample list handling =================

class SampleStatus(str, Enum):
    INACTIVE = 'inactive'
    PENDING = 'pending'
    ACTIVE = 'active'
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

class StageName(str, Enum):
    PREP = 'prep'
    INJECT = 'inject'

@dataclass
class MethodList:
    """Class representing a list of methods representing one LH job. Allows dividing
        prep and inject operations for a single sample."""
    LH_id: int | None = None
    createdDate: str | None = None
    methods: List[MethodsType] = field(default_factory=list)
    methods_complete: List[bool] = field(default_factory=list)
    status: SampleStatus = SampleStatus.INACTIVE

    def __post_init__(self):

        for i, method in enumerate(self.methods):
            if isinstance(method, dict):
                self.methods[i] = lh_methods[method['method_name']](**method)

    def addMethod(self, method: MethodsType) -> None:
        """Adds new method and flag for completion"""
        self.methods.append(method)
        self.methods_complete.append(False)

@dataclass
class Sample:
    """Class representing a sample to be created by Gilson LH"""
    id: str
    name: str
    description: str
    stages: Dict[StageName, MethodList] = field(default_factory=lambda: {StageName.PREP: MethodList(), StageName.INJECT: MethodList()})
    NICE_uuid: str | None = None
    NICE_slotID: int | None = None
    current_contents: str = ''

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

        else:

            print('Warning: undefined sample status. This should never happen!')
            return None

    def toSampleList(self, stage_name: StageName, entry=False) -> dict:
        """Generates dictionary for LH sample list
        
            methodlist: MethodList containing methods to be included

            entry: if a list of sample lists entry, SampleList columns field is null; otherwise,
                    if a full sample list, expose all methods 

            Note:
            1. Before calling this, MethodList.LH_id and Methodlist.createdDate must be set.
        """

        assert stage_name in self.stages, "Must use stage from calling sample!"

        stage = self.stages[stage_name]
        expose_methods = None if entry else [
            m.render_lh_method(self.name, self.description) for m in stage.methods]
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

@dataclass
class SampleContainer:
    """Specialized sample dictionary allowing convenient referencing by sample ID or sample name"""

    samples: list[Sample] = field(default_factory=list)

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

def moveSample(container1: SampleContainer, container2: SampleContainer, key: str, value) -> None:
    """Utility for moving a sample from one SampleContainer to another
        Deprecated in favor of Sample.status enum"""

    sample = container1.getSample(key, value)
    container2.addSample(sample)
    container1.deleteSample(sample)

#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
Sample.__pydantic_model__.update_forward_refs()  # type: ignore
example_method = Sleep(Time=0.1)
example_sample_list: List[Sample] = []
for i in range(10):
    example_sample = Sample(id=str(i), name=f'testsample{i}', description='test sample description')
    example_sample.stages[StageName.PREP].addMethod(example_method)
    example_sample.stages[StageName.INJECT].addMethod(example_method)
    example_sample_list.append(example_sample)

# throw some new statuses in the mix:
example_sample_list[0].stages[StageName.PREP].status = SampleStatus.ACTIVE
example_sample_list[0].stages[StageName.PREP].methods_complete[0] = False
example_sample_list[1].stages[StageName.PREP].status = SampleStatus.COMPLETED
example_sample_list[1].stages[StageName.INJECT].status = SampleStatus.COMPLETED
example_sample_list[1].stages[StageName.PREP].methods_complete = [True for m in example_sample_list[1].stages[StageName.PREP].methods_complete]
example_sample_list[1].stages[StageName.INJECT].methods_complete = [True for m in example_sample_list[1].stages[StageName.INJECT].methods_complete]
example_sample_list[2].stages[StageName.PREP].status = SampleStatus.COMPLETED
example_sample_list[2].stages[StageName.INJECT].status = SampleStatus.INACTIVE
example_sample_list[2].stages[StageName.PREP].methods_complete = [True for m in example_sample_list[2].stages[StageName.PREP].methods_complete]
#example_sample = Sample('12', 'testsample12', 'test sample description')
#example_sample.methods.append(example_method)
#print(methods)

