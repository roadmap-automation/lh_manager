from flask import Flask, render_template, redirect
from .gui_api import gui_blueprint
from .lh_api import lh_blueprint
from .nice_api import nice_blueprint
from .sio import socketio
from .liquid_handler.autocontrol import init_devices

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
app.register_blueprint(nice_blueprint)
app.register_blueprint(lh_blueprint)
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
    init_devices()
    socketio.run(app, host='localhost', port=5002, debug=True)

    #app.run(host='127.0.0.1', port=5001, debug=True)