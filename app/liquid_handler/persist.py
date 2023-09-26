import json
from .state import layout, samples
from dataclasses import asdict
from sio import socketio

LAYOUT_LOG = '../../persistent_state/layout.json'
SAMPLES_LOG = '../../persistent_state/samples.json'

@socketio.on('update_layout')
def layout_update_received():
    print('dumping layout')
    json.dump(open(LAYOUT_LOG, 'w'), asdict(layout))

@socketio.on('update_samples')
@socketio.on('update_sample_status')
def samples_update_received():
    print('dumping samples')
    json.dump(open(SAMPLES_LOG, 'w'), asdict(samples))

