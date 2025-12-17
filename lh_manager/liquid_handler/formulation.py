from typing import List, Tuple, Literal, Dict, Any, Optional
from copy import copy, deepcopy
import logging
import numpy as np
from scipy.optimize import nnls
from pydantic import Field, validator, SerializeAsAny

from .lhmethods import MixMethod, MixWithRinse, TransferMethod, TransferWithRinse, LHMethodCluster

from .bedlayout import Solute, Solvent, Composition, LHBedLayout, Well, WellLocation, empty
from .layoutmap import Zone, LayoutWell2ZoneWell
from .samplelist import example_sample_list
from .methods import MethodContainer, MethodsType, register, method_manager

ORIGIN = None
ZERO_VOLUME_TOLERANCE = 1e-3

def get_all_wells_in_zones(layout: LHBedLayout, include_zones: List[Zone]) -> List[Well]:
    """Gets all wells in the layout belonging to specific zones"""
    return [w for rack in layout.racks.values()
            for w in rack.wells
            if LayoutWell2ZoneWell(w.rack_id, w.well_number)[0] in include_zones]

def make_target_vector(target_composition: Composition) -> Tuple[List[str], List[float], Dict[str, str]]:
    """Makes target vector for formulations"""
    solvent_names, solvent_fractions = target_composition.get_solvent_fractions()
    solute_names, solute_concentrations, solute_units = target_composition.get_solute_concentrations()
    concentrations_with_units = {name: unit for (name, unit) in zip(solute_names, solute_units)}
    return solvent_names + solute_names, solvent_fractions + solute_concentrations, concentrations_with_units

def select_wells(wells: List[Well], target_names: List[str], exact_match: bool) -> Tuple[List[Well], List[str]]:
    """Selects wells based on whether they have the appropriate components"""
    acceptable_wells = []
    all_components = set()
    for well in wells:
        components = well.composition.get_solvent_names() + well.composition.get_solute_names()
        if exact_match:
            if all(cmp in target_names for cmp in components):
                acceptable_wells.append(well)
        else:
            if any(cmp in target_names for cmp in components):
                acceptable_wells.append(well)
        all_components.update(components)
    return acceptable_wells, list(all_components)

def make_source_matrix(source_names: List[str], wells: List[Well], source_units: Dict[str, str]) -> Tuple[List[list], List[Well]]:
    """Makes matrix of source wells that contain desired components"""
    source_matrix = []
    relevant_wells = []
    for well in wells:
        composition = well.composition
        solvent_names, solvent_fractions = composition.get_solvent_fractions()
        solute_names = composition.get_solute_names()
        col = []
        for name in source_names:
            if name in solvent_names:
                col.append(solvent_fractions[solvent_names.index(name)])
            elif name in solute_names:
                col.append(composition.solutes[solute_names.index(name)].convert_units(source_units[name]))
            else:
                col.append(0)
        
        if sum(col):
            source_matrix.append(col)
            relevant_wells.append(well)

    source_matrix = [list(x) for x in zip(*source_matrix)]
    return source_matrix, relevant_wells

def solve_formulation(layout: LHBedLayout,
                      target_composition: Composition,
                      target_volume: float,
                      exact_match: bool = True,
                      include_zones: List[Zone] = [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE]) -> Dict[str, Any]:
    """
    Calculates the formulation logic and returns a result dictionary.
    
    Returns:
        Dict with keys:
            - success (bool): Whether formulation was successful
            - error (str | None): Error message if failed
            - volumes (List[float]): List of volumes required from each well
            - wells (List[Well]): List of source wells
    """
    
    # 1. Create target vector
    target_names, target_vector, target_units = make_target_vector(target_composition)
    logging.info(f'target names: {target_names}')
    logging.info(f'target vector: {target_vector}')

    # 2. Get wells and check components
    all_wells = get_all_wells_in_zones(layout, include_zones)
    source_wells, source_components = select_wells(all_wells, target_names, exact_match)

    if not len(source_wells):
        return {'success': False, 'error': 'Cannot create formulation: no acceptable solutions available', 'volumes': [], 'wells': []}
    
    # 3. Check for missing components
    for target_name in target_names:
        if target_name not in source_components:
            return {'success': False, 'error': f'Cannot make formulation: {target_name} is missing', 'volumes': [], 'wells': []}

    # 4. Attempt to solve
    source_wells_current = list(source_wells) # copy list
    
    while True:
        logging.info(f'Source wells: {source_wells_current}')
        source_matrix, source_wells_current = make_source_matrix(target_names, source_wells_current, target_units)
        
        if not source_wells_current:
             return {'success': False, 'error': 'Solver failed: Ran out of source wells', 'volumes': [], 'wells': []}

        logging.info(f'Source matrix: {source_matrix}')

        # NNLS Solve
        sol, res = nnls(source_matrix, target_vector)

        if np.isclose(res, 0.0, atol=1e-9):
            logging.info(f'Good residual {res:0.0e}, solution {sol}')
            
            # Check volumes
            source_well_volumes = [well.volume for well in source_wells_current]
            required_volumes = sol * target_volume
            
            wells_to_remove = []
            for well, source_well_volume, required_volume in zip(source_wells_current, source_well_volumes, required_volumes):
                # Check if we have enough volume (including dead volume)
                rack_min = layout.racks[well.rack_id].min_volume
                if (required_volume + rack_min) > source_well_volume:
                    logging.warning(f'Well {well} insufficient volume (Needs {required_volume} + {rack_min}, has {source_well_volume}). Removing.')
                    wells_to_remove.append(well)
            
            if not wells_to_remove:
                # Success!
                volumes = []
                result_wells = []
                for well, vol in zip(source_wells_current, sol):
                    if vol * target_volume > ZERO_VOLUME_TOLERANCE:
                        volumes.append(vol * target_volume)
                        result_wells.append(well)
                return {'success': True, 'error': None, 'volumes': volumes, 'wells': result_wells}
            else:
                # Remove bad wells and retry
                for w in wells_to_remove:
                    if w in source_wells_current:
                        source_wells_current.remove(w)
                if not source_wells_current:
                    return {'success': False, 'error': 'Insufficient volume in source wells', 'volumes': [], 'wells': []}
                
        else:
            logging.warning(f'Bad residual {res:0.0e}')
            return {'success': False, 'error': f'Cannot solve formulation (Residual: {res:0.0e})', 'volumes': [], 'wells': []}

@register(origin=ORIGIN)
class Formulation(MethodContainer):

    method_name: Literal['Formulation'] = 'Formulation'
    display_name: Literal['Formulation'] = 'Formulation'
    target_composition: Composition = Field(default_factory=Composition)
    target_volume: float = 0.0
    Target: WellLocation = Field(default_factory=WellLocation)
    include_zones: List[Zone] = Field(default_factory=lambda: [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE])
    """include_zones (List[Zone]): list of zones to include for calculating formulations. Defaults to [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE]"""
    exact_match: bool = True
    """exact_match(bool, optional): Require an exact match between target composition and what
                is created. If False, allows other components to be added as long as the target composition
                is achieved. Defaults to True."""
    transfer_template: SerializeAsAny[TransferMethod] = Field(default_factory=TransferWithRinse)
    mix_template: SerializeAsAny[MixMethod] = Field(default_factory=MixWithRinse)

    _formulation_results: Tuple[List[float], List[Well], bool] | None = None

    @validator('mix_template', 'transfer_template', pre=True)
    def validate_templates(cls, v):
        if isinstance(v, dict):
            return method_manager.get_method_by_name(v['method_name'])(**v)
        return v

    def formulate(self, layout: LHBedLayout) -> Tuple[List[float], List[Well], bool]:
        """Create a formulation from a target composition with a target volume"""
        
        result = solve_formulation(
            layout=layout,
            target_composition=self.target_composition,
            target_volume=self.target_volume,
            exact_match=self.exact_match,
            include_zones=self.include_zones
        )
        
        if not result['success']:
            logging.error(result['error'])
            
        self._formulation_results = result['volumes'], result['wells'], result['success']
        logging.info(self._formulation_results)
        
        return self._formulation_results

    def get_formulation_results(self, layout: LHBedLayout) -> Tuple[List[float], List[Well], bool]:
        """Get cached formulation results, or recalculate

        Args:
            layout (LHBedLayout): LH bed layout

        Returns:
            Tuple[List[float], List[Well], bool]: see formulate()
        """

        if self._formulation_results is None:
            self._formulation_results = self.formulate(layout)
        return self._formulation_results

    def get_expected_composition(self, layout: LHBedLayout) -> Composition:
        """Calculates the expected composition from the formulation

        Returns:
            Composition: expected composition
        """

        volumes, wells, success = self.get_formulation_results(layout)

        if success:
            mix_well = Well(rack_id='', volume=0, composition=Composition(), well_number=0)
            for volume, well in zip(volumes, wells):
                mix_well.mix_with(volume, well.composition)
            return mix_well.composition
        else:
            return Composition()

    def get_target_well(self, layout: LHBedLayout) -> WellLocation:
        """Gets the target well. If the formulation already exists
            in the layout with sufficient volume, use that as the target well;
            otherwise use self.Target


        Args:
            layout (LHBedLayout): current LH bed layout

        Returns:
            WellLocation: target well location
        """
        volumes, wells, success = self.get_formulation_results(layout)

        if success:
            if len(volumes) > 1:
                return self.Target
            else:
                return WellLocation(rack_id=wells[0].rack_id,
                                    well_number=wells[0].well_number,
                                    expected_composition=self.target_composition)

    def get_methods(self, layout: LHBedLayout) -> List[MethodsType]:
        """Overwrites base class method to dynamically create list of methods.
            Returns empty list if the formulation already exists.
        """

        methods = []
        volumes, wells, success = self.get_formulation_results(layout)

        if success:
            # sort by volume (largest first)
            sort_index = np.argsort(volumes)[::-1]
            sorted_volumes = [volumes[si] for si in sort_index]
            sorted_wells: list[Well] = [wells[si] for si in sort_index]

            # Add transfer methods
            for volume, well in zip(sorted_volumes, sorted_wells):
                new_transfer = copy(self.transfer_template)
                new_transfer.Source = WellLocation(rack_id=well.rack_id, well_number=well.well_number)
                new_transfer.Target = self.Target
                new_transfer.Volume = volume
                methods.append(new_transfer)

            # Add a mix method, only if there's more than one transfer. Use 90% of total volume in well, unless mix volume is too small.
            # Assumes well contains more than min_mix_volume
            if len(volumes) > 1:
                total_volume = sum(volumes)
                min_mix_volume = 0.1
                mix_volume = 0.9 * total_volume
                if mix_volume < min_mix_volume:
                    mix_volume = min_mix_volume

                new_mix = copy(self.mix_template)
                new_mix.Target = self.Target
                new_mix.Volume = mix_volume
                methods.append(new_mix)

        return [] if not len(methods) else [LHMethodCluster(methods=methods)]
    
    # Kept for compatibility if used elsewhere, but simply aliases the module-level functions now
    def make_source_matrix(self, source_names, wells, source_units):
        return make_source_matrix(source_names, wells, source_units)
        
    def make_target_vector(self):
        return make_target_vector(self.target_composition)
        
    def select_wells(self, wells, target_names):
        return select_wells(wells, target_names, self.exact_match)
        
    def get_all_wells(self, layout):
        return get_all_wells_in_zones(layout, self.include_zones)

@register
class SoluteFormulation(Formulation):
    """Subclass of Formulation. In target_composition, specify only the solutes
        of interest; any missing volume will be filled in with the diluent."""
    
    method_name: Literal['SoluteFormulation'] = 'SoluteFormulation'
    display_name: Literal['SoluteFormulation'] = 'SoluteFormulation'
    exact_match: bool = False
    diluent: Composition = Field(default_factory=Composition)

    def formulate(self, layout: LHBedLayout) -> Tuple[List[float], List[Well], bool]:
        volumes, wells, success = super().formulate(layout)
        
        # Note: If super().formulate() failed, we return immediately.
        # Ideally, we should check if it failed because of missing solutes vs exact match issues,
        # but since exact_match=False, it likely failed due to missing solutes.
        if not success:
             return [], [], False

        diluent_well = next((well for well in self.get_all_wells(layout) if well.composition == self.diluent), None)
        
        if diluent_well is None:        
            logging.error(f'Diluent ({self.diluent}) not available on bed')
            return [], [], False
        
        diluent_volume = self.target_volume - sum(volumes)

        # if no diluent required, do nothing
        if not np.isclose(diluent_volume, 0.0, atol=ZERO_VOLUME_TOLERANCE):
            volumes += [diluent_volume]
            wells += [diluent_well]

            # only check for this if diluent volume is not close to zero
            if diluent_volume < 0:
                logging.error(f'Diluent volume less than zero; should never happen')
                return [], [], False

        return volumes, wells, True

if __name__ == '__main__':
    pass # Test code