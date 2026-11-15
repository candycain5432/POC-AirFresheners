"""Stage 4: voting with freshener codes, rate limiting, closing rounds."""
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import FailedAttempt, FundingGoal, PartOption, PartTier, Vote, VoteRound
from app.models._common import utcnow
from app.services.codes import create_codes, format_code
from app.services.fund import activate_next_goal, add_goal, fund_summary
from app.services.voting import close_expired_rounds, close_round, pick_winner


@pytest.fixture
def ballot(app):
    """An open round with two parts x two tiers, a closed old round, and some codes."""
    def make_round(title, status="open", closes_in=timedelta(days=2)):
        r = VoteRound(title=title, status=status, opened_at=utcnow() - timedelta(days=1),
                      closes_at=utcnow() + closes_in if closes_in else None)
        for name, tiers in (("Seats", [("budget", 18000), ("mid", 42000)]),
                            ("Exhaust", [("budget", 15000), ("mid", 38000)])):
            option = PartOption(name=name)
            for level, goal in tiers:
                option.tiers.append(PartTier(level=level, goal_cents=goal))
            r.options.append(option)
        db.session.add(r)
        return r

    open_round = make_round("Round 7")
    other_round = make_round("Round 6", status="closed", closes_in=None)
    codes = create_codes(4)
    db.session.commit()
    return {"round": open_round, "other": other_round, "codes": codes,
            "seats_mid": open_round.options[0].tiers[1], "exhaust_budget": open_round.options[1].tiers[0]}


def vote(client, code, tier_id):
    return client.post("/vote/", data={"code": code, "tier_id": tier_id})


def test_ballot_page_lists_every_part_and_tier(client, ballot):
    html = client.get("/vote/").get_data(as_text=True)
    assert "Round 7" in html and "Seats" in html and "Exhaust" in html
    assert html.count('name="tier_id"') == 4
    assert "$420" in html


def test_qr_link_prefills_the_code(client, ballot):
    raw = ballot["codes"][0].code
    html = client.get(f"/vote/?code={raw.lower()}").get_data(as_text=True)
    assert f'value="{format_code(raw)}"' in html


def test_successful_vote_is_recorded_and_highlighted(client, ballot):
    code = format_code(ballot["codes"][0].code).lower()   # sloppy typing is fine
    resp = vote(client, code, ballot["seats_mid"].id)
    assert resp.status_code == 302
    assert Vote.query.count() == 1
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "Vote locked in" in page and "Your vote" in page and "100%" in page


def test_one_vote_per_code_per_round(client, ballot):
    code = ballot["codes"][0].code
    vote(client, code, ballot["seats_mid"].id)
    resp = vote(client, code, ballot["exhaust_budget"].id)
    assert resp.status_code == 409
    assert "already voted" in resp.get_data(as_text=True)
    assert Vote.query.count() == 1
    # A different code from the same person is a separate vote.
    assert vote(client, ballot["codes"][1].code, ballot["exhaust_budget"].id).status_code == 302
    assert Vote.query.count() == 2


def test_wrong_code_is_rejected_and_counted(client, ballot):
    resp = vote(client, "AAAA-AAAA-AA", ballot["seats_mid"].id)
    assert resp.status_code == 400
    assert "couldn&#39;t find that code" in resp.get_data(as_text=True)
    assert FailedAttempt.query.count() == 1 and Vote.query.count() == 0


def test_too_many_wrong_codes_locks_out_even_a_real_code(app, client, ballot):
    app.config["CODE_ATTEMPT_LIMIT"] = 3
    for _ in range(3):
        vote(client, "BBBB-BBBB-BB", ballot["seats_mid"].id)
    resp = vote(client, ballot["codes"][0].code, ballot["seats_mid"].id)
    assert resp.status_code == 429
    assert "Too many wrong codes" in resp.get_data(as_text=True)
    assert Vote.query.count() == 0


def test_lockout_expires_after_the_window(app, client, ballot):
    app.config["CODE_ATTEMPT_LIMIT"] = 2
    for _ in range(2):
        vote(client, "BBBB-BBBB-BB", ballot["seats_mid"].id)
    # Pretend the failures happened long ago.
    for attempt in FailedAttempt.query.all():
        attempt.created_at = utcnow() - timedelta(hours=1)
    db.session.commit()
    assert vote(client, ballot["codes"][0].code, ballot["seats_mid"].id).status_code == 302


def test_cannot_vote_for_a_tier_from_another_round(client, ballot):
    foreign = ballot["other"].options[0].tiers[0]
    resp = vote(client, ballot["codes"][0].code, foreign.id)
    assert resp.status_code == 400 and Vote.query.count() == 0
    assert vote(client, ballot["codes"][0].code, "not-a-number").status_code == 400


def test_must_pick_a_choice(client, ballot):
    resp = vote(client, ballot["codes"][0].code, "")
    assert resp.status_code == 400 and "Pick one part" in resp.get_data(as_text=True)


def test_closed_round_refuses_votes(client, ballot):
    ballot["round"].status = "closed"
    db.session.commit()
    vote(client, ballot["codes"][0].code, ballot["seats_mid"].id)
    assert Vote.query.count() == 0


def test_round_past_close_time_closes_and_winner_becomes_goal(client, ballot):
    for code in ballot["codes"][:2]:
        vote(client, code.code, ballot["seats_mid"].id)
    ballot["round"].closes_at = utcnow() - timedelta(seconds=1)
    db.session.commit()
    vote(client, ballot["codes"][2].code, ballot["exhaust_budget"].id)   # too late
    assert Vote.query.count() == 2
    rnd = ballot["round"]
    assert rnd.status == "closed" and rnd.winning_tier_id == ballot["seats_mid"].id
    goal = FundingGoal.query.filter_by(tier_id=ballot["seats_mid"].id).one()
    assert goal.status == "active" and goal.part_name == "Seats" and goal.goal_cents == 42000
    assert fund_summary()["goal"].id == goal.id
    html = client.get(f"/vote/rounds/{rnd.id}").get_data(as_text=True)
    assert "Winner" in html and "Now funding" in html


def test_winner_waits_in_line_if_a_part_is_still_being_funded(app, ballot):
    current = add_goal("Brake calipers", "mid", 65000)
    db.session.add(Vote(round=ballot["round"], tier=ballot["exhaust_budget"], code=ballot["codes"][0]))
    db.session.commit()
    close_round(ballot["round"])
    queued = FundingGoal.query.filter_by(part_name="Exhaust").one()
    assert queued.status == "queued"
    assert fund_summary()["goal"].id == current.id and fund_summary()["next_goal"].id == queued.id
    # When the calipers are installed, the exhaust becomes the active goal.
    current.status = "installed"
    activate_next_goal()
    db.session.commit()
    assert fund_summary()["goal"].id == queued.id


def test_ties_go_to_the_cheaper_tier(app, ballot):
    codes = ballot["codes"]
    db.session.add_all([Vote(round=ballot["round"], tier=ballot["seats_mid"], code=codes[0]),
                        Vote(round=ballot["round"], tier=ballot["exhaust_budget"], code=codes[1])])
    db.session.commit()
    assert pick_winner(ballot["round"]).id == ballot["exhaust_budget"].id   # $150 beats $420


def test_round_with_no_votes_closes_without_a_goal(app, ballot):
    assert close_round(ballot["round"]) is None
    assert ballot["round"].status == "closed" and FundingGoal.query.count() == 0


def test_closing_twice_is_harmless(app, ballot):
    db.session.add(Vote(round=ballot["round"], tier=ballot["seats_mid"], code=ballot["codes"][0]))
    db.session.commit()
    close_round(ballot["round"])
    close_round(ballot["round"])
    assert close_expired_rounds() == []
    assert FundingGoal.query.count() == 1


def test_no_open_round_page(client, ballot):
    ballot["round"].status = "closed"
    db.session.commit()
    html = client.get("/vote/").get_data(as_text=True)
    assert "No vote open right now" in html and "Past rounds" in html


def test_vote_form_needs_csrf_token(app, ballot):
    app.config["WTF_CSRF_ENABLED"] = True
    resp = app.test_client().post("/vote/", data={"code": ballot["codes"][0].code, "tier_id": ballot["seats_mid"].id})
    assert resp.status_code == 400 and Vote.query.count() == 0


def test_user_input_is_escaped(client, ballot):
    html = vote(client, '<script>alert(1)</script>', ballot["seats_mid"].id).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
