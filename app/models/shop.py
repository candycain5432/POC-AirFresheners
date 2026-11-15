"""
The shop: products, mock orders and blind-bag scents.

Prices are stored in cents. A mock order is recorded exactly like a real
one would be, with `payment_provider = "mock"`, so a Stripe provider can be
added later without changing these tables much.
"""
from ..extensions import db
from ._common import utcnow

# The kinds of product we sell. Stored as short strings to keep it readable.
PRODUCT_KINDS = ("regular", "bundle", "custom", "meet", "blind")


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)  # used in URLs
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False)               # one of PRODUCT_KINDS
    scent_description = db.Column(db.Text, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    # How many physical fresheners one unit contains. A 3-pack is 3, so it
    # produces 3 freshener codes (= 3 votes) at checkout.
    fresheners_per_unit = db.Column(db.Integer, nullable=False, default=1)
    # Colour used for the CSS photo placeholder card.
    accent_color = db.Column(db.String(7), default="#c2571a")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sold_out = db.Column(db.Boolean, default=False, nullable=False)
    # Featured products appear in the row on the home page.
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    meet_drop_id = db.Column(db.Integer, db.ForeignKey("meet_drop.id"))  # set for meet exclusives
    position = db.Column(db.Integer, default=0)


class BlindBagScent(db.Model):
    """A possible result when a blind bag is opened. Chase scents are rare."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300), default="")
    is_chase = db.Column(db.Boolean, default=False, nullable=False)


class Order(db.Model):
    # "order" is a reserved SQL word; SQLAlchemy quotes it for us automatically.
    id = db.Column(db.Integer, primary_key=True)
    # Short public reference shown to the customer, e.g. "SS-7KD4QX".
    reference = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(80), nullable=False)
    customer_email = db.Column(db.String(120), default="")
    total_cents = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="paid")  # pending / paid / failed
    payment_provider = db.Column(db.String(20), nullable=False, default="mock")
    payment_reference = db.Column(db.String(120), default="")  # e.g. a Stripe PaymentIntent id later
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    """One line on an order. Name and price are copied so old orders don't change if the product does."""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    product_name = db.Column(db.String(120), nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    custom_note = db.Column(db.String(300), default="")  # custom freshener: "describe your car"

    product = db.relationship("Product")
    codes = db.relationship("FreshenerCode", backref="order_item")
    blind_results = db.relationship("BlindBagResult", backref="order_item", cascade="all, delete-orphan")

    @property
    def line_total_cents(self):
        return self.unit_price_cents * self.quantity


class BlindBagResult(db.Model):
    """Which scent each blind bag in an order turned out to be."""
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_item.id"), nullable=False)
    scent_id = db.Column(db.Integer, db.ForeignKey("blind_bag_scent.id"), nullable=False)
    scent = db.relationship("BlindBagScent")
