from typing import List, Tuple, Literal
from copy import copy, deepcopy
import numpy as np
from scipy.optimize import nnls
from dataclasses import field
from pydantic.dataclasses import dataclass

from .bedlayout import Solute, Solvent, Composition, LHBedLayout, Well, WellLocation
from .layoutmap import Zone, LayoutWell2ZoneWell
from .samplelist import example_sample_list, StageName
from .methods import MethodContainer, MethodsType, TransferWithRinse, MixWithRinse, \
            TransferMethod, MixMethod, register, method_manager

@register
@dataclass
class Formulation(MethodContainer):

    # Defined from BaseMethod
    # complete: bool
    method_name: Literal['Formulation'] = 'Formulation'
    display_name: Literal['Formulation'] = 'Formulation'
    target_composition: Composition | None = None
    target_volume: float = 0.0
    Target: WellLocation = field(default_factory=WellLocation)
    include_zones: List[Zone] = field(default_factory=lambda: [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE])
    """include_zones (List[Zone]): list of zones to include for calculating formulations. Defaults to [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE]"""
    exact_match: bool = True
    """exact_match(bool, optional): Require an exact match between target composition and what
                is created. If False, allows other components to be added as long as the target composition
                is achieved. Defaults to True."""
    transfer_template: TransferMethod = field(default_factory=TransferWithRinse)
    mix_template: MixMethod = field(default_factory=MixWithRinse)

    def __post_init__(self):
        for attr_name in ('mix_template', 'transfer_template'):
            attr = getattr(self, attr_name)
            if isinstance(attr, dict):
                setattr(self, attr_name, method_manager.get_method_by_name(attr['method_name'])(**attr))

    def formulate(self,
                layout: LHBedLayout) -> Tuple[List[float], List[Well], bool]:
        """Create a formulation from a target composition with a target volume

        Args:
            layout (LHBedLayout): _description_


        Returns:
            Tuple[List[float], List[Well], bool]: _description_
        """

        # 1. Create target vector from target composition.
        target_names, target_vector = self.make_target_vector()
        print(f'target names: {target_names}')
        print(f'target vector: {target_vector}')

        # 2. get all components in layout and zones and check that the required solutions are available
        #    based on whether an exact match is required
        source_wells, source_components = self.select_wells(self.get_all_wells(layout), target_names)

        if not len(source_wells):
            print('Cannot create formulation: no acceptable solutions available')
            return [], [], False
        
        # 3. Check that all components of target are present in layout
        for target_name in target_names:
            if target_name not in source_components:
                print(f'Cannot make formulation: {target_name} is missing')
                return [], [], False

        # 4. Attempt to solve
        success = False
        while not success:
            print(f'Source wells: {source_wells}')
            source_matrix, source_wells = self.make_source_matrix(target_names, source_wells)

            print(f'Source matrix: {source_matrix}')

            # 3. Solve
            sol, res = nnls(source_matrix, target_vector)

            if np.isclose(res, 0.0, atol=1e-9):
                print(f'Good residual {res:0.0e}')
                success = True
            else:
                print(f'Bad residual {res:0.0e}, quitting formulation')
                success = False
                break

            # 3b. add error handling if res is not zero
            source_well_volumes = [well.volume for well in source_wells]
            required_volumes = sol * self.target_volume

            for well, source_well_volume, required_volume in zip(source_wells, source_well_volumes, required_volumes):
                if required_volume > source_well_volume:
                    print(f'Well {well} has volume {source_well_volume}, needs volume {required_volume}, removing it')
                    source_wells.pop(source_wells.index(well))
                    success = False

        # 4. Find all unique solutions an use a priority to find the best one (fewest operations, least time, etc.)
        source_wells = [well for well, vol in zip(source_wells, sol) if vol > 0]

        return (sol[sol>0] * self.target_volume).tolist(), source_wells, success
    
    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods
        """

        methods = []
        volumes, wells, success = self.formulate(layout)

        if success:
            # sort by volume (largest first)
            sorted_volumes = sorted(volumes)[::-1]
            sort_index = [volumes.index(sv) for sv in sorted_volumes]
            sorted_wells = [wells[si] for si in sort_index]

            # Add transfer methods
            for volume, well in zip(sorted_volumes, sorted_wells):
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = WellLocation(well.rack_id, well.well_number)
                new_transfer.Target = self.Target
                new_transfer.Volume = volume
                methods.append(new_transfer)

            # Add a mix method. Use 90% of total volume in well, unless mix volume is too small.
            # Assumes well contains more than min_mix_volume
            total_volume = sum(volumes)
            min_mix_volume = 0.1
            mix_volume = 0.9 * total_volume
            if mix_volume < min_mix_volume:
                mix_volume = min_mix_volume

            new_mix = copy(self.mix_template)
            new_mix.Target = self.Target
            new_mix.Volume = mix_volume
            methods.append(new_mix)

        return methods
    
    def make_source_matrix(self, source_names: List[str], wells: List[Well]) -> Tuple[List[list], List[Well]]:
        """Makes matrix of source wells that contain desired components

        Args:
            source_names (List[str]): list of desired component names
            wells (List[Well]): list of wells to consider

        Returns:
            Tuple[List[list], List[Well]]: Source matrix and list of wells corresponding to each
                column of the source matrix.
        """

        source_matrix = []
        relevant_wells = []
        for well in wells:

            composition = well.composition
            solvent_names, solvent_fractions = composition.get_solvent_fractions()
            solute_names, solute_concentrations = composition.get_solute_concentrations()

            # look for possible contributions
            col = []
            for name in source_names:
                if name in solvent_names:
                    col.append(solvent_fractions[solvent_names.index(name)])
                elif name in solute_names:
                    col.append(solute_concentrations[solute_names.index(name)])
                else:
                    col.append(0)
            
            # if this stock solution can contribute something
            if sum(col):
                source_matrix.append(col)
                relevant_wells.append(well)

        # transpose stock matrix
        source_matrix = [list(x) for x in zip(*source_matrix)]

        return source_matrix, relevant_wells

    def make_target_vector(self) -> Tuple[List[str], List[float]]:
        """Makes target vector for formulations

        Args:
            target_composition (Composition): composition of target
            target_volume (float): volume of target solution

        Returns:
            Tuple[List[str], List[float]]: list of solvent/solute names, and the total amount
            (volume / moles), respectively, of each.
        """

        solvent_names, solvent_fractions = self.target_composition.get_solvent_fractions()
        solute_names, solute_concentrations = self.target_composition.get_solute_concentrations()

        return solvent_names + solute_names, solvent_fractions + solute_concentrations

    def select_wells(self, wells: List[Well], target_names: List[str]) -> Tuple[List[Well], List[str]]:
        """Selects wells based on whether they have the appropriate components

        Args:
            wells (List[Well]): all wells to be considered
            target_names (List[str]): list of components in the target composition

        Returns:
            Tuple[List[Well], List[str]]: list of acceptable wells and list of all components in those wells
        """

        acceptable_wells = []
        all_components = set()
        for well in wells:
            # get solvent and solute names
            components = well.composition.get_solvent_names() + well.composition.get_solute_names()

            # if any additional items, don't include
            if self.exact_match:
                if all(cmp in target_names for cmp in components):
                    acceptable_wells.append(well)

            # any well that has any of the desired components is fine
            else:
                if any(cmp in target_names for cmp in components):
                    acceptable_wells.append(well)

            all_components.update(components)

        return acceptable_wells, list(all_components)

    def get_all_wells(self, layout: LHBedLayout) -> List[Well]:
        """Gets all wells in the layout

        Args:
            layout (LHBedLayout): bed layout to inspect

        Returns:
            List[Well]: list of all wells
        """

        return [w for rack in layout.racks.values()
                for w in rack.wells
                if LayoutWell2ZoneWell(w.rack_id, w.well_number)[0] in self.include_zones]

target_composition = Composition([Solvent('D2O', 1.0)], [Solute('peptide', 1e-6)])

transfer = TransferWithRinse(Flow_Rate=2.0)
mix = MixWithRinse(Repeats=2)

example_formulation = Formulation(target_composition=target_composition,
                target_volume=7.0,
                Target=WellLocation('Mix', 10),
                mix_template=mix)

example_sample_list[9].stages[StageName.PREP].methods[-1] = example_formulation

if __name__ == '__main__':

    from .state import layout, samples

    include_zones = [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE]

    #target_composition = Composition([Solvent('H2O', 0.5), Solvent('D2O', 0.5)], [Solute('KCl', 0.2)])
    target_composition = Composition([Solvent('D2O', 1.0)], [Solute('peptide', 1e-6)])
    target_well, _ = layout.get_well_and_rack('Mix', 1)

    transfer = TransferWithRinse(Flow_Rate=2.0)
    mix = MixWithRinse(Repeats=2)

    f = Formulation(target_composition=target_composition,
                    target_volume=8.0,
                    Target=WellLocation(target_well.rack_id, target_well.well_number),
                    mix_template=mix)
    
    print(f.formulate(layout))
    print(f.get_methods(layout))
    print(f.execute(deepcopy(layout)))
    print(f.render_lh_method('test_name', 'test_description', layout))
    print(samples.getSamplebyName(example_sample_list[9].name).toSampleList('prep', layout, False))
    #print(samples.getSamplebyName(example_sample_list[9].name).stages['prep'].methods)

    #print(formulate(target_composition, 4, layout, include_zones))