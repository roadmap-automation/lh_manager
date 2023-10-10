from sio import socketio
from liquid_handler.state import save_layout, save_samples

def trigger_layout_update(f):
    """Decorator that announces that layout has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_layout', {'msg': 'update_layout'}, include_self=True)
        save_layout()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_run_queue_update(f):
    """Decorator that announces that the run queue has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_run_queue', {'msg': 'update_run_queue'}, include_self=True)
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_samples_update(f):
    """Decorator that announces that samples has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_samples', {'msg': 'update_samples'}, include_self=True)
        save_samples()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_sample_status_update(f):
    """Decorator that announces that samples has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_sample_status', {'msg': 'update_sample_status'}, include_self=True)
        save_samples()
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

