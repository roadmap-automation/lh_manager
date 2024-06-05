from .bedlayout import LHBedLayout, WellLocation
from .error import MethodError
from .layoutmap import LayoutWell2ZoneWell, Zone
from .methods import BaseMethod, MethodType, register, MethodsType
from .devices import DeviceBase, register_device
from .job import JobBase
from .lhmethods import BaseLHMethod, InjectMethod, Sleep

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
    address: str = 'http://localhost:5003'

    @dataclass
    class Job(JobBase):
        pass

    @staticmethod
    def create_job_data(method_list: List[dict]) -> dict:
        """Makes an Job from a list of methods"""

        # only allow one method per list for now
        return {'method_list': method_list}

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
class RoadmapChannelInit(BaseInjectionSystemMethod):
    """Initialize QCMD instrument"""
    display_name: Literal['Init Injection System'] = 'Init Injection System'
    method_name: Literal['RoadmapChannelInit'] = 'RoadmapChannelInit'

    def render_lh_method(self,
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

    def render_lh_method(self,
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

    def render_lh_method(self,
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
    method_name: Literal['ROADMAP_InjectLoop'] = 'ROADMAP_InjectLoop'

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [
            self.sub_method(
                method_name='InjectLoop',
                method_data={'pump_volume': self.Volume,
                             'pump_flow_rate': self.Flow_Rate}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Flow_Rate

@register
@dataclass
class MultiInstrumentSleep(BaseInjectionSystemMethod, BaseLHMethod):
    display_name: Literal['IS + LH Sleep'] = 'IS + LH Sleep'
    method_name: Literal['IS_LH_Sleep'] = 'IS_LH_Sleep'
    Injection_System_Sleep_Time: float = 1.0
    LH_Sleep_Time: float = 1.0

    @dataclass
    class lh_method(BaseLHMethod.lh_method):
        Time: str
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME='NCNR_Sleep',
            Time=f'{self.LH_Sleep_Time}'
        ).to_dict() | 
            self.sub_method(
                method_name='RoadmapChannelSleep',
                method_data={'sleep_time': self.Injection_System_Sleep_Time}
            ).to_dict()]    


@register
@dataclass
class LoadLoop(BaseInjectionSystemMethod, InjectMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    #Volume: float defined in InjectMethod
    Aspirate_Flow_Rate: float = 2.5
    Flow_Rate: float = 2.5
    Outside_Rinse_Volume: float = 0.5
    Extra_Volume: float = 0.1
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    pump_volume: float = 0
    pump_flow_rate: float = 1
    display_name: Literal['Load Injection System Loop'] = 'Load Injection System Loop'
    method_name: Literal['ROADMAP_QCMD_LoadLoop'] = 'ROADMAP_QCMD_LoadLoop'

    @dataclass
    class lh_method(BaseLHMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Flow_Rate: str
        Outside_Rinse_Volume: str
        Extra_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
            
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Flow_Rate=f'{self.Flow_Rate}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Extra_Volume=f'{self.Extra_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
        ).to_dict() | 
            self.sub_method(
                method_name='LoadLoop',
                method_data={'pump_volume': self.Volume,
                             'excess_volume': self.Extra_Volume}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate + self.Volume / self.pump_volume
