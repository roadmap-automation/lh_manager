from dataclasses import dataclass, field, asdict, InitVar, fields
from enum import EnumMeta
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
    """Class representing a Gilson LH sample list"""
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

    def __init__(self, id: str, name: str, description: str, methods: list = []) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.methods = methods
        self.createdDate = None

    def toSampleList(self, entry=False) -> dict:
        """Generates dictionary for LH sample list
        
            entry: if a list of sample lists entry, SampleList columns field is null; otherwise,
                    if a full sample list, expose all methods 
        """

        current_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
        self.createdDate = current_time if self.createdDate is None else self.createdDate
        expose_methods = None if entry else self.methods
        return asdict(SampleList(self.name, f'{self.id}', 'System', self.description, self.createdDate, current_time, current_time, expose_methods))

#example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
example_method = Sleep('Test sample', 'Description of a test sample', '0.1')
example_sample = Sample('12', 'test sample', 'test sample description')
example_sample.methods.append(example_method)
#print(methods)

