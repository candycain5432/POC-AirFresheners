"""Stage 1: models, code generation and the seed data."""
from app.extensions import db
from app.models import FreshenerCode, Vote, VoteRound
from app.services.codes import ALPHABET, CODE_LENGTH, create_codes, find_code, format_code, normalize_code


def test_codes_are_random_unambiguous_and_unique(app):
    codes = create_codes(200)
    db.session.commit()
    values = [c.code for c in codes]
    assert len(set(values)) == 200
    for v in values:
        assert len(v) == CODE_LENGTH
        assert not set(v) & set("O0I1L")
        assert set(v) <= set(ALPHABET)


def test_code_lookup_is_forgiving_about_formatting(app):
    code = create_codes(1)[0]
    db.session.commit()
    typed = format_code(code.code).lower().replace("-", " ")
    assert normalize_code(typed) == code.code
    assert find_code(typed).id == code.id
    assert find_code("NOPE") is None


def test_one_vote_per_code_per_round_enforced_by_database(app):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models import PartOption, PartTier

    rnd = VoteRound(title="R", status="open")
    opt = PartOption(name="Seats")
    tier = PartTier(level="mid", goal_cents=100)
    opt.tiers.append(tier)
    rnd.options.append(opt)
    code = create_codes(1)[0]
    db.session.add(rnd)
    db.session.commit()
    db.session.add(Vote(round=rnd, tier=tier, code=code))
    db.session.commit()
    db.session.add(Vote(round=rnd, tier=tier, code=code))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_seed_runs(app, monkeypatch):
    import seed
    # Point the seed at the test app instead of building its own.
    monkeypatch.setattr(seed, "create_app", lambda: app)
    seed.main()
    assert FreshenerCode.query.count() > 50
    assert VoteRound.query.filter_by(status="open").count() == 1
