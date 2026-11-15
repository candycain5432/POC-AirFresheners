"""
Application factory.

`create_app()` builds and returns a configured Flask app. Using a function
(instead of a global app object) lets tests and the seed script create their
own app with different settings.

Run in development with:  python -m flask --app app run --debug
"""
import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # Make sure the folders for the database and uploads exist.
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # Behind a reverse proxy, trust ONE layer of X-Forwarded-For so
    # request.remote_addr is the visitor's IP, not the proxy's.
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # Attach extensions to this app.
    db.init_app(app)
    csrf.init_app(app)

    # Importing the models registers every table with SQLAlchemy.
    from . import models  # noqa: F401

    # Register page blueprints (one per site section).
    from .routes import register_blueprints
    register_blueprints(app)

    # Template helpers (money formatting etc.) and command-line commands.
    from .template_helpers import register_template_helpers
    register_template_helpers(app)

    from .cli import register_cli
    register_cli(app)

    from .security_headers import register_security_headers
    register_security_headers(app)

    # Create any missing tables. Fine for a proof of concept; a real app
    # would use migrations (e.g. Flask-Migrate) instead.
    with app.app_context():
        db.create_all()

    return app
