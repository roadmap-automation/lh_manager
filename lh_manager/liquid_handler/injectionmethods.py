from .bedlayout import LHBedLayout, Composition
from .methods import BaseMethod, MethodType, register
from .devices import DeviceBase, device_manager
from .job import JobBase
from .rinsemethods import BaseRinseMethod
from .distributionmethods import BaseDistributionMethod

from pydantic import BaseModel, Field

from dataclasses import field
from typing import List, Literal, ClassVar
from enum import Enum
from datetime import datetime

class InjectionSystemDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: Literal['Multichannel Injection System'] = 'Multichannel Injection System'
    device_type: Literal['injection'] = 'injection'
    multichannel: bool = True
    allow_sample_mixing: bool = True
    address: str = 'http://localhost:5003'

    class Job(JobBase):
        pass

injectionsystem = InjectionSystemDevice()
device_manager.register(injectionsystem)

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

            d2 = {injectionsystem.device_name: [self.model_dump()]}

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
    method_type: Literal[MethodType.INJECT] = MethodType.INJECT

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

# =========== Rinse system methods ============

@register
class RinseLoadLoop(BaseInjectionSystemMethod):
    """Load injection system loop via rinse system"""
    Rinse_Composition: Composition = Field(default_factory=Composition)
    Aspirate_Flow_Rate: float = 1 # mL/min
    Flow_Rate: float = 1 # mL/min
    Volume: float = 1 # ml
    Extra_Volume: float = 0.1 #mL
    Air_Gap: float = 0.1 #ml
    Rinse_Volume: float = 0.5 # ml
    display_name: Literal['Load Injection Loop from Rinse'] = 'Load Injection Loop from Rinse'
    method_name: Literal['RinseLoadLoop'] = 'RinseLoadLoop'
    method_type: Literal[MethodType.INJECT] = MethodType.INJECT

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseInjectionSystemMethod.sub_method]:
        
        # Order matters
        return [
            BaseRinseMethod.sub_method(method_name='InitiateRinse',
                                           method_data={}).to_dict() |
            BaseDistributionMethod.sub_method(method_name='InitiateDistribution',
                                           method_data={}).to_dict() |                                           
            self.sub_method(
                method_name='RinseLoadLoop',
                method_data={'composition': self.Rinse_Composition,
                             'aspirate_flow_rate': self.Aspirate_Flow_Rate,
                             'excess_volume': self.Extra_Volume,
                             'air_gap': self.Air_Gap,
                             'rinse_volume': self.Rinse_Volume,
                             'pump_volume': self.Volume,
                             'flow_rate': self.Flow_Rate}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        total_volume = self.Extra_Volume + self.Volume + 2 * self.Air_Gap
        return 60 * (total_volume / self.Aspirate_Flow_Rate + total_volume / self.Flow_Rate + self.Rinse_Volume / self.Flow_Rate)
    
@register
class RinseLoadLoopBubbleSensor(RinseLoadLoop):
    """Inject contents of injection system loop"""
    display_name: Literal['Load Injection Loop from Rinse with Bubble Sensor'] = 'Load Injection Loop from Rinse with Bubble Sensor'
    method_name: Literal['RinseLoadLoopBubbleSensor'] = 'RinseLoadLoopBubbleSensor'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseInjectionSystemMethod.sub_method]:
        # Order matters
        return [BaseRinseMethod.sub_method(method_name='InitiateRinse',
                                           method_data={}).to_dict() |
            BaseDistributionMethod.sub_method(method_name='InitiateDistribution',
                                           method_data={}).to_dict() |                                                   
            self.sub_method(method_name='RinseLoadLoopBubbleSensor',
                                method_data={'composition': self.Rinse_Composition,
                                            'aspirate_flow_rate': self.Aspirate_Flow_Rate,
                                            'excess_volume': self.Extra_Volume,
                                            'air_gap': self.Air_Gap,
                                            'rinse_volume': self.Rinse_Volume,
                                            'pump_volume': self.Volume,
                                            'flow_rate': self.Flow_Rate}
                            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        total_volume = self.Extra_Volume + self.Volume + 2 * self.Air_Gap
        return 60 * (total_volume / self.Aspirate_Flow_Rate + total_volume / self.Flow_Rate + self.Rinse_Volume / self.Flow_Rate)
    
@register
class RinseDirectInjectPrime(BaseInjectionSystemMethod, BaseRinseMethod):
    """Prime injection system loop via rinse system"""
    Volume: float = 1 # ml
    Flow_Rate: float = 1 # mL/min
    display_name: Literal['Prime Direct Injection from Rinse'] = 'Prime Direct Injection from Rinse'
    method_name: Literal['RinseDirectInjectPrime'] = 'RinseDirectInjectPrime'
    method_type: Literal[MethodType.NONE] = MethodType.NONE

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseInjectionSystemMethod.sub_method]:
        # Order matters
        return [BaseRinseMethod.sub_method(method_name='InitiateRinse',
                                           method_data={}).to_dict() |
                BaseDistributionMethod.sub_method(method_name='InitiateDistribution',
                                           method_data={}).to_dict() |                                                   
                self.sub_method(method_name='RinseDirectInjectPrime',
                                method_data={'pump_volume': self.Volume,
                                            'pump_flow_rate': self.Flow_Rate}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return 60 * self.Volume / self.Flow_Rate
