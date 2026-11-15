"""The Revival Car page: profile, story, money totals and the build log timeline."""
from flask import Blueprint, render_template

from ..models import BuildLogEntry, Install, RevivalCar
from ..services.fund import fund_summary

bp = Blueprint("car", __name__, url_prefix="/revival-car")


def build_timeline():
    """
    Merge free-form build log notes and completed installs into one list,
    newest first. Each entry is a small dict so the template can tell the
    two kinds apart with entry.kind.
    """
    entries = [{"kind": "log", "date": e.happened_on, "item": e} for e in BuildLogEntry.query.all()]
    entries += [{"kind": "install", "date": i.installed_on, "item": i} for i in Install.query.all()]
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


@bp.route("/")
def index():
    car = RevivalCar.query.first()
    installs = Install.query.order_by(Install.installed_on.desc()).all()
    return render_template(
        "car/index.html",
        car=car,
        fund=fund_summary(),
        installs=installs,
        timeline=build_timeline(),
    )
