from flask import Blueprint

blueprint = Blueprint('waste_manager', __name__)

from . import endpoints