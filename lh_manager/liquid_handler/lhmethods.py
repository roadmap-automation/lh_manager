from .bedlayout import LHBedLayout, WellLocation, Well
from .status import MethodError
from .layoutmap import LayoutWell2ZoneWell, Zone
from .methods import BaseMethod, MethodType, register, MethodsType
from .devices import DeviceBase, device_manager
from ..waste_manager.wastedata import WasteItem, WATER

from pydantic import BaseModel

from dataclasses import field
from typing import List, Literal, ClassVar
from enum import Enum

class LHMethodType(str, Enum):
    TRANSFER = 'transfer'
    MIX = 'mix'
    INJECT = 'inject'

class LHDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: Literal['Gilson 271 Liquid Handler'] = 'Gilson 271 Liquid Handler'
    device_type: Literal['lh'] = 'lh'
    multichannel: bool = True
    allow_sample_mixing: bool = True
    address: str = 'http://localhost:5001'

lhdevice = LHDevice()
device_manager.register(lhdevice)

EXCLUDE_FIELDS = ['status', 'tasks']

class BaseLHMethod(BaseMethod):
    """Base class for LH methods"""

    method_name: Literal['BaseLHMethod'] = 'BaseLHMethod'
    display_name: Literal['BaseLHMethod'] = 'BaseLHMethod'
    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    class lh_method(BaseModel):
        """Base class for representation in Trilution LH sample lists"""
        SAMPLENAME: str
        SAMPLEDESCRIPTION: str
        METHODNAME: str

        def to_dict(self) -> dict:
            """Creates dictionary representation; all custom field keys are prepended with a hash (#)
            Returns:
                dict: dictionary representation
            """

            d2 = self.model_dump()

            # Following lines prepend all non-fixed fields with hashes
            #d = self.model_dump()
            #d2 = copy(d)
            #for key in d.keys():
            #    if key not in ('SAMPLENAME', 'SAMPLEDESCRIPTION', 'METHODNAME'):
            #        d2['#' + key] = d2.pop(key)

            return d2

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        return None
    
    def waste(self, layout: LHBedLayout) -> WasteItem:
        """Generates a volume and composition of a waste stream

        Args:
            layout (LHBedLayout): current LH layout

        Returns:
            WasteItem: total waste
        """

        return WasteItem()
    
    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns new sample composition if applicable"""
        
        return ''

    def estimated_time(self, layout: LHBedLayout) -> float:
        """Estimated time for method in default time units"""
        return 0.0
    
    def render_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        """Renders the class to a dictionary"""
        
        return [{lhdevice.device_name: [dict(sample_name=sample_name,
                                             sample_description=sample_description,
                                             method_name=self.method_name,
                                             method_data=self.model_dump(exclude=EXCLUDE_FIELDS))]}]
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        """Renders the lh_method class to a Gilson LH-compatible format"""
        
        return [{}]

class LHMethodCluster(BaseLHMethod):

    method_name: Literal['LHMethodCluster'] = 'LHMethodCluster'
    display_name: Literal['LHMethodCluster'] = 'LHMethodCluster'
    method_type: Literal[MethodType.PREPARE] = MethodType.PREPARE
    methods: List[MethodsType] = field(default_factory=list)

    def explode(self, layout: LHBedLayout):
        methods = []
        for m in self.methods:
            methods += m.explode(layout)

        return methods

    def render_method(self, sample_name: str, sample_description: str, layout: LHBedLayout) -> List[dict]:
        
        return [{lhdevice.device_name: [dict(sample_name=sample_name,
                                             sample_description=sample_description,
                                             method_name=m.method_name,
                                             method_data=m.model_dump(exclude=EXCLUDE_FIELDS))
                                        for m in self.methods]}]

class SetWellID(BaseMethod):
    """Sets an Inferred Well Location ID for future use
    """

    well: WellLocation = field(default_factory=WellLocation)
    well_id: str | None = None
    method_type: Literal[MethodType.PREPARE] = MethodType.PREPARE

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        well, _ = layout.get_well_and_rack(self.well.rack_id, self.well.well_number)
        well.id = self.well_id
        

class InjectMethod(BaseLHMethod):
    """Special class for methods that change the sample composition"""

    method_name: Literal['InjectMethod'] = 'InjectMethod'
    display_name: Literal['InjectMethod'] = 'InjectMethod'
    method_type: Literal[MethodType.INJECT] = MethodType.INJECT
    Source: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        return repr(source_well.composition)

    @property
    def sample_volume(self):
        return self.Volume

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)

        if self.sample_volume > source_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Injection of volume {self.sample_volume} requested but well {source_well.well_number} in {source_well.rack_id} rack contains only {source_well.volume}"
                                      )

        source_well.volume -= self.sample_volume


class MixMethod(BaseLHMethod):
    """Special class for methods that change the sample composition"""

    method_name: str = 'MixMethod'
    display_name: str = 'MixMethod'
    method_type: Literal[MethodType.MIX] = MethodType.MIX
    Target: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)
        return repr(target_well.composition)

    @property
    def extra_volume(self):
        return 0.0

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        required_volume = self.Volume + self.extra_volume

        if required_volume > target_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Mix with volume {required_volume} requested but well {target_well.well_number} in {target_well.rack_id} rack contains only {target_well.volume}"
                                      )
        
        target_well.volume -= self.extra_volume

class TransferMethod(BaseLHMethod):
    """Special class for methods that change the sample composition"""

    method_name: str = 'TransferMethod'
    display_name: str = 'TransferMethod'
    method_type: Literal[MethodType.TRANSFER] = MethodType.TRANSFER
    Source: WellLocation = field(default_factory=WellLocation)
    Target: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        return repr(source_well.composition)

    @property
    def transfer_volume(self):
        return self.Volume

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        target_well, target_rack = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.transfer_volume > source_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Well {source_well.well_number} in {source_well.rack_id} \
                                      rack contains {source_well.volume} but needs {self.transfer_volume}")

        source_well.volume -= self.transfer_volume

        if (target_well.volume + self.Volume) > target_rack.max_volume:
            return MethodError(name=self.display_name,
                                      error=f"Total volume {target_well.volume + self.Volume} from existing volume {target_well.volume} and transfer volume {self.Volume} exceeds rack maximum volume {target_rack.max_volume}"
                                      )

        # Perform mix. Note that target_well volume is also changed by this operation
        target_well.mix_with(self.Volume, source_well.composition)


@register
class TransferWithRinse(TransferMethod):
    """Transfer with rinse"""

    # Source, Target, and Volume defined in MixMethod
    method_name: Literal['NCNR_TransferWithRinse'] = 'NCNR_TransferWithRinse'
    display_name: Literal['Transfer With Rinse'] = 'Transfer With Rinse'    

    Flow_Rate: float = 2.5
    Aspirate_Flow_Rate: float = 2.0
    Extra_Volume: float = 0.1
    Outside_Rinse_Volume: float = 0.5
    Inside_Rinse_Volume: float = 0.5
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True

    class lh_method(BaseLHMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Flow_Rate: str
        Aspirate_Flow_Rate: str
        Extra_Volume: str
        Outside_Rinse_Volume: str
        Inside_Rinse_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str
        Target_Zone: Zone
        Target_Well: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:

        self.Source = layout.infer_location(self.Source)
        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
        self.Target = layout.infer_location(self.Target)
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Flow_Rate=f'{self.Flow_Rate}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Extra_Volume=f'{self.Extra_Volume}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Inside_Rinse_Volume=f'{self.Inside_Rinse_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
            Target_Zone=target_zone,
            Target_Well=target_well
        ).to_dict()]

    @property
    def transfer_volume(self):
        return self.Volume + self.Extra_Volume

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Flow_Rate + self.Volume / self.Aspirate_Flow_Rate
    
    def waste(self, layout: LHBedLayout) -> WasteItem:
        inferred_source_well = layout.infer_location(self.Source)
        if inferred_source_well.well_number is not None:
            source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
            source_composition = source_well.composition
        else:
            source_composition = self.Source.expected_composition

        new_waste = WasteItem()
        new_waste.mix_with(volume=self.Extra_Volume, composition=source_composition)
        new_waste.mix_with(volume=self.Outside_Rinse_Volume + self.Inside_Rinse_Volume, composition=WATER)

        return new_waste

@register
class MixWithRinse(MixMethod):
    """Inject with rinse"""
    # Target and Volume defined in MixMethod
    Flow_Rate: float = 2.5
    Aspirate_Flow_Rate: float = 2.0
    Extra_Volume: float = 0.1
    Outside_Rinse_Volume: float = 0.5
    Inside_Rinse_Volume: float = 0.5
    Air_Gap: float = 0.1
    Repeats: int = 3
    Use_Liquid_Level_Detection: bool = True
    display_name: Literal['Mix With Rinse'] = 'Mix With Rinse'
    method_name: Literal['NCNR_MixWithRinse'] = 'NCNR_MixWithRinse'

    class lh_method(BaseLHMethod.lh_method):
        Volume: str
        Flow_Rate: str
        Aspirate_Flow_Rate: str
        Extra_Volume: str
        Outside_Rinse_Volume: str
        Inside_Rinse_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str
        Repeats: str
        Target_Zone: Zone
        Target_Well: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:

        self.Target = layout.infer_location(self.Target)
        target_zone, target_well = LayoutWell2ZoneWell(self.Target.rack_id, self.Target.well_number)
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Volume=f'{self.Volume}',
            Flow_Rate=f'{self.Flow_Rate}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Extra_Volume=f'{self.Extra_Volume}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Inside_Rinse_Volume=f'{self.Inside_Rinse_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
            Repeats=f'{self.Repeats}',
            Target_Zone=target_zone,
            Target_Well=target_well
        ).to_dict()]

    @property
    def extra_volume(self):
        return self.Extra_Volume

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.Volume > target_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Mix with volume {self.Volume} requested but well {target_well.well_number} in {target_well.rack_id} rack contains only {target_well.volume}"
                                      )

        target_well.volume -= self.Extra_Volume

    
    def waste(self, layout: LHBedLayout) -> WasteItem:
        inferred_target_well = layout.infer_location(self.Target)
        if inferred_target_well.well_number is not None:
            target_well, _ = layout.get_well_and_rack(inferred_target_well.rack_id, inferred_target_well.well_number)
            target_composition = target_well.composition
        else:
            target_composition = self.Target.expected_composition

        new_waste = WasteItem()
        new_waste.mix_with(volume=self.Extra_Volume, composition=target_composition)
        new_waste.mix_with(volume=self.Outside_Rinse_Volume + self.Inside_Rinse_Volume, composition=WATER)

        return new_waste

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Repeats * (self.Volume / self.Flow_Rate + self.Volume / self.Aspirate_Flow_Rate)


@register
class InjectWithRinse(InjectMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    #Volume: float defined in InjectMethod
    Aspirate_Flow_Rate: float = 2.0
    Flow_Rate: float = 2.5
    Extra_Volume: float = 0.1
    Outside_Rinse_Volume: float = 0.5
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    display_name: Literal['Inject With Rinse'] = 'Inject With Rinse'
    method_name: Literal['NCNR_InjectWithRinse'] = 'NCNR_InjectWithRinse'

    class lh_method(BaseLHMethod.lh_method):
        Source_Zone: Zone
        Source_Well: str
        Volume: str
        Aspirate_Flow_Rate: str
        Flow_Rate: str
        Extra_Volume: str
        Outside_Rinse_Volume: str
        Air_Gap: str
        Use_Liquid_Level_Detection: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:

        self.Source = layout.infer_location(self.Source)
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
            Extra_Volume=f'{self.Extra_Volume}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}'
        ).to_dict()]

    @property
    def sample_volume(self):
        return self.Volume + self.Extra_Volume

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate

    def waste(self, layout: LHBedLayout) -> WasteItem:
        inferred_source_well = layout.infer_location(self.Source)
        if inferred_source_well.well_number is not None:
            source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
            source_composition = source_well.composition
        else:
            source_composition = self.Source.expected_composition

        new_waste = WasteItem()
        new_waste.mix_with(volume=self.Volume + self.Extra_Volume, composition=source_composition)
        new_waste.mix_with(volume=self.Outside_Rinse_Volume + 0.5, composition=WATER)

        return new_waste

@register
class Sleep(BaseLHMethod):
    """Sleep"""

    Time: float = 1.0
    display_name: Literal['Sleep'] = 'Sleep'
    method_name: Literal['NCNR_Sleep'] = 'NCNR_Sleep'

    class lh_method(BaseLHMethod.lh_method):
        Time: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:

        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Time=f'{self.Time}'
        ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return float(self.Time)


@register
class Sleep2(BaseLHMethod):
    """Sleep"""

    Time2: float = 1.0
    display_name: Literal['Sleep2'] = 'Sleep2'
    method_name: Literal['NCNR_Sleep2'] = 'NCNR_Sleep2'

    class lh_method(BaseLHMethod.lh_method):
        Time2: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:

        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Time2=f'{self.Time2}'
        ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return float(self.Time2)


@register
class Prime(BaseLHMethod):
    """Prime"""

    Volume: float = 10.0
    Repeats: int = 1
    display_name: Literal['Prime'] = 'Prime'
    method_name: Literal['NCNR_Prime'] = 'NCNR_Prime'

    class lh_method(BaseLHMethod.lh_method):
        Volume: str
        Repeats: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseLHMethod.lh_method]:

        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Volume=f'{self.Volume}',
            Repeats=f'{self.Repeats:0.0f}'
        ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        flow_rate = 10.0 # mL/min
        return 2 * float(self.Repeats) * float(self.Volume) / flow_rate
    
    def waste(self, layout: LHBedLayout) -> WasteItem:
        return WasteItem(volume=self.Volume * self.Repeats, composition=WATER)

@register
class ROADMAP_QCMD_LoadLoop(InjectMethod):
    """Inject with rinse"""
    #Source: WellLocation defined in InjectMethod
    #Volume: float defined in InjectMethod
    Aspirate_Flow_Rate: float = 2.5
    Flow_Rate: float = 2.5
    Outside_Rinse_Volume: float = 0.5
    Extra_Volume: float = 0.1
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    display_name: Literal['Load Injection System Loop'] = 'Load Injection System Loop'
    method_name: Literal['ROADMAP_QCMD_LoadLoop'] = 'ROADMAP_QCMD_LoadLoop'

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
        
        self.Source = layout.infer_location(self.Source)
        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
            
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME='ROADMAP_QCMD_LoadLoop',
            Source_Zone=source_zone,
            Source_Well=source_well,
            Volume=f'{self.Volume}',
            Aspirate_Flow_Rate=f'{self.Aspirate_Flow_Rate}',
            Flow_Rate=f'{self.Flow_Rate}',
            Outside_Rinse_Volume=f'{self.Outside_Rinse_Volume}',
            Extra_Volume=f'{self.Extra_Volume}',
            Air_Gap=f'{self.Air_Gap}',
            Use_Liquid_Level_Detection=f'{self.Use_Liquid_Level_Detection}',
        ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate

    def waste(self, layout: LHBedLayout) -> WasteItem:
        inferred_source_well = layout.infer_location(self.Source)
        if inferred_source_well.well_number is not None:
            source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
            source_composition = source_well.composition
        else:
            source_composition = self.Source.expected_composition

        new_waste = WasteItem()
        new_waste.mix_with(volume=self.Volume + self.Extra_Volume, composition=source_composition)
        new_waste.mix_with(volume=self.Outside_Rinse_Volume + 0.5, composition=WATER)

        return new_waste

    @property
    def sample_volume(self):
        return self.Volume + self.Extra_Volume

@register
class ROADMAP_QCMD_DirectInject(InjectMethod):
    """Direct Inject with rinse"""
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
    display_name: Literal['Direct Inject'] = 'Direct Inject'
    method_name: Literal['ROADMAP_QCMD_DirectInject'] = 'ROADMAP_QCMD_DirectInject'

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
        
        self.Source = layout.infer_location(self.Source)
        source_zone, source_well_number = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
                    
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
        ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Injection_Flow_Rate
    
    def waste(self, layout: LHBedLayout) -> WasteItem:
        inferred_source_well = layout.infer_location(self.Source)
        if inferred_source_well.well_number is not None:
            source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
            source_composition = source_well.composition
        else:
            source_composition = self.Source.expected_composition

        new_waste = WasteItem()
        new_waste.mix_with(volume=self.Volume + self.Extra_Volume, composition=source_composition)
        new_waste.mix_with(volume=self.Outside_Rinse_Volume + 0.5, composition=WATER)

        return new_waste

    @property
    def sample_volume(self):
        return self.Volume + self.Extra_Volume