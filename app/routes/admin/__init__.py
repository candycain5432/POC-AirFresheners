"""
The admin panel, at /admin.

Every page here requires the admin to be logged in (see require_admin below).
Each section lives in its own file:

    auth.py       log in / log out
    dashboard.py  overview
    codes.py      code batches: printable QR sheet, CSV, ZIP of QR images
    rounds.py     vote rounds: build, open, extend, close
    installs.py   log installs (video, photos), edit them
    meets.py      meet drops: add, sold out, delete
    garage.py     hide cars, pick Car of the Month
    fund.py       fund ledger and manual adjustments
"""
from flask import Blueprint, redirect, request, url_for

from ...services.admin_auth import is_admin

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Pages reachable without being logged in.
PUBLIC_ENDPOINTS = {"admin.login"}


@bp.before_request
def require_admin():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if not is_admin():
        return redirect(url_for("admin.login", next=request.path))
    return None


@bp.after_request
def private_headers(response):
    # Never cache admin pages (shared computers, proxies) and keep them out of search engines.
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


# Importing these files registers their routes on `bp`.
from . import auth, codes, dashboard, fund, garage, installs, meets, rounds  # noqa: E402,F401
