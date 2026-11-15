"""Admin: vote rounds. Build a draft (parts + tiers), open it, extend it, close it."""
from flask import abort, flash, redirect, render_template, request, url_for

from ...extensions import db
from ...models import PartOption, PartTier, VoteRound
from ...models.voting import TIER_LABELS, TIER_LEVELS
from ...services import voting
from ...services.clock import local_to_utc, utc_to_local
from . import bp
from .forms import FormReader


def _get(model, object_id):
    obj = db.session.get(model, object_id)
    if obj is None:
        abort(404)
    return obj


def _back(round_id):
    return redirect(url_for("admin.round_detail", round_id=round_id))


@bp.route("/rounds", methods=["GET", "POST"])
def rounds():
    voting.close_expired_rounds()
    form = FormReader(request.form)
    if request.method == "POST":
        title = form.text("title", "Title", max_len=120)
        description = form.text("description", "Description", required=False, max_len=1000)
        if not form.errors:
            round_ = voting.create_round(title, description)
            flash("Draft created. Now add the parts and tiers.", "success")
            return _back(round_.id)
    all_rounds = VoteRound.query.order_by(VoteRound.id.desc()).all()
    return render_template("admin/rounds.html", rounds=all_rounds, form=form), (400 if form.errors else 200)


@bp.route("/rounds/<int:round_id>")
def round_detail(round_id):
    voting.close_expired_rounds()
    round_ = _get(VoteRound, round_id)
    return render_template(
        "admin/round_detail.html", round=round_, results=voting.round_results(round_),
        tier_levels=[(level, TIER_LABELS[level]) for level in TIER_LEVELS],
        closes_local=utc_to_local(round_.closes_at),
    )


@bp.route("/rounds/<int:round_id>/options", methods=["POST"])
def round_add_option(round_id):
    round_ = _get(VoteRound, round_id)
    form = FormReader(request.form)
    name = form.text("name", "Part name", max_len=120)
    description = form.text("description", "Description", required=False, max_len=300)
    if form.errors:
        flash(" ".join(form.errors.values()), "error")
    else:
        try:
            voting.add_option(round_, name, description)
        except voting.VoteError as error:
            flash(str(error), "error")
    return _back(round_id)


@bp.route("/options/<int:option_id>/tiers", methods=["POST"])
def round_add_tier(option_id):
    option = _get(PartOption, option_id)
    form = FormReader(request.form)
    level = form.choice("level", "Tier", TIER_LEVELS)
    goal = form.money("goal", "Goal")
    description = form.text("description", "Description", required=False, max_len=200)
    if form.errors:
        flash(" ".join(form.errors.values()), "error")
    else:
        try:
            voting.add_tier(option, level, goal, description)
        except voting.VoteError as error:
            flash(str(error), "error")
    return _back(option.round_id)


@bp.route("/options/<int:option_id>/delete", methods=["POST"])
def round_delete_option(option_id):
    option = _get(PartOption, option_id)
    round_id = option.round_id
    try:
        voting.delete_option(option)
    except voting.VoteError as error:
        flash(str(error), "error")
    return _back(round_id)


@bp.route("/tiers/<int:tier_id>/delete", methods=["POST"])
def round_delete_tier(tier_id):
    tier = _get(PartTier, tier_id)
    round_id = tier.option.round_id
    try:
        voting.delete_tier(tier)
    except voting.VoteError as error:
        flash(str(error), "error")
    return _back(round_id)


@bp.route("/rounds/<int:round_id>/open", methods=["POST"])
def round_open(round_id):
    round_ = _get(VoteRound, round_id)
    form = FormReader(request.form)
    closes_local = form.local_datetime("closes_at", "Close time")
    if form.errors:
        flash(" ".join(form.errors.values()), "error")
        return _back(round_id)
    try:
        voting.open_round(round_, local_to_utc(closes_local))
        flash("Voting is open!", "success")
    except voting.VoteError as error:
        flash(str(error), "error")
    return _back(round_id)


@bp.route("/rounds/<int:round_id>/close-time", methods=["POST"])
def round_close_time(round_id):
    round_ = _get(VoteRound, round_id)
    form = FormReader(request.form)
    closes_local = form.local_datetime("closes_at", "Close time")
    if not form.errors:
        try:
            voting.set_close_time(round_, local_to_utc(closes_local))
            flash("Close time updated.", "success")
        except voting.VoteError as error:
            flash(str(error), "error")
    else:
        flash(" ".join(form.errors.values()), "error")
    return _back(round_id)


@bp.route("/rounds/<int:round_id>/close", methods=["POST"])
def round_close(round_id):
    round_ = _get(VoteRound, round_id)
    if round_.status != "open":
        flash("Only an open round can be closed.", "error")
        return _back(round_id)
    winner = voting.close_round(round_)
    if winner:
        flash(f"Round closed. Winner: {winner.option.name} ({winner.level_label}).", "success")
    else:
        flash("Round closed. Nobody voted, so no goal was added.", "success")
    return _back(round_id)


@bp.route("/rounds/<int:round_id>/delete", methods=["POST"])
def round_delete(round_id):
    round_ = _get(VoteRound, round_id)
    try:
        voting.delete_round(round_)
        flash("Draft deleted.", "success")
    except voting.VoteError:
        flash("Only drafts can be deleted. Open and closed rounds are kept for the record.", "error")
        return _back(round_id)
    return redirect(url_for("admin.rounds"))
