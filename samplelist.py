from dataclasses import dataclass, field, asdict
import datetime

methodlist = []

def liquid_handler_method(func):
    """Decorator function to add methods dataclasses to methodlist global"""
    def wrapper():
        methodlist.append(func)
    return wrapper

## ========== Methods specification =============

method_fields = dict({
    'NCNR_TransferWithRinse': ['Source_Zone', 'Source_Well', 'Source_Volume', 'Flow_Rate', 'Target_Zone', 'Target_Well']
})

example_method = dict({
    'METHODNAME': 'NCNR_TransferWithRinse',
    'SAMPLENAME': 'Test sample',
    'SAMPLEDESCRIPTION': 'Description of a test sample',
    'Source_Zone': 'Solvent Zone',
    'Source_Well': '1',
    'Transfer_Volume': '1000',
    'Flow_Rate': '2',
    'Target_Zone': 'Mix Zone',
    'Target_Well': '1'
})

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

current_time = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
current_time_short = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
example_sample_list = SampleList('test sample list', '1', 'description of test sample list', current_time, current_time_short, current_time_short, [example_method])
#print(example_sample_list)
#print(asdict(example_sample_list))
