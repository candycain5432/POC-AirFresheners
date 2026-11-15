"""Collects every blueprint (site section) and registers it on the app."""


def register_blueprints(app):
    from .car import bp as car_bp
    from .garage import bp as garage_bp
    from .main import bp as main_bp
    from .meets import bp as meets_bp
    from .shop import bp as shop_bp
    from .uploads import bp as uploads_bp
    from .vote import bp as vote_bp

    for bp in (main_bp, car_bp, shop_bp, vote_bp, garage_bp, meets_bp, uploads_bp):
        app.register_blueprint(bp)

    # Friendly error pages instead of Flask's plain defaults.
    from .errors import register_error_handlers
    register_error_handlers(app)
