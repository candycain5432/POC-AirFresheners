"""Stage 5: the Garage (code-as-key profiles, safe photo uploads, Car of the Month)."""
import io
import os

import pytest
from PIL import Image

from app.extensions import db
from app.models import CarOfTheMonth, FailedAttempt, GarageMember
from app.services.codes import create_codes, format_code
from app.services.uploads import MAX_SIDE


def image_bytes(fmt="JPEG", size=(2400, 1800), gps=False):
    """Make an in-memory test photo, optionally carrying GPS EXIF data."""
    img = Image.new("RGB", size, (200, 60, 40))
    out = io.BytesIO()
    if gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (40.0, 26.0, 46.0), 3: "W", 4: (79.0, 58.0, 56.0)}   # GPSInfo
        exif[0x010F] = "PhoneMaker"                                                        # camera make
        img.save(out, fmt, exif=exif)
    else:
        img.save(out, fmt)
    return out.getvalue()


@pytest.fixture
def codes(app):
    made = create_codes(3)
    db.session.commit()
    return made


def join(client, code):
    return client.post("/garage/join", data={"code": code})


def save(client, photo=None, filename="car.jpg", **fields):
    data = {"car_name": "Patina Pete", "owner_name": "Tasha R.", "description": "Daily driver.", **fields}
    if photo is not None:
        data["photo"] = (io.BytesIO(photo), filename)
    return client.post("/garage/edit", data=data, content_type="multipart/form-data")


def stored_path(app, member):
    return os.path.join(app.config["UPLOAD_DIR"], member.photo_filename)


def test_edit_requires_a_code_first(client):
    assert client.get("/garage/edit").headers["Location"].endswith("/garage/join")


def test_wrong_code_is_refused_and_counted(client, codes):
    resp = join(client, "ZZZZ-ZZZZ-ZZ")
    assert resp.status_code == 400 and FailedAttempt.query.count() == 1


def test_lockout_applies_to_the_garage_too(app, client, codes):
    app.config["CODE_ATTEMPT_LIMIT"] = 2
    join(client, "ZZZZ-ZZZZ-ZZ")
    join(client, "ZZZZ-ZZZZ-ZZ")
    assert join(client, codes[0].code).status_code == 429


def test_create_profile_with_photo(app, client, codes):
    assert join(client, format_code(codes[0].code).lower()).headers["Location"].endswith("/garage/edit")
    resp = save(client, photo=image_bytes(gps=True), is_new="1")
    assert resp.status_code == 302
    member = GarageMember.query.one()
    assert member.car_name == "Patina Pete" and member.code_id == codes[0].id

    # Stored as a re-encoded JPEG, shrunk, random name, and with NO EXIF/GPS.
    path = stored_path(app, member)
    assert member.photo_filename.startswith("garage/") and len(os.path.basename(path)) == 36
    with Image.open(path) as saved:
        assert saved.format == "JPEG" and max(saved.size) <= MAX_SIDE
        assert len(saved.getexif()) == 0

    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Patina Pete" in page and "Edit my car" in page
    assert codes[0].code not in page and format_code(codes[0].code) not in page   # the key stays secret


def test_same_code_edits_the_same_profile(app, client, codes):
    join(client, codes[0].code)
    save(client, photo=image_bytes())
    old_photo = stored_path(app, GarageMember.query.one())

    other_browser = app.test_client()
    join(other_browser, codes[0].code)
    assert "Patina Pete" in other_browser.get("/garage/edit").get_data(as_text=True)   # pre-filled
    save(other_browser, car_name="Pete II", photo=image_bytes(fmt="PNG"), filename="new.png")
    assert GarageMember.query.count() == 1
    member = GarageMember.query.one()
    assert member.car_name == "Pete II"
    assert not os.path.exists(old_photo)          # replaced photo is cleaned up


def test_photo_is_optional_and_can_be_removed(app, client, codes):
    join(client, codes[0].code)
    save(client)                                   # no photo
    assert GarageMember.query.one().photo_filename is None
    save(client, photo=image_bytes())
    path = stored_path(app, GarageMember.query.one())
    save(client, remove_photo="1")
    assert GarageMember.query.one().photo_filename is None and not os.path.exists(path)


@pytest.mark.parametrize("payload, filename", [
    (b"this is not an image", "car.jpg"),           # lies about being a JPEG
    (b"GIF89a fake", "car.gif"),                    # wrong type
    (image_bytes(fmt="GIF"), "car.jpg"),            # a real image, but a GIF in disguise
    (b"<?php echo 1; ?>", "shell.php"),             # obviously not
])
def test_bad_uploads_are_refused(client, codes, payload, filename):
    join(client, codes[0].code)
    resp = save(client, photo=payload, filename=filename)
    assert resp.status_code == 400
    assert GarageMember.query.count() == 0


def test_decompression_bomb_is_refused(client, codes):
    join(client, codes[0].code)
    # A tiny PNG that claims to be 10,000 x 10,000 pixels.
    resp = save(client, photo=image_bytes(fmt="PNG", size=(10000, 10000)), filename="bomb.png")
    assert resp.status_code in (400, 413)
    assert GarageMember.query.count() == 0


def test_oversized_upload_is_rejected(app, client, codes):
    join(client, codes[0].code)
    app.config["MAX_CONTENT_LENGTH"] = 1024
    resp = save(client, photo=image_bytes())
    assert resp.status_code == 413 and b"5 MB" in resp.data


def test_required_fields_and_length_limits(client, codes):
    join(client, codes[0].code)
    resp = save(client, car_name="", owner_name="x" * 61)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 400 and "Give your car a name" in html and "under 60" in html
    assert GarageMember.query.count() == 0


def test_text_is_escaped(client, codes):
    join(client, codes[0].code)
    resp = save(client, description="<script>alert('x')</script>")
    html = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "<script>alert('x')</script>" not in html and "&lt;script&gt;" in html


def test_grid_shows_cars_and_hides_moderated_ones(client, codes):
    db.session.add_all([
        GarageMember(code_id=codes[0].id, owner_name="A", car_name="Visible Van"),
        GarageMember(code_id=codes[1].id, owner_name="B", car_name="Hidden Hatch", is_hidden=True),
    ])
    db.session.commit()
    html = client.get("/garage/").get_data(as_text=True)
    assert "Visible Van" in html and "Hidden Hatch" not in html
    hidden = GarageMember.query.filter_by(car_name="Hidden Hatch").one()
    assert client.get(f"/garage/cars/{hidden.id}").status_code == 404


def test_car_of_the_month_on_garage_and_home(client, codes):
    member = GarageMember(code_id=codes[0].id, owner_name="Tasha", car_name="Patina Pete")
    db.session.add(member)
    db.session.flush()
    db.session.add(CarOfTheMonth(member_id=member.id, month="2026-11", blurb="Soul of the Garage."))
    db.session.commit()
    for url in ("/garage/", "/"):
        html = client.get(url).get_data(as_text=True)
        assert "Car of the Month" in html and "Soul of the Garage." in html
    # A hidden car can't stay featured.
    member.is_hidden = True
    db.session.commit()
    assert "Soul of the Garage." not in client.get("/").get_data(as_text=True)


def test_delete_profile_removes_photo_and_feature(app, client, codes):
    join(client, codes[0].code)
    save(client, photo=image_bytes())
    member = GarageMember.query.one()
    path = stored_path(app, member)
    db.session.add(CarOfTheMonth(member_id=member.id, month="2026-12"))
    db.session.commit()
    client.post("/garage/delete")
    assert GarageMember.query.count() == 0 and CarOfTheMonth.query.count() == 0
    assert not os.path.exists(path)
    assert client.get("/garage/edit").status_code == 302   # code forgotten too


def test_leave_forgets_the_code(client, codes):
    join(client, codes[0].code)
    client.post("/garage/leave")
    assert client.get("/garage/edit").status_code == 302


def test_garage_forms_need_csrf(app, codes):
    app.config["WTF_CSRF_ENABLED"] = True
    assert app.test_client().post("/garage/join", data={"code": codes[0].code}).status_code == 400
