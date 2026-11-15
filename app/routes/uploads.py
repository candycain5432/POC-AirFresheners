"""Serves uploaded and generated images from the instance/uploads folder."""
from flask import Blueprint, current_app, send_from_directory

bp = Blueprint("uploads", __name__)


@bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # send_from_directory refuses paths that try to escape the folder (../).
    response = send_from_directory(current_app.config["UPLOAD_DIR"], filename)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response
