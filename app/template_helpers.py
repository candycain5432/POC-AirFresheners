"""
Small helpers available inside every Jinja template.

Usage in a template:  {{ product.price_cents | money }}  ->  "$8.00"
"""
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


def register_template_helpers(app):
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["nice_date"] = nice_date
    app.jinja_env.filters["code"] = format_code
    app.jinja_env.filters["tier_label"] = lambda level: TIER_LABELS.get(level, level)
    app.jinja_env.globals["embed_info"] = embed_info
    app.jinja_env.globals["product_image_url"] = product_image_url
    app.jinja_env.filters["nice_datetime"] = nice_datetime

    @app.context_processor
    def inject_globals():
        # Variables every template can use without passing them in.
        from .services.cart import item_count
        return {"current_year": datetime.now(timezone.utc).year, "cart_count": item_count()}
