from flask import Flask, render_template, redirect
from .lh_api import lh_blueprint
from .sio import socketio

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

app.register_blueprint(lh_blueprint)
socketio.init_app(app)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)

    #app.run(host='127.0.0.1', port=5001, debug=True)