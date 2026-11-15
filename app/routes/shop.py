"""Shop: placeholder until stage 3 builds the real page."""
from flask import Blueprint, render_template

bp = Blueprint("shop", __name__, url_prefix="/shop")


@bp.route("/")
def index():
    return render_template("coming_soon.html", title="Shop", stage=3)
