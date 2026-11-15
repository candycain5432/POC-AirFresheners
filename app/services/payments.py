"""
Payment providers.

Checkout never talks to a payment service directly. It asks the provider
returned by get_payment_provider() to "start" payment for an order. Two
outcomes are possible:

  * PaymentResult(status="paid")      -> paid immediately (the mock does this)
  * PaymentResult(status="redirect")  -> send the visitor to redirect_url
                                         (a Stripe Checkout page would do this;
                                         Stripe's webhook later confirms payment)

ADDING STRIPE TEST MODE LATER (not done now):
  1. pip install stripe; set STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET.
  2. Write StripePaymentProvider.start_payment(): create a Checkout Session
     for the order (metadata={"order_reference": order.reference}) and
     return PaymentResult("redirect", reference=session.id, redirect_url=session.url).
  3. Add a webhook route that verifies Stripe's signature, then calls
     services.checkout.fulfill_order(order, payment_reference=...) on
     "checkout.session.completed". fulfill_order is safe to call twice.
  4. Set PAYMENT_PROVIDER=stripe.
"""
import secrets
from dataclasses import dataclass

from flask import current_app


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


PROVIDERS = {"mock": MockPaymentProvider}


def get_payment_provider():
    name = current_app.config.get("PAYMENT_PROVIDER", "mock")
    return PROVIDERS[name]()
