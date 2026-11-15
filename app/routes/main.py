"""Home page: hero + funding, the open vote, featured products, how it works, latest install."""
from flask import Blueprint, render_template

from ..models import CarOfTheMonth, Install, RevivalCar
from ..services.catalog import featured_products, lowest_price_cents
from ..services.fund import fund_summary
from ..services.voting import current_round, round_results, seconds_left, split_duration

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    open_round = current_round()
    left = seconds_left(open_round)
    return render_template(
        "main/home.html",
        car=RevivalCar.query.first(),
        fund=fund_summary(),
        open_round=open_round,
        results=round_results(open_round) if open_round else None,
        seconds_left=left,
        countdown=split_duration(left),
        featured=featured_products(4),
        from_price=lowest_price_cents(),
        latest_install=Install.query.order_by(Install.installed_on.desc()).first(),
        car_of_month=CarOfTheMonth.query.order_by(CarOfTheMonth.created_at.desc()).first(),
    )
