"""
Small helpers available inside every Jinja template.

Usage in a template:  {{ product.price_cents | money }}  ->  "$8.00"
"""
from datetime import datetime, timezone

from .services.codes import format_code


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


def register_template_helpers(app):
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["nice_date"] = nice_date
    app.jinja_env.filters["code"] = format_code

    @app.context_processor
    def inject_globals():
        # Variables every template can use without passing them in.
        return {"current_year": datetime.now(timezone.utc).year}
