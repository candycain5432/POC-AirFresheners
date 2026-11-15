"""Admin: meet drops. Add a meet (optionally sold online), mark sold out, delete."""
from flask import abort, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import MeetDrop
from ...services.clock import shop_today
from ...services.meets import create_meet, delete_meet, meet_status, set_meet_sold_out
from . import bp
from .forms import FormReader


def _meet_or_404(meet_id):
    meet = db.session.get(MeetDrop, meet_id)
    if meet is None:
        abort(404)
    return meet


@bp.route("/meets", methods=["GET", "POST"])
def meets():
    form = FormReader(request.form)
    if request.method == "POST":
        name = form.text("meet_name", "Meet name", max_len=120)
        when = form.date("meet_date", "Date")
        location = form.text("location", "Location", max_len=160)
        scent = form.text("scent_name", "Scent name", max_len=100)
        notes = form.text("scent_description", "Scent notes", required=False, max_len=250)
        quantity = form.integer("quantity", "Batch size", 1, 100000, required=False)
        sell_online = form.checkbox("sell_online")
        price = form.money("price", "Online price") if sell_online else None
        if not form.errors:
            create_meet(name, when, location, scent, notes, quantity, sell_online=sell_online,
                        price_cents=price or 1000)
            flash(f"Added {name}.", "success")
            return redirect(url_for("admin.meets"))
    else:
        form.values.setdefault("price", "10.00")
    today = shop_today()
    all_meets = MeetDrop.query.order_by(MeetDrop.meet_date.desc()).all()
    return render_template("admin/meets.html", meets=all_meets, form=form, today=today,
                           statuses={m.id: meet_status(m, today) for m in all_meets}), \
        (400 if form.errors else 200)


@bp.route("/meets/<int:meet_id>/sold-out", methods=["POST"])
def meet_sold_out(meet_id):
    meet = _meet_or_404(meet_id)
    sold_out = request.form.get("sold_out") == "1"
    set_meet_sold_out(meet, sold_out)
    flash(f"{meet.meet_name} marked {'sold out' if sold_out else 'back in stock'}.", "success")
    return redirect(url_for("admin.meets"))


@bp.route("/meets/<int:meet_id>/delete", methods=["POST"])
def meet_delete(meet_id):
    meet = _meet_or_404(meet_id)
    delete_meet(meet)
    flash("Meet deleted.", "success")
    return redirect(url_for("admin.meets"))
