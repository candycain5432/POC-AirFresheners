"""Voting: placeholder until stage 4 builds the real page."""
from flask import Blueprint, render_template

bp = Blueprint("vote", __name__, url_prefix="/vote")


@bp.route("/")
def index():
    return render_template("coming_soon.html", title="Voting", stage=4)
