"""
Payment providers.

Checkout never talks to a payment service directly. It asks the provider
returned by get_payment_provider() to "start" payment for an order. Two
outcomes are possible:

  * PaymentResult(status="paid")      -> paid immediately (the mock does this)
  * PaymentResult(status="redirect")  -> send the visitor to redirect_url
                                         (Stripe Checkout does this)

STRIPE TEST MODE (PAYMENT_PROVIDER=stripe)
  * start_payment() creates a Stripe Checkout Session for the order and the
    visitor is sent to Stripe's hosted payment page.
  * Stripe's webhook (POST /shop/stripe/webhook, signature-verified) is the
    main way an order gets fulfilled: it fires even if the buyer closes the
    tab after paying.
  * When the buyer comes back, routes/shop.py also asks Stripe (server to
    server) whether that session is paid, so they see their codes at once.
    fulfill_order() is safe to call twice, so the two paths can't clash.
  * Only TEST keys (sk_test_... / rk_test_...) are accepted. The app refuses
    to start with a live key, so no real card can be charged.
"""
import secrets
import string
from dataclasses import dataclass

import stripe
from flask import current_app, url_for

TEST_KEY_PREFIXES = ("sk_test_", "rk_test_")

# Tags our Checkout Sessions in the Stripe Dashboard (needs 8 random letters).
INTEGRATION_ID = "salvage-scent-poc-" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))


@dataclass
class PaymentResult:
    status: str                 # "paid", "redirect" or "failed"
    reference: str = ""         # provider's id for this payment
    redirect_url: str = ""      # only for status == "redirect"
    error: str = ""             # only for status == "failed"


class MockPaymentProvider:
    """Pretends every payment succeeds instantly. No money moves."""
    name = "mock"

    def start_payment(self, order):
        return PaymentResult(status="paid", reference="mock_" + secrets.token_hex(8))


class StripePaymentProvider:
    """Stripe Checkout in test mode: a hosted payment page, test cards only."""
    name = "stripe"

    def __init__(self):
        self.client = stripe.StripeClient(current_app.config["STRIPE_SECRET_KEY"])

    def start_payment(self, order):
        line_items = []
        for item in order.items:
            product_data = {"name": item.product_name}
            if item.custom_note:
                product_data["description"] = item.custom_note[:300]
            line_items.append({
                "quantity": item.quantity,
                "price_data": {
                    "currency": current_app.config["STRIPE_CURRENCY"],
                    "unit_amount": item.unit_price_cents,   # the price snapshot on the order
                    "product_data": product_data,
                },
            })

        # Stripe swaps {CHECKOUT_SESSION_ID} for the real id. It's added by
        # hand because url_for() would escape the braces.
        success_url = (url_for("shop.stripe_return", reference=order.reference, _external=True)
                       + "?session_id={CHECKOUT_SESSION_ID}")
        params = {
            "mode": "payment",
            "line_items": line_items,
            "client_reference_id": order.reference,
            "metadata": {"order_reference": order.reference},
            "integration_identifier": INTEGRATION_ID,
            "success_url": success_url,
            "cancel_url": url_for("shop.checkout", cancelled=1, _external=True),
        }
        if order.customer_email:
            params["customer_email"] = order.customer_email

        try:
            # The order reference doubles as an idempotency key, so a retried
            # request can never create two sessions for one order.
            session = self.client.v1.checkout.sessions.create(
                params, {"idempotency_key": "checkout-" + order.reference})
        except stripe.StripeError as error:
            current_app.logger.warning("Stripe Checkout Session failed: %s", error)
            return PaymentResult(status="failed",
                                 error="We couldn't open the payment page. Nothing was charged. Please try again.")
        return PaymentResult(status="redirect", reference=session.id, redirect_url=session.url)

    def get_session(self, session_id):
        """Fetch a Checkout Session straight from Stripe (never trust the browser's word), as a dict."""
        return self.client.v1.checkout.sessions.retrieve(session_id).to_dict()

    def parse_webhook(self, payload, signature):
        """Verify Stripe's signature and return the event. Raises ValueError or SignatureVerificationError."""
        return self.client.construct_event(payload, signature, current_app.config["STRIPE_WEBHOOK_SECRET"])


def session_pays_for_order(checkout_session, order):
    """
    True only if this Stripe session (as a dict) is paid, and is for exactly
    this order and amount.
    """
    metadata = checkout_session.get("metadata") or {}
    return (
        checkout_session.get("payment_status") not in (None, "unpaid")
        and checkout_session.get("id") == order.payment_reference
        and metadata.get("order_reference") == order.reference
        and checkout_session.get("amount_total") == order.total_cents
    )


PROVIDERS = {"mock": MockPaymentProvider, "stripe": StripePaymentProvider}


def get_payment_provider():
    name = current_app.config.get("PAYMENT_PROVIDER", "mock")
    return PROVIDERS[name]()


def check_payment_config(app):
    """Fail fast at startup on a bad payment setup, especially a live Stripe key."""
    name = app.config.get("PAYMENT_PROVIDER", "mock")
    if name not in PROVIDERS:
        raise RuntimeError(f"PAYMENT_PROVIDER must be one of {sorted(PROVIDERS)}, not {name!r}.")
    if name == "stripe":
        key = app.config.get("STRIPE_SECRET_KEY", "")
        if not key.startswith(TEST_KEY_PREFIXES):
            raise RuntimeError(
                "PAYMENT_PROVIDER=stripe needs a Stripe TEST secret key (sk_test_...) in "
                "STRIPE_SECRET_KEY. Live keys are refused: this is a proof of concept.")
