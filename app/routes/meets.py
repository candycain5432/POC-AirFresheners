"""Meet Drops: placeholder until stage 6 builds the real page."""
from flask import Blueprint, render_template

bp = Blueprint("meets", __name__, url_prefix="/meets")


@bp.route("/")
def index():
    return render_template("coming_soon.html", title="Meet Drops", stage=6)
