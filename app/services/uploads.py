"""
Safe image uploads.

Never trust an uploaded file: its name, its claimed type and even its
contents can lie. save_image():

  1. checks the request size (Flask already refuses anything over
     MAX_CONTENT_LENGTH = 5 MB with a "413 too large" error),
  2. opens the file with Pillow to prove it really is a JPEG, PNG or WebP,
  3. refuses absurd dimensions BEFORE decoding (a tiny "decompression bomb"
     file can claim to be 100,000 x 100,000 pixels and eat all the memory),
  4. rotates it the right way up (phones store rotation in EXIF),
  5. shrinks it to at most 1600px on the long side, and
  6. re-saves it as a brand-new JPEG with a random file name.

Step 6 also throws away all EXIF metadata, including GPS location, so a
photo taken in someone's driveway doesn't publish their address.
"""
import io
import os
import secrets

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000      # e.g. 8000 x 5000. Real phone photos are well under this.
MAX_SIDE = 1600              # stored photos are at most this wide/tall

# Make Pillow itself refuse decompression bombs too (belt and braces).
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class UploadError(ValueError):
    """A friendly message about why a photo was refused."""


def save_image(file_storage, subfolder):
    """
    Validate and store an uploaded image. Returns the stored path relative to
    UPLOAD_DIR (e.g. "garage/3f9c...e1.jpg"). Raises UploadError if refused.
    """
    if file_storage is None or not file_storage.filename:
        raise UploadError("Choose a photo to upload.")

    extension = os.path.splitext(file_storage.filename.lower())[1]
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadError("Photos must be JPG, PNG or WebP files.")

    data = file_storage.read()
    if not data:
        raise UploadError("That file is empty.")

    try:
        # Image.open only reads the header, so checking the size here is cheap.
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise UploadError("Photos must be JPG, PNG or WebP files.")
            width, height = probe.size
            if width * height > MAX_PIXELS:
                raise UploadError("That photo's dimensions are too large. Try one straight from your phone.")
            probe.verify()                       # checks the file isn't corrupt
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)   # turn it the right way up
            img = img.convert("RGB")             # drops transparency and odd colour modes
            img.thumbnail((MAX_SIDE, MAX_SIDE))  # shrink (never enlarges)
            out = io.BytesIO()
            # No exif= argument: the new file carries NO metadata (no GPS).
            img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    except UploadError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise UploadError("That file isn't a photo we can read. Try a JPG or PNG.")

    folder = os.path.join(current_app.config["UPLOAD_DIR"], subfolder)
    os.makedirs(folder, exist_ok=True)
    # A random name: unguessable, and it can never overwrite another file or
    # contain path tricks like "../".
    name = secrets.token_hex(16) + ".jpg"
    with open(os.path.join(folder, name), "wb") as fh:
        fh.write(out.getvalue())
    return f"{subfolder}/{name}"


def delete_upload(relative_path):
    """Remove a stored upload (ignores missing files and anything outside UPLOAD_DIR)."""
    if not relative_path:
        return
    root = os.path.realpath(current_app.config["UPLOAD_DIR"])
    path = os.path.realpath(os.path.join(root, relative_path))
    if path.startswith(root + os.sep) and os.path.isfile(path):
        os.remove(path)
