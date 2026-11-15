"""Collects every blueprint (site section) and registers it on the app."""


def register_blueprints(app):
    from .main import bp as main_bp

    app.register_blueprint(main_bp)

    # Uploaded images are stored outside /static, so serve them with their own route.
    from .uploads import bp as uploads_bp
    app.register_blueprint(uploads_bp)
