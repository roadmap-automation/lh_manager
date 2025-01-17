"""Waste manager initialization"""
import json
import os

from dataclasses import dataclass, field

from ..liquid_handler.bedlayout import LHBedLayout, Rack, Well, Composition
from ..liquid_handler.state import make_persistent_dir
from ..app_config import parser, config

WASTE_LOG = config.log_path / 'waste.json'
WASTE_RACK = 'waste'

@dataclass
class WasteItem:

    composition: Composition = field(default_factory=Composition())
    volume: float = 0.0

def load_waste():

    layout = None

    if os.path.exists(WASTE_LOG):
        layout = LHBedLayout(**json.load(open(WASTE_LOG, 'r')))

    return layout

def save_waste():
    make_persistent_dir()
    with open(WASTE_LOG, 'w') as f:
        f.write(waste_layout.model_dump_json(indent=2))

waste_layout = load_waste()

 ## ======= Initialize bed layout =========
if waste_layout is None:

    print('Creating new waste layout...')

    # Single 10L waste bottle for now
    waste_rack = Rack(columns=1,
                      rows=1,
                      max_volume=10e3,
                      wells=[])
    # layout is sent to the GUI
    waste_layout = LHBedLayout(racks={WASTE_RACK: waste_rack})

    # add waste bottles
    carboy = Well(rack_id='',
                  well_number=1,
                  composition=Composition(),
                  volume=0.0)
    
    waste_layout.add_well_to_rack(WASTE_RACK, carboy)    

    save_waste()
