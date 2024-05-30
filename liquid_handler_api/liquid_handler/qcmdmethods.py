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
    device_type: str = 'qcmd'
    multichannel: bool = True
    address: str = 'http://localhost:5011'

    @dataclass
    class Job(LHJob):
        pass

    @staticmethod
    def create_job_data(method_list: List[dict]) -> dict:
        """Makes an LHJob from a list of methods"""

        return {'method_list': method_list}

@dataclass
class BaseQCMDMethod(BaseMethod):
    """Base class for LH methods"""

    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    @dataclass
    class sub_method:
        """Base class for representation in sample lists"""
        method_name: str
        method_data: dict = field(default_factory=dict)

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

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data={}).to_dict()]

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

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data=dict(sleep_time=self.sleep_time)
                                ).to_dict()]

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

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data=dict(record_time=self.record_time,
                                                 sleep_time=self.sleep_time)
                                ).to_dict()]
    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return self.sleep_time + self.record_time
