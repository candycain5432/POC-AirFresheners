"""Home page. Stage 1 shows a simple database check; the real page comes in stage 2."""
from flask import Blueprint, render_template

from ..models import FreshenerCode, MeetDrop, Order, Product, RevivalCar, VoteRound

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    # Temporary stage-1 page: count rows so you can confirm the seed worked.
    counts = {
        "Products": Product.query.count(),
        "Orders": Order.query.count(),
        "Freshener codes": FreshenerCode.query.count(),
        "Vote rounds": VoteRound.query.count(),
        "Meet drops": MeetDrop.query.count(),
    }
    car = RevivalCar.query.first()
    return render_template("main/stage1.html", counts=counts, car=car)
