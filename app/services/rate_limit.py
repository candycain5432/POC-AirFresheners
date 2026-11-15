"""
Stops people guessing freshener codes.

Every WRONG code is written to the failed_attempt table with the visitor's
IP address. If one IP racks up CODE_ATTEMPT_LIMIT wrong codes within
CODE_ATTEMPT_WINDOW_MINUTES, that IP is locked out of code entry until the
oldest of those attempts ages out of the window.

Correct codes are never counted, so real buyers are never locked out by
typing their own codes. Storing attempts in the database (not in memory)
means the limit holds even with several server processes.

The same helpers will protect the admin login in stage 7 (action="admin_login").
"""
from datetime import timedelta

from flask import current_app, request

from ..extensions import db
from ..models import FailedAttempt
from ..models._common import utcnow


def client_ip():
    """The visitor's IP. Behind a proxy, set TRUST_PROXY=1 so this is the real one."""
    return (request.remote_addr or "unknown")[:45]


def _window():
    return timedelta(minutes=current_app.config["CODE_ATTEMPT_WINDOW_MINUTES"])


def _recent_failures(ip, action):
    since = utcnow() - _window()
    return (FailedAttempt.query
            .filter(FailedAttempt.ip_address == ip, FailedAttempt.action == action,
                    FailedAttempt.created_at >= since)
            .order_by(FailedAttempt.created_at))


def minutes_locked(ip, action="code"):
    """0 if this IP may try again now; otherwise roughly how many minutes to wait."""
    limit = current_app.config["CODE_ATTEMPT_LIMIT"]
    failures = _recent_failures(ip, action).all()
    if len(failures) < limit:
        return 0
    # Unlocks when enough of the oldest failures age out of the window.
    unlock_at = failures[len(failures) - limit].created_at + _window()
    seconds = (unlock_at - utcnow()).total_seconds()
    return max(1, int(seconds // 60) + 1)


def record_failure(ip, action="code"):
    db.session.add(FailedAttempt(ip_address=ip, action=action))
    # Tidy up: forget failures far older than the window so the table stays small.
    cutoff = utcnow() - _window() * 4
    FailedAttempt.query.filter(FailedAttempt.created_at < cutoff).delete()
    db.session.commit()
