"""Stripe Checkout in test mode. Stripe's API is faked; webhook signatures are real."""
import hashlib
import hmac
import json
import os
import time

import pytest
import stripe

from app import create_app
from app.extensions import db
from app.models import FreshenerCode, FundEntry, Order, Product
from app.services import payments

WEBHOOK_SECRET = "whsec_test_secret"


class FakeSessions:
    """Stands in for client.v1.checkout.sessions; remembers what it was asked."""

    def __init__(self):
        self.created = []         # (params, options) per create() call
        self.stored = {}          # session id -> session dict, as Stripe would hold it
        self.fail = False

    def create(self, params, options=None):
        if self.fail:
            raise stripe.APIConnectionError("network down")
        session_id = f"cs_test_{len(self.created) + 1}"
        self.created.append((params, options))
        total = sum(li["price_data"]["unit_amount"] * li["quantity"] for li in params["line_items"])
        self.stored[session_id] = {"id": session_id, "object": "checkout.session", "payment_status": "unpaid",
                                   "amount_total": total, "metadata": params["metadata"]}
        return stripe.checkout.Session.construct_from(
            {"id": session_id, "url": f"https://checkout.stripe.com/c/pay/{session_id}"}, "sk_test_fake")

    def retrieve(self, session_id, params=None, options=None):
        return stripe.checkout.Session.construct_from(self.stored[session_id], "sk_test_fake")

    def pay(self, session_id):
        self.stored[session_id]["payment_status"] = "paid"
        return self.stored[session_id]


@pytest.fixture
def app(tmp_path, monkeypatch):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "test.db"),
        "UPLOAD_DIR": str(tmp_path / "uploads"),
        "WTF_CSRF_ENABLED": False,
        "PAYMENT_PROVIDER": "stripe",
        "STRIPE_SECRET_KEY": "sk_test_fake",
        "STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET,
    })
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    with app.app_context():
        yield app
        db.session.remove()


@pytest.fixture
def fake(monkeypatch):
    sessions = FakeSessions()
    real_client = stripe.StripeClient

    def make_client(key):
        client = real_client(key)          # real construct_event() for signature checks
        client.v1.checkout.sessions = sessions
        return client

    monkeypatch.setattr(payments.stripe, "StripeClient", make_client)
    return sessions


@pytest.fixture
def shop(app):
    db.session.add_all([
        Product(slug="burnt-clutch", name="Burnt Clutch", kind="regular", scent_description="x", price_cents=800),
        Product(slug="three-pack", name="3-Pack", kind="bundle", scent_description="x", price_cents=2000,
                fresheners_per_unit=3),
    ])
    db.session.commit()


def start_checkout(client, email="tasha@example.com"):
    client.post("/shop/cart/add", data={"slug": "burnt-clutch", "qty": 2})
    client.post("/shop/cart/add", data={"slug": "three-pack", "qty": 1})
    return client.post("/shop/checkout", data={"name": "Tasha", "email": email})


def signed_post(client, event, secret=WEBHOOK_SECRET):
    payload = json.dumps(event)
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/shop/stripe/webhook", data=payload, content_type="application/json",
                       headers={"Stripe-Signature": f"t={timestamp},v1={signature}"})


def event(kind, session):
    return {"id": "evt_1", "object": "event", "type": kind, "data": {"object": session}}


# ---------- startup safety ----------
@pytest.mark.parametrize("key", ["", "sk_live_abc", "rk_live_abc", "pk_test_abc"])
def test_app_refuses_to_start_without_a_test_key(tmp_path, key):
    with pytest.raises(RuntimeError, match="TEST secret key"):
        create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "x.db"),
                    "UPLOAD_DIR": str(tmp_path / "u"), "PAYMENT_PROVIDER": "stripe", "STRIPE_SECRET_KEY": key})


# ---------- checkout -> Stripe ----------
def test_checkout_redirects_to_stripe_with_order_prices(client, shop, fake):
    resp = start_checkout(client)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://checkout.stripe.com/c/pay/cs_test_1"
    assert "form-action 'self' https://checkout.stripe.com" in resp.headers["Content-Security-Policy"]

    order = Order.query.one()
    assert order.status == "pending" and order.payment_reference == "cs_test_1"
    assert FreshenerCode.query.count() == 0 and FundEntry.query.count() == 0   # nothing until paid

    params, options = fake.created[0]
    assert options == {"idempotency_key": "checkout-" + order.reference}
    assert params["metadata"] == {"order_reference": order.reference}
    assert params["customer_email"] == "tasha@example.com"
    assert "payment_method_types" not in params
    assert [(li["price_data"]["unit_amount"], li["quantity"]) for li in params["line_items"]] == [(800, 2), (2000, 1)]
    assert params["success_url"].endswith(f"/shop/order/{order.reference}/stripe-return?session_id={{CHECKOUT_SESSION_ID}}")
    # The cart survives until payment is confirmed (e.g. if the buyer cancels).
    assert "Burnt Clutch" in client.get("/shop/cart").get_data(as_text=True)


def test_checkout_page_explains_test_cards(client, shop, fake):
    client.post("/shop/cart/add", data={"slug": "burnt-clutch"})
    html = client.get("/shop/checkout").get_data(as_text=True)
    assert "Pay with Stripe (test)" in html and "4242 4242 4242 4242" in html


def test_stripe_error_fails_the_order_and_charges_nothing(client, shop, fake):
    fake.fail = True
    resp = start_checkout(client)
    assert resp.headers["Location"].endswith("/shop/checkout")
    assert Order.query.one().status == "failed"


def test_cancel_keeps_cart(client, shop, fake):
    start_checkout(client)
    html = client.get("/shop/checkout?cancelled=1").get_data(as_text=True)
    assert "Payment cancelled" in html and "Burnt Clutch" in html


# ---------- buyer returns from Stripe ----------
def test_return_after_payment_fulfills_and_shows_codes(client, shop, fake):
    start_checkout(client)
    order = Order.query.one()
    fake.pay("cs_test_1")
    resp = client.get(f"/shop/order/{order.reference}/stripe-return?session_id=cs_test_1")
    assert resp.headers["Location"].endswith(f"/shop/order/{order.reference}")
    assert order.status == "paid" and order.payment_provider == "stripe"
    assert FreshenerCode.query.count() == 2 + 3
    assert FundEntry.query.one().amount_cents == 3600
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Stripe test payment" in page
    assert "Nothing on the bench yet" in client.get("/shop/cart").get_data(as_text=True)


def test_return_without_payment_does_not_fulfill(client, shop, fake):
    start_checkout(client)
    order = Order.query.one()
    resp = client.get(f"/shop/order/{order.reference}/stripe-return?session_id=cs_test_1")
    assert resp.headers["Location"].endswith("/shop/cart")
    assert order.status == "pending" and FreshenerCode.query.count() == 0


def test_return_rejects_wrong_session_or_other_browser(app, client, shop, fake):
    start_checkout(client)
    order = Order.query.one()
    fake.pay("cs_test_1")
    assert client.get(f"/shop/order/{order.reference}/stripe-return?session_id=cs_test_999").status_code == 404
    stranger = app.test_client()
    assert stranger.get(f"/shop/order/{order.reference}/stripe-return?session_id=cs_test_1").status_code == 404
    assert order.status == "pending"


# ---------- webhook ----------
def test_webhook_rejects_bad_signature(client, shop, fake):
    start_checkout(client)
    paid = fake.pay("cs_test_1")
    assert signed_post(client, event("checkout.session.completed", paid), secret="whsec_wrong").status_code == 400
    assert Order.query.one().status == "pending"


def test_webhook_fulfills_once_even_if_repeated(client, shop, fake):
    start_checkout(client)
    paid = fake.pay("cs_test_1")
    for _ in range(2):
        assert signed_post(client, event("checkout.session.completed", paid)).status_code == 200
    order = Order.query.one()
    assert order.status == "paid"
    assert FreshenerCode.query.count() == 5 and FundEntry.query.count() == 1
    # The buyer arriving afterwards just sees their codes; nothing is doubled.
    client.get(f"/shop/order/{order.reference}/stripe-return?session_id=cs_test_1")
    assert FreshenerCode.query.count() == 5 and FundEntry.query.count() == 1


def test_webhook_ignores_unpaid_or_mismatched_sessions(client, shop, fake):
    start_checkout(client)
    unpaid = dict(fake.stored["cs_test_1"])
    assert signed_post(client, event("checkout.session.completed", unpaid)).status_code == 200
    wrong_amount = dict(fake.pay("cs_test_1"), amount_total=1)
    assert signed_post(client, event("checkout.session.completed", wrong_amount)).status_code == 200
    assert Order.query.one().status == "pending"


def test_webhook_async_success_and_expiry(client, shop, fake):
    start_checkout(client)
    paid = fake.pay("cs_test_1")
    signed_post(client, event("checkout.session.async_payment_succeeded", paid))
    assert Order.query.one().status == "paid"

    client.get("/shop/cart")   # second order, which the buyer abandons
    start_checkout(client)
    second = Order.query.filter_by(payment_reference="cs_test_2").one()
    signed_post(client, event("checkout.session.expired", fake.stored["cs_test_2"]))
    assert second.status == "failed"
    # Expiry can never undo a paid order.
    signed_post(client, event("checkout.session.expired", paid))
    assert Order.query.filter_by(payment_reference="cs_test_1").one().status == "paid"


def test_webhook_is_off_in_mock_mode(tmp_path):
    mock_app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "m.db"),
                           "UPLOAD_DIR": str(tmp_path / "u"), "STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET})
    assert mock_app.test_client().post("/shop/stripe/webhook", data="{}").status_code == 404
