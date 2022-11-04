from flask import Flask, render_template
from gui_api import gui_blueprint
from lh_api import lh_blueprint

app = Flask(__name__)

app.register_blueprint(gui_blueprint)
app.register_blueprint(lh_blueprint)
#socketio = SocketIO(app)

@app.route('/')
def root():
    return render_template('index.html')

if __name__ == '__main__':
    #socketio.run(app, host='127.0.0.1', port=5001, debug=True)

    app.run(host='127.0.0.1', port=5001, debug=True)