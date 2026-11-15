"""
App settings.

Every setting is read from an environment variable so that the same code can
run on your laptop, in Docker, or on a server without edits. Sensible
development defaults are provided where it is safe to do so.
"""
import os

# Folder that holds this file's parent: the project root.
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# "instance" is Flask's conventional folder for files that belong to one
# running copy of the app (the SQLite database, uploaded photos). It is
# kept out of git.
INSTANCE_DIR = os.environ.get("INSTANCE_DIR", os.path.join(BASE_DIR, "instance"))


class Config:
    # Used to sign the session cookie (which holds the cart) and CSRF tokens.
    # MUST be set to a long random value in production.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # SQLite database file. SQLAlchemy URL format: sqlite:///<absolute path>
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "rust_revival.db")
    )

    # Where uploaded/generated images live, and the largest request we accept.
    # Flask rejects bigger requests with "413 Request Entity Too Large".
    UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # The admin password is stored ONLY as a hash. Generate one with:
    #   flask --app app hash-password
    ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

    # Which payment provider checkout uses. Only "mock" exists for now;
    # see app/services/payments.py for how to add Stripe test mode.
    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "mock")

    # Code-guessing protection: this many wrong codes from one IP within the
    # window locks that IP out of code entry until the window passes.
    CODE_ATTEMPT_LIMIT = int(os.environ.get("CODE_ATTEMPT_LIMIT", "10"))
    CODE_ATTEMPT_WINDOW_MINUTES = int(os.environ.get("CODE_ATTEMPT_WINDOW_MINUTES", "15"))

    # Set to 1 when running behind a reverse proxy (nginx, Render, Fly...)
    # so the real visitor IP is used for rate limiting.
    TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"

    # Cookie hardening. SESSION_COOKIE_SECURE should be on when served over HTTPS.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
