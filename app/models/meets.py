"""Meet drops: car meets where we sell an exclusive scent."""
from ..extensions import db


class MeetDrop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meet_name = db.Column(db.String(120), nullable=False)
    meet_date = db.Column(db.Date, nullable=False)
    location = db.Column(db.String(160), nullable=False)
    scent_name = db.Column(db.String(120), nullable=False)
    scent_description = db.Column(db.String(300), default="")
    quantity = db.Column(db.Integer)   # how many were made (optional)
    sold_out = db.Column(db.Boolean, default=False, nullable=False)
