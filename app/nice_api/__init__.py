from flask import Blueprint

nice_blueprint = Blueprint('nice', __name__)

from . import endpoints