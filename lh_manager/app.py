import datetime
from flask import Flask, render_template, redirect
from logging.config import dictConfig

# config contains logging configuration and should be imported first
from .app_config import config

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'stream': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://sys.stdout',
        'level': 'INFO',
        'formatter': 'default'
    },
    'file': {
        'class': 'logging.FileHandler',
        'filename': config.log_path / (datetime.datetime.now().strftime('%Y%m%d%H%M%S') + '_manager_log.txt'),
        'level': 'INFO',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['stream', 'file']
    }
})

from .gui_api import gui_blueprint
from .lh_api import lh_blueprint
from .sio import socketio
from .material_db import blueprint as material_db_blueprint
from .waste_manager.waste_api import blueprint as waste_blueprint
from .autocontrol.autocontrol import launch_autocontrol_interface
from .autocontrol.autocontrol_api import autocontrol_blueprint

import mimetypes
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/svg+xml", ".svg")

app = Flask(__name__, static_folder='static')
app.config['JSON_SORT_KEYS'] = False

app.register_blueprint(gui_blueprint)
app.register_blueprint(lh_blueprint)
app.register_blueprint(autocontrol_blueprint)
app.register_blueprint(material_db_blueprint)
app.register_blueprint(waste_blueprint)
socketio.init_app(app)

#@app.route('/')
#def root():
#    return render_template('index.html')

@app.route('/')
def root():
    return redirect('/static/dist/index.html')

@app.route('/test_emit/')
def test_emit():
    return render_template('test_emit.html')

if __name__ == '__main__':

    config.stage_names = ['methods']

    launch_autocontrol_interface(poll_delay=5)
    socketio.run(app, host='localhost', port=5001, debug=False)

    #app.run(host='127.0.0.1', port=5001, debug=True)