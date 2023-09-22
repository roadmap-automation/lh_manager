from typing import List, Tuple
from copy import copy
import numpy as np
from scipy.optimize import nnls

from .bedlayout import Solute, Solvent, Composition, combine_components, LHBedLayout, Well, WellLocation
from .layoutmap import Zone, LayoutWell2ZoneWell

def formulate(target_composition: Composition,
              target_volume: float,
              layout: LHBedLayout,
              include_zones: List[Zone] = [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE],
              exact_match=True) -> Tuple[List[float], List[Well], bool]:
    """Create a formulation from a target composition with a target volume

    Args:
        target_composition (Composition): composition object describing the desired composition.
        target_volume (float): _description_
        layout (LHBedLayout): _description_
        include_zones (List[Zone], optional): _description_. Defaults to [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE].
        exact_match(bool, optional): Require an exact match between target composition and what
            is created. If False, allows other components to be added as long as the target composition
            is achieved. Defaults to True.

    Returns:
        Tuple[List[float], List[Well], bool]: _description_
    """

    # 1. Create target vector from target composition.
    target_names, target_vector = make_target_vector(target_composition)
    print(f'target names: {target_names}')
    print(f'target vector: {target_vector}')

    # 2. get all components in layout and zones and check that the required solutions are available
    #    based on whether an exact match is required
    source_wells, source_components = select_wells(get_all_wells(layout, include_zones), target_names, exact_match)

    if not len(source_wells):
        print(f'Cannot create formulation: no acceptable solutions available')
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
        source_matrix, source_wells = make_source_matrix(target_names, source_wells)

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
        required_volumes = sol * target_volume

        for well, source_well_volume, required_volume in zip(source_wells, source_well_volumes, required_volumes):
            if required_volume > source_well_volume:
                print(f'Well {well} has volume {source_well_volume}, needs volume {required_volume}, removing it')
                source_wells.pop(source_wells.index(well))
                success = False

    # 4. Find all unique solutions an use a priority to find the best one (fewest operations, least time, etc.)
    source_wells = [well for well, vol in zip(source_wells, sol) if vol > 0]

    return (sol[sol>0] * target_volume).tolist(), source_wells, success

def make_source_matrix(source_names: List[str], wells: List[Well]) -> Tuple[List[list], List[Well]]:

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

def make_target_vector(target_composition: Composition) -> Tuple[List[str], List[float]]:
    """Makes target vector for formulations

    Args:
        target_composition (Composition): composition of target
        target_volume (float): volume of target solution

    Returns:
        Tuple[List[str], List[float]]: list of solvent/solute names, and the total amount
        (volume / moles), respectively, of each.
    """

    solvent_names, solvent_fractions = target_composition.get_solvent_fractions()
    solute_names, solute_concentrations = target_composition.get_solute_concentrations()

    return solvent_names + solute_names, solvent_fractions + solute_concentrations

def get_all_components(wells: List[Well]) -> Tuple[List[str], List[str]]:
    """Gets lists of all solvents and solutes in the specified zones from a bed layout

    Args:
        layout (LHBedLayout): bed layout to inspect
        include_zones (List[Zone]): zone names to include

    Returns:
        Tuple[List[str], List[str]]: lists of solvent and solute names
    """

    solvents = set()
    solutes = set()
    for well in wells:
        solvents.update(set(well.composition.get_solvent_names()))
        solutes.update(set(well.composition.get_solute_names()))

    return list(solvents), list(solutes)

def select_wells(wells: List[Well], target_names: List[str], exact_match=True) -> Tuple[List[Well], List[str]]:
    """Selects wells based on whether they have the appropriate components

    Args:
        wells (List[Well]): all wells to be considered
        target_names (List[str]): list of components in the target composition
        exact_match (bool, optional): Whether additional components that are not in the target
            composition are prohibited. Defaults to True.

    Returns:
        Tuple[List[Well], List[str]]: list of acceptable wells and list of all components in those wells
    """

    acceptable_wells = []
    all_components = set()
    for well in wells:
        # get solvent and solute names
        components = well.composition.get_solvent_names() + well.composition.get_solute_names()

        # if any additional items, don't include
        if exact_match:
            if all(cmp in target_names for cmp in components):
                acceptable_wells.append(well)

        # any well that has any of the desired components is fine
        else:
            if any(cmp in target_names for cmp in components):
                acceptable_wells.append(well)

        all_components.update(components)

    return acceptable_wells, list(all_components)

def get_all_wells(layout: LHBedLayout, include_zones: List[Zone]) -> List[Well]:
    """Gets all wells in the layout

    Args:
        layout (LHBedLayout): bed layout to inspect
        include_zones (List[Zone]): zone names to include

    Returns:
        List[Well]: list of all wells
    """

    return [w for rack in layout.racks.values()
            for w in rack.wells
            if LayoutWell2ZoneWell(w.rack_id, w.well_number)[0] in include_zones]

if __name__ == '__main__':

    from .state import layout

    include_zones = [Zone.SOLVENT, Zone.STOCK, Zone.SAMPLE]

    #target_composition = Composition([Solvent('H2O', 0.5), Solvent('D2O', 0.5)], [Solute('KCl', 0.2)])
    target_composition = Composition([Solvent('D2O', 1.0)], [Solute('peptide', 1e-6)])

    print(formulate(target_composition, 4, layout, include_zones))