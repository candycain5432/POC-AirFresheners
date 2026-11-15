"""
Small helpers available inside every Jinja template.

Usage in a template:  {{ product.price_cents | money }}  ->  "$8.00"
"""
import math
from datetime import datetime, timezone

from .models.voting import TIER_LABELS
from .services.codes import format_code
from .services.catalog import product_image_url
from .services.embeds import embed_info


def money(cents, show_cents=True):
    """Format integer cents as dollars. 2000 -> "$20.00" (or "$20" with show_cents=False)."""
    cents = cents or 0
    sign = "-" if cents < 0 else ""
    dollars = abs(cents) / 100
    if show_cents:
        return f"{sign}${dollars:,.2f}"
    return f"{sign}${dollars:,.0f}"


def nice_date(value):
    """date/datetime -> "Nov 15, 2026"."""
    if not value:
        return ""
    return value.strftime("%b %-d, %Y")


def nice_datetime(value):
    """datetime -> "Fri, Nov 20 at 18:00 UTC" (stored times are UTC)."""
    if not value:
        return ""
    return value.strftime("%a, %b %-d at %H:%M UTC")


def local_datetime(value):
    """Naive UTC datetime from the database -> "Nov 20, 2026, 8:00 PM" in SHOP_TIMEZONE."""
    from .services.clock import utc_to_local
    local = utc_to_local(value)
    return local.strftime("%b %-d, %Y, %-I:%M %p") if local else ""


# ---- The tachometer funding gauge (partials/progress.html) ----
# The dial sweeps 270 degrees: from -135 (0%) round to +135 (100%), 0 = straight up.
GAUGE_START, GAUGE_SWEEP = -135, 270


def gauge_angle(percent):
    """Needle angle in degrees for a 0-100 percentage."""
    percent = max(0, min(100, percent or 0))
    return GAUGE_START + GAUGE_SWEEP * percent / 100


def gauge_ticks(count=10, radius=50, centre=100):
    """Tick marks and number positions (0..count) around the dial, in SVG units."""
    ticks = []
    for i in range(count + 1):
        angle = GAUGE_START + GAUGE_SWEEP * i / count
        rad = math.radians(angle)
        ticks.append({"label": i, "angle": angle,
                      "x": round(centre + radius * math.sin(rad), 1),
                      "y": round(centre - radius * math.cos(rad), 1)})
    return ticks


def ticker_items():
    """
    Short lines for the scrolling ticker under the header, from live data.
    Falls back to fixed lines if the database can't be read (e.g. on an error page).
    """
    items = []
    try:
        from .services.fund import fund_summary
        from .services.voting import current_round, is_open
        fund = fund_summary()
        if fund["goal"] and not fund["funded"]:
            items.append(f"{money(fund['remaining'], False)} to go on the {fund['goal'].part_name.lower()}")
        elif fund["goal"]:
            items.append(f"{fund['goal'].part_name} fully funded")
        items.append(f"{money(fund['raised'], False)} raised so far")
        round_ = current_round()
        if round_ and is_open(round_):
            items.append(f"Voting open: {round_.title}")
    except Exception:  # noqa: BLE001 - decoration must never break a page
        pass
    return items + ["Every freshener = one vote", "Hand-poured in the garage", "Every install filmed"]


def register_template_helpers(app):
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["nice_date"] = nice_date
    app.jinja_env.filters["code"] = format_code
    app.jinja_env.filters["tier_label"] = lambda level: TIER_LABELS.get(level, level)
    app.jinja_env.globals["embed_info"] = embed_info
    app.jinja_env.globals["product_image_url"] = product_image_url
    app.jinja_env.filters["nice_datetime"] = nice_datetime
    app.jinja_env.filters["local_datetime"] = local_datetime
    app.jinja_env.globals["gauge_angle"] = gauge_angle
    app.jinja_env.globals["gauge_ticks"] = gauge_ticks
    app.jinja_env.globals["ticker_items"] = ticker_items

    @app.context_processor
    def inject_globals():
        # Variables every template can use without passing them in.
        from .services.cart import item_count
        return {"current_year": datetime.now(timezone.utc).year, "cart_count": item_count()}
