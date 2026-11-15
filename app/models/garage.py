"""The Garage: community profiles for buyers' own cars."""
from ..extensions import db
from ._common import utcnow


class GarageMember(db.Model):
    """
    A member's car profile. There are no passwords in the proof of concept:
    the freshener code IS the key, so one code owns at most one profile.
    """
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.Integer, db.ForeignKey("freshener_code.id"), unique=True, nullable=False)
    owner_name = db.Column(db.String(60), nullable=False)    # display name / handle
    car_name = db.Column(db.String(80), nullable=False)      # "Patina Pete"
    description = db.Column(db.String(500), default="")
    photo_filename = db.Column(db.String(120))
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)  # admin moderation
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    code = db.relationship("FreshenerCode")


class CarOfTheMonth(db.Model):
    """Featured member car. The newest row is the current pick."""
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("garage_member.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # "2026-11"
    blurb = db.Column(db.String(300), default="")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    member = db.relationship("GarageMember")
