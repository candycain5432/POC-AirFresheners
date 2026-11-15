"""
Admin login.

There is one admin password. Only its HASH is stored, in the
ADMIN_PASSWORD_HASH setting (make one with: python -m flask --app app hash-password).
check_password_hash() re-hashes what was typed with the same salt and
compares, so the real password is never stored anywhere.

A successful login stores an expiry time in the signed session cookie. Each
admin page view pushes the expiry forward; after ADMIN_SESSION_MINUTES of
inactivity the admin must log in again.
"""
import time

from flask import current_app, session
from werkzeug.security import check_password_hash

SESSION_KEY = "admin_until"


def admin_configured():
    return bool(current_app.config.get("ADMIN_PASSWORD_HASH"))


def password_ok(password):
    hashed = current_app.config.get("ADMIN_PASSWORD_HASH")
    if not hashed or not password:
        return False
    try:
        return check_password_hash(hashed, password)
    except (ValueError, TypeError):      # a malformed hash in the settings
        return False


def _expiry():
    return time.time() + current_app.config["ADMIN_SESSION_MINUTES"] * 60


def log_in():
    session[SESSION_KEY] = _expiry()


def log_out():
    session.pop(SESSION_KEY, None)


def is_admin(refresh=True):
    until = session.get(SESSION_KEY)
    if not isinstance(until, (int, float)) or until < time.time():
        session.pop(SESSION_KEY, None)
        return False
    if refresh:
        session[SESSION_KEY] = _expiry()
    return True
