"""
Meet Drops.

    GET /meets/              next meet, upcoming meets, past meets
    GET /meets/<id>.ics      "Add to calendar" file for one meet

The rules (status, dates, calendar format) live in services/meets.py.
"""
import re

from flask import Blueprint, Response, abort, render_template, url_for

from ..extensions import db
from ..models import MeetDrop
from ..services.meets import meet_ics, meet_status, past_meets, relative_day, shop_today, upcoming_meets

bp = Blueprint("meets", __name__, url_prefix="/meets")


@bp.route("/")
def index():
    today = shop_today()
    upcoming = upcoming_meets(today)
    past = past_meets(today)
    # Work out each meet's status and "in 3 weeks" text once, here, so the
    # template stays simple.
    info = {m.id: {"status": meet_status(m, today), "when": relative_day(m.meet_date, today)}
            for m in upcoming + past}
    return render_template(
        "meets/index.html",
        next_meet=upcoming[0] if upcoming else None,
        upcoming=upcoming[1:],
        past=past,
        info=info,
        days_to_next=(upcoming[0].meet_date - today).days if upcoming else None,
    )


@bp.route("/<int:meet_id>.ics")
def calendar(meet_id):
    meet = db.session.get(MeetDrop, meet_id)
    if meet is None:
        abort(404)
    page_url = url_for("meets.index", _external=True) + f"#meet-{meet.id}"
    # A safe file name: letters, numbers and dashes only.
    filename = re.sub(r"[^a-z0-9]+", "-", meet.meet_name.lower()).strip("-") or "meet"
    return Response(
        meet_ics(meet, page_url),
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}.ics"'},
    )
