"""The Garage: placeholder until stage 5 builds the real page."""
from flask import Blueprint, render_template

bp = Blueprint("garage", __name__, url_prefix="/garage")


@bp.route("/")
def index():
    return render_template("coming_soon.html", title="The Garage", stage=5)
