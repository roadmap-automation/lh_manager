from flask import Blueprint

autocontrol_blueprint = Blueprint('autocontrol', __name__)

from . import endpoints