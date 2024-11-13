from liquid_handler_api.liquid_handler.error import MethodError
from .bedlayout import LHBedLayout, Composition, WellLocation, Well, find_composition, InferredWellLocation
from .layoutmap import LayoutWell2ZoneWell, Zone
from .methods import BaseMethod, register, MethodContainer, MethodsType, MethodType
from .formulation import Formulation, SoluteFormulation
from .injectionmethods import InjectLoop, BaseInjectionSystemMethod
from .lhmethods import BaseLHMethod, TransferWithRinse, MixWithRinse, InjectWithRinse, InjectMethod, ROADMAP_QCMD_LoadLoop, ROADMAP_QCMD_DirectInject, TransferMethod, LHMethodCluster
from .qcmdmethods import QCMDRecord, QCMDRecordTag, QCMDMeasurementDevice, BaseQCMDMethod, QCMDAcceptTransfer

import numpy as np
from copy import copy
from typing import List, Literal, Tuple

from dataclasses import field

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

@register    
class TransferOrganicsWithRinse(TransferWithRinse):
    Flow_Rate: float = 1.0
    Aspirate_Flow_Rate: float = 2.0
    Use_Liquid_Level_Detection: bool = False

@register
class MixOrganicsWithRinse(MixWithRinse):
    Flow_Rate: float = 1.0
    Aspirate_Flow_Rate: float = 2.0
    Use_Liquid_Level_Detection: bool = False

@register
class InjectOrganicsWithRinse(InjectWithRinse):
    Aspirate_Flow_Rate: float = 1.0
    Flow_Rate: float = 2.0
    Use_Liquid_Level_Detection: bool = False

@register
class ROADMAP_QCMD_MakeBilayer(MethodContainer):
    """Make a bilayer with solvent exchange"""
    Bilayer_Composition: Composition | None = None
    Bilayer_Solvent: Composition | None = None
    Lipid_Injection_Volume: float = 0.0
    Buffer_Composition: Composition | None = None
    Buffer_Injection_Volume: float = 0.0
    Extra_Volume: float = 0.1
    Rinse_Volume: float = 2.0
    Flow_Rate: float = 2.0
    Exchange_Flow_Rate: float = 0.1
    Equilibration_Time: float = 1.0
    Measurement_Time: float = 2.0
    display_name: Literal['ROADMAP QCMD Make Bilayer'] = 'ROADMAP QCMD Make Bilayer'
    method_name: Literal['ROADMAP_QCMD_MakeBilayer'] = 'ROADMAP_QCMD_MakeBilayer'

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        minimum_volume = 0.15
        
        mix_extra_volume = 0.05
        extra_volume = self.Extra_Volume
        rinse_volume = self.Rinse_Volume
        injection_flow_rate=self.Flow_Rate
        exchange_flow_rate=self.Exchange_Flow_Rate
        equilibration_time = self.Equilibration_Time
        measurement_time = self.Measurement_Time

        """
        Questions:
            1. Which of the above to expose? Different for different methods? Can they be the same?
            2. Go through the process and check everything against existing methods

            TODO: make a formulate_if_doesn't_exist method
        """

        # ==== Solvent rinse ====
        required_volume = minimum_volume + extra_volume + rinse_volume
        lipid_prep_well, error = find_well_and_volume(self.Bilayer_Solvent, required_volume, layout.get_all_wells())
        if lipid_prep_well is None:
            print('Error: insufficient or nonexistent bilayer solvent. Aborting.')
            return []

        inject_rinse = ROADMAP_QCMD_LoopInjectandMeasure(Target_Composition=lipid_prep_well.composition,
                                                         Volume=rinse_volume,
                                                         Injection_Flow_Rate=injection_flow_rate,
                                                         Extra_Volume=extra_volume,
                                                         Is_Organic=True,
                                                         Use_Bubble_Sensors=True,
                                                         Equilibration_Time=equilibration_time,
                                                         Measurement_Time=measurement_time)

        methods += inject_rinse.get_methods_from_well(lipid_prep_well, lipid_prep_well.composition, layout)

        # ==== Lipids in solvent ====
        required_volume = minimum_volume + extra_volume + self.Lipid_Injection_Volume
        lipid_mixing_well, error = find_well_and_volume(self.Bilayer_Composition, required_volume, layout.get_all_wells())
        if lipid_mixing_well is None:
            lipid_mixing_well = InferredWellLocation('Mix')

            bilayer_formulation = SoluteFormulation(target_composition=self.Bilayer_Composition,
                                            diluent=self.Bilayer_Solvent,
                                            target_volume=self.Lipid_Injection_Volume + minimum_volume + extra_volume + mix_extra_volume,
                                            Target=lipid_mixing_well,
                                            transfer_template=TransferOrganicsWithRinse(),
                                            mix_template=MixOrganicsWithRinse(Repeats=1,
                                                                              Extra_Volume=mix_extra_volume))
            
            lipid_mixing_well.expected_composition = bilayer_formulation.get_expected_composition(layout)

            methods += [LHMethodCluster(method_type=MethodType.PREPARE,
                                        methods=bilayer_formulation.get_methods(layout))]
        else:
            lipid_mixing_well = WellLocation(lipid_mixing_well.rack_id, lipid_mixing_well.well_number, expected_composition=lipid_mixing_well.composition)

        direct_inject = ROADMAP_DirectInjecttoQCMD(Source=lipid_mixing_well,
                             Volume=self.Lipid_Injection_Volume,
                             Aspirate_Flow_Rate=1.0,
                             Load_Flow_Rate=2.0,
                             Injection_Flow_Rate=injection_flow_rate,
                             Outside_Rinse_Volume=0.5,
                             Extra_Volume=self.Extra_Volume,
                             Air_Gap=0.1,
                             Use_Liquid_Level_Detection=False,
                             Use_Bubble_Sensors=True
                             )
        
        methods += direct_inject.get_methods(layout)

        measure = QCMDRecordTag(record_time=self.Measurement_Time * 60,
                                sleep_time=self.Equilibration_Time * 60,
                                tag_name=repr(lipid_mixing_well.expected_composition))
        
        methods += measure.get_methods(layout)

        # ==== Buffer ====
        required_volume = minimum_volume + extra_volume + self.Buffer_Injection_Volume
        buffer_mixing_well, error = find_well_and_volume(self.Buffer_Composition, required_volume, layout.get_all_wells())
        if buffer_mixing_well is None:
            buffer_mixing_well = InferredWellLocation('Mix')

            buffer_formulation = Formulation(target_composition=self.Buffer_Composition,
                                            target_volume=self.Buffer_Injection_Volume + minimum_volume + extra_volume,
                                            Target=buffer_mixing_well,
                                            exact_match=True,
                                            transfer_template=TransferWithRinse(),
                                            mix_template=MixWithRinse())
            
            buffer_mixing_well.expected_composition = buffer_formulation.get_expected_composition(layout)

            methods += [LHMethodCluster(method_type=MethodType.PREPARE,
                                        methods=buffer_formulation.get_methods(layout))]
        else:
            buffer_mixing_well = InferredWellLocation(buffer_mixing_well.rack_id, buffer_mixing_well.well_number, expected_composition=buffer_mixing_well.composition)

        inject_buffer = ROADMAP_QCMD_LoopInjectandMeasure(Target_Composition=self.Bilayer_Composition, 
                                                         Volume=self.Buffer_Injection_Volume,
                                                         Injection_Flow_Rate=exchange_flow_rate,
                                                         Is_Organic=False,
                                                         Use_Bubble_Sensors=True,
                                                         Equilibration_Time=equilibration_time,
                                                         Measurement_Time=measurement_time)
        
        methods += inject_buffer.get_methods_from_well(buffer_mixing_well, buffer_mixing_well.expected_composition, layout)

        return methods

@register
class MultiInstrumentSleep(BaseInjectionSystemMethod, BaseLHMethod):
    display_name: Literal['IS + LH Sleep'] = 'IS + LH Sleep'
    method_name: Literal['IS_LH_Sleep'] = 'IS_LH_Sleep'
    Injection_System_Sleep_Time: float = 1.0
    LH_Sleep_Time: float = 1.0

    class lh_method(BaseLHMethod.lh_method):
        Time: str
    
    def render_method(self,
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
class MultiTransfer(MethodContainer):
    Source: WellLocation = field(default_factory=WellLocation)
    display_name: Literal['TestWellInference'] = 'TestWellInference'
    method_name: Literal['Test Well Inference'] = 'Test Well Inference'

    def get_methods(self, layout: LHBedLayout) -> List[BaseMethod]:
        
        methods = []
        target_well = InferredWellLocation('Mix')

        first_cluster = LHMethodCluster()

        first_transfer = TransferWithRinse(Source=self.Source,
                                           Target=target_well,
                                           Volume=0.1)
        
        first_cluster.methods += first_transfer.get_methods(layout)
        
        second_transfer = TransferWithRinse(Source=self.Source,
                                           Target=target_well,
                                           Volume=0.1)
        
        first_cluster.methods += second_transfer.get_methods(layout)

        methods += [first_cluster]

        new_target_well = InferredWellLocation('Mix')

        third_transfer = TransferWithRinse(Source=self.Source,
                                           Target=new_target_well,
                                           Volume=0.1)
        
        methods += third_transfer.get_methods(layout)
        
        fourth_transfer = TransferWithRinse(Source=target_well,
                                           Target=new_target_well,
                                           Volume=0.1)
        
        methods += fourth_transfer.get_methods(layout)

        return methods

@register
class ROADMAP_LoadLoop_Sync(ROADMAP_QCMD_LoadLoop, BaseInjectionSystemMethod):
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
    display_name: Literal['ROADMAP Load Injection System Loop'] = 'ROADMAP Load Injection System Loop'
    method_name: Literal['ROADMAP_LoadLoop_Sync'] = 'ROADMAP_LoadLoop_Sync'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:
        
        return [super().render_method(sample_name=sample_name,
                                        sample_description=sample_description,
                                        layout=layout)[0] | 
            self.sub_method(
                method_name='LoadLoopBubbleSensor' if self.Use_Bubble_Sensors else 'LoadLoop',
                method_data=dict(pump_volume=self.Volume * 1000,
                                 excess_volume=self.Extra_Volume * 1000,
                                 air_gap=self.Air_Gap * 1000)
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate + self.Volume / self.Flow_Rate

@register
class ROADMAP_InjectLooptoQCMD(InjectLoop, QCMDAcceptTransfer):
    """Inject contents of injection system loop"""
    Use_Bubble_Sensors: bool = True
    display_name: Literal['ROADMAP Inject Injection System Loop'] = 'ROADMAP Inject Injection System Loop'
    method_name: Literal['ROADMAP_InjectLooptoQCMD'] = 'ROADMAP_InjectLooptoQCMD'

    def render_method(self,
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
class ROADMAP_DirectInjecttoQCMD(ROADMAP_QCMD_DirectInject, BaseInjectionSystemMethod, BaseQCMDMethod):
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
    display_name: Literal['ROADMAP Direct Inject to QCMD'] = 'ROADMAP Direct Inject to QCMD'
    method_name: Literal['ROADMAP_DirectInjecttoQCMD'] = 'ROADMAP_DirectInjecttoQCMD'

    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        
        self.Source = layout.infer_location(self.Source)
        if self.Source.well_number is not None:
            source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
            composition = repr(source_well.composition)
        else:
            composition = self.Source.expected_composition
                    
        return [super().render_method(sample_name=sample_name,
                                        sample_description=sample_description,
                                        layout=layout)[0] | 
            BaseInjectionSystemMethod.sub_method(
                method_name='DirectInjectBubbleSensor' if self.Use_Bubble_Sensors else 'DirectInject',
                method_data=dict(pump_volume=self.Volume * 1000,
                                 pump_flow_rate=self.Injection_Flow_Rate)
            ).to_dict() |
            QCMDAcceptTransfer.sub_method(
                method_name='QCMDAcceptTransfer',
                method_data=dict(contents=composition)
            ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Injection_Flow_Rate

@register
class ROADMAP_QCMD_LoopInjectandMeasure(MethodContainer):
    """Make a bilayer with solvent exchange"""
    Target_Composition: Composition | None = None
    Volume: float = 0.0
    Injection_Flow_Rate: float = 1.0
    Extra_Volume: float = 0.1
    Is_Organic: bool = False
    Use_Bubble_Sensors: bool = True
    Equilibration_Time: float = 0.5
    Measurement_Time: float = 1.0
    display_name: Literal['ROADMAP QCMD Loop Inject and Measure'] = 'ROADMAP QCMD Loop Inject and Measure'
    method_name: Literal['ROADMAP_QCMD_LoopInjectandMeasure'] = 'ROADMAP_QCMD_LoopInjectandMeasure'

    def get_methods_from_well(self, target_well: Well, composition: Composition, layout: LHBedLayout) -> List[MethodsType]:
        """Helper function that gets all methods from a well location

        Args:
            well (WellLocation): Well location for injections

        Returns:
            List[MethodsType]: method list
        """

        methods = []

        load_loop = ROADMAP_LoadLoop_Sync(Source=WellLocation(target_well.rack_id, target_well.well_number),
                             Volume=self.Volume,
                             Aspirate_Flow_Rate=(1.0 if self.Is_Organic else 2.5),
                             Flow_Rate=2.0,
                             Outside_Rinse_Volume=0.5,
                             Extra_Volume=self.Extra_Volume,
                             Air_Gap=0.1,
                             Use_Bubble_Sensors=self.Use_Bubble_Sensors,
                             Use_Liquid_Level_Detection=(False if self.Is_Organic else True))
        
        methods += load_loop.get_methods(layout)

        inject_loop = ROADMAP_InjectLooptoQCMD(Volume=self.Volume,
                                 Flow_Rate=self.Injection_Flow_Rate,
                                 contents=repr(composition))
        
        methods += inject_loop.get_methods(layout)

        measure = QCMDRecordTag(record_time=self.Measurement_Time * 60,
                                sleep_time=self.Equilibration_Time * 60,
                                tag_name=repr(composition))
        
        methods += measure.get_methods(layout)

        return methods

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        minimum_volume = 0.15
        extra_volume = self.Extra_Volume
        required_volume = self.Volume + minimum_volume + extra_volume

        # select well with sufficient volume
        target_well, error = find_well_and_volume(self.Target_Composition, required_volume, layout.get_all_wells())
        if error is not None:
            print(f'Warning in {self.method_name}' + error + ', aborting')
            return []
        else:
            print(f'Found well in rack {target_well.rack_id} with number {target_well.well_number} with composition {repr(target_well.composition)} that matches target composition {self.Target_Composition}')
       
        methods += self.get_methods_from_well(target_well, target_well.composition, layout)

        return methods

@register
class ROADMAP_QCMD_DirectInjectandMeasure(MethodContainer):
    """Make a bilayer with solvent exchange"""
    Target_Composition: Composition | None = None
    Volume: float = 0.0
    Injection_Flow_Rate: float = 1.0
    Extra_Volume: float = 0.1
    Is_Organic: bool = False
    Use_Bubble_Sensors: bool = True
    Equilibration_Time: float = 0.5
    Measurement_Time: float = 1.0
    display_name: Literal['ROADMAP QCMD Direct Inject and Measure'] = 'ROADMAP QCMD Direct Inject and Measure'
    method_name: Literal['ROADMAP_QCMD_DirectInjectandMeasure'] = 'ROADMAP_QCMD_DirectInjectandMeasure'

    def get_methods_from_well(self, target_well: Well, composition: Composition, layout: LHBedLayout) -> List[MethodsType]:
        """Helper function that gets all methods from a well location

        Args:
            well (WellLocation): Well location for injections

        Returns:
            List[MethodsType]: method list
        """

        methods = []

        direct_inject = ROADMAP_DirectInjecttoQCMD(Source=WellLocation(target_well.rack_id, target_well.well_number),
                             Volume=self.Volume,
                             Aspirate_Flow_Rate=(1.0 if self.Is_Organic else 2.5),
                             Load_Flow_Rate=2.0,
                             Injection_Flow_Rate=self.Injection_Flow_Rate,
                             Outside_Rinse_Volume=0.5,
                             Extra_Volume=self.Extra_Volume,
                             Air_Gap=0.1,
                             Use_Liquid_Level_Detection=(False if self.Is_Organic else True),
                             Use_Bubble_Sensors=self.Use_Bubble_Sensors
                             )
        
        methods += direct_inject.get_methods(layout)

        measure = QCMDRecordTag(record_time=self.Measurement_Time * 60,
                                sleep_time=self.Equilibration_Time * 60,
                                tag_name=repr(composition))
        
        methods += measure.get_methods(layout)

        return methods

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

        methods += self.get_methods_from_well(target_well, target_well.composition, layout)

        return methods
