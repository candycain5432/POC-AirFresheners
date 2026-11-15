"""
Shared Flask extension objects.

They are created here, without an app, and attached to the app later inside
create_app(). This avoids circular imports: models and routes can import
`db` from this file without importing the whole application.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# The database handle. Models subclass db.Model; queries use db.session.
db = SQLAlchemy()

# Adds a hidden CSRF token check to every POST form. Templates include
# {{ csrf_token() }} in each form; requests without a valid token get a 400.
csrf = CSRFProtect()
