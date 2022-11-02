from dataclasses import InitVar, dataclass, asdict, fields, field
from enum import EnumMeta
from typing import Literal
from bedlayout import Well, LHBedLayout
from layoutmap import LayoutWell2ZoneWell, Zone
import datetime

from util import reinstantiate, reinstantiate_list

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
        """Used to create self.method from instantiating parent class
        
            self.method_name must be defined in parent class with the exact name of the Trilution method"""

        # self.method = self.lh_method(sample_name, sample_description, self.method_name)

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

    def __post_init__(self, sample_name: str, sample_description: str) -> None:

        self.Source = reinstantiate(self.Source, Well)
        self.Target = reinstantiate(self.Target, Well)
        self.Volume = float(self.Volume)
        self.Flow_Rate = float(self.Flow_Rate)

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        self.method = self.lh_method(sample_name, sample_description, self.method_name, source_zone, source_well, f'{self.Volume}', f'{self.Flow_Rate}', target_zone, target_well)

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

    def __post_init__(self, sample_name: str, sample_description: str) -> None:

        self.Target = reinstantiate(self.Target, Well)
        self.Volume = float(self.Volume)
        self.Flow_Rate = float(self.Flow_Rate)
        self.Number_of_Mixes = int(self.Number_of_Mixes)

        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        self.method = self.lh_method(sample_name, sample_description, self.method_name, f'{self.Volume}', f'{self.Flow_Rate}', f'{self.Number_of_Mixes}', target_zone, target_well)

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

    def __post_init__(self, sample_name: str, sample_description: str):

        self.Source = reinstantiate(self.Source, Well)
        self.Volume = float(self.Volume)
        self.Aspirate_Flow_Rate = float(self.Aspirate_Flow_Rate)
        self.Flow_Rate = float(self.Flow_Rate)

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        self.method = self.lh_method(sample_name, sample_description, self.method_name, source_zone, source_well, f'{self.Volume}', f'{self.Aspirate_Flow_Rate}', f'{self.Flow_Rate}')

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

    def __post_init__(self, sample_name: str, sample_description: str):

        self.method = self.lh_method(sample_name, sample_description, self.method_name, f'{self.Time}')

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
        else:
            key = method.method_name
    lh_method_fields[key] = {'fields': fieldlist, 'display_name': method.display_name}

# =============== Sample list handling =================

class SampleStatus(EnumMeta):
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
    columns: list[dict]

@dataclass
class Sample:
    """Class representing a sample to be created by Gilson LH"""
    id: int
    name: str
    description: str
    methods: list = field(default_factory=list)
    methods_complete: list = field(default_factory=list)
    createdDate: str | None = None
    status: SampleStatus = SampleStatus.PENDING

    def __post_init__(self):

        for i, method in enumerate(self.methods):
            if isinstance(method, dict):
                method['sample_name'] = self.name
                method['sample_description'] = self.description
                self.methods[i] = lh_methods[method['method_name']](**method)

        if len(self.methods) > len(self.methods_complete):
            self.methods_complete = [False] * len(self.methods)
            
    def addMethod(self, method) -> None:
        """Adds new method and flag for completion"""
        self.methods.append(method)
        self.methods_complete.append(False)

    def toSampleList(self, entry=False) -> dict:
        """Generates dictionary for LH sample list
        
            entry: if a list of sample lists entry, SampleList columns field is null; otherwise,
                    if a full sample list, expose all methods 
        """

        current_time = datetime.datetime.now().strftime(DATE_FORMAT)
        self.createdDate = current_time if self.createdDate is None else self.createdDate
        expose_methods = None if entry else [m.method for m in self.methods]
        return asdict(SampleList(self.name, f'{self.id}', 'System', self.description, self.createdDate, current_time, current_time, expose_methods))

@dataclass
class SampleContainer:
    """Specialized sample dictionary allowing convenient referencing by sample ID or sample name"""

    samples: list[Sample] = field(default_factory=list)

    def __post_init__(self) -> None:

        self.samples = reinstantiate_list(self.samples, Sample)

    def _getIDs(self) -> list[int]:

        return [s.id for s in self.samples]

    def _getNames(self) -> list[int]:

        return [s.name for s in self.samples]

    def getSamplebyID(self, id: int, status: SampleStatus = None) -> Sample:
        """Return sample with specific id"""
        ids = self._getIDs()
        if id in ids:
            sample = self.samples[ids.index(id)]
            return sample if (sample.status == status) | (status is None) else None
        else:
            raise ValueError(f"Sample ID {id} not found!")

    def getSamplebyName(self, name: str, status: SampleStatus = None) -> Sample:
        names = self._getNames()
        if name in names:
            sample = self.samples[names.index(name)]
            return sample if (sample.status == status) | (status is None) else None
        else:
            raise ValueError(f"Sample name {name} not found!")

    def addSample(self, sample: Sample) -> None:
        """Sample appender that checks for proper ID value"""
        if sample.id in self._getIDs():
            new_id = self.getMaxID() + 1
            print(f'Warning: id {sample.id} already taken. Changing to id {new_id}')
            sample.id = new_id
        self.samples.append(sample)
        
    def deleteSample(self, sample: Sample) -> None:
        """Special remover that also updates index object"""
        
        self.samples.pop(self.samples.index(sample))

    def getMaxID(self) -> int:
        """ Returns maximum index value for desired index"""

        return max(self._getIDs())

def moveSample(container1: SampleContainer, container2: SampleContainer, key: str, value) -> None:
    """Utility for moving a sample from one SampleContainer to another
        Deprecated in favor of Sample.status enum"""

    sample = container1.getSample(key, value)
    container2.addSample(sample)
    container1.deleteSample(sample)


#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
example_method = Sleep('Test_sample', 'Description of a test sample', '0.1')
example_sample_list = []
for i in range(10):
    example_sample = Sample(i, f'testsample{i}', 'test sample description', methods=[])
    example_sample.addMethod(example_method)
    example_sample.addMethod(example_method)
    example_sample_list.append(example_sample)
#example_sample = Sample('12', 'testsample12', 'test sample description')
#example_sample.methods.append(example_method)
#print(methods)

