from flask import Blueprint

lh_blueprint = Blueprint('liquid_handler', __name__)

from . import endpoints