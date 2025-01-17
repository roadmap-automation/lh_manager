from flask import Flask, render_template, redirect
from .gui_api import gui_blueprint
from .lh_api import lh_blueprint
from .sio import socketio
from .material_db import blueprint as material_db_blueprint
from .autocontrol.autocontrol import launch_autocontrol_interface
from .autocontrol.autocontrol_api import autocontrol_blueprint
import liquid_handler_api.app_config as app_config

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

    config = app_config.config
    config.stage_names = ['methods']

    launch_autocontrol_interface(poll_delay=5)
    socketio.run(app, host='localhost', port=5001, debug=False)

    #app.run(host='127.0.0.1', port=5001, debug=True)