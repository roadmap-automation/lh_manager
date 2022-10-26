from dataclasses import dataclass, field, asdict, InitVar, fields
from enum import EnumMeta
import datetime

methods = {}

def liquid_handler_method(func):
    """Decorator function to add methods dataclasses to methodlist global"""
    def wrapper(*args, **kwargs):
        fi = func(*args, **kwargs)
        methods[fi.METHODNAME] = [f.name for f in fields(fi)]
        return fi
    return wrapper

## ========== Methods specification =============

class Zone(EnumMeta):
    SOLVENT = 'Solvent Zone'
    SAMPLE = 'Sample Zone'
    STOCK = 'Stock Zone'
    MIX = 'Mix Zone'
    INJECT = 'Injection Zone'

@liquid_handler_method
@dataclass
class TransferWithRinse:
    """Transfer with rinse"""
    SAMPLENAME: str
    SAMPLEDESCRIPTION: str
    Source_Zone: Zone
    Source_Well: str
    Transfer_Volume: str
    Flow_Rate: str
    Target_Zone: Zone
    Target_Well: str
    METHODNAME: str = 'NCNR_TransferWithRinse'

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
current_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
current_time_short = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
example_sample_list = SampleList('test sample list', '1', 'description of test sample list', current_time, current_time_short, current_time_short, [example_method])
#print(example_sample_list)
#print(asdict(example_sample_list))
print(methods)
#print(example_method)
