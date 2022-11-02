"""Class definitions for bed layout, wells, and compositions"""
from dataclasses import dataclass, field
from util import reinstantiate, reinstantiate_list
from typing import Tuple

@dataclass
class Solvent:
    name: str
    fraction: float

@dataclass
class Solute:
    name: str
    concentration: float
    units: str = 'M' # not currently used

@dataclass
class Composition:
    """Class representing a solution composition"""
    solvents: list[Solvent] = field(default_factory=list)
    solutes: list[Solute] = field(default_factory=list)

    def __post_init__(self):

        self.solvents = reinstantiate_list(self.solvents, Solvent)
        self.solutes = reinstantiate_list(self.solutes, Solute)

    @classmethod
    def from_list(cls, solvent_names: list[str], solvent_fractions: list[float], solute_names: list[str], solute_concentrations: list[float]) -> None:

        return cls([Solvent(name, fraction) for name, fraction in zip(solvent_names, solvent_fractions)],
                   [Solute(name, conc) for name, conc in zip(solute_names, solute_concentrations)])

    def get_solvent_fractions(self) -> Tuple[list[str], list[float]]:
        """Returns lists of solvent names and volume fractions"""

        names = [solvent.name for solvent in self.solvents]
        fractions = [solvent.fraction for solvent in self.solvents]

        return names, fractions

    def get_solute_concentrations(self) -> Tuple[list[str], list[float]]:
        """Returns lists of solute names and concentrations"""

        names = [solute.name for solute in self.solutes]
        concentrations = [solute.concentration for solute in self.solutes]

        return names, concentrations

def combine_components(components1: list[str], concs1: list[float], volume1: float, components2: list[str], concs2: list[float], volume2: float) -> Tuple[list[str], list[float], float]:
    """Utility function for combining two sets of components
        
        components1 and components2 are lists of names of components
        concs1 and concs2 are concentrations of those components (can also be volume fractions)"""

    new_components = set(components1) | set(components2)
    new_concs = []
    for component in new_components:
        
        conc = 0
        conc += concs1[components1.index(component)] * volume1 if component in components1 else 0
        conc += concs2[components2.index(component)] * volume2 if component in components2 else 0

        new_concs.append(conc / (volume1 + volume2))

    return new_components, new_concs, volume1 + volume2

@dataclass
class Well:
    """Class representing the contents of a single well
    
        rack: Rack value where well is located
        well_number: Well number in specified rack
        volume: total volume in the well in mL. None indicates unoccupied well
        composition: Composition class representing composition of solution in well"""

    rack_id: str
    well_number: int
    composition: Composition
    volume: float

    def __post_init__(self):

        self.composition = reinstantiate(self.composition, Composition)

    def mix_with(self, volume: float, composition: Composition) -> None:
        """Update volume and composition from mixing with new solution"""

        solvents1, fractions1 = self.composition.get_solvent_fractions()
        solutes1, concentrations1 = self.composition.get_solute_concentrations()

        solvents2, fractions2 = composition.get_solvent_fractions()
        solutes2, concentrations2 = composition.get_solute_concentrations()

        new_solvents, new_fractions, new_volume = combine_components(solvents1, fractions1, self.volume,
                                                         solvents2, fractions2, volume)

        new_solutes, new_concentrations, _ = combine_components(solutes1, concentrations1, self.volume,
                                                             solutes2, concentrations2, volume)

        self.volume = new_volume
        self.composition = Composition.from_list(new_solvents, new_fractions, new_solutes, new_concentrations)

@dataclass
class Rack:
    """Class representing a rack"""
    columns: int
    rows: int
    max_volume: float
    wells: list[Well]
    style: str = 'grid' # grid | staggered

    def __post_init__(self):

        self.wells = reinstantiate_list(self.wells, Well)

@dataclass
class LHBedLayout:
    """Class representing a general LH bed layout"""
    racks: dict[str, Rack] = field(default_factory=dict)

    def __post_init__(self):

        for (k, v) in self.racks.items():
            self.racks[k] = reinstantiate(v, Rack)

    def add_rack_from_dict(self, name, d: dict):
        """ Add a rack from dictionary definition (i.e. config file)"""
        if 'wells' not in d.keys():
            d['wells'] = []

        self.racks[name] = Rack(**d)

    def add_well_to_rack(self, rack_id: str, well: Well) -> None:
        """Add a well to a rack in this layout"""

        # associate well with rack
        well.rack_id = rack_id

        # add well to appropriate rack
        self.racks[rack_id].wells.append(well)

    def get_well_and_rack(self, rack_id: str, well_number: int) -> Tuple[Well, Rack]:
        """Get well using the GUI (rack, well) specification"""
        return self.racks[rack_id][well_number], self.racks[rack_id]
