from sio import socketio
import os
import json
from liquid_handler.state import layout, samples
from dataclasses import asdict

LAYOUT_LOG = 'persistent_state/layout.json'
SAMPLES_LOG = 'persistent_state/samples.json'

@socketio.on('update_layout')
def layout_update_received():
    #print('dumping layout')
    json.dump(asdict(layout), open(LAYOUT_LOG, 'w'))

@socketio.on('update_sample_status')
def samples_update_received():
    #print('dumping samples')
    json.dump(asdict(samples), open(SAMPLES_LOG, 'w'))

def trigger_layout_update(f):
    """Decorator that announces that layout has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_layout', {'msg': 'update_layout'}, include_self=True)
        layout_update_received()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_samples_update(f):
    """Decorator that announces that samples has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_samples', {'msg': 'update_samples'}, include_self=True)
        samples_update_received()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_sample_status_update(f):
    """Decorator that announces that samples has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_sample_status', {'msg': 'update_sample_status'}, include_self=True)
        samples_update_received()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

