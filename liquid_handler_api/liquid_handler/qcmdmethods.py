from .bedlayout import LHBedLayout
from .error import MethodError
from .methods import BaseMethod, MethodType, register
from .devices import DeviceBase, device_manager
from .job import JobBase

from dataclasses import field
from pydantic import BaseModel
from typing import List, Literal, ClassVar

class QCMDMeasurementDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: ClassVar[str] = 'QCMD Measurement Device'
    device_type: str = 'qcmd'
    multichannel: bool = True
    allow_sample_mixing: bool = False
    address: str = 'http://localhost:5005'

    class Job(JobBase):
        pass

device_manager.register(QCMDMeasurementDevice())

class BaseQCMDMethod(BaseMethod):
    """Base class for LH methods"""

    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    class sub_method(BaseModel):
        """Base class for representation in sample lists"""
        method_name: str
        method_data: dict = field(default_factory=dict)

        def to_dict(self) -> dict:
            """Creates dictionary representation; all custom field keys are prepended with a hash (#)
            Returns:
                dict: dictionary representation
            """

            d2 = {QCMDMeasurementDevice.device_name: [self.model_dump()]}

            return d2

@register
class QCMDInit(BaseQCMDMethod):
    """Initialize QCMD instrument"""
    display_name: Literal['QCMD Init'] = 'QCMD Init'
    method_name: Literal['QCMDInit'] = 'QCMDInit'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data={}).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return 0.0

@register
class QCMDSleep(BaseQCMDMethod):
    """Sleep the QCMD instrument"""
    sleep_time: float = 10.0
    display_name: Literal['QCMD Sleep'] = 'QCMD Sleep'
    method_name: Literal['QCMDSleep'] = 'QCMDSleep'

    def render_method(self,
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
class QCMDAcceptTransfer(BaseQCMDMethod):
    """Register a solution in the QCMD instrument"""
    contents: str = ''
    display_name: Literal['QCMD Accept Transfer'] = 'QCMD Accept Transfer'
    method_name: Literal['QCMDAcceptTransfer'] = 'QCMDAcceptTransfer'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data=dict(contents=self.contents)
                                ).to_dict()]

@register
class QCMDRecord(BaseQCMDMethod):
    """Record QCMD measurements"""
    record_time: float = 60.0
    sleep_time: float = 0.0
    method_type: Literal[MethodType.MEASURE] = MethodType.MEASURE
    display_name: Literal['QCMD Record'] = 'QCMD Record'
    method_name: Literal['QCMDRecord'] = 'QCMDRecord'

    def render_method(self,
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

@register
class QCMDRecordTag(QCMDRecord):
    """Record QCMD measurements"""
    tag_name: str = ''
    method_type: Literal[MethodType.MEASURE] = MethodType.MEASURE    
    display_name: Literal['QCMD Record Tag'] = 'QCMD Record Tag'
    method_name: Literal['QCMDRecordTag'] = 'QCMDRecordTag'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data=dict(tag_name=self.tag_name,
                                                 record_time=self.record_time,
                                                 sleep_time=self.sleep_time)
                                ).to_dict()]
    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return self.sleep_time + self.record_time

@register
class QCMDStop(BaseQCMDMethod):
    """Stops QCMD recording"""

    display_name: Literal['QCMD Stop'] = 'QCMD Stop'
    method_name: Literal['QCMDStop'] = 'QCMDStop'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [self.sub_method(method_name=self.method_name,
                                method_data=dict()
                                ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return 0.0