from typing import List, Tuple, Literal
from copy import copy, deepcopy
import numpy as np
from scipy.optimize import nnls
from dataclasses import field
from pydantic.v1.dataclasses import dataclass

from .bedlayout import Solute, Solvent, Composition, LHBedLayout, Well, WellLocation
from .layoutmap import Zone, LayoutWell2ZoneWell
from .samplelist import example_sample_list, StageName
from .methods import MethodContainer, MethodsType, TransferWithRinse, MixWithRinse, \
            TransferMethod, MixMethod, register, method_manager

@register
@dataclass
class SerialDilution(MethodContainer):

    # Defined from BaseMethod
    # complete: bool
    method_name: Literal['SerialDilution'] = 'SerialDilution'
    display_name: Literal['Serial Dilution'] = 'Serial Dilution'
    sample_source: WellLocation = field(default_factory=WellLocation)
    diluent_source: WellLocation = field(default_factory=WellLocation)
    first_target_well: WellLocation = field(default_factory=WellLocation)
    number_of_dilutions: int = 10
    initial_dilution_factor: float = 1.0
    dilution_factor: float = 2.0
    volume: float = 1.0
    transfer_template: TransferMethod = field(default_factory=TransferWithRinse)
    mix_template: MixMethod = field(default_factory=MixWithRinse)

    def __post_init__(self):
        for attr_name in ('mix_template', 'transfer_template'):
            attr = getattr(self, attr_name)
            if isinstance(attr, dict):
                setattr(self, attr_name, method_manager.get_method_by_name(attr['method_name'])(**attr))

    def _find_dilution_volumes(self,
                              layout: LHBedLayout):
        
        success = True
        # if number_of_dilutions is infinite, total volume required per well is up to
        # self.target_volume * (1 + 1 / (dilution_factor - 1)).
        max_volume_required = self.volume * (1 + 1. / (self.dilution_factor - 1))

        rack_max_volume = layout.racks[self.first_target_well.rack_id].max_volume
        if max_volume_required > rack_max_volume:
            success = False
            raise Warning(f'Maximum volume required for serial dilutions is {max_volume_required}, only {rack_max_volume} is available in rack id {self.first_target_well.rack_id}')

        # 1. Calculate total volume required in each well

        # dilution factors
        dilution_factors = [self.dilution_factor] * (self.number_of_dilutions - 1)

        # total required to make next dilution (last one is just the target_volume) and leave
        # the appropriate target volume behind
        total_volumes = [self.volume]
        previous_dilution_volume = 0.0

        # start from the last one and work backwards
        for df in dilution_factors[::-1]:
            previous_dilution_volume = (self.volume + previous_dilution_volume) / df
            total_volumes.append(self.volume + previous_dilution_volume)

        total_volumes = total_volumes[::-1]

        # 2. Calculate diluent fractions for each well
        diluent_fractions = [1.0 - 1.0 / self.initial_dilution_factor] + [1.0 - 1.0 / self.dilution_factor] * (self.number_of_dilutions - 1)

        return total_volumes, diluent_fractions, success

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        total_volumes, diluent_fractions, success = self._find_dilution_volumes(layout)

        if success:
            target_well = copy(self.first_target_well)
            sample_well = copy(self.sample_source)
            for total_volume, diluent_fraction in zip(total_volumes, diluent_fractions):
                
                # diluent transfer
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = self.diluent_source
                new_transfer.Target = target_well
                new_transfer.Volume = total_volume * diluent_fraction
                methods.append(new_transfer)

                # sample transfer
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = sample_well
                new_transfer.Target = target_well
                new_transfer.Volume = total_volume * (1.0 - diluent_fraction)
                methods.append(new_transfer)

                # mix
                mix_volume = min(0.9 * total_volume, total_volume - 0.15)
                mix_volume = min(total_volume, mix_volume)

                new_mix = copy(self.mix_template)
                new_mix.Target = target_well
                new_mix.Volume = mix_volume
                methods.append(new_mix)

                # update sample (now previous target) and target (next well)
                sample_well = copy(target_well)
                target_well = WellLocation(target_well.rack_id, target_well.well_number + 1)

        return methods

@register
@dataclass
class SerialDilutionVariableVolume(SerialDilution):

    # Defined from BaseMethod
    # complete: bool
    method_name: Literal['SerialDilutionVariableVolume'] = 'SerialDilutionVariableVolume'
    display_name: Literal['Serial DilutionVariableVolume'] = 'Serial DilutionVariableVolume'
    max_volume: float = 1.0

    def __post_init__(self):
        for attr_name in ('mix_template', 'transfer_template'):
            attr = getattr(self, attr_name)
            if isinstance(attr, dict):
                setattr(self, attr_name, method_manager.get_method_by_name(attr['method_name'])(**attr))

    def _find_dilution_volumes(self,
                              layout: LHBedLayout):
        
        success = True
        # if number_of_dilutions is infinite, total volume required per well is up to
        # self.target_volume * (1 + 1 / (dilution_factor - 1)).

        # 1. Calculate total volume required in each well

        # dilution factors
        dilution_factors = [self.dilution_factor] * (self.number_of_dilutions - 1)

        # total required to make next dilution (last one is just the target_volume) and leave
        # the appropriate target volume behind
        total_volumes = [self.max_volume]
        previous_dilution_volume = 0.0
        previous_target_volume = self.max_volume

        # start from the last one and work backwards
        for df in dilution_factors[::-1]:
            #print(df, previous_target_volume, previous_dilution_volume, total_volumes[-1])
            previous_dilution_volume = (previous_target_volume + previous_dilution_volume) / df
            previous_target_volume = max(previous_target_volume / df, self.volume)
            total_volumes.append(previous_target_volume + previous_dilution_volume)

        total_volumes = total_volumes[::-1]

        # 2. Calculate diluent fractions for each well
        diluent_fractions = [1.0 - 1.0 / self.initial_dilution_factor] + [1.0 - 1.0 / self.dilution_factor] * (self.number_of_dilutions - 1)

        return total_volumes, diluent_fractions, success

if __name__ == '__main__':

    @dataclass
    class TestDilution:
        initial_dilution_factor = 10.0
        dilution_factor = 2
        number_of_dilutions = 10
        target_volume = 1.0
    
        def dilute(self):
            
            max_volume_required = self.target_volume * (1 + 1. / (self.dilution_factor - 1))
            print(max_volume_required)

            dilution_factors = [self.dilution_factor] * (self.number_of_dilutions - 1)
            diluent_fractions = [1.0 - 1.0 / self.initial_dilution_factor] + [1.0 - 1.0 / self.dilution_factor] * (self.number_of_dilutions - 1)

            # total required to make next dilution (last one is just the target_volume) and leave
            # the appropriate target volume behind
            total_volumes = [self.target_volume]
            previous_dilution_volume = 0.0

            # start from the last one and work backwards
            for df in dilution_factors[::-1]:
                previous_dilution_volume = (self.target_volume + previous_dilution_volume) / df
                total_volumes.append(self.target_volume + previous_dilution_volume)

            total_volumes = total_volumes[::-1]

            return total_volumes, diluent_fractions

    d = TestDilution()
    print(d.dilute())

    #print(f.get_methods(layout))
    #print(f.execute(deepcopy(layout)))
    #print(f.render_lh_method('test_name', 'test_description', layout))
    #print(samples.getSamplebyName(example_sample_list[9].name).toSampleList('prep', layout, False))
    #print(samples.getSamplebyName(example_sample_list[9].name).stages['prep'].methods)

    #print(formulate(target_composition, 4, layout, include_zones))