"""Class definitions for bed layout, wells, and compositions"""
from dataclasses import field
from pydantic.dataclasses import dataclass
from typing import Optional, Tuple, List

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

    def __repr__(self) -> str:
        """Custom representation of composition for metadata"""

        if len(self.solvents) > 1:
            sorted_solvents = sorted(self.solvents, key=lambda s: s.fraction, reverse=True)
            solvent_ratios = ':'.join(f'{s.fraction * 100:0.0f}' for s in sorted_solvents)
            solvent_names = ':'.join(s.name for s in sorted_solvents)
            res = solvent_ratios + ' ' + solvent_names
        elif len(self.solvents) == 1:
            res = self.solvents[0].name
        else:
            res = ''

        for solute in self.solutes:
            res += f' + {solute.concentration:.4g} {solute.units} {solute.name}'

        return res

    @classmethod
    def from_list(cls, solvent_names: list[str], solvent_fractions: list[float], solute_names: list[str], solute_concentrations: list[float]) -> None:

        return cls([Solvent(name, fraction) for name, fraction in zip(solvent_names, solvent_fractions)],
                   [Solute(name, conc) for name, conc in zip(solute_names, solute_concentrations)])

    def get_solvent_names(self) -> Tuple[list[str]]:
        """Returns list of solvent names"""

        return [solvent.name for solvent in self.solvents]

    def get_solute_names(self) -> Tuple[list[str]]:
        """Returns list of solute names"""

        return [solute.name for solute in self.solutes]

    def get_solvent_fractions(self) -> Tuple[list[str], list[float]]:
        """Returns lists of solvent names and volume fractions"""

        fractions = [solvent.fraction for solvent in self.solvents]

        return self.get_solvent_names(), fractions

    def get_solute_concentrations(self) -> Tuple[list[str], list[float]]:
        """Returns lists of solute names and concentrations"""

        concentrations = [solute.concentration for solute in self.solutes]

        return self.get_solute_names(), concentrations

    def has_component(self, name: str) -> float | None:
        """Checks if component exists and if so returns the concentration (for solutes) or 
            volume fraction (for solvents)

        Args:
            name (str): name of component to check against solvent and solute name lists

        Returns:
            float | None: volume fraction (solvents) or amount (solute) if present; otherwise None
        """

        solvent_names, solvent_fractions = self.get_solvent_fractions()

        if name in solvent_names:
            return solvent_fractions[solvent_names.index(name)]
        
        solute_names, solute_concentrations = self.get_solute_concentrations()

        if name in solute_names:
            return solute_concentrations[solute_names.index(name)]
        

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
class WellLocation:
    rack_id: Optional[str] = None
    well_number: Optional[int] = None


@dataclass
class Well:
    """Class representing the contents of a single well
    
        rack_id (str): String description of rack where well is located
        well_number (int): Well number in specified rack
        composition (Composition): composition of solution in well
        volume (float | None): total volume in the well in mL. None indicates unoccupied well
        """

    rack_id: str
    well_number: int
    composition: Composition
    volume: float | None

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

@dataclass
class LHBedLayout:
    """Class representing a general LH bed layout"""
    racks: dict[str, Rack] = field(default_factory=dict)

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
        rack = self.racks[rack_id]
        well_numbers = [well.well_number for well in rack.wells]
        return rack.wells[well_numbers.index(well_number)], rack
    
    def get_all_wells(self) -> List[Well]:
        """Gets all wells in the layout

        Returns:
            List[Well]: list of all wells
        """

        return [w for rack in self.racks.values() for w in rack.wells]

    def update_well(self, well: Well):
        """Removes existing wells with the same rack_id, well_number
        Then appends the well to the end of that rack.wells """

        rack = self.racks[well.rack_id]
        # removes all existing wells with same well_number (go backwards to pop off the end):
        for i, existing_well in reversed(list(enumerate(rack.wells))):
            if existing_well.well_number == well.well_number:
                rack.wells.pop(i)
        rack.wells.append(well)

d2o = Solvent('D2O', 1.0)
kcl0 = Solute('KCl', 0.1)
kcl1 = Solute('KCl', 1.0)
h2o = Solvent('H2O', 1.0)
peptide = Solute('peptide', 1e-3)

dbuffer = Composition([d2o], [kcl0])
hbuffer = Composition([h2o], [kcl1])
water = Composition([h2o], [])
dwater = Composition([d2o], [])
peptide_solution = Composition([h2o], [peptide])
dpeptide_solution = Composition([d2o], [peptide])

mix_well = Well('Mix', 2, dbuffer, 4.0)
mix_well.mix_with(2, hbuffer)

empty = Composition([], [])
example_wells: List[Well] = [Well('Stock', 1, dwater, 2.0),
                 Well('Stock', 3, dwater, 8.0),
                 Well('Stock', 2, hbuffer, 8.0),
                 Well('Mix', 1, empty, 0.0),
                 Well('Mix', 10, water, 6.0),
                 mix_well,
                 Well('Solvent', 1, water, 200),
                 Well('Samples', 1, peptide_solution, 2),
                 Well('Samples', 2, dpeptide_solution, 2),
                 Well('Solvent', 2, dbuffer, 200)]


