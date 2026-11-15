"""Stage 7: the admin panel."""
import io
import time
import zipfile
from datetime import date, datetime, timedelta

import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    CarOfTheMonth, CodeBatch, FailedAttempt, FreshenerCode, FundEntry, FundingGoal, GarageMember, Install,
    MeetDrop, Product, Vote, VoteRound,
)
from app.models._common import utcnow
from app.services.clock import local_to_utc, utc_to_local
from app.services.codes import create_codes
from app.services.fund import add_goal, fund_summary

PASSWORD = "correct horse battery staple"


@pytest.fixture
def admin_app(app):
    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(PASSWORD)
    return app


@pytest.fixture
def admin(admin_app):
    """A test client that is logged in as admin."""
    client = admin_app.test_client()
    assert client.post("/admin/login", data={"password": PASSWORD}).status_code == 302
    return client


def photo(name="p.jpg"):
    out = io.BytesIO()
    Image.new("RGB", (800, 600), (90, 90, 90)).save(out, "JPEG")
    return (io.BytesIO(out.getvalue()), name)


# ---------------------------------------------------------------- login & protection
ADMIN_PAGES = ["/admin/", "/admin/codes", "/admin/rounds", "/admin/installs", "/admin/meets", "/admin/garage", "/admin/fund"]


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_every_admin_page_needs_login(admin_app, client, url):
    resp = client.get(url)
    assert resp.status_code == 302 and "/admin/login" in resp.headers["Location"]


def test_admin_actions_need_login(admin_app, client):
    assert client.post("/admin/fund", data={"amount": "100", "note": "x"}).status_code == 302
    assert FundEntry.query.count() == 0


def test_wrong_password_and_lockout(admin_app, client):
    admin_app.config["ADMIN_LOGIN_ATTEMPT_LIMIT"] = 3
    for _ in range(3):
        assert client.post("/admin/login", data={"password": "nope"}).status_code == 401
    assert FailedAttempt.query.filter_by(action="admin_login").count() == 3
    # Locked out even with the right password now.
    resp = client.post("/admin/login", data={"password": PASSWORD})
    assert resp.status_code == 429 and b"Too many wrong passwords" in resp.data


def test_login_disabled_without_a_hash(app, client):
    app.config["ADMIN_PASSWORD_HASH"] = ""
    assert b"Admin is locked" in client.get("/admin/login").data
    assert client.post("/admin/login", data={"password": "anything"}).status_code == 503


def test_password_is_never_stored_in_plain_text(admin_app):
    assert PASSWORD not in admin_app.config["ADMIN_PASSWORD_HASH"]
    assert admin_app.config["ADMIN_PASSWORD_HASH"].startswith(("scrypt:", "pbkdf2:"))


def test_login_redirects_only_to_admin_pages(admin_app, client):
    resp = client.post("/admin/login?next=https://evil.example/", data={"password": PASSWORD})
    assert resp.headers["Location"].endswith("/admin/")
    client.post("/admin/logout")
    resp = client.post("/admin/login?next=/admin/fund", data={"password": PASSWORD})
    assert resp.headers["Location"].endswith("/admin/fund")


def test_logout_and_session_expiry(admin_app, admin):
    assert admin.get("/admin/").status_code == 200
    with admin.session_transaction() as s:
        s["admin_until"] = time.time() - 1          # pretend the session went stale
    assert admin.get("/admin/").status_code == 302
    admin.post("/admin/login", data={"password": PASSWORD})
    admin.post("/admin/logout")
    assert admin.get("/admin/").status_code == 302


def test_admin_pages_are_private(admin):
    resp = admin.get("/admin/")
    assert resp.headers["Cache-Control"] == "no-store"
    assert "noindex" in resp.headers["X-Robots-Tag"]


def test_admin_forms_need_csrf(admin_app):
    admin_app.config["WTF_CSRF_ENABLED"] = True
    assert admin_app.test_client().post("/admin/login", data={"password": PASSWORD}).status_code == 400


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_every_admin_page_renders(admin, url):
    assert admin.get(url).status_code == 200


# ---------------------------------------------------------------- codes
def test_code_batch_print_csv_and_zip(admin):
    resp = admin.post("/admin/codes", data={"label": "Frost Fest table", "count": "12"})
    batch = CodeBatch.query.one()
    assert resp.headers["Location"].endswith(f"/admin/codes/{batch.id}")
    assert len(batch.codes) == 12 and FreshenerCode.query.count() == 12

    sheet = admin.get(f"/admin/codes/{batch.id}/print").get_data(as_text=True)
    assert sheet.count("data:image/png;base64,") == 12 and "print-tag" in sheet

    csv_text = admin.get(f"/admin/codes/{batch.id}.csv").get_data(as_text=True)
    assert csv_text.splitlines()[0] == "code,batch,created_utc" and len(csv_text.splitlines()) == 13

    archive = zipfile.ZipFile(io.BytesIO(admin.get(f"/admin/codes/{batch.id}/qr.zip").data))
    assert len(archive.namelist()) == 12 and all(n.endswith(".png") for n in archive.namelist())


def test_code_batch_limits(admin):
    assert admin.post("/admin/codes", data={"label": "Too many", "count": "5000"}).status_code == 400
    assert admin.post("/admin/codes", data={"label": "", "count": "5"}).status_code == 400
    assert CodeBatch.query.count() == 0


# ---------------------------------------------------------------- vote rounds
def build_round(admin):
    admin.post("/admin/rounds", data={"title": "Round 8", "description": "Interior time"})
    rnd = VoteRound.query.filter_by(title="Round 8").one()
    admin.post(f"/admin/rounds/{rnd.id}/options", data={"name": "Seats"})
    admin.post(f"/admin/rounds/{rnd.id}/options", data={"name": "Carpet"})
    seats, carpet = rnd.options
    admin.post(f"/admin/options/{seats.id}/tiers", data={"level": "budget", "goal": "180", "description": "Junkyard"})
    admin.post(f"/admin/options/{seats.id}/tiers", data={"level": "mid", "goal": "$420.00"})
    admin.post(f"/admin/options/{carpet.id}/tiers", data={"level": "budget", "goal": "90"})
    return rnd


def local_input(delta):
    """A datetime-local form value, `delta` from now in the shop's time zone."""
    return (utc_to_local(utcnow()) + delta).strftime("%Y-%m-%dT%H:%M")


def test_build_open_extend_and_close_a_round(admin):
    rnd = build_round(admin)
    assert rnd.status == "draft" and sum(len(o.tiers) for o in rnd.options) == 3
    assert rnd.options[0].tiers[1].goal_cents == 42000

    admin.post(f"/admin/rounds/{rnd.id}/open", data={"closes_at": local_input(timedelta(days=3))})
    assert rnd.status == "open" and rnd.closes_at > utcnow() + timedelta(days=2)

    # Structure is frozen once open.
    admin.post(f"/admin/rounds/{rnd.id}/options", data={"name": "Sneaky"})
    assert len(rnd.options) == 2

    admin.post(f"/admin/rounds/{rnd.id}/close-time", data={"closes_at": local_input(timedelta(days=6))})
    assert rnd.closes_at > utcnow() + timedelta(days=5)

    code = create_codes(1)[0]
    db.session.add(Vote(round=rnd, tier=rnd.options[1].tiers[0], code=code))
    db.session.commit()
    admin.post(f"/admin/rounds/{rnd.id}/close")
    assert rnd.status == "closed" and rnd.winning_tier.option.name == "Carpet"
    assert FundingGoal.query.filter_by(part_name="Carpet").one().status == "active"


def test_round_open_rules(admin):
    rnd = build_round(admin)
    # Close time in the past is refused.
    admin.post(f"/admin/rounds/{rnd.id}/open", data={"closes_at": local_input(-timedelta(hours=1))})
    assert rnd.status == "draft"
    # Only one open round at a time.
    other = VoteRound(title="Already open", status="open", closes_at=utcnow() + timedelta(days=1))
    db.session.add(other)
    db.session.commit()
    resp = admin.post(f"/admin/rounds/{rnd.id}/open", data={"closes_at": local_input(timedelta(days=2))},
                      follow_redirects=True)
    assert rnd.status == "draft" and b"Another round is already open" in resp.data


def test_draft_can_be_deleted_but_not_closed_rounds(admin):
    rnd = build_round(admin)
    admin.post(f"/admin/rounds/{rnd.id}/delete")
    assert VoteRound.query.filter_by(title="Round 8").count() == 0
    closed = VoteRound(title="Old", status="closed")
    db.session.add(closed)
    db.session.commit()
    admin.post(f"/admin/rounds/{closed.id}/delete")
    assert db.session.get(VoteRound, closed.id) is not None


def test_round_close_time_is_local_time(admin_app):
    with admin_app.test_request_context():
        admin_app.config["SHOP_TIMEZONE"] = "America/New_York"
        # 8pm in New York in November (EST, UTC-5) is 1am UTC the next day.
        assert local_to_utc(datetime(2026, 11, 20, 20, 0)) == datetime(2026, 11, 21, 1, 0)
        assert utc_to_local(datetime(2026, 11, 21, 1, 0)) == datetime(2026, 11, 20, 20, 0)


# ---------------------------------------------------------------- installs
def test_log_install_completes_goal_and_promotes_queued(admin):
    calipers = add_goal("Brake calipers", "mid", 65000)
    seats = add_goal("Seats", "budget", 18000)        # queued behind the calipers
    db.session.add(FundEntry(amount_cents=100000, source="manual"))
    db.session.commit()
    assert seats.status == "queued"

    resp = admin.post("/admin/installs", content_type="multipart/form-data", data={
        "part_name": "Brake calipers", "tier": "mid", "cost": "612.40", "installed_on": "2026-11-28",
        "video_url": "https://youtu.be/aqz-KE-bpKQ", "notes": "Stops now!", "completes_goal": "1",
        "before_photos": [photo("a.jpg"), photo("b.jpg")], "after_photos": [photo("c.jpg")],
    })
    assert resp.status_code == 302
    install = Install.query.one()
    assert install.cost_cents == 61240 and install.goal_id == calipers.id
    assert len(install.before_photos) == 2 and len(install.after_photos) == 1
    assert calipers.status == "installed" and seats.status == "active"
    summary = fund_summary()
    assert summary["spent"] == 61240 and summary["goal"].id == seats.id


def test_install_video_must_be_youtube_or_tiktok(admin):
    resp = admin.post("/admin/installs", content_type="multipart/form-data", data={
        "part_name": "Radio", "tier": "budget", "cost": "40", "installed_on": "2026-11-28",
        "video_url": "https://evil.example/video",
    })
    assert resp.status_code == 400 and Install.query.count() == 0


def test_bad_photo_rolls_back_the_whole_install(admin, app):
    resp = admin.post("/admin/installs", content_type="multipart/form-data", data={
        "part_name": "Radio", "tier": "budget", "cost": "40", "installed_on": "2026-11-28",
        "before_photos": [photo("ok.jpg"), (io.BytesIO(b"not an image"), "bad.jpg")],
    })
    assert resp.status_code == 400 and Install.query.count() == 0
    import os
    folder = os.path.join(app.config["UPLOAD_DIR"], "installs")
    assert not os.path.isdir(folder) or os.listdir(folder) == []   # the good photo was cleaned up


def test_edit_install_adds_real_video_link(admin):
    install = Install(part_name="Radiator", tier="mid", cost_cents=26000, installed_on=date(2026, 7, 2))
    db.session.add(install)
    db.session.commit()
    admin.post(f"/admin/installs/{install.id}", content_type="multipart/form-data", data={
        "video_url": "https://www.tiktok.com/@shop/video/7300000000000000099", "notes": "Real video!", "cost": "260",
        "after_photos": [photo()],
    })
    assert install.video_url.endswith("0099") and len(install.photos) == 1
    admin.post(f"/admin/install-photos/{install.photos[0].id}/delete")
    assert len(install.photos) == 0


# ---------------------------------------------------------------- meets
def test_add_meet_with_online_product_and_sold_out_sync(admin, client):
    admin.post("/admin/meets", data={
        "meet_name": "Spring Thaw 2027", "meet_date": (date.today() + timedelta(days=30)).isoformat(),
        "location": "Fairgrounds", "scent_name": "Mud Season", "scent_description": "Wet earth.",
        "quantity": "80", "sell_online": "1", "price": "12",
    })
    meet = MeetDrop.query.one()
    product = Product.query.filter_by(meet_drop_id=meet.id).one()
    assert product.price_cents == 1200 and product.slug == "meet-mud-season"
    assert "Mud Season" in client.get("/shop/").get_data(as_text=True)

    admin.post(f"/admin/meets/{meet.id}/sold-out", data={"sold_out": "1"})
    assert meet.sold_out and product.sold_out
    admin.post(f"/admin/meets/{meet.id}/sold-out", data={"sold_out": "0"})
    assert not meet.sold_out and not product.sold_out

    admin.post(f"/admin/meets/{meet.id}/delete")
    assert MeetDrop.query.count() == 0
    assert Product.query.one().is_active is False      # kept for old orders, but off the shop


def test_add_meet_validation(admin):
    resp = admin.post("/admin/meets", data={"meet_name": "", "meet_date": "not a date", "location": "x", "scent_name": "y"})
    assert resp.status_code == 400 and MeetDrop.query.count() == 0


# ---------------------------------------------------------------- garage
def test_hide_and_feature_garage_cars(admin, client):
    code_a, code_b = create_codes(2)
    db.session.commit()                               # gives the codes their ids
    a = GarageMember(code_id=code_a.id, owner_name="A", car_name="Patina Pete")
    b = GarageMember(code_id=code_b.id, owner_name="B", car_name="Rude Rod")
    db.session.add_all([a, b])
    db.session.commit()

    admin.post(f"/admin/garage/{b.id}/hide", data={"hidden": "1"})
    assert b.is_hidden and "Rude Rod" not in client.get("/garage/").get_data(as_text=True)

    admin.post(f"/admin/garage/{b.id}/feature", data={"month": "2026-12", "blurb": "x"})
    assert CarOfTheMonth.query.count() == 0          # hidden cars can't be featured

    admin.post(f"/admin/garage/{a.id}/feature", data={"month": "2026-12", "blurb": "Fifty years of sun."})
    assert "Fifty years of sun." in client.get("/").get_data(as_text=True)


# ---------------------------------------------------------------- fund
def test_manual_fund_entries(admin):
    admin.post("/admin/fund", data={"amount": "125.50", "note": "Cash at Frost Fest"})
    admin.post("/admin/fund", data={"amount": "-20", "note": "Correction"})
    assert fund_summary()["raised"] == 10550
    assert admin.post("/admin/fund", data={"amount": "0", "note": "x"}).status_code == 400
    assert admin.post("/admin/fund", data={"amount": "12.345", "note": "x"}).status_code == 400
    assert admin.post("/admin/fund", data={"amount": "100", "note": ""}).status_code == 400
    page = admin.get("/admin/fund").get_data(as_text=True)
    assert "Cash at Frost Fest" in page and "-$20.00" in page


def test_dashboard_with_seed_data(admin, admin_app, monkeypatch):
    import seed
    monkeypatch.setattr(seed, "create_app", lambda: admin_app)
    seed.main()
    html = admin.get("/admin/").get_data(as_text=True)
    assert "Round 7" in html and "Recent orders" in html and "Brake calipers" in html
