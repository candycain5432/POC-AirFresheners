"""
Meet drops: car meets where we sell an exclusive scent.

    shop_today()      today's date in the shop's time zone (SHOP_TIMEZONE)
    upcoming_meets()  today or later, soonest first
    past_meets()      before today, most recent first
    meet_status()     what to show on a meet: sold out / on sale / at the meet only / over
    relative_day()    "Tomorrow", "In 3 weeks", "5 days ago"...
    meet_ics()        an .ics calendar file so people can add a meet to their phone calendar
"""
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import MeetDrop, Product
from .cart import can_buy
from .clock import shop_today  # noqa: F401  (meet dates are local dates; re-exported for callers)


def upcoming_meets(today):
    return MeetDrop.query.filter(MeetDrop.meet_date >= today).order_by(MeetDrop.meet_date).all()


def past_meets(today):
    return MeetDrop.query.filter(MeetDrop.meet_date < today).order_by(MeetDrop.meet_date.desc()).all()


def online_product(meet):
    """The shop product for this meet's exclusive scent, if it's sold online at all."""
    return next((p for p in meet.products if p.is_active), None)


def meet_status(meet, today):
    """
    One status per meet, with a `tone` the template turns into a colour:
        sold-out  - none left anywhere
        on-sale   - buyable online right now (links to the product)
        meet-only - only sold in person at the meet
        over      - the meet happened and nothing is left online
    """
    product = online_product(meet)
    buyable = product is not None and can_buy(product)
    if meet.sold_out:
        return {"label": "Sold out", "tone": "sold-out", "product": None}
    if meet.meet_date >= today:
        if buyable:
            return {"label": "On sale now", "tone": "on-sale", "product": product}
        return {"label": "At the meet only", "tone": "meet-only", "product": None}
    if buyable:
        return {"label": "A few left online", "tone": "on-sale", "product": product}
    return {"label": "Meet over", "tone": "over", "product": None}


def relative_day(when, today):
    """Friendly distance between two dates: "Today", "In 3 weeks", "2 months ago"."""
    days = (when - today).days
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    if days == -1:
        return "Yesterday"
    n = abs(days)
    if n < 14:
        amount = f"{n} days"
    elif n < 60:
        weeks = round(n / 7)
        amount = f"{weeks} weeks"
    else:
        months = round(n / 30)
        amount = f"{months} month{'s' if months != 1 else ''}"
    return f"In {amount}" if days > 0 else f"{amount} ago"


# ---------------------------------------------------------------- calendar file
# Characters that must be escaped in .ics text (RFC 5545), and their escaped form.
_ICS_ESCAPES = {"\\": "\\\\", ";": "\\;", ",": "\\,", "\n": "\\n"}


def _ics_text(value):
    """Escape text for an .ics file: backslash, semicolon, comma and newline."""
    return "".join(_ICS_ESCAPES.get(char, char) for char in (value or ""))


def _fold(line):
    """.ics lines must be at most 75 bytes; longer ones continue on the next line after a space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, chunk = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(chunk) + len(encoded) > (75 if not parts else 74):
            parts.append(chunk.decode("utf-8"))
            chunk = b""
        chunk += encoded
    parts.append(chunk.decode("utf-8"))
    return "\r\n ".join(parts)


def meet_ics(meet, page_url):
    """An all-day calendar event for one meet, as the text of an .ics file."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    description = (f"Exclusive scent: {meet.scent_name}. {meet.scent_description} "
                   f"Every freshener funds the Revival Car. {page_url}")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Salvage & Scent//Meet Drops//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:meet-{meet.id}@salvage-and-scent",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{meet.meet_date:%Y%m%d}",
        f"DTEND;VALUE=DATE:{meet.meet_date + timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{_ics_text(meet.meet_name + ' (Salvage & Scent meet drop)')}",
        f"LOCATION:{_ics_text(meet.location)}",
        f"DESCRIPTION:{_ics_text(description)}",
        f"URL:{page_url}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- admin actions
def create_meet(meet_name, meet_date, location, scent_name, scent_description, quantity,
                sell_online=False, price_cents=1000):
    """Add a meet. With sell_online, also create its exclusive product in the shop."""
    meet = MeetDrop(meet_name=meet_name, meet_date=meet_date, location=location, scent_name=scent_name,
                    scent_description=scent_description, quantity=quantity)
    db.session.add(meet)
    db.session.flush()   # gives the meet an id
    if sell_online:
        slug = _unique_slug("meet-" + "-".join(scent_name.lower().split()))
        db.session.add(Product(
            slug=slug, name=f"{scent_name} (Meet Exclusive)", kind="meet", meet_drop_id=meet.id,
            scent_description=f"{scent_description} Only made for {meet_name}.".strip(),
            price_cents=price_cents, accent_color="#9c2a3a", position=100 + meet.id,
        ))
    db.session.commit()
    return meet


def _unique_slug(base):
    base = "".join(ch for ch in base if ch.isalnum() or ch == "-")[:70] or "meet"
    slug, n = base, 2
    while Product.query.filter_by(slug=slug).first():
        slug, n = f"{base}-{n}", n + 1
    return slug


def set_meet_sold_out(meet, sold_out):
    """Mark a meet (and its exclusive product, so the shop agrees) sold out or back in stock."""
    meet.sold_out = sold_out
    for product in meet.products:
        product.sold_out = sold_out
    db.session.commit()


def delete_meet(meet):
    """Delete a meet. Its product is retired (kept for old orders) rather than deleted."""
    for product in meet.products:
        product.is_active = False
        product.meet_drop_id = None
    db.session.delete(meet)
    db.session.commit()
