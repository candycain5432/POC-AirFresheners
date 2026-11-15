"""
Draws simple placeholder "photos" for the seed data with Pillow, so the
site has images to show before real photos are uploaded.

Each image is a dark, workshop-style card: a rust-coloured gradient,
hazard stripes along the bottom and a label. No logos, no brand names.
"""
import os
import random

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


def make_placeholder(folder, filename, label, sublabel="", accent=RUST, size=(960, 720), seed=0):
    rnd = random.Random(seed)
    w, h = size
    img = Image.new("RGB", size, DARK)
    draw = ImageDraw.Draw(img)

    # Vertical gradient from the accent colour (top) to near-black (bottom).
    for y in range(h):
        t = y / h
        r = int(accent[0] * (1 - t) * 0.55 + DARK[0] * t)
        g = int(accent[1] * (1 - t) * 0.55 + DARK[1] * t)
        b = int(accent[2] * (1 - t) * 0.55 + DARK[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Random "rust speckles" for texture.
    for _ in range(900):
        x, y = rnd.randrange(w), rnd.randrange(h)
        rad = rnd.choice([1, 1, 2, 3])
        shade = rnd.randint(60, 140)
        draw.ellipse([x, y, x + rad, y + rad], fill=(shade, shade // 2, shade // 5))

    # Hazard stripes along the bottom edge.
    stripe_h = 34
    for x in range(-stripe_h, w + stripe_h, 40):
        draw.polygon([(x, h), (x + 20, h), (x + 20 + stripe_h, h - stripe_h), (x + stripe_h, h - stripe_h)],
                     fill=(230, 170, 30))

    # Label text, centred.
    big, small = _font(54), _font(28)
    tw = draw.textlength(label, font=big)
    draw.text(((w - tw) / 2, h / 2 - 50), label, font=big, fill=(245, 235, 220))
    if sublabel:
        sw = draw.textlength(sublabel, font=small)
        draw.text(((w - sw) / 2, h / 2 + 20), sublabel, font=small, fill=(230, 160, 110))
    draw.text((24, 20), "PLACEHOLDER PHOTO", font=_font(20), fill=(200, 190, 180))

    os.makedirs(folder, exist_ok=True)
    img.save(os.path.join(folder, filename), "JPEG", quality=80)
    return filename
