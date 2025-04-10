"""Class definitions for bed layout, wells, and compositions"""
from copy import deepcopy
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import Optional, Tuple, List

# ======= Unit conversions ===========
MASS_UNITS = ['mg/mL', 'mg/L', 'ug/mL']
VOLUME_UNITS = ['M', 'mM', 'uM', 'nM']

# factor to convert units to M
volume_conversion = {'M': 1,
                   'mM': 1e-3,
                   'uM': 1e-6,
                   'nM': 1e-9}

# factor to convert units to mg/mL
mass_conversion = {'mg/mL': 1,
                   'mg/L': 1e-3,
                   'ug/mL': 1e3}

def volumeunits2massunits(c: float, mw: float):
    """Convert M to mg/mL"""
    return c * mw

def massunits2volumeunits(c: float, mw: float):
    """Convert mg/mL to M"""
    return c / mw

def is_close(a, b, tol=1e-10):
    return (abs(a - b) < tol)

class Solvent(BaseModel):
    name: str = ''
    fraction: float = 0.0

    def __eq__(self, value):
        if not isinstance(value, Solvent):
            return NotImplemented
        return (self.name == value.name) & (is_close(self.fraction, value.fraction))
    
class Solute(BaseModel):
    name: str = ''
    concentration: float = 0.0
    molecular_weight: float | None = None
    units: str = 'M'

    def convert_units(self, ref_units: str = 'M'):
        """Returns concentration value in reference units

        Args:
            ref_units (str, optional): reference units. Defaults to M.

        Returns:
            float: concentration in reference units
        """
        if self.units == ref_units:
            return self.concentration
        elif (self.units in MASS_UNITS) & (ref_units in MASS_UNITS):
            ref_conversion = mass_conversion[ref_units]
            value_conversion = mass_conversion[self.units]
            return self.concentration * value_conversion / ref_conversion
        elif (self.units in MASS_UNITS) & (ref_units in VOLUME_UNITS):
            return self.concentration * mass_conversion[self.units] /  self.molecular_weight / volume_conversion[ref_units]
        elif (self.units in VOLUME_UNITS) & (ref_units in MASS_UNITS):
            return self.concentration * volume_conversion[self.units] * self.molecular_weight / mass_conversion[ref_units]
        elif (self.units in VOLUME_UNITS) & (ref_units in VOLUME_UNITS):
            ref_conversion = volume_conversion[ref_units]
            value_conversion = volume_conversion[self.units]
            return self.concentration * value_conversion / ref_conversion
        elif (self.units not in (VOLUME_UNITS + MASS_UNITS)):
            raise ValueError(f'Unknown units {self.units}')
        elif (ref_units not in (VOLUME_UNITS + MASS_UNITS)):
            raise ValueError(f'Unknown units {ref_units}')

    def __eq__(self, value):
        if not isinstance(value, Solute):
            return NotImplemented

        # NOTE: compares name and converted concentration. There is an edge case where molecular weights
        # are different and this leads to an incorrect equality; but it is better to allow molecular weights
        # to occasionally be None
        return (self.name == value.name) & (is_close(self.concentration, value.convert_units(self.units)))

class Composition(BaseModel):
    """Class representing a solution composition"""
    solvents: list[Solvent] = Field(default_factory=list)
    solutes: list[Solute] = Field(default_factory=list)

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

    def _normalize_solvent_fractions(self):
        """conditions class to normalize solvent fractions"""

        sum_solvents = sum(solvent.fraction for solvent in self.solvents)
        for solvent in self.solvents:
            solvent.fraction /= sum_solvents

        return self.solvents


    def __eq__(self, value) -> bool:
        if not isinstance(value, Composition):
            return NotImplemented
        
        # check solvents. assumes no duplicates
        solvents_same = False
        sum_fractions = sum(s.fraction for s in self.solvents)
        solvents = set((s.name, s.fraction / sum_fractions) for s in self.solvents if s.fraction > 0)
        value_sum_fractions = sum(s.fraction for s in value.solvents)
        value_solvents = set((s.name, s.fraction / value_sum_fractions) for s in value.solvents if s.fraction > 0)
        solvents_same = (set(solvents) == set(value_solvents))

        # check solutes. assumes no duplicates
        solutes_same = False
        self_solute_names = [s.name for s in self.solutes if s.concentration > 0]
        value_solute_names = [s.name for s in value.solutes if s.concentration > 0]
        if set(self_solute_names) == set(value_solute_names):
            if all(s == value.solutes[value_solute_names.index(s.name)] for s in self.solutes):
                solutes_same = True

        return solvents_same & solutes_same

    @property
    def is_empty(self):
        return (len(self.solutes) == 0) & (len(self.solvents) == 0)

    @classmethod
    def from_list(cls, solvent_names: list[str], solvent_fractions: list[float], solute_names: list[str], solute_concentrations: list[float]) -> None:

        return cls(solvents=[Solvent(name=name, fraction=fraction) for name, fraction in zip(solvent_names, solvent_fractions)],
                   solutes=[Solute(name=name, concentration=conc) for name, conc in zip(solute_names, solute_concentrations)])

    def get_solvent_names(self) -> Tuple[list[str]]:
        """Returns list of solvent names"""

        return [solvent.name for solvent in self.solvents]

    def get_solute_names(self) -> Tuple[list[str]]:
        """Returns list of solute names"""

        return [solute.name for solute in self.solutes]

    def get_solvent_fractions(self) -> Tuple[list[str], list[float]]:
        """Returns lists of solvent names and volume fractions"""

        fractions = [solvent.fraction for solvent in self.solvents]

        return self.get_solvent_names(), [f / sum(fractions) for f in fractions]

    def get_solute_concentrations(self, ref_unit: str = 'M') -> Tuple[list[str], list[float]]:
        """Returns lists of solute names and concentrations, converting to a given reference unit"""

        concentrations = [solute.concentration for solute in self.solutes]
        units = [solute.units for solute in self.solutes]

        return self.get_solute_names(), concentrations, units

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

class WellLocation(BaseModel):
    rack_id: Optional[str] = None
    well_number: Optional[int] = None
    id: Optional[str] = None
    expected_composition: Composition | None = None    

class InferredWellLocation(WellLocation):
    def model_post_init(self, __context):

        if self.id is None:
            self.id = str(uuid4())

class Solution(BaseModel):
    """Class representing a volume and composition of material"""

    composition: Composition = Field(default_factory=Composition)
    volume: float = 0.0

    def mix_with(self, volume: float, composition: Composition) -> None:
        """Update volume and composition from mixing with new solution. Priority in unit conversions is given to the existing composition"""

        solvents1, fractions1 = self.composition.get_solvent_fractions()
        solutes1 = self.composition.get_solute_names()

        solvents2, fractions2 = composition.get_solvent_fractions()
        solutes2 = composition.get_solute_names()

        new_solvents, new_fractions, new_volume = combine_components(solvents1, fractions1, self.volume,
                                                         solvents2, fractions2, volume)
        
        # handle solutes differently because units can be different
        new_solutes: list[Solute] = []
        for solute_name, solute in zip(solutes1, self.composition.solutes):
            if solute_name not in solutes2:
                new_solute = deepcopy(solute)
                new_solute.concentration *= self.volume / new_volume
            else:
                solute2 = composition.solutes[solutes2.index(solute_name)]
                new_concentration = (solute.concentration * self.volume + solute2.convert_units(solute.units) * volume) / new_volume
                new_solute = Solute(name=solute_name,
                                    concentration=new_concentration,
                                    molecular_weight=solute.molecular_weight,
                                    units=solute.units)
                
            new_solutes.append(new_solute)
        
        for solute_name, solute in zip(solutes2, composition.solutes):
            # check if this solute is already processed
            if solute_name not in solutes1:
                new_solute = deepcopy(solute)
                new_solute.concentration *= volume / new_volume
                new_solutes.append(new_solute)

        self.volume = new_volume
        self.composition = Composition(solutes=new_solutes,
                                       solvents=[Solvent(name=name, fraction=fraction) for name, fraction in zip(new_solvents, new_fractions)])

class Well(Solution):
    """Class representing the contents of a single well
    
        rack_id (str): String description of rack where well is located
        well_number (int): Well number in specified rack
        composition (Composition): composition of solution in well
        volume (float | None): total volume in the well in mL. None indicates unoccupied well
        id (str | None): optional UUID of well. Used for matching InferredWellLocation to existing wells
        """

    rack_id: str
    well_number: int
    id: str | None = None

def find_composition(composition: Composition, wells: List[Well]) -> List[Well]:
    """Finds wells containing the desired composition

    Args:
        composition (Composition): target composition
        wells (List[Well]): list of wells to search

    Returns:
        List[Well]: list of wells containing that composition
    """

    return [well for well in wells if well.composition == composition]


class Rack(BaseModel):
    """Class representing a rack"""
    columns: int
    rows: int
    max_volume: float
    wells: list[Well]
    style: str = 'grid' # grid | staggered
    height: int
    width: int
    x_translate: int
    y_translate: int
    shape: str = 'rect' # rect | circle
    editable: bool = True

class LHBedLayout(BaseModel):
    """Class representing a general LH bed layout"""
    racks: dict[str, Rack] = Field(default_factory=dict)

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

    def find_next_empty(self, rack_id: str | None = None) -> WellLocation | None:
        """Finds the next empty well in a rack. Requires volume to be zero and an
            ID not to have been assigned.

        Args:
            rack_id (str|None): Target rack if provided, otherwise use all wells

        Returns:
            WellLocation: location of returned 
        """

        rack = self.racks[rack_id]
        next_empty = next((w
                            for w in sorted(rack.wells, key=lambda w: w.well_number)
                            if (w.volume == 0) & (w.id is None)),
                        None)
        if next_empty is not None:
            return WellLocation(rack_id=rack_id, well_number=next_empty.well_number)

    def infer_location(self, well: WellLocation) -> WellLocation | None:
        """Finds the next empty and fills in the inferred well location by ID or by next empty.
            If well.id is None, returns the original well

        Args:
            well (WellLocation): well location to use for inference

        Returns:
            WellLocation: updated inferred well location
        """

        if well.id is None:
            return well

        # check for well ID match
        next_match = next((w for w in self.get_all_wells() if w.id == well.id), None)

        # if match found
        if next_match is not None:
            well.rack_id, well.well_number = next_match.rack_id, next_match.well_number
            return well
        else:        
            # otherwise find the next empty and associate the InferredWellLocation well ID with that well
            next_empty = self.find_next_empty(well.rack_id)
            if next_empty is not None:
                target_well, _ = self.get_well_and_rack(next_empty.rack_id, next_empty.well_number)
                target_well.id = well.id

                well.rack_id, well.well_number = next_empty.rack_id, next_empty.well_number
                return well
        
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

        wells = self.remove_well_definition(well.rack_id, well.well_number)
        wells.append(well)

    def remove_well_definition(self, rack_id: str, well_number: int) -> List[Well]:
        """ Removes existing well definition(s) in rack.wells with matching well_number """

        rack = self.racks[rack_id]
        wells = rack.wells
        # removes all existing wells with same well_number (go backwards to pop off the end):
        for i, existing_well in reversed(list(enumerate(wells))):
            if existing_well.well_number == well_number:
                wells.pop(i)
        return wells
    
    @property
    def carrier_well(self):
        if 'Carrier' in self.racks:
            carrier_well, _ = self.get_well_and_rack('Carrier', 1)
            return carrier_well

d2o = Solvent(name='D2O', fraction=1.0)
kcl0 = Solute(name='KCl', molecular_weight=74.55, concentration=0.1, units='M')
nacl0 = Solute(name='NaCl', molecular_weight=58.44, concentration=0.1, units='mg/mL')
kcl1 = Solute(name='KCl', molecular_weight=74.55, concentration=1.0, units='mg/L')
h2o = Solvent(name='H2O', fraction=1.0)
peptide = Solute(name='peptide', fraction=1e-3)

dbuffer = Composition(solvents=[d2o], solutes=[kcl0, nacl0])
hbuffer = Composition(solvents=[h2o], solutes=[kcl1])
water = Composition(solvents=[h2o])
dwater = Composition(solvents=[d2o])
peptide_solution = Composition(solvents=[h2o], solutes=[peptide])
dpeptide_solution = Composition(solvents=[d2o], solutes=[peptide])

mix_well = Well(rack_id='Mix', well_number=2, composition=dbuffer, volume=4.0)
mix_well.mix_with(2, hbuffer)

empty = Composition()
example_wells: List[Well] = [Well(rack_id='Stock', well_number=1, composition=dwater, volume=2.0),
                 Well(rack_id='Stock', well_number=3, composition=dwater, volume=8.0),
                 Well(rack_id='Stock', well_number=2, composition=hbuffer, volume=8.0),
                 Well(rack_id='Mix', well_number=1, composition=empty, volume=0.0),
#                 Well('Mix', 10, water, 6.0),
                 mix_well,
#                 Well('Solvent', 1, water, 200),
#                 Well('Samples', 1, peptide_solution, 2),
#                 Well('Samples', 2, dpeptide_solution, 2),
                 Well(rack_id='Solvent', well_number=2, composition=dbuffer, volume=200)]

if __name__ == '__main__':
    mix_well = Well(rack_id='Mix', well_number=2, composition=dbuffer, volume=4.0)
    mix_well.mix_with(2, hbuffer)
    print(mix_well.composition)
    print(kcl1.convert_units('nM'))


