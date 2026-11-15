"""
Dates and times in the shop's own time zone.

The database stores times in UTC (no time zone attached). People think in
local time. These helpers convert between the two using SHOP_TIMEZONE, so a
vote round set to close "Friday 8pm" in the admin closes at 8pm local time.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def shop_tz():
    return ZoneInfo(current_app.config["SHOP_TIMEZONE"])


def shop_today():
    """Today's date where the shop is (not where the server is)."""
    return datetime.now(shop_tz()).date()


def local_to_utc(local_naive):
    """A local wall-clock time (e.g. from <input type=datetime-local>) -> naive UTC for the database."""
    return local_naive.replace(tzinfo=shop_tz()).astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(utc_naive):
    """A naive UTC time from the database -> local wall-clock time (naive)."""
    if utc_naive is None:
        return None
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(shop_tz()).replace(tzinfo=None)
