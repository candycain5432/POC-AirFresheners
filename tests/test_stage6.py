"""Stage 6: meet drops."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import MeetDrop, Product
from app.services.cart import can_buy
from app.services.meets import meet_ics, meet_status, relative_day, shop_today


@pytest.fixture
def meets(app):
    today = shop_today()

    def meet(name, offset, sold_out=False, online=True):
        m = MeetDrop(meet_name=name, meet_date=today + timedelta(days=offset), location=f"{name} Lot, Springfield",
                     scent_name=f"{name} Scent", scent_description="Notes.", quantity=100, sold_out=sold_out)
        db.session.add(m)
        db.session.flush()
        if online:
            db.session.add(Product(slug=f"meet-{m.id}", name=f"{name} Scent (Meet Exclusive)", kind="meet",
                                   scent_description="x", price_cents=1000, meet_drop_id=m.id, sold_out=sold_out))
        return m

    made = {
        "soon": meet("Soon", 10),
        "later": meet("Later", 40),
        "in_person": meet("InPerson", 70, online=False),
        "past_gone": meet("PastGone", -30, sold_out=True),
        "past_left": meet("PastLeft", -5),
    }
    db.session.commit()
    return made


def test_page_splits_next_upcoming_and_past(client, meets):
    html = client.get("/meets/").get_data(as_text=True)
    assert "Next up" in html and "Soon" in html
    assert html.index("Soon") < html.index("Later") < html.index("InPerson") < html.index("Past drops")
    assert html.index("Past drops") < html.index("PastLeft") < html.index("PastGone")   # newest past first
    assert "10</strong> days to go" in html


def test_statuses(app, meets):
    today = shop_today()
    assert meet_status(meets["soon"], today)["label"] == "On sale now"
    assert meet_status(meets["in_person"], today)["label"] == "At the meet only"
    assert meet_status(meets["past_gone"], today)["label"] == "Sold out"
    assert meet_status(meets["past_left"], today)["label"] == "A few left online"
    meets["past_left"].products[0].sold_out = True
    assert meet_status(meets["past_left"], today)["label"] == "Meet over"


def test_sold_out_meet_blocks_its_product_even_if_product_flag_is_stale(client, meets):
    product = meets["soon"].products[0]
    meets["soon"].sold_out = True        # admin marked the MEET sold out, product flag not updated
    db.session.commit()
    assert can_buy(product) is False
    client.post("/shop/cart/add", data={"slug": product.slug, "qty": 1})
    assert "Nothing on the bench" in client.get("/shop/cart").get_data(as_text=True)


def test_buy_link_only_when_on_sale(client, meets):
    html = client.get("/meets/").get_data(as_text=True)
    assert f'/shop/product/meet-{meets["soon"].id}' in html
    assert f'/shop/product/meet-{meets["past_gone"].id}"' not in html


@pytest.mark.parametrize("offset, text", [
    (0, "Today"), (1, "Tomorrow"), (-1, "Yesterday"), (5, "In 5 days"), (-9, "9 days ago"),
    (21, "In 3 weeks"), (-35, "5 weeks ago"), (90, "In 3 months"), (-31 * 7, "7 months ago"),
])
def test_relative_day(offset, text):
    today = date(2026, 11, 15)
    assert relative_day(today + timedelta(days=offset), today) == text


def test_calendar_file(client, meets):
    resp = client.get(f"/meets/{meets['soon'].id}.ics")
    assert resp.status_code == 200 and resp.mimetype == "text/calendar"
    assert 'filename="soon.ics"' in resp.headers["Content-Disposition"]
    body = resp.get_data(as_text=True)
    start = meets["soon"].meet_date
    assert f"DTSTART;VALUE=DATE:{start:%Y%m%d}" in body
    assert f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}" in body
    assert "LOCATION:Soon Lot\\, Springfield" in body        # comma escaped
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert client.get("/meets/9999.ics").status_code == 404


def test_ics_escapes_and_folds_long_text(app):
    meet = MeetDrop(id=7, meet_name="Cars; Coffee, & More", meet_date=date(2026, 12, 6), location="A\nB",
                    scent_name="Pine", scent_description="x" * 300)
    text = meet_ics(meet, "https://example.com/meets/#meet-7")
    assert "SUMMARY:Cars\\; Coffee\\, & More" in text and "LOCATION:A\\nB" in text
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


def test_empty_calendar(client):
    assert "No meets on the calendar" in client.get("/meets/").get_data(as_text=True)


def test_upcoming_uses_the_shop_time_zone(app, meets):
    # Whatever the server's clock zone, "today" follows SHOP_TIMEZONE.
    app.config["SHOP_TIMEZONE"] = "Pacific/Kiritimati"     # UTC+14
    ahead = shop_today()
    app.config["SHOP_TIMEZONE"] = "Pacific/Pago_Pago"      # UTC-11
    behind = shop_today()
    assert (ahead - behind).days in (1, 2)
