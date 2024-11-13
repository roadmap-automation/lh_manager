from typing import List, Tuple, Literal
from copy import copy
from dataclasses import field

import numpy as np

from .lhmethods import InjectMethod, InjectWithRinse, MixMethod, MixWithRinse, TransferMethod, TransferWithRinse

from .bedlayout import LHBedLayout, WellLocation
from .methods import MethodContainer, MethodsType, register, method_manager

@register
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
    min_volume: float = 1.0
    max_volume: float = 1.0
    extra_volume: float = 0.15
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

        # 1. Calculate total volume required in each well

        # dilution factors
        dilution_factors = [self.dilution_factor] * (self.number_of_dilutions - 1)

        # total required to make next dilution (last one is just the target_volume) and leave
        # the appropriate target volume behind
        previous_dilution_volume = 0.0
        previous_target_volume = self.max_volume + self.extra_volume
        injection_volumes = [previous_target_volume - self.extra_volume]
        total_volumes = [previous_target_volume + previous_dilution_volume]

        # start from the last one and work backwards
        for df in dilution_factors[::-1]:
            #print(df, previous_target_volume, previous_dilution_volume, total_volumes[-1])
            previous_dilution_volume = (previous_target_volume + previous_dilution_volume) / df
            previous_target_volume = max(previous_target_volume / df, self.min_volume + self.extra_volume)
            total_volumes.append(previous_target_volume + previous_dilution_volume)
            injection_volumes.append(previous_target_volume - self.extra_volume)

        total_volumes = total_volumes[::-1]
        injection_volumes = injection_volumes[::-1]

        # 2. Calculate diluent fractions for each well
        diluent_fractions = [1.0 - 1.0 / self.initial_dilution_factor] + [1.0 - 1.0 / self.dilution_factor] * (self.number_of_dilutions - 1)

        return total_volumes, diluent_fractions, injection_volumes, success

    def _get_transfermix_methods(self, layout: LHBedLayout) -> Tuple[List[List[MethodsType]], List[List[MethodsType]]]:

        transfer_methods = []
        mix_methods = []
        target_wells = []
        total_volumes, diluent_fractions, injection_volumes, success = self._find_dilution_volumes(layout)

        if success:
            target_well = copy(self.first_target_well)
            sample_well = copy(self.sample_source)
            for total_volume, diluent_fraction in zip(total_volumes, diluent_fractions):

                itransfer_methods = []
                imix_methods = []
                
                # diluent transfer
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = self.diluent_source
                new_transfer.Target = target_well
                new_transfer.Volume = total_volume * diluent_fraction
                itransfer_methods.append(new_transfer)

                # sample transfer
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = sample_well
                new_transfer.Target = target_well
                new_transfer.Volume = total_volume * (1.0 - diluent_fraction)
                itransfer_methods.append(new_transfer)

                # mix
                mix_volume = min(0.9 * total_volume, total_volume - self.extra_volume)
                mix_volume = min(total_volume, mix_volume)

                new_mix = copy(self.mix_template)
                new_mix.Target = target_well
                new_mix.Volume = mix_volume
                imix_methods.append(new_mix)

                # add transfer and mix methods to respective lists
                transfer_methods.append(itransfer_methods)
                mix_methods.append(imix_methods)
                target_wells.append(target_well)

                # update sample (now previous target) and target (next well)
                sample_well = copy(target_well)
                target_well = WellLocation(target_well.rack_id, target_well.well_number + 1)

        return transfer_methods, mix_methods, target_wells, injection_volumes, success

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        transfer_methods, mix_methods, _, _, success = self._get_transfermix_methods(layout)

        if success:

            nested_methods = [tm + mm for tm, mm in zip(transfer_methods, mix_methods)]
            methods = [item for mlist in nested_methods for item in mlist]

        return methods


@register
class SerialDilutionInject(SerialDilution):

    method_name: Literal['SerialDilutionInject'] = 'SerialDilutionInject'
    display_name: Literal['Serial Dilution with Injection'] = 'Serial Dilution with Injection'
    inject_template: InjectMethod = field(default_factory=InjectWithRinse)

    def __post_init__(self):
        for attr_name in ('mix_template', 'transfer_template', 'inject_template'):
            attr = getattr(self, attr_name)
            if isinstance(attr, dict):
                setattr(self, attr_name, method_manager.get_method_by_name(attr['method_name'])(**attr))


    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        transfer_methods, mix_methods, target_wells, injection_volumes, success = self._get_transfermix_methods(layout)

        if success:
            inject_methods = []
            for target_well, volume in zip(target_wells, injection_volumes):
                new_inject = copy(self.inject_template)
                new_inject.Source = target_well
                new_inject.Volume = volume
                inject_methods.append([new_inject])

            # make everything first, then inject in reverse order
            nested_methods = [tm + mm for tm, mm in zip(transfer_methods, mix_methods)] + inject_methods[::-1]

            methods = [item for mlist in nested_methods for item in mlist]

        return methods

@register
class StandardDilution(MethodContainer):

    # Defined from BaseMethod
    # complete: bool
    method_name: Literal['StandardDilution'] = 'StandardDilution'
    display_name: Literal['Standard Dilution'] = 'Standard Dilution'
    sample_source: WellLocation = field(default_factory=WellLocation)
    diluent_source: WellLocation = field(default_factory=WellLocation)
    first_target_well: WellLocation = field(default_factory=WellLocation)
    number_of_dilutions: int = 10
    dilution_factor: float = 2.0
    min_volume: float = 1.0
    max_volume: float = 1.0
    extra_volume: float = 0.15
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

        # 1. Calculate total volume required in each well

        # dilution factors
        dilution_factors = self.dilution_factor ** (np.arange(self.number_of_dilutions) + 1.0)

        # injection volumes
        injection_volumes = self.max_volume * np.ones_like(dilution_factors)
        injection_volumes /= (dilution_factors[-1] / dilution_factors)
        injection_volumes = np.clip(injection_volumes, self.min_volume, self.max_volume)
        total_volumes = injection_volumes + self.extra_volume

        # 2. Calculate diluent fractions for each well
        diluent_fractions = 1.0 - 1.0 / dilution_factors

        return total_volumes[::-1], diluent_fractions[::-1], injection_volumes[::-1], success

    def _get_transfermix_methods(self, layout: LHBedLayout) -> Tuple[List[List[MethodsType]], List[List[MethodsType]]]:

        transfer_methods = []
        mix_methods = []
        target_wells = []
        total_volumes, diluent_fractions, injection_volumes, success = self._find_dilution_volumes(layout)

        if success:
            target_well = copy(self.first_target_well)
            for total_volume, diluent_fraction in zip(total_volumes, diluent_fractions):

                itransfer_methods = []
                imix_methods = []
                
                # diluent transfer
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = self.diluent_source
                new_transfer.Target = target_well
                new_transfer.Volume = total_volume * diluent_fraction
                itransfer_methods.append(new_transfer)

                # sample transfer
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = self.sample_source
                new_transfer.Target = target_well
                new_transfer.Volume = total_volume * (1.0 - diluent_fraction)
                itransfer_methods.append(new_transfer)

                # mix
                mix_volume = min(0.9 * total_volume, total_volume - self.extra_volume)
                mix_volume = min(total_volume, mix_volume)

                new_mix = copy(self.mix_template)
                new_mix.Target = target_well
                new_mix.Volume = mix_volume
                imix_methods.append(new_mix)

                # add transfer and mix methods to respective lists
                transfer_methods.append(itransfer_methods)
                mix_methods.append(imix_methods)
                target_wells.append(target_well)

                # update target (next well)
                target_well = WellLocation(target_well.rack_id, target_well.well_number + 1)

        return transfer_methods, mix_methods, target_wells, injection_volumes, success

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        transfer_methods, mix_methods, _, _, success = self._get_transfermix_methods(layout)

        if success:

            nested_methods = [tm + mm for tm, mm in zip(transfer_methods, mix_methods)]
            methods = [item for mlist in nested_methods for item in mlist]

        return methods

@register
class StandardDilutionInject(StandardDilution):

    # Defined from BaseMethod
    # complete: bool
    method_name: Literal['StandardDilutionInject'] = 'StandardDilutionInject'
    display_name: Literal['Standard Dilution with Injection'] = 'Standard Dilution with Injection'
    inject_template: InjectMethod = field(default_factory=InjectWithRinse)

    def __post_init__(self):
        for attr_name in ('mix_template', 'transfer_template', 'inject_template'):
            attr = getattr(self, attr_name)
            if isinstance(attr, dict):
                setattr(self, attr_name, method_manager.get_method_by_name(attr['method_name'])(**attr))

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        transfer_methods, mix_methods, target_wells, injection_volumes, success = self._get_transfermix_methods(layout)

        if success:
            inject_methods = []
            for target_well, volume in zip(target_wells, injection_volumes):
                new_inject = copy(self.inject_template)
                new_inject.Source = target_well
                new_inject.Volume = volume
                inject_methods.append([new_inject])

            # inject immediately after each solution is made
            nested_methods = [tm + mm + im for tm, mm, im in zip(transfer_methods, mix_methods, inject_methods)]

            methods = [item for mlist in nested_methods for item in mlist]

        return methods

if __name__ == '__main__':

    from pydantic import BaseModel

    class TestDilution(BaseModel):
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