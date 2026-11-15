"""Admin log in / log out, with brute-force protection on the password."""
from flask import flash, redirect, render_template, request, url_for

from ...services.admin_auth import admin_configured, is_admin, log_in, log_out, password_ok
from ...services.rate_limit import client_ip, minutes_locked, record_failure
from . import bp


def _safe_next(target):
    """Only follow ?next= to admin pages on THIS site (no redirecting visitors elsewhere)."""
    if target and target.startswith("/admin") and not target.startswith("//"):
        return target
    return url_for("admin.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if is_admin(refresh=False):
        return redirect(url_for("admin.dashboard"))
    error, status = None, 200
    if request.method == "POST":
        ip = client_ip()
        wait = minutes_locked(ip, "admin_login")
        if not admin_configured():
            error, status = "Admin login is turned off: ADMIN_PASSWORD_HASH isn't set. See the README.", 503
        elif wait:
            error, status = f"Too many wrong passwords. Try again in about {wait} minute{'s' if wait != 1 else ''}.", 429
        elif password_ok(request.form.get("password", "")):
            log_in()
            flash("Logged in.", "success")
            return redirect(_safe_next(request.args.get("next")))
        else:
            record_failure(ip, "admin_login")
            error, status = "That password isn't right.", 401
    return render_template("admin/login.html", error=error, configured=admin_configured()), status


@bp.route("/logout", methods=["POST"])
def logout():
    log_out()
    flash("Logged out.", "success")
    return redirect(url_for("main.home"))
