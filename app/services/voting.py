"""
Vote rounds: which round is open, how much time is left, the results,
casting a vote, and closing a round (the winner becomes a funding goal).

Results are counted per ballot line (a part + tier, e.g. "Seats, mid-range"),
and also added up per part so the page can show both.
"""
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import PartTier, Vote, VoteRound
from ..models._common import utcnow
from .fund import add_goal


def current_round():
    """The open round, or None. (If several are open, the newest wins.)"""
    return VoteRound.query.filter_by(status="open").order_by(VoteRound.opened_at.desc()).first()


def seconds_left(round_):
    """Whole seconds until the round closes; 0 if past; None if no close time is set."""
    if round_ is None or round_.closes_at is None:
        return None
    return max(0, int((round_.closes_at - utcnow()).total_seconds()))


def split_duration(seconds):
    """123456 -> {"days": 1, "hours": 10, "minutes": 17, "seconds": 36}"""
    seconds = seconds or 0
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    return {"days": days, "hours": hours, "minutes": minutes, "seconds": secs}


def _percent(part, whole):
    return round(100 * part / whole) if whole else 0


def round_results(round_):
    """
    Count the votes in one query and shape them for templates:

    {"total": 61,
     "options": [{"option": <PartOption>, "votes": 32, "percent": 52,
                  "tiers": [{"tier": <PartTier>, "votes": 8, "percent": 13}, ...]}, ...],
     "leading_tier_id": 17}
    """
    # SELECT tier_id, COUNT(*) FROM vote WHERE round_id = ? GROUP BY tier_id
    rows = (db.session.query(Vote.tier_id, func.count(Vote.id))
            .filter(Vote.round_id == round_.id)
            .group_by(Vote.tier_id)
            .all())
    counts = dict(rows)
    total = sum(counts.values())

    options = []
    for option in round_.options:
        tiers = [{"tier": t, "votes": counts.get(t.id, 0), "percent": _percent(counts.get(t.id, 0), total)}
                 for t in option.tiers]
        option_votes = sum(t["votes"] for t in tiers)
        options.append({"option": option, "votes": option_votes,
                        "percent": _percent(option_votes, total), "tiers": tiers})

    leading = max(counts, key=counts.get) if counts else None
    return {"total": total, "options": options, "leading_tier_id": leading}


# ---------------------------------------------------------------- casting votes
class VoteError(ValueError):
    """A vote that can't be accepted, with a message safe to show the visitor."""


def is_open(round_):
    """Open = status is open AND the close time (if any) hasn't passed."""
    return round_ is not None and round_.status == "open" and seconds_left(round_) != 0


def find_tier_in_round(round_, tier_id):
    """The PartTier with this id, but ONLY if it belongs to this round (no voting across rounds)."""
    try:
        tier_id = int(tier_id)
    except (TypeError, ValueError):
        return None
    tier = db.session.get(PartTier, tier_id)
    if tier is None or tier.option.round_id != round_.id:
        return None
    return tier


def has_voted(round_, code):
    return Vote.query.filter_by(round_id=round_.id, code_id=code.id).first() is not None


def cast_vote(round_, code, tier):
    """
    Record one vote. Raises VoteError if the round has closed or this code
    already voted. The database's unique constraint (one vote per code per
    round) is the final safety net if two requests arrive at the same moment.
    """
    if not is_open(round_):
        raise VoteError("This round has closed. Check the results below.")
    if has_voted(round_, code):
        raise VoteError("That code has already voted in this round. Each code gets one vote per round.")
    vote = Vote(round=round_, tier=tier, code=code)
    db.session.add(vote)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise VoteError("That code has already voted in this round. Each code gets one vote per round.")
    return vote


# ---------------------------------------------------------------- closing rounds
def pick_winner(round_):
    """
    The tier with the most votes. Ties go to the cheaper tier (it gets
    installed sooner), then to the one listed first. None if nobody voted.
    """
    results = round_results(round_)
    candidates = [t for row in results["options"] for t in row["tiers"] if t["votes"] > 0]
    if not candidates:
        return None
    best = max(candidates, key=lambda t: (t["votes"], -t["tier"].goal_cents))
    return best["tier"]


def close_round(round_):
    """
    Close a round: pick the winner and turn it into a funding goal (active
    now, or queued behind the part currently being funded). Safe to call twice.
    """
    if round_.status == "closed":
        return round_.winning_tier
    winner = pick_winner(round_)
    round_.status = "closed"
    round_.closed_at = utcnow()
    if winner:
        round_.winning_tier_id = winner.id
        add_goal(winner.option.name, winner.level, winner.goal_cents, tier_id=winner.id)
    db.session.commit()
    return winner


def close_expired_rounds():
    """
    Close any open round whose close time has passed. There's no background
    scheduler in this proof of concept, so pages that show rounds call this
    first ("close on read"). The admin can also close a round by hand (stage 7).
    """
    now = utcnow()
    expired = VoteRound.query.filter(VoteRound.status == "open", VoteRound.closes_at.isnot(None),
                                     VoteRound.closes_at <= now).all()
    for round_ in expired:
        close_round(round_)
    return expired


def closed_rounds():
    return VoteRound.query.filter_by(status="closed").order_by(VoteRound.closed_at.desc()).all()
