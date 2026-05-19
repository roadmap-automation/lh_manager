"""Liquid handler state initialization"""
import json
import logging
import os
from pathlib import Path
from .samplecontainer import SampleContainer
from .samplelist import example_sample_list
from . import qcmd, dilution, injectionmethods, qcmdmethods, roadmapmethods
from .items import Item
from .devices import device_manager
from .notify import notifier
from ..app_config import parser, config

LOG_PATH, SAMPLES_LOG, DEVICES_LOG = config.persistent_path, config.samples_path, config.devices_path

def load_state():

    samples = None

    if not parser.parse_args().noload_samples:
        if os.path.exists(SAMPLES_LOG):
            samples = SampleContainer(**json.load(open(SAMPLES_LOG, 'r')))

    if os.path.exists(DEVICES_LOG):
        device_data = json.load(open(DEVICES_LOG, 'r'))
        for device in device_manager.device_list:
            update = device_data.get(device.device_name, {})
            if update:
                device = device.model_copy(update=update)
                device_manager.register(device)

    return samples

def make_persistent_dir():
    if not os.path.exists(LOG_PATH):
        os.mkdir(LOG_PATH)
    
def save_samples():
    make_persistent_dir()
    with open(SAMPLES_LOG, 'w') as f:
        f.write(samples.model_dump_json(indent=2))

def save_devices():
    make_persistent_dir()
    with open(DEVICES_LOG, 'w') as f:
        f.write(json.dumps(device_manager.get_all_schema(), indent=2))

logging.info('loading state!')
samples = load_state()

notifier.load_config(config.notify_path)
notifier.connect()

if samples is None:

    ## ======= Initialize samples =========
    # samples is sent to the GUI
    samples = SampleContainer(n_channels=parser.parse_args().channels)

    # TODO: remove for production
    for example_sample in example_sample_list:
        samples.addSample(example_sample)

samples.n_channels = parser.parse_args().channels

# layout is now owned by gilson_lh device service; lh_manager no longer holds it
layout = None

#samples.dryrun_queue.add_item(Item(example_sample_list[9].id, StageName.PREP))
#example_sample_list[1].NICE_uuid = 'test_NICE_uuid'
#samples.archiveSample(example_sample_list[1])