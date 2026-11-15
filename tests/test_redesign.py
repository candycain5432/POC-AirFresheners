"""The Salvage & Scent redesign: rename, live 'from' price, countdown, results, photos, contrast."""
import os
import re
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Order, Product, VoteRound
from app.models._common import utcnow
from app.services.catalog import lowest_price_cents, product_image_url
from app.services.voting import round_results, seconds_left, split_duration

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def seeded(app, monkeypatch):
    import seed
    monkeypatch.setattr(seed, "create_app", lambda: app)
    seed.main()
    return app


def test_brand_is_salvage_and_scent_everywhere(client, seeded):
    for url in ("/", "/revival-car/", "/shop/"):
        html = client.get(url).get_data(as_text=True)
        assert "Salvage &amp; Scent" in html
        assert "Rust &amp; Revival" not in html and "Rust and Revival" not in html


def test_new_order_references_use_new_prefix(client, seeded):
    client.post("/shop/cart/add", data={"slug": "burnt-clutch", "qty": 1})
    client.post("/shop/checkout", data={"name": "Pat"})
    newest = Order.query.order_by(Order.id.desc()).first()
    assert newest.reference.startswith("SS-")


def test_from_price_comes_from_the_database(client, seeded):
    assert lowest_price_cents() == 600                       # the $6 blind bag
    assert "Fresheners from $6" in client.get("/").get_data(as_text=True)
    Product.query.filter_by(slug="blind-bag-chase").one().sold_out = True
    db.session.commit()
    assert "Fresheners from $8" in client.get("/").get_data(as_text=True)


def test_countdown_uses_close_time_from_database(client, seeded):
    rnd = VoteRound.query.filter_by(status="open").one()
    html = client.get("/").get_data(as_text=True)
    assert f'data-closes-at="{rnd.closes_at.isoformat()}Z"' in html
    assert re.search(r'<p class="countdown-closed"\s+hidden>', html)

    # Once the close time passes, the round closes on the next page view and
    # the home page shows the "Voting closed" band with the winner.
    rnd.closes_at = utcnow() - timedelta(minutes=1)
    db.session.commit()
    html = client.get("/").get_data(as_text=True)
    assert rnd.status == "closed"
    assert "Voting closed" in html and "See the final results" in html


def test_time_left_helpers(app):
    assert split_duration(90061) == {"days": 1, "hours": 1, "minutes": 1, "seconds": 1}
    assert seconds_left(None) is None
    past = VoteRound(title="x", closes_at=utcnow() - timedelta(hours=1))
    assert seconds_left(past) == 0


def test_results_add_up_and_show_on_home(client, seeded):
    rnd = VoteRound.query.filter_by(status="open").one()
    results = round_results(rnd)
    assert results["total"] == len(rnd.votes) > 0
    assert sum(o["votes"] for o in results["options"]) == results["total"]
    assert 97 <= sum(o["percent"] for o in results["options"]) <= 103   # rounding
    html = client.get("/").get_data(as_text=True)
    assert "Cast your vote" in html and 'class="bar is-leading"' in html
    for option in rnd.options:
        assert option.name in html


def test_product_photos_use_static_files_with_svg_fallback(app, seeded):
    with app.test_request_context():
        assert product_image_url(Product.query.filter_by(slug="burnt-clutch").one()) == \
            "/static/img/products/burnt-clutch.jpg"
        new = Product(slug="no-photo-yet", name="New", kind="regular", scent_description="x", price_cents=800)
        assert product_image_url(new).endswith("/shop/product/no-photo-yet/image.svg")


def test_placeholder_images_exist():
    for name in ("lazarus-hero.jpg", "lazarus-before.jpg", "lazarus-now.jpg", "noise.svg"):
        assert os.path.exists(os.path.join(ROOT, "app", "static", "img", name))


def test_revival_car_page_has_before_now_slider(client, seeded):
    html = client.get("/revival-car/").get_data(as_text=True)
    assert 'class="compare"' in html and 'type="range"' in html
    assert "lazarus-before.jpg" in html and "lazarus-now.jpg" in html


def _luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_muted_text_meets_wcag_aa():
    css = open(os.path.join(ROOT, "app", "static", "css", "style.css")).read()
    var = lambda name: re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", css).group(1)
    for background in ("bg", "surface", "surface-2"):
        assert _contrast(var("muted"), var(background)) >= 4.5, background
    assert _contrast(var("muted-on-dark"), var("ink")) >= 4.5
    assert _contrast(var("accent-on-dark"), var("ink")) >= 4.5
