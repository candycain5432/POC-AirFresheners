"""
The shopping cart, kept in the visitor's session cookie.

Flask signs the session cookie with SECRET_KEY, so visitors can read but
not tamper with it. We store only product ids, quantities and the custom
note. Prices are ALWAYS looked up fresh from the database, never trusted
from the cookie.

Cart format in the session:
    session["cart"] = [{"product_id": 3, "qty": 2, "note": ""}, ...]
"""
from flask import session

from ..extensions import db
from ..models import Product

MAX_QTY_PER_LINE = 10
MAX_LINES = 20
MAX_NOTE_LENGTH = 300


class CartError(ValueError):
    """Raised with a friendly message when a cart change isn't allowed."""


def _raw_cart():
    cart = session.get("cart")
    return cart if isinstance(cart, list) else []


def _save(cart):
    session["cart"] = cart
    session.modified = True


def can_buy(product):
    return product is not None and product.is_active and not product.sold_out


def add_item(product, qty, note=""):
    """Add a product to the cart, merging with an identical existing line."""
    if not can_buy(product):
        raise CartError("Sorry, that one isn't available.")
    if not 1 <= qty <= MAX_QTY_PER_LINE:
        raise CartError(f"Quantity must be between 1 and {MAX_QTY_PER_LINE}.")
    note = (note or "").strip()
    if product.kind == "custom":
        if not note:
            raise CartError("Tell us about your car so we can make your custom freshener.")
        if len(note) > MAX_NOTE_LENGTH:
            raise CartError(f"Please keep the description under {MAX_NOTE_LENGTH} characters.")
    else:
        note = ""  # only custom fresheners carry a note

    cart = _raw_cart()
    for line in cart:
        if line["product_id"] == product.id and line.get("note", "") == note:
            line["qty"] = min(MAX_QTY_PER_LINE, line["qty"] + qty)
            _save(cart)
            return
    if len(cart) >= MAX_LINES:
        raise CartError("Your cart is full. Check out first, then start another order.")
    cart.append({"product_id": product.id, "qty": qty, "note": note})
    _save(cart)


def update_qty(index, qty):
    """Change a line's quantity; 0 removes it. `index` is the line's position."""
    cart = _raw_cart()
    if not 0 <= index < len(cart):
        return
    if qty <= 0:
        cart.pop(index)
    else:
        cart[index]["qty"] = min(qty, MAX_QTY_PER_LINE)
    _save(cart)


def clear():
    session.pop("cart", None)


def get_lines():
    """
    Return the cart as a list of dicts with the real Product attached and
    prices from the database. Lines whose product vanished or sold out are
    marked unavailable so the cart page can say so.
    """
    lines = []
    for index, raw in enumerate(_raw_cart()):
        try:
            product = db.session.get(Product, int(raw.get("product_id")))
            qty = int(raw.get("qty", 1))
        except (TypeError, ValueError):
            continue  # ignore a malformed line rather than crash
        if product is None:
            continue
        lines.append({
            "index": index,
            "product": product,
            "qty": qty,
            "note": raw.get("note", ""),
            "available": can_buy(product),
            "line_total_cents": product.price_cents * qty,
        })
    return lines


def total_cents(lines):
    return sum(line["line_total_cents"] for line in lines if line["available"])


def item_count():
    """Number of units in the cart, for the header badge."""
    return sum(int(line.get("qty", 0)) for line in _raw_cart())
