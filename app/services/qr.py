"""
QR code images, made with the `qrcode` library.

qr_data_uri() returns the PNG as a "data:" URI so it can go straight into
an <img src="..."> with no extra file or request.
"""
import base64
import io

import qrcode
from qrcode.image.pil import PilImage


def qr_png_bytes(text, box_size=6):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_data_uri(text, box_size=6):
    return "data:image/png;base64," + base64.b64encode(qr_png_bytes(text, box_size)).decode("ascii")
