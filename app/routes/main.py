"""Home page: tagline, Revival Car progress bar, current vote, shop, latest install video."""
from flask import Blueprint, render_template

from ..models import CarOfTheMonth, Install, RevivalCar, VoteRound
from ..services.fund import fund_summary

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    car = RevivalCar.query.first()
    latest_install = Install.query.order_by(Install.installed_on.desc()).first()
    open_round = VoteRound.query.filter_by(status="open").order_by(VoteRound.opened_at.desc()).first()
    car_of_month = CarOfTheMonth.query.order_by(CarOfTheMonth.created_at.desc()).first()
    return render_template(
        "main/home.html",
        car=car,
        fund=fund_summary(),
        latest_install=latest_install,
        open_round=open_round,
        car_of_month=car_of_month,
    )
