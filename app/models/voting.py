"""
Voting: buyers choose which part goes on the Revival Car next.

Structure:
    VoteRound  -> has several PartOptions ("Brake calipers", "Seats", ...)
    PartOption -> has several PartTiers (budget / mid / high, each with a goal)
    Vote       -> one freshener code choosing one PartTier in one round

The ballot is "part + tier together": a voter picks one PartTier line.
"""
from ..extensions import db
from ._common import utcnow

TIER_LEVELS = ("budget", "mid", "high")
TIER_LABELS = {"budget": "Budget", "mid": "Mid-range", "high": "High-end"}


class VoteRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="draft")  # draft / open / closed
    opened_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    # use_alter: rounds point at a tier and tiers (via options) point at
    # rounds. This tells SQLAlchemy the circular link is intentional.
    winning_tier_id = db.Column(db.Integer, db.ForeignKey("part_tier.id", use_alter=True))

    options = db.relationship("PartOption", backref="round", order_by="PartOption.position",
                              cascade="all, delete-orphan")
    winning_tier = db.relationship("PartTier", foreign_keys=[winning_tier_id], post_update=True)


class PartOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey("vote_round.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300), default="")
    position = db.Column(db.Integer, default=0)

    tiers = db.relationship("PartTier", backref="option", order_by="PartTier.goal_cents",
                            cascade="all, delete-orphan")


class PartTier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("part_option.id"), nullable=False)
    level = db.Column(db.String(10), nullable=False)       # one of TIER_LEVELS
    description = db.Column(db.String(200), default="")   # e.g. "Remanufactured units"
    goal_cents = db.Column(db.Integer, nullable=False)

    @property
    def level_label(self):
        return TIER_LABELS.get(self.level, self.level)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey("vote_round.id"), nullable=False)
    tier_id = db.Column(db.Integer, db.ForeignKey("part_tier.id"), nullable=False)
    code_id = db.Column(db.Integer, db.ForeignKey("freshener_code.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    round = db.relationship("VoteRound", backref="votes")
    tier = db.relationship("PartTier")
    code = db.relationship("FreshenerCode")

    # The database guarantees one vote per code per round, even if two
    # requests arrive at the same instant.
    __table_args__ = (db.UniqueConstraint("round_id", "code_id", name="one_vote_per_code_per_round"),)
