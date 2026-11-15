"""
Draws simple placeholder "photos" for the seed data with Pillow, so the
site has images to show before real photos are uploaded.

Each image is a light, clean card to match the off-white site: a soft
gradient tinted with an accent colour, and a dark label. No logos, no brand names.
"""
import os

from PIL import Image, ImageDraw, ImageFont

RED = (212, 42, 31)
INK = (21, 20, 19)
LIGHT_TOP = (240, 236, 228)
LIGHT_BOTTOM = (214, 207, 194)


def _font(size):
    # load_default(size=...) gives a scalable built-in font (Pillow 10.1+),
    # so this works without any font files installed.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _mix(a, b, amount):
    """Blend colour a toward colour b by `amount` (0..1)."""
    return tuple(int(x + (y - x) * amount) for x, y in zip(a, b))


def make_placeholder(folder, filename, label, sublabel="", accent=RED, size=(960, 720), seed=0):
    """`seed` is unused now; it's kept so existing calls still work."""
    w, h = size
    img = Image.new("RGB", size, LIGHT_TOP)
    draw = ImageDraw.Draw(img)

    # Vertical gradient: a light tint of the accent at the top, warm grey at the bottom.
    top = _mix(LIGHT_TOP, accent, 0.18)
    for y in range(h):
        draw.line([(0, y), (w, y)], fill=_mix(top, LIGHT_BOTTOM, y / h))

    # Label text, centred.
    big, small = _font(56), _font(28)
    tw = draw.textlength(label, font=big)
    draw.text(((w - tw) / 2, h / 2 - 50), label, font=big, fill=INK)
    if sublabel:
        sw = draw.textlength(sublabel, font=small)
        draw.text(((w - sw) / 2, h / 2 + 22), sublabel, font=small, fill=_mix(INK, RED, 0.85))
    draw.text((24, 20), "PLACEHOLDER PHOTO", font=_font(18), fill=(130, 124, 116))

    os.makedirs(folder, exist_ok=True)
    img.save(os.path.join(folder, filename), "JPEG", quality=85)
    return filename
