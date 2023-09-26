"""Liquid handler state initialization"""
from .samplelist import SampleContainer, example_sample_list
from . import formulation
from .layoutmap import racks
from .bedlayout import LHBedLayout, example_wells

## ======= Initialize samples =========
# samples is sent to the GUI
samples = SampleContainer()

# TODO: remove for production
for example_sample in example_sample_list:
    samples.addSample(example_sample)

## ======= Initialize bed layout =========

# layout is sent to the GUI
layout = LHBedLayout(racks={})
for name, rack in racks.items():
    layout.add_rack_from_dict(name, rack)

# TODO: remove for production
for well in example_wells:
    layout.add_well_to_rack(well.rack_id, well)