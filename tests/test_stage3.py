"""Stage 3: shop, cart and mock checkout."""

import pytest

from app.extensions import db
from app.models import BlindBagScent, FreshenerCode, FundEntry, Order, Product
from app.services.checkout import fulfill_order
from app.services.fund import total_raised_cents


@pytest.fixture
def shop(app):
    """A small catalogue: one regular, one 3-pack, one custom, one blind bag, one sold-out item."""
    products = {
        "regular": Product(slug="burnt-clutch", name="Burnt Clutch", kind="regular", scent_description="x", price_cents=800),
        "bundle": Product(slug="three-pack", name="3-Pack", kind="bundle", scent_description="x", price_cents=2000,
                          fresheners_per_unit=3),
        "custom": Product(slug="custom", name="Custom", kind="custom", scent_description="x", price_cents=1400),
        "blind": Product(slug="blind", name="Blind Bag", kind="blind", scent_description="x", price_cents=600),
        "gone": Product(slug="gone", name="Gone", kind="meet", scent_description="x", price_cents=1000, sold_out=True),
    }
    db.session.add_all(products.values())
    db.session.add_all([BlindBagScent(name="Shop Rag"), BlindBagScent(name="Gold Leaf", is_chase=True)])
    db.session.commit()
    return products


def add(client, slug, qty=1, note=""):
    return client.post("/shop/cart/add", data={"slug": slug, "qty": qty, "note": note})


def checkout(client, name="Tasha", email=""):
    return client.post("/shop/checkout", data={"name": name, "email": email})


def test_shop_lists_products_and_sold_out(client, shop):
    html = client.get("/shop/").get_data(as_text=True)
    assert "Burnt Clutch" in html and "3-Pack" in html and "Sold out" in html


def test_full_mock_checkout_creates_codes_and_funds_car(client, shop):
    add(client, "burnt-clutch", 2)
    add(client, "three-pack", 1)
    add(client, "blind", 1)
    resp = checkout(client)
    assert resp.status_code == 302
    order = Order.query.one()
    assert order.status == "paid" and order.payment_provider == "mock"
    assert order.total_cents == 2 * 800 + 2000 + 600
    # 2 regular + 3 from the 3-pack + 1 blind bag = 6 codes
    assert FreshenerCode.query.count() == 6
    assert total_raised_cents() == order.total_cents
    blind_item = next(i for i in order.items if i.product_name == "Blind Bag")
    assert len(blind_item.blind_results) == 1

    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    for c in FreshenerCode.query.all():
        assert c.code[:4] in page                      # every code is shown (formatted)
    assert page.count("data:image/png;base64,") == 6   # one QR per code
    assert "Blind bag reveal" in page
    # The cart is emptied after checkout.
    assert "Nothing on the bench" in client.get("/shop/cart").get_data(as_text=True)


def test_custom_freshener_requires_a_description(client, shop):
    add(client, "custom", 1, note="")
    assert client.get("/shop/cart").get_data(as_text=True).count("cart-line ") == 0
    add(client, "custom", 1, note="Green pickup <script>alert(1)</script>")
    html = client.get("/shop/cart").get_data(as_text=True)
    assert "Green pickup" in html and "<script>alert(1)" not in html  # escaped


def test_cannot_buy_sold_out_or_silly_quantities(client, shop):
    add(client, "gone")
    add(client, "burnt-clutch", 999)
    add(client, "burnt-clutch", -3)
    add(client, "no-such-product")
    assert "Nothing on the bench" in client.get("/shop/cart").get_data(as_text=True)


def test_prices_come_from_database_not_the_cookie(client, shop):
    add(client, "burnt-clutch", 1)
    with client.session_transaction() as s:
        s["cart"][0]["price_cents"] = 1  # tampering attempt (ignored: we never read prices from the cookie)
    checkout(client)
    assert Order.query.one().total_cents == 800


def test_checkout_validates_name_and_email(client, shop):
    add(client, "burnt-clutch")
    assert "Please enter your name" in checkout(client, name="").get_data(as_text=True)
    assert "doesn&#39;t look right" in checkout(client, email="not-an-email").get_data(as_text=True)
    assert Order.query.count() == 0


def test_item_sold_out_while_in_cart_blocks_checkout(client, shop):
    add(client, "burnt-clutch")
    shop["regular"].sold_out = True
    db.session.commit()
    checkout(client)
    assert Order.query.count() == 0


def test_order_page_only_visible_to_the_buyer(app, client, shop):
    add(client, "burnt-clutch")
    location = checkout(client).headers["Location"]
    assert client.get(location).status_code == 200
    stranger = app.test_client()
    assert stranger.get(location).status_code == 404


def test_fulfill_order_is_idempotent(client, shop):
    add(client, "three-pack")
    checkout(client)
    order = Order.query.one()
    fulfill_order(order, "again")   # e.g. a payment webhook firing twice
    assert FreshenerCode.query.count() == 3
    assert FundEntry.query.count() == 1


def test_placeholder_svg_is_escaped(client, shop):
    shop["regular"].name = '<script>x</script>'
    db.session.commit()
    resp = client.get("/shop/product/burnt-clutch/image.svg")
    assert resp.content_type.startswith("image/svg+xml")
    assert b"<script>" not in resp.data.lower().replace(b"&lt;script&gt;", b"")


def test_csrf_is_enforced_when_enabled(app, shop):
    app.config["WTF_CSRF_ENABLED"] = True
    resp = app.test_client().post("/shop/cart/add", data={"slug": "burnt-clutch", "qty": 1})
    assert resp.status_code == 400 and b"Form expired" in resp.data
