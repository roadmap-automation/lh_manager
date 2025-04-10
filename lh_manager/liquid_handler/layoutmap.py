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
racks={'Carrier': {'columns': 1, 'rows': 1, 'max_volume': 2000.0, 'min_volume': 300.0, 'style': 'grid', 'height': 200, 'width': 200, 'x_translate': 0, 'y_translate': 100, 'shape': 'rect', 'editable': True},
       'Rinse': {'columns': 1, 'rows': 1, 'max_volume': 1000.0, 'min_volume': 300.0, 'style': 'grid', 'height': 200, 'width': 200, 'x_translate': 0, 'y_translate': 300, 'shape': 'rect', 'editable': True},
       'Solvent': {'columns': 3, 'rows': 1, 'max_volume': 700.0, 'min_volume': 10.0, 'style': 'grid', 'height': 200, 'width': 900, 'x_translate': 200, 'y_translate': 0, 'shape': 'rect', 'editable': True},
       'Samples': {'columns': 4, 'rows': 15, 'max_volume': 2, 'min_volume': 0.1, 'style': 'grid', 'height': 800, 'width': 300, 'x_translate': 200, 'y_translate': 200, 'shape': 'circle', 'editable': True},
       'Stock':   {'columns': 2, 'rows': 7, 'max_volume': 40, 'min_volume': 0.5, 'style': 'grid', 'height': 800, 'width': 300, 'x_translate': 500, 'y_translate': 200, 'shape': 'circle', 'editable': True},
       'Mix':     {'columns': 4, 'rows': 20, 'max_volume': 8.5, 'min_volume': 0.2, 'style': 'staggered', 'height': 800, 'width': 300, 'x_translate': 800, 'y_translate': 200, 'shape': 'circle', 'editable': True},
       #'MTPlateTop': {'columns': 6, 'rows': 8, 'max_volume': 2.0, 'min_volume': 0.05, 'style': 'grid', 'height': 400, 'width': 300, 'x_translate': 900, 'y_translate': 200, 'shape': 'rect'},
       #'MTPlateBottom': {'columns': 6, 'rows': 8, 'max_volume': 2.0, 'min_volume': 0.05, 'style': 'grid', 'height': 400, 'width': 300, 'x_translate': 900, 'y_translate': 600, 'shape': 'rect'},
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
    
    if zone in zone2rack:
        return zone2rack[zone], int(well_number)
    else:
        return zone, int(well_number)

def LayoutWell2ZoneWell(rack_id: str, well_number:int) -> Tuple[Zone, str]:
    """Translates GUI (rack, well) specification to Trilution (zone, well) specification"""

    if rack_id in rack2zone:
        return rack2zone[rack_id], f'{well_number}'
    
    else:
        return rack_id, f'{well_number}'

