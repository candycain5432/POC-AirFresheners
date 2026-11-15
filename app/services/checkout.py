"""
Checkout: turning a cart into an order, and "fulfilling" a paid order.

    create_pending_order()  -> Order(status="pending"), prices copied from the DB
    fulfill_order()         -> marks it paid, then:
                                 * one freshener code per physical freshener
                                   (a 3-pack makes 3 codes)
                                 * opens each blind bag (rare chase ~1 in 10)
                                 * adds the order total to the Revival Car fund

fulfill_order() is the single place where a sale "counts". It does nothing
if the order is already paid, so a payment webhook that fires twice (or a
webhook and the buyer's return page arriving together) can't create
duplicate codes or double-count money.
"""
import secrets

from sqlalchemy import update

from ..extensions import db
from ..models import BlindBagResult, BlindBagScent, FundEntry, Order, OrderItem
from .codes import create_codes, new_order_reference

CHASE_ODDS = 0.10            # 1 in 10 blind bags is a chase scent

# A cryptographically secure random generator, so chase pulls can't be predicted.
_random = secrets.SystemRandom()


class CheckoutError(ValueError):
    pass


def create_pending_order(lines, customer_name, customer_email=""):
    """Build an unpaid Order from cart lines (from services.cart.get_lines())."""
    buyable = [line for line in lines if line["available"]]
    if not buyable:
        raise CheckoutError("Your cart is empty.")
    if len(buyable) != len(lines):
        raise CheckoutError("Something in your cart sold out. Please review your cart.")

    order = Order(reference=new_order_reference(), customer_name=customer_name,
                  customer_email=customer_email, total_cents=0, status="pending")
    for line in buyable:
        product = line["product"]
        order.items.append(OrderItem(
            product=product,
            product_name=product.name,               # snapshot: survives later renames
            unit_price_cents=product.price_cents,    # snapshot: survives later price changes
            quantity=line["qty"],
            custom_note=line["note"],
        ))
    order.total_cents = sum(item.unit_price_cents * item.quantity for item in order.items)
    db.session.add(order)
    db.session.commit()
    return order


def _open_blind_bag():
    """Pick a blind-bag scent: chase with CHASE_ODDS, otherwise a regular one."""
    want_chase = _random.random() < CHASE_ODDS
    pool = BlindBagScent.query.filter_by(is_chase=want_chase).all()
    if not pool:  # e.g. no chase scents configured: fall back to anything
        pool = BlindBagScent.query.all()
    return _random.choice(pool) if pool else None


def fulfill_order(order, payment_reference, provider_name="mock"):
    """Mark an order paid and hand out everything it earned. Safe to repeat."""
    if order.status == "paid":
        return order

    # Claim the order with one conditional UPDATE. If two requests race here,
    # the database lets only one of them change "pending" to "paid"; the other
    # updates 0 rows and stops.
    claimed = db.session.execute(
        update(Order)
        .where(Order.id == order.id, Order.status != "paid")
        .values(status="paid", payment_provider=provider_name, payment_reference=payment_reference)
    ).rowcount
    if not claimed:
        db.session.rollback()
        db.session.refresh(order)
        return order

    for item in order.items:
        per_unit = item.product.fresheners_per_unit if item.product else 1
        create_codes(item.quantity * per_unit, order_item=item)
        if item.product and item.product.kind == "blind":
            for _ in range(item.quantity):
                scent = _open_blind_bag()
                if scent:
                    item.blind_results.append(BlindBagResult(scent=scent))

    db.session.add(FundEntry(amount_cents=order.total_cents, source="order",
                             order=order, note=f"Order {order.reference}"))
    # One commit: either ALL of the above is saved, or none of it.
    db.session.commit()
    return order


def find_order(reference):
    return Order.query.filter_by(reference=reference).first()


def mark_order_failed(order):
    """An unpaid order whose payment failed or expired. Paid orders are never touched."""
    if order.status == "pending":
        order.status = "failed"
        db.session.commit()
