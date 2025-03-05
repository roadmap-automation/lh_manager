#import socketio as sio

from ...sio import socketio

def trigger_waste_update(f):
    """Decorator that announces that layout has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_waste', {'msg': 'update_waste'}, include_self=True)
        return ret_val
    wrap.__name__ = f.__name__
    return wrap