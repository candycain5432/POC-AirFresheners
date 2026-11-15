"""Stage 2: fund maths, video embeds, home and Revival Car pages."""
from datetime import date

import pytest

from app.extensions import db
from app.models import FundEntry, FundingGoal, Install
from app.services.embeds import embed_info
from app.services.fund import fund_summary


def test_fund_summary_counts_on_hand_money_toward_goal(app):
    db.session.add_all([
        FundEntry(amount_cents=100_000, source="manual"),
        Install(part_name="Battery", tier="budget", cost_cents=60_000, installed_on=date(2026, 1, 1)),
        FundingGoal(part_name="Calipers", tier="mid", goal_cents=65_000, status="active"),
    ])
    db.session.commit()
    s = fund_summary()
    assert (s["raised"], s["spent"], s["on_hand"]) == (100_000, 60_000, 40_000)
    assert s["toward_goal"] == 40_000 and s["remaining"] == 25_000 and s["percent"] == 62
    assert not s["funded"]


def test_fund_summary_caps_at_goal_and_handles_no_goal(app):
    db.session.add(FundEntry(amount_cents=999_00, source="manual"))
    db.session.commit()
    assert fund_summary()["goal"] is None
    db.session.add(FundingGoal(part_name="Seats", tier="budget", goal_cents=100_00, status="active"))
    db.session.commit()
    s = fund_summary()
    assert s["percent"] == 100 and s["remaining"] == 0 and s["funded"]


@pytest.mark.parametrize("url, expected_src, vertical", [
    ("https://www.youtube.com/watch?v=aqz-KE-bpKQ", "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ", False),
    ("https://youtu.be/aqz-KE-bpKQ?t=10", "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ", False),
    ("https://youtube.com/shorts/aqz-KE-bpKQ", "https://www.youtube-nocookie.com/embed/aqz-KE-bpKQ", True),
    ("https://www.tiktok.com/@shop/video/7300000000000000001", "https://www.tiktok.com/embed/v2/7300000000000000001", True),
])
def test_embed_info_accepts_youtube_and_tiktok(url, expected_src, vertical):
    info = embed_info(url)
    assert info["src"] == expected_src and info["vertical"] is vertical


@pytest.mark.parametrize("url", [
    "", "javascript:alert(1)", "https://evil.example/watch?v=aqz-KE-bpKQ",
    "https://www.youtube.com/watch?v=bad\"><script>", "https://youtube.com.evil.example/watch?v=aqz-KE-bpKQ",
    "https://www.tiktok.com/@x/video/abc",
])
def test_embed_info_rejects_everything_else(url):
    assert embed_info(url) is None


def seed_app(app, monkeypatch):
    import seed
    monkeypatch.setattr(seed, "create_app", lambda: app)
    seed.main()


def test_home_page(app, client, monkeypatch):
    seed_app(app, monkeypatch)
    html = client.get("/").get_data(as_text=True)
    assert "Every freshener helps bring a" in html
    assert "$340 to go" in html
    assert "Proof of concept: no real purchases are processed." in html
    assert "Patina Pete" in html            # Car of the Month
    assert "Round 7" in html                # current vote


def test_revival_car_page(app, client, monkeypatch):
    seed_app(app, monkeypatch)
    resp = client.get("/revival-car/")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Lazarus" in html and "$1,440" in html and "$1,130" in html
    assert "Ignition refresh" in html and "youtube-nocookie.com/embed/" in html
    assert "Content-Security-Policy" in resp.headers


def test_pages_work_with_empty_database(client):
    assert client.get("/").status_code == 200
    assert client.get("/revival-car/").status_code == 200
    assert client.get("/missing").status_code == 404
