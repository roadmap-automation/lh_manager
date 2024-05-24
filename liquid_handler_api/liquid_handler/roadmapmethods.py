from .bedlayout import LHBedLayout, Composition, WellLocation, Well
from .methods import BaseMethod, register, MethodContainer, MethodsType
from .formulation import Formulation, SoluteFormulation
from .injectionmethods import InjectLoop, LoadLoop, BaseInjectionSystemMethod
from .lhmethods import BaseLHMethod, TransferWithRinse, MixWithRinse

import numpy as np
from copy import copy
from typing import List, Literal, Tuple
from pydantic.v1.dataclasses import dataclass

from dataclasses import field, asdict

class TransferOrganicsWithRinse(TransferWithRinse):
    Flow_Rate: float = 2.0
    Aspirate_Flow_Rate: float = 1.0
    Use_Liquid_Level_Detection: bool = False

class MixOrganicsWithRinse(MixWithRinse):
    Flow_Rate: float = 2.0
    Aspirate_Flow_Rate: float = 1.0
    Use_Liquid_Level_Detection: bool = False

@register
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

