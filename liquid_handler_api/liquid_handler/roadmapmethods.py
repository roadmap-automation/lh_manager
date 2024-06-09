from liquid_handler_api.liquid_handler.error import MethodError
from .bedlayout import LHBedLayout, Composition, WellLocation, Well, find_composition
from .layoutmap import LayoutWell2ZoneWell, Zone
from .methods import BaseMethod, register, MethodContainer, MethodsType
from .formulation import Formulation, SoluteFormulation
from .injectionmethods import InjectLoop, BaseInjectionSystemMethod
from .lhmethods import BaseLHMethod, TransferWithRinse, MixWithRinse, InjectWithRinse, InjectMethod
from .qcmdmethods import QCMDRecord, QCMDRecordTag, QCMDMeasurementDevice, BaseQCMDMethod, QCMDAcceptTransfer

import numpy as np
from copy import copy
from typing import List, Literal, Tuple
from pydantic.v1.dataclasses import dataclass

from dataclasses import field, asdict

def find_well_and_volume(composition: Composition, volume: float, wells: List[Well]) -> Tuple[Well | None, str | None]:
    """Finds the well with the target composition and the most available volume

    Args:
        composition (Composition): target composition
        volume (float): volume required
        wells (List[Well]): list of wells to search

    Returns:
        Tuple[Well | None, str | None]: selected well and error
    """

    # find all wells containing target composition
    well_candidates = find_composition(composition, wells)
    if not len(well_candidates):
        return None, f'no target wells with composition {composition} found'
    
    # check for sufficient well volume
    well_volumes = [well.volume for well in well_candidates]
    if not any(wv >= volume for wv in well_volumes):
        return None, f'no target wells with composition {composition} and required volume {volume} found'

    return well_candidates[well_volumes.index(max(well_volumes))], None
    

class TransferOrganicsWithRinse(TransferWithRinse):
    Flow_Rate: float = 2.0
    Aspirate_Flow_Rate: float = 1.0
    Use_Liquid_Level_Detection: bool = False

class MixOrganicsWithRinse(MixWithRinse):
    Flow_Rate: float = 2.0
    Aspirate_Flow_Rate: float = 1.0
    Use_Liquid_Level_Detection: bool = False

class InjectOrganicsWithRinse(InjectWithRinse):
    Aspirate_Flow_Rate: float = 1.0
    Flow_Rate: float = 2.0
    Use_Liquid_Level_Detection: bool = False

@dataclass
class MakeBilayer(MethodContainer):
    """Make a bilayer with solvent exchange"""
    Bilayer_Composition: Composition | None = None
    Bilayer_Solvent: Composition | None = None
    Lipid_Mixing_Well: WellLocation = field(default_factory=WellLocation)
    Lipid_Injection_Volume: float = 0.0
    Buffer_Composition: Composition | None = None
    Buffer_Mixing_Well: WellLocation = field(default_factory=WellLocation)
    Buffer_Injection_Volume: float = 0.0
    display_name: Literal['Make Bilayer'] = 'Make Bilayer'
    method_name: Literal['MakeBilayer'] = 'MakeBilayer'

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        minimum_volume = 0.15
        extra_volume = 0.1
        bilayer_formulation = SoluteFormulation(target_composition=self.Bilayer_Composition,
                                          diluent=self.Bilayer_Solvent,
                                          target_volume=self.Lipid_Injection_Volume + minimum_volume + extra_volume,
                                          Target=self.Lipid_Mixing_Well,
                                          transfer_template=TransferOrganicsWithRinse,
                                          mix_template=MixOrganicsWithRinse)
        methods += bilayer_formulation.get_methods(layout)

        # DirectInject here (with bubble sensors?)

        buffer_formulation = Formulation(target_composition=self.Buffer_Composition,
                                          target_volume=self.Buffer_Injection_Volume + minimum_volume + extra_volume,
                                          Target=self.Buffer_Mixing_Well,
                                          exact_match=True,
                                          transfer_template=TransferWithRinse,
                                          mix_template=MixWithRinse)
        methods += buffer_formulation.get_methods(layout)

        # LoadLoop and InjectLoop

        return methods

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
    Use_Bubble_Sensors: bool = True
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
                method_name='LoadLoopBubbleSensor' if self.Use_Bubble_Sensors else 'LoadLoop',
                method_data=dict(pump_volume=self.Volume * 1000,
                                 excess_volume=self.Extra_Volume * 1000,
                                 air_gap=self.Air_Gap * 1000)
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate + self.Volume / self.Flow_Rate

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        return InjectMethod.execute(self, layout)

@register
@dataclass
class InjectLooptoQCMD(InjectLoop, QCMDAcceptTransfer):
    """Inject contents of injection system loop"""
    Use_Bubble_Sensors: bool = True
    display_name: Literal['ROADMAP Inject Injection System Loop'] = 'ROADMAP Inject Injection System Loop'
    method_name: Literal['ROADMAP_InjectLooptoQCMD'] = 'ROADMAP_InjectLooptoQCMD'

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [
            InjectLoop.sub_method(
                method_name='InjectLoopBubbleSensor' if self.Use_Bubble_Sensors else 'InjectLoop',
                method_data=dict(pump_volume=self.Volume * 1000,
                                 pump_flow_rate=self.Flow_Rate)
            ).to_dict() |
            QCMDAcceptTransfer.sub_method(method_name='QCMDAcceptTransfer',
                method_data={'contents': self.contents}
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Flow_Rate

@register
@dataclass
class DirectInjecttoQCMD(BaseInjectionSystemMethod, InjectMethod, BaseQCMDMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    #Volume: float defined in InjectMethod
    Aspirate_Flow_Rate: float = 2.5
    Load_Flow_Rate: float = 2.5
    Injection_Flow_Rate: float = 1.0
    Outside_Rinse_Volume: float = 0.5
    Extra_Volume: float = 0.1
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    Use_Bubble_Sensors: bool = True
    display_name: Literal['Direct Inject to QCMD'] = 'Direct Inject to QCMD'
    method_name: Literal['ROADMAP_QCMD_DirectInject'] = 'ROADMAP_QCMD_DirectInject'

    @dataclass
    class lh_method(BaseLHMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Load_Flow_Rate: str
        Injection_Flow_Rate: str
        Outside_Rinse_Volume: str
        Extra_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        source_zone, source_well_number = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
                    
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME='ROADMAP_QCMD_DirectInject_BubbleSensor' if self.Use_Bubble_Sensors else 'ROADMAP_QCMD_DirectInject',
            Source_Zone=source_zone,
            Source_Well=source_well_number,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Load_Flow_Rate=f'{self.Load_Flow_Rate}',
            Injection_Flow_Rate=f'{self.Injection_Flow_Rate}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Extra_Volume=f'{self.Extra_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
        ).to_dict() | 
            BaseInjectionSystemMethod.sub_method(
                method_name='DirectInjectBubbleSensor' if self.Use_Bubble_Sensors else 'DirectInject',
                method_data={}
            ).to_dict() |
            QCMDAcceptTransfer.sub_method(
                method_name='QCMDAcceptTransfer',
                method_data=dict(contents=repr(source_well.composition))
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Injection_Flow_Rate

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        return InjectMethod.execute(self, layout)

@register
@dataclass
class LoopInjectandMeasure(MethodContainer):
    """Make a bilayer with solvent exchange"""
    Target_Composition: Composition | None = None
    Volume: float = 0.0
    Injection_Flow_Rate: float = 1.0
    Is_Organic: bool = False
    Use_Bubble_Sensors: bool = True
    Equilibration_Time: float = 0.5
    Measurement_Time: float = 1.0
    display_name: Literal['Loop Inject and Measure'] = 'Loop Inject and Measure'
    method_name: Literal['LoopInjectandMeasure'] = 'LoopInjectandMeasure'

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        minimum_volume = 0.15
        extra_volume = 0.0
        required_volume = self.Volume + minimum_volume + extra_volume

        # select well with sufficient volume
        target_well, error = find_well_and_volume(self.Target_Composition, required_volume, layout.get_all_wells())
        if error is not None:
            print(f'Warning in {self.method_name}' + error + ', aborting')
            return []
        else:
            print(f'Found well in rack {target_well.rack_id} with number {target_well.well_number} with composition {repr(target_well.composition)} that matches target composition {self.Target_Composition}')
       

        load_loop = LoadLoop(Source=WellLocation(target_well.rack_id, target_well.well_number),
                             Volume=self.Volume,
                             Aspirate_Flow_Rate=(1.0 if self.Is_Organic else 2.5),
                             Flow_Rate=2.0,
                             Outside_Rinse_Volume=0.5,
                             Extra_Volume=extra_volume,
                             Air_Gap=0.1,
                             Use_Bubble_Sensors=self.Use_Bubble_Sensors,
                             Use_Liquid_Level_Detection=(False if self.Is_Organic else True))
        
        methods += load_loop.get_methods(layout)

        inject_loop = InjectLooptoQCMD(Volume=self.Volume,
                                 Flow_Rate=self.Injection_Flow_Rate,
                                 contents=repr(target_well.composition))
        
        methods += inject_loop.get_methods(layout)

        measure = QCMDRecordTag(record_time=self.Measurement_Time * 60,
                                sleep_time=self.Equilibration_Time * 60,
                                tag_name=repr(target_well.composition))
        
        methods += measure.get_methods(layout)

        return methods

@register
@dataclass
class DirectInjectandMeasure(MethodContainer):
    """Make a bilayer with solvent exchange"""
    Target_Composition: Composition | None = None
    Volume: float = 0.0
    Injection_Flow_Rate: float = 1.0
    Is_Organic: bool = False
    Use_Bubble_Sensors: bool = True
    Equilibration_Time: float = 0.5
    Measurement_Time: float = 1.0
    display_name: Literal['Direct Inject and Measure'] = 'Direct Inject and Measure'
    method_name: Literal['DirectInjectandMeasure'] = 'DirectInjectandMeasure'

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        minimum_volume = 0.15
        extra_volume = 0.1
        required_volume = self.Volume + minimum_volume + extra_volume

        # select well with sufficient volume
        target_well, error = find_well_and_volume(self.Target_Composition, required_volume, layout.get_all_wells())
        if error is not None:
            print(f'Warning in {self.method_name}' + error + ', aborting')
            return []
        else:
            print(f'Found well in rack {target_well.rack_id} with number {target_well.well_number} with composition {repr(target_well.composition)} that matches target composition {self.Target_Composition}')

        direct_inject = DirectInjecttoQCMD(Source=WellLocation(target_well.rack_id, target_well.well_number),
                             Volume=self.Volume,
                             Aspirate_Flow_Rate=(1.0 if self.Is_Organic else 2.5),
                             Load_Flow_Rate=2.0,
                             Injection_Flow_Rate=self.Injection_Flow_Rate,
                             Outside_Rinse_Volume=0.5,
                             Extra_Volume=extra_volume,
                             Air_Gap=0.1,
                             Use_Liquid_Level_Detection=(False if self.Is_Organic else True),
                             Use_Bubble_Sensors=self.Use_Bubble_Sensors
                             )
        
        methods += direct_inject.get_methods(layout)

        measure = QCMDRecordTag(record_time=self.Measurement_Time * 60,
                                sleep_time=self.Equilibration_Time * 60,
                                tag_name=repr(target_well.composition))
        
        methods += measure.get_methods(layout)

        return methods
