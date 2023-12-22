from dataclasses import fields, field, asdict
from pydantic.v1.dataclasses import dataclass
from enum import Enum
from copy import copy
from typing import Dict, List, Literal, Union, Set
from .bedlayout import LHBedLayout, WellLocation
from .layoutmap import LayoutWell2ZoneWell, Zone
from .items import MethodError

EXCLUDE_FIELDS = set(["method_name", "display_name", "complete", "method_type"])

## ========== Base Methods specification =============

class MethodType(str, Enum):
    NONE = 'none'
    CONTAINER = 'container'
    TRANSFER = 'transfer'
    MIX = 'mix'
    INJECT = 'inject'

@dataclass
class BaseMethod:
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

    def get_methods(self, layout: LHBedLayout):
        return [self]
    
    def explode(self, layout: LHBedLayout) -> None:
        pass
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[lh_method]:
        """Renders the lh_method class to a Gilson LH-compatible format"""
        
        return []

@dataclass
class MethodContainer(BaseMethod):
    """Special method that generates a list of basic methods when rendered"""

    method_type: Literal[MethodType.CONTAINER] = MethodType.CONTAINER
    display_name: str = 'MethodContainer'

    def get_methods(self, layout: LHBedLayout) -> List[BaseMethod]:
        """Generates list of methods. Intended to be superceded for specific applications

        Args:
            layout (LHBedLayout): layout to use for generating method list

        Returns:
            List[BaseMethod]: list of base methods
        """

        return []

    def execute(self, layout: LHBedLayout) -> MethodError | None:
        """Returns the error if any of the submethods give errors"""
        for m in self.get_methods(layout):
            error = m.execute(layout)
            if error is not None:
                return MethodError(f'{self.display_name}.{error.name}', error.error)

    def estimated_time(self, layout: LHBedLayout) -> float:
        return sum(m.estimated_time() for m in self.get_methods(layout))
    
    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        rendered_methods = []
        for m in self.get_methods(layout):
            rendered_methods += m.render_lh_method(sample_name=sample_name,
                                                   sample_description=sample_description,
                                                   layout=layout)
        return rendered_methods

@dataclass
class InjectMethod(BaseMethod):
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
class MixMethod(BaseMethod):
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
class TransferMethod(BaseMethod):
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

### =========== Methods manager ==============

MethodsType = Union[BaseMethod, InjectMethod, MixMethod, TransferMethod, MethodContainer]

class MethodManager:
    """Convenience class for managing methods."""

    def __init__(self) -> None:

        self.method_list: Set[MethodsType] = set()

    def register(self, method: MethodsType) -> None:
        """Registers a method in the manager

        Args:
            method (BaseMethod): method to register
        """

        self.method_list.add(method)

    def get_all_schema(self) -> Dict[str, Dict]:
        """Gets the schema of all the methods in the manager

        Returns:
            Dict[str, Dict]: Dictionary of method names and schema. Schema has fields 'fields', 
                                'display_name', and 'schema'; the last is the pydantic schema
        """

        lh_method_fields: Dict[str, Dict] = {}
        for method in self.method_list:
            fieldlist = []
            for fi in fields(method):
                if not fi.name in EXCLUDE_FIELDS:
                    fieldlist.append(fi.name)
            lh_method_fields[method.method_name] = {'fields': fieldlist, 'display_name': method.display_name, 'schema': method.__pydantic_model__.schema()}

        return lh_method_fields
    
    def get_method_by_name(self, method_name: str) -> MethodsType:
        """Gets method object by name

        Args:
            method_name (str): method name

        Returns:
            MethodsType: method class
        """

        return next(m for m in self.method_list if m.method_name == method_name)

method_manager = MethodManager()

def register(cls):
    """Decorator to register a class
    """
    method_manager.register(cls)
    return cls

## ========== Methods specification =============
# methods must be registered in methods manager

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
    class lh_method(BaseMethod.lh_method):
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
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:

        source_zone, source_well = LayoutWell2ZoneWell(self.Source.rack_id, self.Source.well_number)
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
        )]

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
    class lh_method(BaseMethod.lh_method):
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
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
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
        )]

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
    class lh_method(BaseMethod.lh_method):
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
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
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
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return self.Volume / self.Aspirate_Flow_Rate + self.Volume / self.Flow_Rate

@register
@dataclass
class Sleep(BaseMethod):
    """Sleep"""

    Time: float = 1.0
    display_name: Literal['Sleep'] = 'Sleep'
    method_name: Literal['NCNR_Sleep'] = 'NCNR_Sleep'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Time: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Time=f'{self.Time}'
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return float(self.Time)
    
@register
@dataclass
class Sleep2(BaseMethod):
    """Sleep"""

    Time2: float = 1.0
    display_name: Literal['Sleep2'] = 'Sleep2'
    method_name: Literal['NCNR_Sleep2'] = 'NCNR_Sleep2'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Time2: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Time2=f'{self.Time2}'
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        return float(self.Time2)

@register
@dataclass
class Prime(BaseMethod):
    """Prime"""

    Volume: float = 10.0
    Repeats: int = 1
    display_name: Literal['Prime'] = 'Prime'
    method_name: Literal['NCNR_Prime'] = 'NCNR_Prime'

    @dataclass
    class lh_method(BaseMethod.lh_method):
        Volume: str
        Repeats: str

    def render_lh_method(self,
                         sample_name: str,
                         sample_description: str,
                         layout: LHBedLayout) -> List[BaseMethod.lh_method]:
        
        return [self.lh_method(
            SAMPLENAME=sample_name,
            SAMPLEDESCRIPTION=sample_description,
            METHODNAME=self.method_name,
            Volume=f'{self.Volume}',
            Repeats=f'{self.Repeats:0.0f}'
        )]

    def estimated_time(self, layout: LHBedLayout) -> float:
        flow_rate = 10.0 # mL/min
        return 2 * float(self.Repeats) * float(self.Volume) / flow_rate


