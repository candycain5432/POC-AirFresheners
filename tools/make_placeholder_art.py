"""
Draws the PLACEHOLDER images that live in app/static/img/ so the site looks
finished before real photos exist. Run it again any time:

    python tools/make_placeholder_art.py

What it makes (replace any of these with a real photo of the same name):
    app/static/img/lazarus-hero.jpg      home page hero          (about 1600 x 1280)
    app/static/img/lazarus-before.jpg    Revival Car "Before"    (about 1600 x 1000)
    app/static/img/lazarus-now.jpg       Revival Car "Now"       (same size as Before)
    app/static/img/products/<slug>.jpg   one per product         (square, about 800 x 800)

The car is a generic, unbranded 1980s hatchback drawn from simple shapes:
no carmaker names or logos.
"""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

IMG_DIR = os.path.join(ROOT, "app", "static", "img")
PRODUCT_DIR = os.path.join(IMG_DIR, "products")
FONT_DIR = os.path.join(ROOT, "app", "static", "fonts")

INK = (21, 20, 19)
CREAM = (244, 241, 234)
RED = (212, 42, 31)


def font(size, weight="700"):
    """The site's own Barlow Condensed font, or Pillow's built-in one as a fallback."""
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, f"barlow-condensed-latin-{weight}-normal.woff2"), size)
    except OSError:
        return ImageFont.load_default(size=size)


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def vertical_gradient(size, top, bottom):
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    w, h = size
    for y in range(h):
        draw.line([(0, y), (w, y)], fill=mix(top, bottom, y / h))
    return img


def add_grain(img, amount=0.10, sigma=60):
    """Film-grain style noise so placeholders feel like photos, not clip art."""
    noise = Image.effect_noise(img.size, sigma).convert("RGB")
    return Image.blend(img, noise, amount)


def vignette(img, strength=0.55):
    """Darken the edges."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([-w * 0.15, -h * 0.2, w * 1.15, h * 1.2], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(img, Image.blend(img, dark, strength), mask)


def label(img, text):
    """Small 'placeholder' note in the bottom-left corner."""
    draw = ImageDraw.Draw(img)
    f = font(26, "600")
    x, y = 28, img.size[1] - 52
    box = draw.textbbox((x, y), text, font=f)
    draw.rectangle([box[0] - 10, box[1] - 6, box[2] + 10, box[3] + 8], fill=(0, 0, 0))
    draw.text((x, y), text, font=f, fill=CREAM)


# ---------------------------------------------------------------- the car
def draw_hatchback(draw, ox, ground, scale, body, state):
    """
    A side-on boxy hatchback facing right. `ox` is the left edge, `ground` the
    ground line, `scale` 1.0 = about 1000px long. `state` is "before" or "now".
    """
    def p(x, y):
        return (ox + x * scale, ground + y * scale)

    rnd = random.Random(7)
    flat = state == "before"
    wheel_y = -85
    tyre = (24, 23, 22)

    # Shadow under the car.
    draw.ellipse([p(10, -18), p(1010, 22)], fill=(0, 0, 0))

    # Body shell.
    shell = [p(20, -95), p(20, -205), p(95, -258), p(300, -338), p(600, -333), p(725, -208),
             p(985, -180), p(1002, -150), p(1002, -95)]
    draw.polygon(shell, fill=body)

    # Rust patches / primer patches.
    if flat:
        for _ in range(26):
            x, y = rnd.randint(40, 960), rnd.randint(-200, -100)
            r = rnd.randint(12, 46)
            draw.ellipse([p(x - r, y - r * .6), p(x + r, y + r * .6)], fill=mix(body, (70, 35, 15), rnd.uniform(.3, .7)))
    else:
        # one freshly painted red door and a pinstripe
        draw.polygon([p(460, -212), p(462, -100), p(700, -100), p(700, -212)], fill=RED)
        draw.line([p(25, -150), p(1000, -150)], fill=CREAM, width=max(2, int(6 * scale)))

    # Windows.
    glass = (30, 34, 38) if flat else (58, 70, 80)
    draw.polygon([p(115, -248), p(300, -322), p(445, -322), p(445, -215), p(115, -215)], fill=glass)
    draw.polygon([p(465, -322), p(592, -320), p(700, -215), p(465, -215)], fill=glass)
    if flat:  # cracked glass
        draw.line([p(500, -300), p(560, -240), p(620, -280)], fill=(120, 120, 120), width=2)
        draw.line([p(560, -240), p(590, -225)], fill=(120, 120, 120), width=2)
    else:  # a highlight on the glass
        draw.line([p(480, -305), p(530, -230)], fill=(110, 125, 135), width=max(2, int(8 * scale)))

    # Door shut lines and handle.
    for x in (455, 705):
        draw.line([p(x, -212), p(x, -100)], fill=mix(body, INK, .55), width=max(1, int(3 * scale)))
    draw.rectangle([p(660, -192), p(690, -184)], fill=INK)

    # Bumpers and lights.
    draw.rectangle([p(8, -120), p(40, -95)], fill=(40, 40, 40))
    if not flat:
        draw.rectangle([p(975, -125), p(1012, -95)], fill=(40, 40, 40))
    draw.rectangle([p(985, -172), p(1002, -152)], fill=(230, 220, 170) if not flat else (90, 90, 80))
    draw.rectangle([p(22, -195), p(34, -170)], fill=(150, 30, 25) if not flat else (80, 40, 30))

    # Wheel arches (cut-outs) and wheels.
    for cx in (215, 800):
        draw.ellipse([p(cx - 100, -185), p(cx + 100, 15)], fill=mix(body, INK, .75))
        if flat:  # same size wheel, rusty hub; grass drawn later hides the bottom
            draw.ellipse([p(cx - 82, wheel_y - 82), p(cx + 82, wheel_y + 82)], fill=tyre)
            draw.ellipse([p(cx - 46, wheel_y - 46), p(cx + 46, wheel_y + 46)], fill=(96, 62, 40))
        else:
            draw.ellipse([p(cx - 82, wheel_y - 82), p(cx + 82, wheel_y + 82)], fill=tyre)
            draw.ellipse([p(cx - 46, wheel_y - 46), p(cx + 46, wheel_y + 46)], fill=(170, 170, 165))
            for k in range(5):  # simple five-spoke hint
                import math
                a = k * 2 * math.pi / 5
                draw.line([p(cx, wheel_y), p(cx + 40 * math.cos(a), wheel_y + 40 * math.sin(a))],
                          fill=(110, 110, 105), width=max(2, int(9 * scale)))
            draw.ellipse([p(cx - 10, wheel_y - 10), p(cx + 10, wheel_y + 10)], fill=(60, 60, 58))

    # Grass tufts growing around the wheels of the field find.
    if flat:
        for _ in range(140):
            x = rnd.randint(-20, 1040)
            h = rnd.randint(30, 95)
            lean = rnd.randint(-14, 14)
            draw.line([p(x, 8), p(x + lean, 8 - h)], fill=mix((120, 125, 60), (190, 170, 90), rnd.random()),
                      width=max(2, int(4 * scale)))


def garage_scene(size, car_scale, car_x, ground_frac, state):
    w, h = size
    img = vertical_gradient(size, (58, 54, 50), (30, 28, 26))           # wall
    draw = ImageDraw.Draw(img)
    ground = int(h * ground_frac)
    floor = vertical_gradient((w, h - ground), (88, 84, 78), (40, 38, 35))  # concrete floor
    img.paste(floor, (0, ground))
    # A warm work light glow from the top right.
    glow = Image.new("RGB", size, (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([w * .45, -h * .5, w * 1.3, h * .55], fill=(255, 190, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(w // 8))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L")), .35)
    draw = ImageDraw.Draw(img)
    # Pegboard dots on the wall.
    for x in range(30, w, 46):
        for y in range(40, ground - 40, 46):
            draw.ellipse([x, y, x + 5, y + 5], fill=(40, 37, 34))
    body = (138, 133, 126) if state == "now" else (124, 74, 42)
    draw_hatchback(draw, car_x, ground + int(40 * car_scale), car_scale, body, state)
    return img


def field_scene(size, car_scale, car_x, ground_frac):
    w, h = size
    img = vertical_gradient(size, (182, 196, 204), (226, 214, 180))     # hazy sky
    draw = ImageDraw.Draw(img)
    ground = int(h * ground_frac)
    field = vertical_gradient((w, h - ground), (178, 160, 98), (120, 104, 60))
    img.paste(field, (0, ground))
    draw = ImageDraw.Draw(img)
    # A distant tree line.
    rnd = random.Random(3)
    for x in range(0, w, 18):
        r = rnd.randint(30, 70)
        draw.ellipse([x - r, ground - r * 1.4, x + r, ground + 10], fill=(92, 104, 78))
    draw_hatchback(draw, car_x, ground + int(40 * car_scale), car_scale, (124, 74, 42), "before")
    return img


def save(img, path, quality=80):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    print(f"  {os.path.relpath(path, ROOT)}  ({os.path.getsize(path) // 1024} KB)")


def make_car_images():
    # Hero: "Lazarus now", tighter crop, moody.
    # Car sits high and to the right, so the funding card (which hangs off the
    # photo's bottom-left corner) doesn't cover it.
    hero = garage_scene((1600, 1280), .9, 660, .5, "now")
    hero = vignette(add_grain(hero, .07), .4)
    label(hero, "PLACEHOLDER: replace app/static/img/lazarus-hero.jpg")
    save(hero, os.path.join(IMG_DIR, "lazarus-hero.jpg"))

    # Before / Now: identical framing so the comparison slider lines up.
    before = vignette(add_grain(field_scene((1600, 1000), 1.2, 200, .64), .08), .35)
    label(before, "PLACEHOLDER: replace app/static/img/lazarus-before.jpg")
    save(before, os.path.join(IMG_DIR, "lazarus-before.jpg"))

    now = vignette(add_grain(garage_scene((1600, 1000), 1.2, 200, .64, "now"), .08), .35)
    label(now, "PLACEHOLDER: replace app/static/img/lazarus-now.jpg")
    save(now, os.path.join(IMG_DIR, "lazarus-now.jpg"))


# ---------------------------------------------------------------- products
def product_photo(name, colour, kind, size=800):
    """A bead freshener hanging in front of a light studio backdrop."""
    s = size
    img = vertical_gradient((s, s), (250, 247, 241), (226, 219, 206))
    body = hex_rgb(colour)

    # Soft drop shadow.
    shadow = Image.new("L", (s, s), 0)
    ImageDraw.Draw(shadow).ellipse([s * .30, s * .84, s * .72, s * .90], fill=120)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img = Image.composite(Image.new("RGB", (s, s), (150, 140, 128)), img, shadow)

    # The freshener on its own layer so it can be tilted slightly.
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    top, bottom = s * .22, s * .80
    left, right = s * .30, s * .70
    shape = [(left, top + 20), (s / 2, top - 10), (right, top + 20), (right + 22, bottom - 20)]
    for i in range(21):  # curved bottom edge
        t = i / 20
        shape.append((right + 22 - t * (right - left + 44), bottom - 20 + 26 * (1 - (2 * t - 1) ** 2)))
    shape.append((left - 22, bottom - 20))
    d.polygon(shape, fill=body + (255,))
    # Aroma beads: small lighter dots.
    for y in range(int(top + 30), int(bottom), 22):
        for x in range(int(left - 10), int(right + 20), 22):
            d.ellipse([x, y, x + 11, y + 11], fill=mix(body, (255, 255, 255), .22) + (255,))
    d.polygon(shape, outline=mix(body, INK, .35) + (255,), width=3)
    # Re-clip the dots to the shape.
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).polygon(shape, fill=255)
    layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (s, s), 0), mask))
    d = ImageDraw.Draw(layer)
    hole = (s / 2, top + 22)
    d.ellipse([hole[0] - 13, hole[1] - 13, hole[0] + 13, hole[1] + 13], fill=(250, 247, 241, 255), outline=INK + (255,), width=4)

    # Name (or a big "?" for blind bags), shrunk to fit.
    if kind == "blind":
        lines, base = ["?"], 220
    else:
        clean = name.replace(" (Meet Exclusive)", "").upper()
        words, lines, cur = clean.split(), [], ""
        for word in words:
            if len(cur + " " + word) > 10 and cur:
                lines.append(cur)
                cur = word
            else:
                cur = (cur + " " + word).strip()
        lines.append(cur)
        base = 86
    y = s * .50 - len(lines) * base * .55
    for line in lines:
        size_px = base
        while size_px > 30 and d.textlength(line, font=font(size_px)) > (right - left + 10):
            size_px -= 4
        f = font(size_px)
        tw = d.textlength(line, font=f)
        d.text((s / 2 - tw / 2 + 3, y + 3), line, font=f, fill=(0, 0, 0, 90))
        d.text((s / 2 - tw / 2, y), line, font=f, fill=(250, 246, 238, 255))
        y += size_px * 1.02

    layer = layer.rotate(-4, resample=Image.BICUBIC, center=(s / 2, top))
    img.paste(layer, (0, 0), layer)
    draw = ImageDraw.Draw(img)
    draw.line([(s / 2, 0), (s / 2, top + 10)], fill=INK, width=3)  # the string

    if kind == "meet":
        draw.rounded_rectangle([28, 28, 238, 78], radius=25, fill=RED)
        f = font(30, "600")
        draw.text((133 - draw.textlength("MEET ONLY", font=f) / 2, 36), "MEET ONLY", font=f, fill=(255, 255, 255))
    img = add_grain(img, .04, 40)
    label(img, "PLACEHOLDER PHOTO")
    return img


def make_product_images():
    from seed import MEETS, PRODUCTS, meet_slug
    items = [(slug, name, colour, kind) for slug, name, kind, _d, _p, _u, colour in PRODUCTS]
    items += [(meet_slug(m[3]), m[3], m[-1], "meet") for m in MEETS if m[-2]]   # only meets sold online
    for slug, name, colour, kind in items:
        save(product_photo(name, colour, kind), os.path.join(PRODUCT_DIR, f"{slug}.jpg"), quality=78)


def make_noise_texture():
    """A tiny SVG noise tile used behind section headers (see style.css)."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">'
           '<filter id="n"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="3" stitchTiles="stitch"/>'
           '<feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .55 0"/></filter>'
           '<rect width="100%" height="100%" filter="url(#n)"/></svg>')
    path = os.path.join(IMG_DIR, "noise.svg")
    with open(path, "w") as fh:
        fh.write(svg)
    print(f"  {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    print("Drawing placeholder images:")
    make_car_images()
    make_product_images()
    make_noise_texture()
