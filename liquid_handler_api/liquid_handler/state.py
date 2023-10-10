"""Liquid handler state initialization"""
import json
import os
from dataclasses import asdict
from .samplecontainer import SampleContainer
from .samplelist import example_sample_list, StageName
from . import formulation
from .layoutmap import racks
from .bedlayout import LHBedLayout, example_wells
from .items import Item
from ..app_config import parser

LOG_PATH = 'persistent_state'
LAYOUT_LOG = os.path.join(LOG_PATH, 'layout.json')
SAMPLES_LOG = os.path.join(LOG_PATH, 'samples.json')

def load_state():

    layout, samples = None, None

    if os.path.exists(LAYOUT_LOG):
        layout = LHBedLayout(**json.load(open(LAYOUT_LOG, 'r')))
    
    if os.path.exists(SAMPLES_LOG):
        samples = SampleContainer(**json.load(open(SAMPLES_LOG, 'r')))

    return layout, samples

def make_persistent_dir():
    if not os.path.exists(LOG_PATH):
        os.mkdir(LOG_PATH)
    
def save_layout():
    make_persistent_dir()
    json.dump(asdict(layout), open(LAYOUT_LOG, 'w'))

def save_samples():
    make_persistent_dir()
    json.dump(asdict(samples), open(SAMPLES_LOG, 'w'))

if not parser.parse_args().noload:
    print('loading state!')
    layout, samples = load_state()
else:
    layout, samples = None, None

if samples is None:

    ## ======= Initialize samples =========
    # samples is sent to the GUI
    samples = SampleContainer()

    # TODO: remove for production
    for example_sample in example_sample_list:
        samples.addSample(example_sample)

    ## ======= Initialize bed layout =========
if layout is None:
    # layout is sent to the GUI
    layout = LHBedLayout(racks={})
    for name, rack in racks.items():
        layout.add_rack_from_dict(name, rack)

    # TODO: remove for production
    for well in example_wells:
        layout.add_well_to_rack(well.rack_id, well)

samples.dryrun_queue.add_item(Item(example_sample_list[9].id, StageName.PREP))