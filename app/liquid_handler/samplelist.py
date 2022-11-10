from dataclasses import InitVar, asdict, fields, field
from pydantic.dataclasses import dataclass
from enum import Enum
from typing import Literal, Union, Tuple
from .bedlayout import Well, LHBedLayout
from .layoutmap import LayoutWell2ZoneWell, Zone
from datetime import datetime

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

## ========== Methods specification =============
# methods must also be added to lh_methods list to be used

@dataclass
class BaseMethod:
    """Base class for LH methods"""

    sample_name: InitVar[str]
    sample_description: InitVar[str]
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    @dataclass
    class lh_method:
        """Base class for representation in Trilution LH sample lists"""
        SAMPLENAME: str
        SAMPLEDESCRIPTION: str
        METHODNAME: str

    def __post_init__(self, sample_name, sample_description):
        """Used to store sample_name and sample_description"""
        
        self.sample_name = sample_name  # type: ignore
        self.sample_description = sample_description  # type: ignore

    def execute(self, layout: LHBedLayout) -> None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        pass

    def estimated_time(self) -> float:
        """Estimated time for method in default time units"""
        return 0.0

@dataclass
class TransferWithRinse(BaseMethod):
    """Transfer with rinse"""

    Source: Well
    Target: Well
    Volume: float
    Flow_Rate: float
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

    def render_lh_method(self) -> BaseMethod.lh_method:

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return self.lh_method(self.sample_name, self.sample_description, self.method_name, source_zone, source_well, f'{self.Volume}', f'{self.Flow_Rate}', target_zone, target_well)

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
    Target: Well
    Volume: float
    Flow_Rate: float
    Number_of_Mixes: int
    display_name: Literal['Mix With Rinse'] = 'Mix With Rinse'
    method_name: Literal['NCNR_MixWithRinse'] = 'NCNR_MixWithRinse'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Volume: str
        Flow_Rate: str
        Number_of_Mixes: str
        Target_Zone: Zone
        Target_Well: str

    def render_lh_method(self) -> BaseMethod.lh_method:

        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return self.lh_method(self.sample_name, self.sample_description, self.method_name, f'{self.Volume}', f'{self.Flow_Rate}', f'{self.Number_of_Mixes}', target_zone, target_well)

    def estimated_time(self) -> float:
        return 2 * self.Number_of_Mixes * self.Volume / self.Flow_Rate

@dataclass
class InjectWithRinse(BaseMethod):
    """Inject with rinse"""
    Source: Well
    Volume: float
    Aspirate_Flow_Rate: float
    Flow_Rate: float
    display_name: Literal['Inject With Rinse'] = 'Inject With Rinse'
    method_name: Literal['NCNR_InjectWithRinse'] = 'NCNR_InjectWithRinse'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Flow_Rate: str

    def render_lh_method(self) -> BaseMethod.lh_method:

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        return self.lh_method(self.sample_name, self.sample_description, self.method_name, source_zone, source_well, f'{self.Volume}', f'{self.Aspirate_Flow_Rate}', f'{self.Flow_Rate}')

    def execute(self, layout: LHBedLayout) -> None:
        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        source_well.volume -= self.Volume

    def estimated_time(self) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate

@dataclass
class Sleep(BaseMethod):
    """Sleep"""
    Time: str
    display_name: Literal['Sleep'] = 'Sleep'
    method_name: Literal['NCNR_Sleep'] = 'NCNR_Sleep'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Time: str

    def render_lh_method(self) -> BaseMethod.lh_method:

        return self.lh_method(self.sample_name, self.sample_description, self.method_name, f'{self.Time}')

    def estimated_time(self) -> float:
        return float(self.Time)

# get "methods" specification of fields
method_list = [TransferWithRinse, MixWithRinse, InjectWithRinse, Sleep]
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

class MethodListRole(str, Enum):
    PREP = 'prep'
    INJECT = 'inject'

@dataclass
class MethodList:
    """Class representing a list of methods representing one LH job. Allows dividing
        prep and inject operations for a single sample."""
    role: MethodListRole
    LH_id: int | None = None
    createdDate: str | None = None
    methods: list = field(default_factory=list)
    methods_complete: list[bool] = field(default_factory=list)
    status: SampleStatus = SampleStatus.PENDING

    def __post_init__(self):

        for i, method in enumerate(self.methods):
            if isinstance(method, dict):
                self.methods[i] = lh_methods[method['method_name']](**method)

    def addMethod(self, method) -> None:
        """Adds new method and flag for completion"""
        self.methods.append(method)
        self.methods_complete.append(False)

@dataclass
class Sample:
    """Class representing a sample to be created by Gilson LH"""
    id: str
    name: str
    description: str
    prep_methods: MethodList
    inject_methods: MethodList
    NICE_uuid: str | None = None
    NICE_slotID: int | None = None

    def __post_init__(self):
        """Define mapping between method list roles and method lists. Designed to allow more than two method lists if necessary."""

        self.rolemap = {MethodListRole.PREP: self.prep_methods,
                        MethodListRole.INJECT : self.inject_methods}

    def get_LH_ids(self) -> list[int | None]:

        return [methodlist.LH_id for methodlist in self.rolemap.values()]

    def getMethodListbyID(self, id: int) -> MethodList:

        return [methodlist for methodlist in self.rolemap.values() if methodlist.LH_id == id]

    def get_created_dates(self) -> list[datetime]:
        """Returns list of MethodList.createdDates from the sample"""

        return [datetime.strptime(methodlist.createdDate, DATE_FORMAT) for methodlist in self.rolemap.values() if methodlist.createdDate is not None]

    def get_earliest_date(self) -> datetime | None:
        """Gets earliest createdDate in the sample"""

        datelist = self.get_created_dates()

        return None if len(datelist) < 1 else min(datelist)

    def get_status(self) -> SampleStatus:

        method_status = [methodlist.status for methodlist in self.rolemap.values()]

        # all are pending
        if all([ms == SampleStatus.PENDING for ms in method_status]):

            return SampleStatus.PENDING

        # any are active
        elif any([ms == SampleStatus.ACTIVE for ms in method_status]):

            return SampleStatus.ACTIVE

        # all are completed
        elif all([ms == SampleStatus.COMPLETED for ms in method_status]):

            return SampleStatus.COMPLETED

        else:

            print('Warning: undefined sample status. This should never happen!')
            return None

    def toSampleList(self, select: list(MethodListRole), entry=False) -> dict:
        """Generates dictionary for LH sample list
        
            select: list of roles ('prep', 'inject') to turn into LH sample lists. Typical values are ['prep'], ['inject'], or ['prep', 'inject']

            entry: if a list of sample lists entry, SampleList columns field is null; otherwise,
                    if a full sample list, expose all methods 

            Note that before calling this, MethodList.LH_id and Methodlist.createdDate must be set.
        """
        for role in select:
            methodlist = self.rolemap[role]
            expose_methods = None if entry else [m.render_lh_method() for m in methodlist.methods]
            return asdict(SampleList(self.name, f'{methodlist.LH_id}', 'System', self.description, methodlist.createdDate, methodlist.createdDate, methodlist.createdDate, expose_methods))

@dataclass
class SampleContainer:
    """Specialized sample dictionary allowing convenient referencing by sample ID or sample name"""

    samples: list[Sample] = field(default_factory=list)

    def _getIDs(self) -> list[str]:

        return [s.id for s in self.samples]

    def _getNames(self) -> list[str]:

        return [s.name for s in self.samples]

    def getSamplebyLH_ID(self, id: int) -> Tuple[Sample | None, MethodList | None]:
        """Return sample with specific id"""

        for sample in self.samples:
            if id in sample.get_LH_ids():
                return sample, sample.getMethodListbyID(id)

        return None, None
        #raise ValueError(f"Sample ID {id} not found!")

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
example_method = Sleep('Test_sample', 'Description of a test sample', '0.1')  # type: ignore
example_sample_list = []
for i in range(10):
    example_sample = Sample(i, f'testsample{i}', 'test sample description', prep_methods=MethodList(MethodListRole.PREP), inject_methods=MethodList(MethodListRole.INJECT))
    example_sample.prep_methods.addMethod(example_method)
    example_sample.inject_methods.addMethod(example_method)
    example_sample_list.append(example_sample)
#example_sample = Sample('12', 'testsample12', 'test sample description')
#example_sample.methods.append(example_method)
#print(methods)

