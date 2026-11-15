"""
The Garage: members' car profiles.

There are no accounts. A freshener code is the key: whoever has the code
can create (or later edit) that code's ONE profile. After a correct code is
entered, its id is kept in the visitor's signed session cookie.
The code itself is never shown on any public page.
"""
from flask import session

from ..extensions import db
from ..models import CarOfTheMonth, FreshenerCode, GarageMember
from .uploads import delete_upload, save_image

SESSION_KEY = "garage_code_id"
PAGE_SIZE = 24

LIMITS = {"owner_name": 60, "car_name": 80, "description": 500}


# ---------------------------------------------------------------- reading
def visible_members(page=1):
    """Public grid, newest first, skipping profiles the admin has hidden."""
    query = GarageMember.query.filter_by(is_hidden=False).order_by(GarageMember.created_at.desc())
    return query.paginate(page=page, per_page=PAGE_SIZE, error_out=False)


def current_car_of_month():
    """The newest Car of the Month pick whose car is still visible, or None."""
    return (CarOfTheMonth.query.join(GarageMember)
            .filter(GarageMember.is_hidden.is_(False))
            .order_by(CarOfTheMonth.created_at.desc())
            .first())


# ---------------------------------------------------------------- who is editing
def remember_code(code):
    session[SESSION_KEY] = code.id


def forget_code():
    session.pop(SESSION_KEY, None)


def code_in_session():
    """The FreshenerCode this browser has unlocked, or None."""
    code_id = session.get(SESSION_KEY)
    return db.session.get(FreshenerCode, code_id) if code_id else None


def member_for_code(code):
    return GarageMember.query.filter_by(code_id=code.id).first() if code else None


# ---------------------------------------------------------------- saving
def clean_form(form):
    """Trim the text fields and return (values, errors)."""
    values = {key: (form.get(key) or "").strip() for key in LIMITS}
    errors = {}
    if not values["owner_name"]:
        errors["owner_name"] = "Add a name or handle so people know whose car it is."
    if not values["car_name"]:
        errors["car_name"] = "Give your car a name. Every project car has one."
    for key, limit in LIMITS.items():
        if len(values[key]) > limit:
            errors[key] = f"Please keep this under {limit} characters."
    return values, errors


def save_profile(code, values, photo=None, remove_photo=False):
    """
    Create or update the profile that belongs to `code`. `photo` is an
    optional uploaded file; it may raise uploads.UploadError (nothing is
    saved in that case).
    """
    member = member_for_code(code) or GarageMember(code_id=code.id)
    new_photo = save_image(photo, "garage") if photo is not None and photo.filename else None

    member.owner_name = values["owner_name"]
    member.car_name = values["car_name"]
    member.description = values["description"]
    if new_photo or remove_photo:
        delete_upload(member.photo_filename)
        member.photo_filename = new_photo
    db.session.add(member)
    db.session.commit()
    return member


def delete_profile(member):
    """Remove a profile and its photo. Car of the Month picks for it go too."""
    CarOfTheMonth.query.filter_by(member_id=member.id).delete()
    delete_upload(member.photo_filename)
    db.session.delete(member)
    db.session.commit()
