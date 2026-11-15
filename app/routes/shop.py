"""
Shop pages: product list, product detail, cart, checkout and order confirmation.

The rules (prices, codes, the fund) live in services/cart.py and
services/checkout.py. These routes only read forms, call those
functions and pick a template.
"""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from ..models import Product
from ..services import cart as cart_service
from ..services.checkout import CheckoutError, create_pending_order, find_order, fulfill_order
from ..services.fund import fund_summary
from ..services.payments import get_payment_provider
from ..services.qr import qr_data_uri

bp = Blueprint("shop", __name__, url_prefix="/shop")

# Sections of the shop page, in display order.
SECTIONS = [
    ("regular", "Fresheners", "Hand-poured aroma beads. $8 each, one code each."),
    ("bundle", "Bundles", "More scents, more votes."),
    ("custom", "Custom", "Your car, as a freshener."),
    ("blind", "Blind bags", "Mystery scent. Chase the rare ones."),
    ("meet", "Meet exclusives", "Made for one meet only. When they're gone, they're gone."),
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
    sections = [(kind, title, blurb, [p for p in products if p.kind == kind])
                for kind, title, blurb in SECTIONS]
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
@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    lines = cart_service.get_lines()
    if not lines:
        flash("Your cart is empty.", "error")
        return redirect(url_for("shop.index"))

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
            if result.status == "redirect":            # e.g. Stripe Checkout, later
                return redirect(result.redirect_url)
            if result.status != "paid":
                flash(result.error or "Payment failed. Nothing was charged.", "error")
                return redirect(url_for("shop.checkout"))

            fulfill_order(order, payment_reference=result.reference, provider_name=provider.name)
            cart_service.clear()
            # Remember which orders THIS browser placed. Only they may see
            # the confirmation page, because it shows the voting codes.
            session["my_orders"] = (session.get("my_orders", []) + [order.reference])[-10:]
            return redirect(url_for("shop.order_complete", reference=order.reference))

    return render_template("shop/checkout.html", lines=lines, total=cart_service.total_cents(lines),
                           form=form, errors=errors)


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
