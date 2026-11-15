"""
Vote rounds: which round is open, how much time is left, and the results.

Results are counted per ballot line (a part + tier, e.g. "Seats, mid-range"),
and also added up per part so the page can show both.
"""
from sqlalchemy import func

from ..extensions import db
from ..models import Vote, VoteRound
from ..models._common import utcnow


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
