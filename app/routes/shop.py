"""
Shop pages: product list, product detail, cart, checkout and order confirmation.

The rules (prices, codes, the fund) live in services/cart.py and
services/checkout.py. These routes only read forms, call those
functions and pick a template.
"""
import re

import stripe
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from ..extensions import csrf, db
from ..models import Product
from ..services import cart as cart_service
from ..services.checkout import (CheckoutError, create_pending_order, find_order, fulfill_order,
                                 mark_order_failed)
from ..services.fund import fund_summary
from ..services.payments import get_payment_provider, session_pays_for_order
from ..services.qr import qr_data_uri

bp = Blueprint("shop", __name__, url_prefix="/shop")

# Sections of the shop page, in display order: (anchor id, title, blurb, product kinds).
SECTIONS = [
    ("fresheners", "Fresheners", "Hand-poured aroma beads. $8 each, one code each.", ("regular",)),
    ("more", "More ways to buy", "Bundles for more votes, a freshener shaped like your car, or a mystery blind bag.",
     ("bundle", "custom", "blind")),
    ("meet", "Meet exclusives", "Made for one meet only. When they're gone, they're gone.", ("meet",)),
]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _int_field(name, default=0):
    """Read a whole number from the form, falling back to `default` on junk input."""
    try:
        return int(request.form.get(name, default))
    except (TypeError, ValueError):
        return default


@bp.route("/")
def index():
    products = Product.query.filter_by(is_active=True).order_by(Product.position).all()
    sections = []
    for anchor, title, blurb, kinds in SECTIONS:
        items = [p for p in products if p.kind in kinds]
        items.sort(key=lambda p: p.sold_out)   # available first; sort() keeps the order otherwise
        sections.append((anchor, title, blurb, items))
    return render_template("shop/index.html", sections=sections)


@bp.route("/product/<slug>")
def product(slug):
    item = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    return render_template("shop/product.html", product=item,
                           max_qty=cart_service.MAX_QTY_PER_LINE, max_note=cart_service.MAX_NOTE_LENGTH)


@bp.route("/product/<slug>/image.svg")
def product_image(slug):
    """
    Placeholder product photo drawn as SVG in the product's colour.
    (An image, rather than an inline style, keeps our strict CSP happy.)
    """
    item = Product.query.filter_by(slug=slug).first_or_404()
    color = item.accent_color if HEX_COLOR.match(item.accent_color or "") else "#c2571a"
    svg = render_template("shop/placeholder.svg", product=item, color=color)
    return svg, 200, {"Content-Type": "image/svg+xml", "Cache-Control": "public, max-age=3600"}


# ---------------- Cart ----------------
@bp.route("/cart")
def cart():
    lines = cart_service.get_lines()
    return render_template("shop/cart.html", lines=lines, total=cart_service.total_cents(lines),
                           max_qty=cart_service.MAX_QTY_PER_LINE)


@bp.route("/cart/add", methods=["POST"])
def cart_add():
    item = Product.query.filter_by(slug=request.form.get("slug", "")).first()
    try:
        cart_service.add_item(item, _int_field("qty", 1), request.form.get("note", ""))
    except cart_service.CartError as error:
        flash(str(error), "error")
        return redirect(url_for("shop.product", slug=item.slug) if item else url_for("shop.index"))
    flash(f"Added {item.name} to your cart.", "success")
    return redirect(url_for("shop.cart"))


@bp.route("/cart/update", methods=["POST"])
def cart_update():
    cart_service.update_qty(_int_field("index", -1), _int_field("qty", 0))
    return redirect(url_for("shop.cart"))


# ---------------- Checkout ----------------
def _remember_order(reference):
    """Only the browser that placed an order may see its confirmation page (it shows the codes)."""
    session["my_orders"] = (session.get("my_orders", []) + [reference])[-10:]


@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    lines = cart_service.get_lines()
    if not lines:
        flash("Your cart is empty.", "error")
        return redirect(url_for("shop.index"))
    if request.method == "GET" and request.args.get("cancelled"):
        flash("Payment cancelled. Nothing was charged, and your cart is still here.", "error")

    form = {"name": "", "email": ""}
    errors = {}
    if request.method == "POST":
        form["name"] = request.form.get("name", "").strip()
        form["email"] = request.form.get("email", "").strip()
        if not 1 <= len(form["name"]) <= 80:
            errors["name"] = "Please enter your name (up to 80 characters)."
        if form["email"] and (len(form["email"]) > 120 or not EMAIL_PATTERN.match(form["email"])):
            errors["email"] = "That email address doesn't look right."

        if not errors:
            try:
                order = create_pending_order(lines, form["name"], form["email"])
            except CheckoutError as error:
                flash(str(error), "error")
                return redirect(url_for("shop.cart"))

            provider = get_payment_provider()
            result = provider.start_payment(order)
            if result.status == "redirect":            # Stripe Checkout
                # Store the session id so the return page and webhook can
                # check that Stripe's session belongs to this order.
                order.payment_provider = provider.name
                order.payment_reference = result.reference
                db.session.commit()
                _remember_order(order.reference)
                return redirect(result.redirect_url)   # cart is kept until payment is confirmed
            if result.status != "paid":
                mark_order_failed(order)
                flash(result.error or "Payment failed. Nothing was charged.", "error")
                return redirect(url_for("shop.checkout"))

            fulfill_order(order, payment_reference=result.reference, provider_name=provider.name)
            cart_service.clear()
            _remember_order(order.reference)
            return redirect(url_for("shop.order_complete", reference=order.reference))

    return render_template("shop/checkout.html", lines=lines, total=cart_service.total_cents(lines),
                           form=form, errors=errors, provider=get_payment_provider().name)


@bp.route("/order/<reference>/stripe-return")
def stripe_return(reference):
    """
    Stripe sends the buyer here after paying. We never trust the URL: the
    session is fetched from Stripe and must be paid, for this order, for
    this amount. (The webhook usually got there first; that's fine.)
    """
    if reference not in session.get("my_orders", []):
        abort(404)
    order = find_order(reference)
    session_id = request.args.get("session_id", "")
    if order is None or order.payment_provider != "stripe" or session_id != order.payment_reference:
        abort(404)

    if order.status != "paid":
        try:
            checkout_session = get_payment_provider().get_session(session_id)
        except stripe.StripeError:
            flash("We couldn't confirm your payment with Stripe yet. Refresh this page in a moment.", "error")
            return redirect(url_for("shop.cart"))
        if not session_pays_for_order(checkout_session, order):
            flash("Your payment hasn't gone through yet. If you were charged, your codes "
                  "will appear when Stripe confirms it. Refresh this page in a moment.", "error")
            return redirect(url_for("shop.cart"))
        fulfill_order(order, payment_reference=session_id, provider_name="stripe")

    cart_service.clear()
    return redirect(url_for("shop.order_complete", reference=order.reference))


@bp.route("/stripe/webhook", methods=["POST"])
@csrf.exempt   # Stripe can't send our CSRF token; its signature is checked instead
def stripe_webhook():
    if current_app.config.get("PAYMENT_PROVIDER") != "stripe" or not current_app.config.get("STRIPE_WEBHOOK_SECRET"):
        abort(404)
    try:
        event = get_payment_provider().parse_webhook(
            request.get_data(), request.headers.get("Stripe-Signature", ""))
    except (ValueError, stripe.SignatureVerificationError):
        return "Invalid signature", 400

    if event.type.startswith("checkout.session."):
        checkout_session = event.data.object.to_dict()
        order = find_order((checkout_session.get("metadata") or {}).get("order_reference", ""))
        if order is not None and checkout_session.get("id") == order.payment_reference:
            if event.type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
                if session_pays_for_order(checkout_session, order):
                    fulfill_order(order, payment_reference=checkout_session.get("id"), provider_name="stripe")
            elif event.type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
                mark_order_failed(order)
    # Always 200 for events we don't act on, so Stripe doesn't keep retrying them.
    return "", 200


@bp.route("/order/<reference>")
def order_complete(reference):
    if reference not in session.get("my_orders", []):
        abort(404)  # don't reveal whether someone else's order exists
    order = find_order(reference)
    if order is None or order.status != "paid":
        abort(404)

    # Each code's QR image carries a link to the vote page with the code filled in.
    codes = []
    for item in order.items:
        for code in item.codes:
            link = url_for("vote.index", code=code.code, _external=True)
            codes.append({"code": code.code, "item": item.product_name, "qr": qr_data_uri(link, box_size=4)})

    return render_template("shop/order_complete.html", order=order, codes=codes, fund=fund_summary())
