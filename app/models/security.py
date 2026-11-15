"""Records of failed code/password attempts, used for rate limiting."""
from ..extensions import db
from ._common import utcnow


class FailedAttempt(db.Model):
    """
    One wrong guess. Stored in the database (not in memory) so the limit
    works even when several server processes are running.
    """
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)  # 45 chars fits IPv6
    action = db.Column(db.String(20), nullable=False)                   # "code" or "admin_login"
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
