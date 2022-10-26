from dataclasses import dataclass, field, asdict, InitVar, fields
from enum import EnumMeta
import datetime

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

# get "methods" specification of fields
lh_methods = [TransferWithRinse, MixWithRinse, InjectWithRinse]
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
    description: str
    createDate: str
    startDate: str
    endDate: str
    columns: list[dict]
    createdBy: str = 'System'

example_method = TransferWithRinse('Test sample', 'Description of a test sample', Zone.SOLVENT, '1', '1000', '2', Zone.MIX, '1')
current_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
current_time_short = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
example_sample_list = SampleList('test sample list3', '3', 'description of test sample list3', current_time, current_time_short, current_time_short, [example_method])
#print(example_sample_list)
#print(asdict(example_sample_list))
print(methods)
#print(example_method)
