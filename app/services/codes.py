"""
Freshener code generation and lookup.

Codes look like "K7PX-M3QD-WR" when displayed. They are 10 random characters
from a 31-symbol alphabet with look-alike characters removed (no O/0, I/1/L),
which gives 31**10 = ~820 trillion possibilities. With guessing rate-limited
to a handful of tries per IP, brute force is hopeless.
"""
import secrets

from ..extensions import db
from ..models import FreshenerCode

# Digits 2-9 and letters A-Z minus I, L, O. (0/O and 1/I/L look alike.)
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 10


def _random_code():
    # secrets.choice uses a cryptographically secure random source,
    # unlike random.choice, which is predictable.
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw):
    """
    Turn whatever the user typed into the stored form.
    " k7px-m3qd wr " -> "K7PXM3QDWR". Lower case is upper-cased, and dashes,
    spaces and any character not in ALPHABET are dropped.
    """
    if not raw:
        return ""
    cleaned = raw.upper()
    return "".join(ch for ch in cleaned if ch in ALPHABET)


def format_code(code):
    """Add dashes for readability: K7PXM3QDWR -> K7PX-M3QD-WR."""
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def create_codes(count, order_item=None, batch=None):
    """
    Create `count` new unique codes, attached to an order item or an admin
    batch. Rows are added to the session; the caller commits.
    """
    new_codes = []
    taken = set()
    while len(new_codes) < count:
        candidate = _random_code()
        # A collision is astronomically unlikely, but checking is cheap.
        if candidate in taken or FreshenerCode.query.filter_by(code=candidate).first():
            continue
        taken.add(candidate)
        row = FreshenerCode(code=candidate, order_item=order_item, batch=batch)
        db.session.add(row)
        new_codes.append(row)
    return new_codes


def find_code(raw):
    """Return the FreshenerCode for user input, or None if it doesn't exist."""
    code = normalize_code(raw)
    if len(code) != CODE_LENGTH:
        return None
    return FreshenerCode.query.filter_by(code=code).first()


def new_order_reference():
    """Short, human-friendly order number like "RR-7KD4QX" (not secret, just unique)."""
    from ..models import Order
    while True:
        ref = "RR-" + "".join(secrets.choice(ALPHABET) for _ in range(6))
        if not Order.query.filter_by(reference=ref).first():
            return ref
