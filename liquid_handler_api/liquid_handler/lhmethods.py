from .bedlayout import LHBedLayout, WellLocation
from .error import MethodError
from .layoutmap import LayoutWell2ZoneWell, Zone
from .methods import BaseMethod, MethodType, register, MethodContainer, MethodsType, method_manager
from .devices import DeviceBase, register_device

from pydantic.v1.dataclasses import dataclass

from dataclasses import field, asdict
from typing import List, Literal
from enum import Enum

class LHMethodType(str, Enum):
    TRANSFER = 'transfer'
    MIX = 'mix'
    INJECT = 'inject'

@register_device
@dataclass
class LHDevice(DeviceBase):
    """Liquid Handler device
    """

    device_name: str = 'Gilson 271 Liquid Handler'
    device_type: str = 'lh'
    multichannel: bool = True
    address: str = 'http://localhost:5001'

@dataclass
class BaseLHMethod(BaseMethod):
    """Base class for LH methods"""

    method_type: Literal[MethodType.NONE] = MethodType.NONE
    #method_name: Literal['<name of Trilution method>'] = <name of Trilution method>

    @dataclass
    class lh_method:
        """Base class for representation in Trilution LH sample lists"""
        SAMPLENAME: str
        SAMPLEDESCRIPTION: str
        METHODNAME: str

        def to_dict(self) -> dict:
            """Creates dictionary representation; all custom field keys are prepended with a hash (#)
            Returns:
                dict: dictionary representation
            """

            d2 = asdict(self)

            # Following lines prepend all non-fixed fields with hashes
            #d = asdict(self)
            #d2 = copy(d)
            #for key in d.keys():
            #    if key not in ('SAMPLENAME', 'SAMPLEDESCRIPTION', 'METHODNAME'):
            #        d2['#' + key] = d2.pop(key)

            return d2

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Actions to be taken upon executing method. Default is nothing changes"""
        return None
    
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
        
        return [{LHDevice.device_name: [dict(sample_name=sample_name,
                                             sample_description=sample_description,
                                             method=asdict(self))]}]
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[dict]:
        """Renders the lh_method class to a Gilson LH-compatible format"""
        
        return [{}]

@dataclass
class LHMethodCluster(BaseLHMethod):

    method_type: Literal[MethodType.PREPARE] = MethodType.PREPARE
    methods: List[MethodsType] = field(default_factory=list)

    def explode(self, layout: LHBedLayout):
        methods = []
        for m in self.methods:
            methods += m.explode(layout)

        return methods

    def render_method(self, sample_name: str, sample_description: str, layout: LHBedLayout) -> List[dict]:
        
        return [{LHDevice.device_name: [dict(sample_name=sample_name,
                                             sample_description=sample_description,
                                             method=asdict(m))
                                        for m in self.methods]}]

@dataclass
class InjectMethod(BaseLHMethod):
    """Special class for methods that change the sample composition"""

    method_type: Literal[MethodType.INJECT] = MethodType.INJECT
    Source: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        return repr(source_well.composition)

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)

        if self.Volume > source_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Injection of volume {self.Volume} requested but well {source_well.well_number} in {source_well.rack_id} rack contains only {source_well.volume}"
                                      )

        source_well.volume -= self.Volume


@dataclass
class MixMethod(BaseLHMethod):
    """Special class for methods that change the sample composition"""

    method_type: Literal[MethodType.MIX] = MethodType.MIX
    Target: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)
        return repr(target_well.composition)

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.Volume > target_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Mix with volume {self.Volume} requested but well {target_well.well_number} in {target_well.rack_id} rack contains only {target_well.volume}"
                                      )


@dataclass
class TransferMethod(BaseLHMethod):
    """Special class for methods that change the sample composition"""

    method_type: Literal[MethodType.TRANSFER] = MethodType.TRANSFER
    Source: WellLocation = field(default_factory=WellLocation)
    Target: WellLocation = field(default_factory=WellLocation)
    Volume: float = 1.0

    def new_sample_composition(self, layout: LHBedLayout) -> str:
        """Returns string representation of source well composition"""
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        return repr(source_well.composition)

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        # use layout.get_well_and_rack so operation can be performed on a copy of a layout instead of on self.Source directly
        source_well, _ = layout.get_well_and_rack(self.Source.rack_id, self.Source.well_number)
        target_well, target_rack = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.Volume > source_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Well {source_well.well_number} in {source_well.rack_id} \
                                      rack contains {source_well.volume} but needs {self.Volume}")

        source_well.volume -= self.Volume

        if (target_well.volume + self.Volume) > target_rack.max_volume:
            return MethodError(name=self.display_name,
                                      error=f"Total volume {target_well.volume + self.Volume} from existing volume {target_well.volume} and transfer volume {self.Volume} exceeds rack maximum volume {target_rack.max_volume}"
                                      )

        # Perform mix. Note that target_well volume is also changed by this operation
        target_well.mix_with(self.Volume, source_well.composition)


@register
@dataclass
class TransferWithRinse(TransferMethod):
    """Transfer with rinse"""

    # Source, Target, and Volume defined in MixMethod
    Flow_Rate: float = 2.5
    Aspirate_Flow_Rate: float = 2.0
    Extra_Volume: float = 0.1
    Outside_Rinse_Volume: float = 0.5
    Inside_Rinse_Volume: float = 0.5
    Air_Gap: float = 0.1
    Use_Liquid_Level_Detection: bool = True
    display_name: Literal['Transfer With Rinse'] = 'Transfer With Rinse'
    method_name: Literal['NCNR_TransferWithRinse'] = 'NCNR_TransferWithRinse'

    @dataclass
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

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Flow_Rate + self.Volume / self.Aspirate_Flow_Rate


@register
@dataclass
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

    @dataclass
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

    def execute(self, layout: LHBedLayout) -> MethodError | None:

        target_well, _ = layout.get_well_and_rack(self.Target.rack_id, self.Target.well_number)

        if self.Volume > target_well.volume:
            return MethodError(name=self.display_name,
                                      error=f"Mix with volume {self.Volume} requested but well {target_well.well_number} in {target_well.rack_id} rack contains only {target_well.volume}"
                                      )

        target_well.volume -= self.Extra_Volume

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Repeats * (self.Volume / self.Flow_Rate + self.Volume / self.Aspirate_Flow_Rate)


@register
@dataclass
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

    @dataclass
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

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate


@register
@dataclass
class Sleep(BaseLHMethod):
    """Sleep"""

    Time: float = 1.0
    display_name: Literal['Sleep'] = 'Sleep'
    method_name: Literal['NCNR_Sleep'] = 'NCNR_Sleep'

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
            METHODNAME=self.method_name,
            Time=f'{self.Time}'
        ).to_dict()]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return float(self.Time)


@register
@dataclass
class Sleep2(BaseLHMethod):
    """Sleep"""

    Time2: float = 1.0
    display_name: Literal['Sleep2'] = 'Sleep2'
    method_name: Literal['NCNR_Sleep2'] = 'NCNR_Sleep2'

    @dataclass
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
@dataclass
class Prime(BaseLHMethod):
    """Prime"""

    Volume: float = 10.0
    Repeats: int = 1
    display_name: Literal['Prime'] = 'Prime'
    method_name: Literal['NCNR_Prime'] = 'NCNR_Prime'

    @dataclass
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
    
@register
@dataclass
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
    
@register
@dataclass
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