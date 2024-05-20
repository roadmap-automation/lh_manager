from .bedlayout import LHBedLayout, WellLocation
from .error import MethodError
from .layoutmap import LayoutWell2ZoneWell, Zone
from .methods import BaseMethod, MethodType, register, MethodsType
from .devices import DeviceBase, register_device
from .lhinterface import LHJob, DATE_FORMAT
from .task import TaskData

from pydantic.v1.dataclasses import dataclass

from dataclasses import field, asdict
from typing import List, Literal
from enum import Enum
from datetime import datetime

@register_device
@dataclass
class QCMDMeasurementDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: str = 'QCMD Measurement Device'

    @dataclass
    class Job(LHJob):
        pass

    @staticmethod
    def create_job_data(method_list: List[dict]) -> dict:
        """Makes an LHJob from a list of methods"""

        return {'method_data': [method_list]}

@dataclass
class BaseQCMDMethod(BaseMethod):
    """Base class for LH methods"""

    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    @dataclass
    class sub_method:
        """Base class for representation in sample lists"""

        def to_dict(self) -> dict:
            """Creates dictionary representation; all custom field keys are prepended with a hash (#)
            Returns:
                dict: dictionary representation
            """

            d2 = {QCMDMeasurementDevice.device_name: [asdict(self)]}

            return d2

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        return None

    def get_methods(self, layout: LHBedLayout):
        return [self]
    
    def explode(self, layout: LHBedLayout) -> None:
        pass
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        """Renders the lh_method class to a Gilson LH-compatible format"""
        
        return [{}]


@register
@dataclass
class QCMDInit(BaseQCMDMethod):
    """Initialize QCMD instrument"""
    display_name: Literal['QCMD Init'] = 'QCMD Init'
    method_name: Literal['QCMDInit'] = 'QCMDInit'

    @dataclass
    class sub_method(BaseQCMDMethod.sub_method):
        pass

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method().to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return 0.0

@register
@dataclass
class QCMDSleep(BaseQCMDMethod):
    """Sleep the QCMD instrument"""
    sleep_time: float = 10.0
    display_name: Literal['QCMD Sleep'] = 'QCMD Sleep'
    method_name: Literal['QCMDSleep'] = 'QCMDSleep'

    @dataclass
    class sub_method(BaseQCMDMethod.sub_method):
        sleep_time: float

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(self.sleep_time).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return self.sleep_time
    
@register
@dataclass
class QCMDRecord(BaseQCMDMethod):
    """Record QCMD measurements"""
    record_time: float = 60.0
    sleep_time: float = 0.0
    display_name: Literal['QCMD Record'] = 'QCMD Record'
    method_name: Literal['QCMDRecord'] = 'QCMDRecord'

    @dataclass
    class sub_method(BaseQCMDMethod.sub_method):
        record_time: float
        sleep_time: float

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(record_time=self.record_time,
                                sleep_time=self.sleep_time).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return self.sleep_time + self.record_time
