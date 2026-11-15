"""
Small product helpers used by several pages: featured products, the lowest
price ("Fresheners from $X") and where each product's photo lives.
"""
import os

from flask import current_app, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import Product


def buyable_products():
    """Products a visitor can actually add to the cart right now."""
    return Product.query.filter_by(is_active=True, sold_out=False)


def lowest_price_cents():
    """Cheapest buyable product, read from the database (None if the shop is empty)."""
    return (db.session.query(func.min(Product.price_cents))
            .filter(Product.is_active.is_(True), Product.sold_out.is_(False))
            .scalar())


def featured_products(limit=4):
    """Products marked is_featured; if none are, fall back to the first buyable ones."""
    featured = buyable_products().filter_by(is_featured=True).order_by(Product.position).limit(limit).all()
    return featured or buyable_products().order_by(Product.position).limit(limit).all()


def product_image_url(product):
    """
    URL of a product's photo.

    Drop a real photo at app/static/img/products/<slug>.jpg (square works best)
    and it is used automatically. Without one, a drawn SVG placeholder is shown.
    """
    relative = f"img/products/{product.slug}.jpg"
    if os.path.exists(os.path.join(current_app.static_folder, relative)):
        return url_for("static", filename=relative)
    return url_for("shop.product_image", slug=product.slug)
