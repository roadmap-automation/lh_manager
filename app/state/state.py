from liquid_handler.samplelist import SampleContainer, example_sample_list
from liquid_handler.layoutmap import racks
from liquid_handler.bedlayout import LHBedLayout, example_wells

## ======= Initialize samples =========
samples = SampleContainer()

# TODO: remove for production
for example_sample in example_sample_list:
    samples.addSample(example_sample)

## ======= Initialize bed layout =========

layout = LHBedLayout(racks={})
for name, rack in racks.items():
    layout.add_rack_from_dict(name, rack)

# TODO: remove for production
for well in example_wells:
    layout.add_well_to_rack(well.rack_id, well)