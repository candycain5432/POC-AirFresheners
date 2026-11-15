"""Friendly error pages that keep the site's look."""
from flask import render_template
from flask_wtf.csrf import CSRFError


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, title="Part not found",
                               message="That page isn't on the shelf. Maybe it's still in the junkyard."), 404

    @app.errorhandler(CSRFError)
    def csrf_failed(error):
        return render_template("error.html", code=400, title="Form expired",
                               message="That form was open too long or came from somewhere else. "
                                       "Go back, refresh the page and try again."), 400

    @app.errorhandler(413)
    def too_large(error):
        return render_template("error.html", code=413, title="File too big",
                               message="Uploads can be at most 5 MB. Try a smaller photo."), 413

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", code=500, title="Something seized up",
                               message="That one's on us. Please try again in a minute."), 500
