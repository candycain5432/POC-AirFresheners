"""Admin: Garage moderation (hide/show cars) and Car of the Month."""
from flask import abort, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import CarOfTheMonth, GarageMember
from ...services.clock import shop_today
from ...services.garage import current_car_of_month, feature_member, set_hidden
from . import bp
from .forms import FormReader


def _member_or_404(member_id):
    member = db.session.get(GarageMember, member_id)
    if member is None:
        abort(404)
    return member


@bp.route("/garage")
def garage():
    return render_template(
        "admin/garage.html",
        members=GarageMember.query.order_by(GarageMember.created_at.desc()).all(),
        current=current_car_of_month(),
        history=CarOfTheMonth.query.order_by(CarOfTheMonth.created_at.desc()).limit(12).all(),
        this_month=shop_today().strftime("%Y-%m"),
    )


@bp.route("/garage/<int:member_id>/hide", methods=["POST"])
def garage_hide(member_id):
    member = _member_or_404(member_id)
    hidden = request.form.get("hidden") == "1"
    set_hidden(member, hidden)
    flash(f"{member.car_name} is now {'hidden' if hidden else 'visible'}.", "success")
    return redirect(url_for("admin.garage"))


@bp.route("/garage/<int:member_id>/feature", methods=["POST"])
def garage_feature(member_id):
    member = _member_or_404(member_id)
    form = FormReader(request.form)
    month = form.text("month", "Month", max_len=7)
    blurb = form.text("blurb", "Blurb", required=False, max_len=300)
    if member.is_hidden:
        form.errors["member"] = "Unhide this car before featuring it."
    if len(month) != 7 or month[4] != "-":
        form.errors["month"] = "Month must look like 2026-11."
    if form.errors:
        flash(" ".join(form.errors.values()), "error")
    else:
        feature_member(member, month, blurb)
        flash(f"{member.car_name} is Car of the Month!", "success")
    return redirect(url_for("admin.garage"))
