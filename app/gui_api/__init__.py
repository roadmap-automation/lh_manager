from flask import Blueprint

gui_blueprint = Blueprint('gui', __name__)

from . import endpoints