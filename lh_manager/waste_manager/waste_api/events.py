#import socketio as sio

from ...sio import socketio
from .waste import waste_layout

def trigger_waste_update(f):
    """Decorator that announces that layout has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_waste', {'msg': 'update_waste'}, include_self=True)
        waste_layout.save_waste()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap