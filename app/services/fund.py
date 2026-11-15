"""
The Revival Car fund: how much has been raised, spent, and how close we are
to the part currently being funded.

    raised  = sum of all FundEntry rows   (mock sales + manual adjustments)
    spent   = sum of all Install costs
    on hand = raised - spent

The progress bar counts money on hand toward the active FundingGoal. When
an install is logged, `spent` goes up, so on-hand money drops and the next
goal starts from whatever is left over. Nothing is ever counted twice.
"""
from sqlalchemy import func

from ..extensions import db
from ..models import FundEntry, FundingGoal, Install


def total_raised_cents():
    # coalesce(..., 0) turns "no rows" (NULL) into 0.
    return db.session.query(func.coalesce(func.sum(FundEntry.amount_cents), 0)).scalar()


def total_spent_cents():
    return db.session.query(func.coalesce(func.sum(Install.cost_cents), 0)).scalar()


def active_goal():
    """The part being funded right now, or None if no goal is set."""
    return FundingGoal.query.filter_by(status="active").order_by(FundingGoal.created_at.desc()).first()


def next_goal():
    """The part queued up after the current one (a vote winner waiting its turn), or None."""
    return FundingGoal.query.filter_by(status="queued").order_by(FundingGoal.created_at).first()


def add_goal(part_name, tier, goal_cents, tier_id=None):
    """
    Add a new part to fund. It becomes the active goal straight away if
    nothing is being funded; otherwise it is queued and waits its turn, so a
    half-funded part never disappears from the progress bar.
    """
    status = "queued" if active_goal() else "active"
    goal = FundingGoal(part_name=part_name, tier=tier, goal_cents=goal_cents, tier_id=tier_id, status=status)
    db.session.add(goal)
    return goal


def activate_next_goal():
    """Called after the active part is installed: promote the next queued goal (if any)."""
    if active_goal():
        return active_goal()
    goal = next_goal()
    if goal:
        goal.status = "active"
    return goal


def fund_summary():
    """
    Everything the progress bar and totals need, in one dictionary.
    `goal` is None when nothing is being funded; templates handle that case.
    """
    raised = total_raised_cents()
    spent = total_spent_cents()
    on_hand = raised - spent
    goal = active_goal()

    summary = {"raised": raised, "spent": spent, "on_hand": on_hand, "goal": goal, "next_goal": next_goal(),
               "toward_goal": 0, "remaining": 0, "percent": 0, "funded": False}
    if goal:
        toward = max(0, min(on_hand, goal.goal_cents))   # clamp to 0..goal
        summary["toward_goal"] = toward
        summary["remaining"] = goal.goal_cents - toward
        summary["percent"] = round(100 * toward / goal.goal_cents) if goal.goal_cents else 100
        summary["funded"] = summary["remaining"] == 0
    return summary
