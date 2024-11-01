from .bedlayout import LHBedLayout
from .error import MethodError
from .methods import BaseMethod, MethodType, register
from .devices import DeviceBase, register_device
from .job import JobBase

from pydantic.v1.dataclasses import dataclass

from dataclasses import field, asdict
from typing import List, Literal
from enum import Enum
from datetime import datetime

@register_device
@dataclass
class InjectionSystemDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: str = 'Multichannel Injection System'
    device_type: str = 'injection'
    multichannel: bool = True
    allow_sample_mixing: bool = True
    address: str = 'http://localhost:5003'

    @dataclass
    class Job(JobBase):
        pass

@dataclass
class BaseInjectionSystemMethod(BaseMethod):
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

            d2 = {InjectionSystemDevice.device_name: [asdict(self)]}

            return d2

@register
@dataclass
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
@dataclass
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
@dataclass
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
@dataclass
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

