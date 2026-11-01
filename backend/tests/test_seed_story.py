"""The example hatchery must tell the exact story in the seed file and SPEC §7.6, §13."""
from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from app import config, db, models
from app.rules.text import TankBrief, fmt_count, fmt_survival, headline_for, reason_for, summary_for
from app.seed import run_seed
from app.services.world import load_world

EXPECTED = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))["expected"]

SUMMARY_FULL = (
    "Line 2 water has been corrosive since yesterday. It now affects T-04 and T-05, and T-06 is on the same "
    "line. Separately, T-03 shows a pattern that matches a bacterial outbreak."
)

REASONS_FULL = {
    "T-02": "Size spread is widening: CV 0.21, up from 0.14 at the last check.",
    "T-03": "Dead larvae 24%, up from 9% at the last check. Growth has stalled.",
    "T-04": "Line 2 water is corrosive (Ω 1.4). Abnormal shells are up to 19%.",
    "T-05": "Line 2 water is corrosive (Ω 1.4). Abnormal shells are up to 13%.",
    "T-06": "On line 2 (Ω 1.4). Larvae look normal so far.",
    "T-10": "Growth is 4.1 µm a day, below the 9 expected. Guts look light.",
}


def _briefs(world):
    return [TankBrief(s.id, s.level, s.assessment.pattern if s.assessment else None, s.line_id, s.active)
            for s in world.tanks.values()]


def _pending(session):
    rows = session.exec(select(models.Decision).where(models.Decision.status == "pending"))
    return sorted(f"{d.line_id if d.scope == 'line' else d.tank_id}:{d.action}" for d in rows)


@pytest.fixture(scope="module", params=["demo", "full"])
def seeded(request):
    run_seed(full=request.param == "full", reset=True)
    with Session(db.get_engine()) as session:
        yield request.param, session, load_world(session)


def test_levels_and_patterns(seeded):
    mode, _, world = seeded
    for tank_id, want in EXPECTED[mode].items():
        state = world.tanks[tank_id]
        assert state.level == want["level"], tank_id
        assert state.assessment.pattern == want["pattern"], tank_id


def test_empty_tanks(seeded):
    _, _, world = seeded
    for tank_id in EXPECTED["empty_tanks"]:
        assert world.tanks[tank_id].level == "empty"
        assert world.tanks[tank_id].batch is None
    assert world.tanks["T-09"].tank.status == "cleaning"
    assert world.tanks["S-02"].tank.status == "empty"


def test_pending_decisions(seeded):
    mode, session, _ = seeded
    assert _pending(session) == sorted(EXPECTED["pending_decisions"][mode])


def test_headline(seeded):
    mode, _, world = seeded
    assert headline_for(_briefs(world)) == EXPECTED["headline"][mode]


def test_every_row_is_flagged_as_example(seeded):
    _, session, _ = seeded
    for table in (models.Tank, models.Batch, models.Check, models.Decision):
        assert all(row.is_example for row in session.exec(select(table)))
    assert session.get(models.Hatchery, 1).is_example
    assert all(photo.synthetic for photo in session.exec(select(models.Photo)))


def test_seeded_stats_match_the_file(seeded):
    mode, session, _ = seeded
    source = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))
    batches = {b.code: b for b in session.exec(select(models.Batch))}
    for spec in source["batches"]:
        rows = list(session.exec(
            select(models.Check).where(models.Check.batch_id == batches[spec["code"]].id).order_by(models.Check.sampled_at)
        ))
        wanted = [c for c in sorted(spec["checks"], key=lambda c: (c["day"], c["time"]))
                  if mode == "full" or not c.get("demo_live")]
        assert len(rows) == len(wanted), spec["code"]
        for row, item in zip(rows, wanted, strict=True):
            assert (row.n_live, row.n_abnormal, row.n_dead) == (
                item["counts"]["live"], item["counts"]["abnormal"], item["counts"]["dead"]
            )
            assert row.mean_len_um == pytest.approx(item["mean_len_um"], abs=0.1), spec["code"]
            assert row.sd_len_um == pytest.approx(item["sd_len_um"], abs=0.1), spec["code"]
            assert row.gut == pytest.approx(item["gut"], abs=0.01), spec["code"]
            assert row.live_est == item["live_est"]


def test_every_check_has_a_risk_snapshot_and_photo(seeded):
    _, session, _ = seeded
    for check in session.exec(select(models.Check)):
        assert check.level in ("ok", "watch", "risk", "critical")
        assert check.rules_version == config.RULES_VERSION
        photos = list(session.exec(select(models.Photo).where(models.Photo.check_id == check.id)))
        assert len(photos) == 1
        assert (config.data_dir() / photos[0].path).exists()


def test_full_mode_numbers():
    run_seed(full=True, reset=True)
    with Session(db.get_engine()) as session:
        world = load_world(session)
        active = [s for s in world.tanks.values() if s.active]
        total = sum(s.latest.live_est for s in active)
        survival = sum(s.assessment.survival for s in active) / len(active)
        assert fmt_count(total) == "135.6M"
        assert fmt_survival(survival) == "65%"
        assert len(active) == 10 and len(world.tanks) == 12
        assert len(_pending(session)) == 7
        assert summary_for(_briefs(world), world.alerts, world.now) == SUMMARY_FULL
        for tank_id, reason in REASONS_FULL.items():
            state = world.tanks[tank_id]
            text = reason_for(state.assessment, state.line_id, state.alert is not None, len(state.checks), world.cfg)
            assert text == reason, tank_id


def test_t03_demo_photo_matches_the_fixture_byte_for_byte():
    run_seed(full=True, reset=True)
    with Session(db.get_engine()) as session:
        world = load_world(session)
        latest = world.tanks["T-03"].latest
        photo = session.exec(select(models.Photo).where(models.Photo.check_id == latest.id)).one()
    saved = (config.data_dir() / photo.path).read_bytes()
    assert saved == (config.FIXTURES_DIR / "demo" / "t03-today.jpg").read_bytes()
