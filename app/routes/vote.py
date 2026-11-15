"""
Voting pages.

    GET  /vote/                  the ballot for the open round (+ past rounds)
    POST /vote/                  cast a vote with a freshener code
    GET  /vote/rounds/<id>       results for one round (yours highlighted)

The rules (who may vote, closing rounds, winners) live in services/voting.py.
Code guessing is blocked by services/rate_limit.py.
"""
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from ..extensions import db
from ..models import FundingGoal, VoteRound
from ..services.codes import find_code, format_code, normalize_code
from ..services.rate_limit import client_ip, minutes_locked, record_failure
from ..services.voting import (
    VoteError, cast_vote, close_expired_rounds, closed_rounds, current_round, find_tier_in_round,
    is_open, round_results, seconds_left, split_duration,
)

bp = Blueprint("vote", __name__, url_prefix="/vote")


def _remember_vote(round_, tier):
    """Remember (in this browser only) what was voted, to highlight it on the results page."""
    votes = dict(session.get("my_votes", {}))
    votes[str(round_.id)] = tier.id
    session["my_votes"] = votes


def _render_ballot(round_, form, errors, status=200):
    left = seconds_left(round_) if round_ else None
    return render_template(
        "vote/index.html",
        round=round_,
        seconds_left=left,
        countdown=split_duration(left),
        form=form,
        errors=errors,
        past_rounds=closed_rounds(),
    ), status


@bp.route("/", methods=["GET", "POST"])
def index():
    close_expired_rounds()
    round_ = current_round()

    # A QR code on a freshener links to /vote/?code=XXXX: pre-fill the box.
    # (Only formatting here: the code is checked when the form is submitted.)
    form = {"code": format_code(normalize_code(request.args.get("code", ""))), "tier_id": ""}
    errors = {}

    if request.method == "GET":
        return _render_ballot(round_, form, errors)

    # ---------------- POST: cast a vote ----------------
    form["code"] = request.form.get("code", "").strip()[:30]
    form["tier_id"] = request.form.get("tier_id", "")

    if round_ is None or not is_open(round_):
        flash("This round has closed. Check the results below.", "error")
        return redirect(url_for("vote.index"))

    # 1. Locked out for guessing? Check BEFORE looking at the code.
    ip = client_ip()
    wait = minutes_locked(ip)
    if wait:
        errors["code"] = (f"Too many wrong codes from this connection. "
                          f"Please wait about {wait} minute{'s' if wait != 1 else ''} and try again.")
        return _render_ballot(round_, form, errors, status=429)

    # 2. A choice must be picked, and it must belong to THIS round.
    tier = find_tier_in_round(round_, form["tier_id"])
    if tier is None:
        errors["tier_id"] = "Pick one part and budget to vote for."

    # 3. The code must exist. Wrong codes count toward the lockout.
    code = find_code(form["code"])
    if code is None:
        errors["code"] = "We couldn't find that code. Check the tag on your freshener and try again."
        record_failure(ip)

    if errors:
        return _render_ballot(round_, form, errors, status=400)

    # 4. Cast it (refuses a second vote from the same code).
    try:
        cast_vote(round_, code, tier)
    except VoteError as error:
        errors["code"] = str(error)
        return _render_ballot(round_, form, errors, status=409)

    _remember_vote(round_, tier)
    flash(f"Vote locked in: {tier.option.name}, {tier.level_label.lower()}. Thanks for building with us!", "success")
    return redirect(url_for("vote.results", round_id=round_.id))


@bp.route("/rounds/<int:round_id>")
def results(round_id):
    close_expired_rounds()
    round_ = db.session.get(VoteRound, round_id)
    if round_ is None or round_.status == "draft":
        abort(404)
    left = seconds_left(round_)
    results_data = round_results(round_)
    winner_goal = None
    if round_.status == "closed":
        # Once closed, the official winner (ties go to the cheaper tier) is the one highlighted.
        results_data["leading_tier_id"] = round_.winning_tier_id
        if round_.winning_tier_id:
            winner_goal = FundingGoal.query.filter_by(tier_id=round_.winning_tier_id).first()
    return render_template(
        "vote/results.html",
        round=round_,
        results=results_data,
        winner_goal=winner_goal,
        my_tier_id=session.get("my_votes", {}).get(str(round_.id)),
        open_now=is_open(round_),
        seconds_left=left,
        countdown=split_duration(left),
    )
