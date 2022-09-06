from flask import Flask
import numpy as np
import matplotlib.pyplot as plt
import mpld3


app = Flask(__name__)

@app.route('/<int:number>/', methods=['GET', 'POST'])
@app.route('/<float:number>/', methods=['GET', 'POST'])
def plot(number):
    x = np.linspace(-2 * np.pi, 2 * np.pi, 101)
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    ax.plot(x, np.sin(number * x), label='sine wave')
    ax.legend()
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    return mpld3.fig_to_html(fig)

@app.route('/hello/', methods=['GET', 'POST'])
def welcome():
    return "Hello World!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)