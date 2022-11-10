from sio import socketio

def trigger_layout_update(f):
    """Decorator that announces that layout has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_layout', {'msg': 'update_layout'})
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_samples_update(f):
    """Decorator that announces that samples has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_samples', {'msg': 'update_samples'})
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

def trigger_sample_status_update(f):
    """Decorator that announces that samples has changed"""
    def wrap(*args, **kwargs):
        ret_val = f(*args, **kwargs)
        socketio.emit('update_sample_status', {'msg': 'update_sample_status'})
        return ret_val
    wrap.__name__ = f.__name__
    return wrap

@socketio.on('layout_update_received')
def layout_update_received():
    print('received layout update')

@socketio.on('samples_update_received')
def samples_update_received():
    print('received samples update')

@socketio.on('sample_status_update_received')
def samples_update_received():
    print('received sample status update')
