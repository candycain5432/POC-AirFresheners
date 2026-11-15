"""
The Revival Car: the junk project car being rebuilt in public, plus the
money that pays for it.

How the money works (all amounts are whole cents, e.g. 899 = $8.99):
  * FundEntry rows are money IN (mock sales, manual admin adjustments).
  * Install rows are money OUT (each part bought and installed).
  * Money on hand = sum(FundEntry) - sum(Install.cost).
  * The progress bar compares money on hand with the active FundingGoal.
See app/services/fund.py for those calculations.
"""
from ..extensions import db
from ._common import utcnow


class RevivalCar(db.Model):
    """The one project car. The site assumes a single row, but the table could hold more."""
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), nullable=False)       # e.g. "Lazarus"
    description = db.Column(db.String(200), nullable=False)   # generic, no carmaker names
    story = db.Column(db.Text, nullable=False)                 # a few paragraphs
    acquired_on = db.Column(db.Date)

    photos = db.relationship("CarPhoto", backref="car", order_by="CarPhoto.position",
                             cascade="all, delete-orphan")


class CarPhoto(db.Model):
    """A gallery photo of the Revival Car."""
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("revival_car.id"), nullable=False)
    filename = db.Column(db.String(120), nullable=False)  # file inside UPLOAD_DIR
    caption = db.Column(db.String(200), default="")
    position = db.Column(db.Integer, default=0)            # display order


class BuildLogEntry(db.Model):
    """A free-form timeline note (e.g. 'Towed it home'). Installs appear on the timeline too."""
    id = db.Column(db.Integer, primary_key=True)
    happened_on = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, default="")


class FundingGoal(db.Model):
    """
    The part currently being funded (shown on the progress bar).

    Usually created automatically when a vote round closes (the winning
    part + tier). Only one goal has status "active" at a time; it becomes
    "installed" when the admin logs the install.
    """
    id = db.Column(db.Integer, primary_key=True)
    part_name = db.Column(db.String(120), nullable=False)   # "Brake calipers"
    tier = db.Column(db.String(20), nullable=False)          # budget / mid / high
    goal_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # active / installed
    tier_id = db.Column(db.Integer, db.ForeignKey("part_tier.id"))       # winning ballot line, if any
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Install(db.Model):
    """A completed part install: what it was, what it cost, and the video."""
    id = db.Column(db.Integer, primary_key=True)
    part_name = db.Column(db.String(120), nullable=False)
    tier = db.Column(db.String(20), nullable=False)
    cost_cents = db.Column(db.Integer, nullable=False)
    installed_on = db.Column(db.Date, nullable=False)
    video_url = db.Column(db.String(300), default="")  # YouTube or TikTok link
    notes = db.Column(db.Text, default="")
    goal_id = db.Column(db.Integer, db.ForeignKey("funding_goal.id"))

    photos = db.relationship("InstallPhoto", backref="install", cascade="all, delete-orphan")
    goal = db.relationship("FundingGoal")

    @property
    def before_photos(self):
        return [p for p in self.photos if p.kind == "before"]

    @property
    def after_photos(self):
        return [p for p in self.photos if p.kind == "after"]


class InstallPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    install_id = db.Column(db.Integer, db.ForeignKey("install.id"), nullable=False)
    kind = db.Column(db.String(10), nullable=False)  # "before" or "after"
    filename = db.Column(db.String(120), nullable=False)


class FundEntry(db.Model):
    """
    One line in the fund ledger: money coming in.
    source = "order" (a mock sale) or "manual" (admin adjustment, may be negative).
    """
    id = db.Column(db.Integer, primary_key=True)
    amount_cents = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(20), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"))
    note = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    order = db.relationship("Order")
