from dataclasses import dataclass, asdict, fields
from enum import EnumMeta, EnumMeta
import datetime

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

## ========== Methods specification =============
# methods must also be added to lh_methods list to be used

class Zone(EnumMeta):
    SOLVENT = 'Solvent Zone'
    SAMPLE = 'Sample Zone'
    STOCK = 'Stock Zone'
    MIX = 'Mix Zone'
    INJECT = 'Injection Zone'

class SampleStatus(EnumMeta):
    PENDING = 'pending'
    ACTIVE = 'active'
    COMPLETED = 'completed'

@dataclass
class TransferWithRinse:
    """Transfer with rinse"""
    SAMPLENAME: str
    SAMPLEDESCRIPTION: str
    Source_Zone: Zone
    Source_Well: str
    Volume: str
    Flow_Rate: str
    Target_Zone: Zone
    Target_Well: str
    METHODNAME: str = 'NCNR_TransferWithRinse'

@dataclass
class MixWithRinse:
    """Inject with rinse"""
    SAMPLENAME: str
    SAMPLEDESCRIPTION: str
    Target_Zone: Zone
    Target_Well: str
    Volume: str
    Flow_Rate: str
    Number_of_Mixes: str
    METHODNAME: str = 'NCNR_MixWithRinse'

@dataclass
class InjectWithRinse:
    """Inject with rinse"""
    SAMPLENAME: str
    SAMPLEDESCRIPTION: str
    Source_Zone: Zone
    Source_Well: str
    Volume: str
    Aspirate_Flow_Rate: str
    Flow_Rate: str
    METHODNAME: str = 'NCNR_InjectWithRinse'

@dataclass
class Sleep:
    """Sleep"""
    SAMPLENAME: str
    SAMPLEDESCRIPTION: str
    Time: str
    METHODNAME: str = 'NCNR_Sleep'

# get "methods" specification of fields
lh_methods = [TransferWithRinse, MixWithRinse, InjectWithRinse, Sleep]
methods = {}
for method in lh_methods:
    fieldlist = []
    for fi in fields(method):
        if fi.name != 'METHODNAME':
            fieldlist.append(fi.name)
        else:
            key = fi.default
    methods[key] = fieldlist    

# =============== Sample list handling =================
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

class Sample:
    """Class representing a sample to be created by Gilson LH"""

    def __init__(self, id: int, name: str, description: str, methods: list = []) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.methods = methods
        self.createdDate = None
        self.status = SampleStatus.PENDING

    def toSampleList(self, entry=False) -> dict:
        """Generates dictionary for LH sample list
        
            entry: if a list of sample lists entry, SampleList columns field is null; otherwise,
                    if a full sample list, expose all methods 
        """

        current_time = datetime.datetime.now().strftime(DATE_FORMAT)
        self.createdDate = current_time if self.createdDate is None else self.createdDate
        expose_methods = None if entry else self.methods
        return asdict(SampleList(self.name, f'{self.id}', 'System', self.description, self.createdDate, current_time, current_time, expose_methods))

class SampleContainer:
    """Specialized sample dictionary allowing convenient referencing by sample ID or sample name"""

    def __init__(self) -> None:
        # lists of sample IDs and sample names (can be expanded to other values as well)
        self.index = {'id': [], 'name': []}

        # list of sample objects
        self.samples: list[Sample] = []

    def getSample(self, key: str, value: str, status: SampleStatus = None) -> Sample:
        # TODO: add error handler
        assert key in self.index.keys(), "Wrong index reference!"
        try:
            sample = self.samples[self.index[key].index(value)]
            return sample if (sample.status == status) | (status is None) else None
        except ValueError:
            # if sample not found
            print('Warning: ValueError raised; sample not found')
            return None

    def addSample(self, sample: Sample) -> None:
        """Special appender that also updates index object"""
        self.samples.append(sample)
        for key in self.index.keys():
            self.index[key].append(getattr(sample, key))

    def deleteSample(self, sample: Sample) -> None:
        """Special remover that also updates index object
            
            Can use, e.g. deleteSample(getSample('id', 1))"""
        idx = self.samples.index(sample)
        self.samples.pop(idx)
        for key in self.index.keys():
            self.index[key].pop(idx)

    def getMaxIndex(self, key: str) -> int:
        """ Returns maximum index value for desired index"""

        return max([int(idx) for idx in self.index[key]])

def moveSample(container1: SampleContainer, container2: SampleContainer, key: str, value) -> None:
    """Utility for moving a sample from one SampleContainer to another
        Deprecated in favor of Sample.status enum"""

    sample = container1.getSample(key, value)
    container2.addSample(sample)
    container1.deleteSample(sample)


#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
example_method = Sleep('Test_sample', 'Description of a test sample', '0.1')
example_sample = Sample('12', 'testsample12', 'test sample description')
example_sample.methods.append(example_method)
#print(methods)

