from .bedlayout import LHBedLayout
from .error import MethodError
from .methods import BaseMethod, MethodType, register
from .devices import DeviceBase, device_manager
from .job import JobBase

from pydantic import BaseModel

from dataclasses import field
from typing import List, Literal, ClassVar
from enum import Enum
from datetime import datetime

class InjectionSystemDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: ClassVar[str] = 'Multichannel Injection System'
    device_type: str = 'injection'
    multichannel: bool = True
    allow_sample_mixing: bool = True
    address: str = 'http://localhost:5003'

    class Job(JobBase):
        pass

device_manager.register(InjectionSystemDevice())

class BaseInjectionSystemMethod(BaseMethod):
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

            d2 = {InjectionSystemDevice.device_name: [self.model_dump()]}

            return d2

@register
class RoadmapChannelInit(BaseInjectionSystemMethod):
    """Initialize QCMD instrument"""
    display_name: Literal['Init Injection System'] = 'Init Injection System'
    method_name: Literal['RoadmapChannelInit'] = 'RoadmapChannelInit'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [
            self.sub_method(
                method_name='RoadmapChannelInit'
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return 0.0


@register
class RoadmapChannelSleep(BaseInjectionSystemMethod):
    """Initialize QCMD instrument"""
    display_name: Literal['Sleep Injection System'] = 'Sleep Injection System'
    method_name: Literal['RoadmapChannelSleep'] = 'RoadmapChannelSleep'
    sleep_time: float = 1.0

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [
            self.sub_method(
                method_name='RoadmapChannelSleep',
                method_data={'sleep_time': self.sleep_time}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return self.sleep_time

@register
class PrimeLoop(BaseInjectionSystemMethod):
    """Prime a loop"""
    number_of_primes: int = 3
    display_name: Literal['Prime Injection System Loop'] = 'Prime Injection System Loop'
    method_name: Literal['PrimeLoop'] = 'PrimeLoop'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        return [
            self.sub_method(
                method_name='PrimeLoop',
                method_data={'number_of_primes': self.number_of_primes}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        # flow rates are not defined, so can't really do this. Need to know loop volume and aspirate and dispense flow rates
        return 0.0
    
@register
class InjectLoop(BaseInjectionSystemMethod):
    """Inject contents of injection system loop"""
    Volume: float = 0
    Flow_Rate: float = 1
    display_name: Literal['Inject Injection System Loop'] = 'Inject Injection System Loop'
    method_name: Literal['InjectLoop'] = 'InjectLoop'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseInjectionSystemMethod.sub_method]:
        
        return [
            self.sub_method(
                method_name='InjectLoop',
                method_data={'pump_volume': self.Volume * 1000,
                             'pump_flow_rate': self.Flow_Rate}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Flow_Rate

