from enum import Enum
from typing import Tuple

# Zones from Trilution LH Bed Layout
class Zone(str, Enum):
    SOLVENT = 'Solvent Zone'
    SAMPLE = 'Sample Zone'
    STOCK = 'Stock Zone'
    MIX = 'Mix Zone'
    INJECT = 'Injection Zone'

# Physical racks that are present
racks={'Solvent': {'columns': 3, 'rows': 1, 'max_volume': 700.0, 'min_volume': 10.0, 'style': 'grid'},
       'Samples': {'columns': 4, 'rows': 15, 'max_volume': 2, 'min_volume': 0.1, 'style': 'grid'},
       'Stock':   {'columns': 2, 'rows': 7, 'max_volume': 40, 'min_volume': 0.5, 'style': 'grid'},
       'Mix':     {'columns': 4, 'rows': 20, 'max_volume': 8.5, 'min_volume': 0.15, 'style': 'staggered'},
       'MTPlateTop': {'columns': 8, 'rows': 12, 'max_volume': 0.28, 'min_volume': 0.05, 'style': 'grid'},
       'MTPlateBottom': {'columns': 8, 'rows': 12, 'max_volume': 0.28, 'min_volume': 0.05, 'style': 'grid'},
    }

# Mapping from zones to racks. For convenience in following functions (does not have to be 1:1 mapping)
zone2rack = {Zone.SOLVENT: 'Solvent',
             Zone.SAMPLE: 'Samples',
             Zone.STOCK: 'Stock',
             Zone.MIX: 'Mix',
             Zone.INJECT: 'Inject'}

rack2zone = {v: k for k, v in zone2rack.items()}

def ZoneWell2LayoutWell(zone: Zone, well_number: str) -> Tuple[str, int]:
    """Translates Trilution (zone, well) specification to the GUI (rack, well) specification"""
    
    return zone2rack[zone], int(well_number)

def LayoutWell2ZoneWell(rack_id: str, well_number:int) -> Tuple[Zone, str]:
    """Translates GUI (rack, well) specification to Trilution (zone, well) specification"""
    
    return rack2zone[rack_id], f'{well_number}'

