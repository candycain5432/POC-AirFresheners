"""
Draws simple placeholder "photos" for the seed data with Pillow, so the
site has images to show before real photos are uploaded.

Each image is a simple dark card: a soft colour gradient and a label.
No logos, no brand names.
"""
import os

from PIL import Image, ImageDraw, ImageFont

RUST = (194, 87, 26)
DARK = (28, 25, 22)


def _font(size):
    # load_default(size=...) gives a scalable built-in font (Pillow 10.1+),
    # so this works without any font files installed.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_placeholder(folder, filename, label, sublabel="", accent=RUST, size=(960, 720), seed=0):  # seed kept for call compatibility
    w, h = size
    img = Image.new("RGB", size, DARK)
    draw = ImageDraw.Draw(img)

    # Vertical gradient from the accent colour (top) to near-black (bottom).
    for y in range(h):
        t = y / h
        r = int(accent[0] * (1 - t) * 0.45 + DARK[0] * t)
        g = int(accent[1] * (1 - t) * 0.45 + DARK[1] * t)
        b = int(accent[2] * (1 - t) * 0.45 + DARK[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Label text, centred.
    big, small = _font(54), _font(28)
    tw = draw.textlength(label, font=big)
    draw.text(((w - tw) / 2, h / 2 - 50), label, font=big, fill=(245, 235, 220))
    if sublabel:
        sw = draw.textlength(sublabel, font=small)
        draw.text(((w - sw) / 2, h / 2 + 20), sublabel, font=small, fill=(230, 160, 110))
    draw.text((24, 20), "PLACEHOLDER PHOTO", font=_font(18), fill=(150, 140, 130))

    os.makedirs(folder, exist_ok=True)
    img.save(os.path.join(folder, filename), "JPEG", quality=80)
    return filename
