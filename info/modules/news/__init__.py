from flask import Blueprint
detail_blu = Blueprint("detail", __name__, url_prefix="/news")
from .views import *