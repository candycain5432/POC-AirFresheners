"""
A tiny helper for reading admin forms without a forms library.

    form = FormReader(request.form)
    title = form.text("title", "Title", max_len=120)
    goal = form.money("goal", "Goal")
    if form.errors: ...re-show the page with form.errors and form.values...

Each reader method returns the cleaned value (or None) and records a
friendly error message under the field's name if something's wrong.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class FormReader:
    def __init__(self, data):
        self.data = data
        self.values = {key: (data.get(key) or "").strip() for key in data.keys()}
        self.errors = {}

    def _raw(self, name):
        return (self.data.get(name) or "").strip()

    def text(self, name, label, required=True, max_len=200):
        value = self._raw(name)
        if required and not value:
            self.errors[name] = f"{label} is required."
        elif len(value) > max_len:
            self.errors[name] = f"{label} must be {max_len} characters or fewer."
        return value

    def money(self, name, label, required=True, allow_negative=False, maximum=1_000_000):
        """"12.50", "$1,200" or "-40" -> whole cents (int)."""
        raw = self._raw(name).replace("$", "").replace(",", "")
        if not raw:
            if required:
                self.errors[name] = f"{label} is required."
            return None
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            self.errors[name] = f"{label} must be an amount like 12.50."
            return None
        if amount != amount.quantize(Decimal("0.01")):
            self.errors[name] = f"{label} can't have more than two decimal places."
            return None
        if (amount < 0 and not allow_negative) or amount == 0 and not allow_negative:
            self.errors[name] = f"{label} must be more than zero."
            return None
        if abs(amount) > maximum:
            self.errors[name] = f"{label} looks too large."
            return None
        return int(amount * 100)

    def integer(self, name, label, minimum, maximum, required=True):
        raw = self._raw(name)
        if not raw:
            if required:
                self.errors[name] = f"{label} is required."
            return None
        try:
            number = int(raw)
        except ValueError:
            self.errors[name] = f"{label} must be a whole number."
            return None
        if not minimum <= number <= maximum:
            self.errors[name] = f"{label} must be between {minimum} and {maximum}."
            return None
        return number

    def date(self, name, label):
        try:
            return date.fromisoformat(self._raw(name))
        except ValueError:
            self.errors[name] = f"{label} must be a date."
            return None

    def local_datetime(self, name, label):
        """Value of an <input type="datetime-local">, e.g. "2026-11-20T20:00" (local time)."""
        try:
            return datetime.fromisoformat(self._raw(name))
        except ValueError:
            self.errors[name] = f"{label} must be a date and time."
            return None

    def choice(self, name, label, options):
        value = self._raw(name)
        if value not in options:
            self.errors[name] = f"Choose a {label.lower()}."
            return None
        return value

    def checkbox(self, name):
        return self.data.get(name) in ("1", "on", "true")
