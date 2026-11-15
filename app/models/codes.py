"""
Freshener codes: the key that lets a buyer vote and join the Garage.

A code comes from either a mock order (one per physical freshener) or an
admin batch (printed on fresheners sold in person at meets).
"""
from ..extensions import db
from ._common import utcnow


class CodeBatch(db.Model):
    """A group of codes the admin generated in one go, e.g. 'Spring meet stock'."""
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    codes = db.relationship("FreshenerCode", backref="batch")


class FreshenerCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # unique=True makes the database itself refuse duplicate codes.
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_item.id"))
    batch_id = db.Column(db.Integer, db.ForeignKey("code_batch.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
