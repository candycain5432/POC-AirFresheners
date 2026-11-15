"""Admin: the fund ledger and manual adjustments (cash sales, donations, corrections)."""
from flask import flash, redirect, render_template, request, url_for

from ...services.fund import add_manual_entry, fund_summary, recent_entries
from . import bp
from .forms import FormReader


@bp.route("/fund", methods=["GET", "POST"])
def fund():
    form = FormReader(request.form)
    if request.method == "POST":
        amount = form.money("amount", "Amount", allow_negative=True)
        note = form.text("note", "Note", max_len=200)
        if amount == 0:
            form.errors["amount"] = "Amount can't be zero."
        if not form.errors:
            add_manual_entry(amount, note)
            flash("Fund updated.", "success")
            return redirect(url_for("admin.fund"))
    return render_template("admin/fund.html", form=form, fund=fund_summary(), entries=recent_entries()), \
        (400 if form.errors else 200)
