"""The Advisor's rules on the example hatchery, and the API around them (SPEC §16). No Claude here."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import db, models
from app.config import DEFAULTS
from app.main import app
from app.rules.advisor import yield_opportunities
from app.rules.assess import assess
from app.rules.facts import Pace, TankFacts, batch_loss_per_day, feed_cells_per_larva_day, pace_batch, project, size_below_share
from app.rules.playbook import Playbook, advice_for
from app.rules.series import BatchData, CheckData
from app.rules.water import WaterReading
from app.seed import run_seed


@pytest.fixture()
def client():
    run_seed(full=False, reset=True)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def full_client():
    run_seed(full=True, reset=True)
    with TestClient(app) as test_client:
        yield test_client


def _facts(checks, stocked=20_000_000, spawn=date(2026, 10, 1), kind="larval", volume_l=2000.0, tank_id="T-99", line="L1",
           hist=None) -> TankFacts:
    data = tuple(checks)
    assessment = assess(data, BatchData(spawn, stocked), kind, DEFAULTS)
    return TankFacts(
        id=tank_id, kind=kind, room_id="A", room_name="Room", line_id=line, volume_l=volume_l, status="active", batch_code="B",
        spawn_date=spawn, stocked=stocked, day=10, checks=data, assessment=assessment, level=assessment.level, hist=hist,
    )


# ------------------------------------------------------------------ crash risks


def test_a_line_alert_is_one_risk_covering_its_tanks(client):
    page = client.get("/api/advisor").json()
    line = page["risks"][0]
    assert line["id"] == "line-L2"
    assert line["title"] == "Line 2 water is corrosive"
    assert line["tank_ids"] == ["T-04", "T-05", "T-06"]
    assert line["level"] == "risk"
    assert line["at_stake"] == pytest.approx(16_500_000 + 18_000_000 + 22_400_000)
    assert line["at_stake_text"] == "56.9M"
    assert [t["key"] for t in line["tiles"]] == ["ph", "omega", "abnormal"]
    assert line["tiles"][0]["tank_id"] == "T-04" and line["tiles"][0]["now_text"] == "7.62"
    assert [s["action"] for s in line["steps"]] == ["buffer_line", "hold_spawn"]


def test_risks_come_worst_first_and_each_tank_with_a_problem_is_covered(client):
    page = client.get("/api/advisor").json()
    assert [r["id"] for r in page["risks"]] == ["line-L2", "tank-T-10", "tank-T-03"]
    # A splitting batch costs yield rather than threatening a crash, so it's a yield suggestion
    assert not any("T-02" in r["tank_ids"] for r in page["risks"])
    assert page["totals"]["at_risk_text"] == "75.1M"
    assert page["headline"] == "3 risks could turn into a crash. 3 ways to raise yield."


def test_t03_turns_critical_and_leads_the_list_with_its_steps(full_client):
    page = full_client.get("/api/advisor").json()
    first = page["risks"][0]
    assert first["id"] == "tank-T-03" and first["level"] == "critical"
    assert "bacterial outbreak" in first["title"]
    assert [s["action"] for s in first["steps"]] == ["isolate", "sample_vibrio", "restock"]
    assert any("sodium hypochlorite" in s["how"] for s in first["steps"])
    assert [t["key"] for t in first["tiles"]][0] == "dead"


def test_why_text_matches_what_the_readings_show(client):
    risks = {r["id"]: r for r in client.get("/api/advisor").json()["risks"]}
    assert "light guts" in risks["tank-T-10"]["why"]  # T-10's guts are light
    assert "guts still look normal" in risks["tank-T-03"]["why"]  # T-03's aren't, yet


def test_steps_already_decided_show_as_decided(client):
    risks = {r["id"]: r for r in client.get("/api/advisor").json()["risks"]}
    step = risks["tank-T-03"]["steps"][0]
    assert step["action"] == "feed_check" and step["status"] == "approved"
    assert risks["tank-T-03"]["steps_left"] == 0
    assert risks["line-L2"]["steps_left"] == 2


# ------------------------------------------------------------------ doses and the plant's chemicals


def _buffer_step(page: dict) -> dict:
    return next(s for s in page["risks"][0]["steps"] if s["action"] == "buffer_line")


def test_the_buffer_step_carries_a_calculated_dose(client):
    step = _buffer_step(client.get("/api/advisor").json())
    assert "sodium carbonate" in step["how"]
    dose = step["dose"]
    assert dose["buffer"] == "sodium_carbonate"
    assert dose["per_1000l_text"] == "16 g per 1,000 L"
    assert dose["total_text"] == "96 g across T-04, T-05 and T-06 (6,000 L)"
    assert dose["effect_text"].startswith("Ω 1.4 to 3.0, pH 7.62 to")
    assert "jar" in dose["note"]
    assert {o["key"] for o in dose["options"]} == {"sodium_carbonate", "sodium_hydroxide", "sodium_bicarbonate"}


def test_changing_the_plants_buffer_changes_the_dose_everywhere(client):
    before = _buffer_step(client.get("/api/advisor").json())["dose"]["per_1000l_g"]
    assert client.post("/api/advisor/plant", json={"buffer": "sodium_hydroxide"}).status_code == 200
    page = client.get("/api/advisor").json()
    step = _buffer_step(page)
    assert page["plant"]["buffer"] == "sodium_hydroxide"
    assert step["dose"]["buffer"] == "sodium_hydroxide" and step["dose"]["per_1000l_g"] < before
    assert "sodium hydroxide" in step["how"]
    # The tank page and the Decisions page read the same setting
    tank = client.get("/api/tanks/T-04").json()
    assert next(a for a in tank["actions"] if a["action"] == "buffer_line")["dose"]["buffer"] == "sodium_hydroxide"
    groups = client.get("/api/decisions?status=pending").json()["groups"]
    line = next(g for g in groups if g["kind"] == "line")
    assert line["items"][0]["dose"]["buffer"] == "sodium_hydroxide"


def test_changing_the_disinfectant_changes_the_steps(full_client):
    assert full_client.post("/api/advisor/plant", json={"disinfectant": "peracetic_acid"}).status_code == 200
    steps = full_client.get("/api/advisor").json()["risks"][0]["steps"]
    assert any("peracetic acid" in s["how"] for s in steps)
    assert not any("hypochlorite" in s["how"] for s in steps)


@pytest.mark.parametrize("body", [{"buffer": "lye"}, {"disinfectant": "holy water"}])
def test_unknown_chemicals_are_refused(client, body):
    assert client.post("/api/advisor/plant", json=body).status_code == 422


def test_re_seeding_restores_the_default_chemicals(client):
    client.post("/api/advisor/plant", json={"buffer": "sodium_hydroxide"})
    run_seed(full=False, reset=True)
    assert client.get("/api/advisor").json()["plant"]["buffer"] == "sodium_carbonate"


# ------------------------------------------------------------------ yield suggestions


def test_yield_suggestions_for_the_example_hatchery(client):
    page = client.get("/api/advisor").json()
    assert [o["id"] for o in page["opportunities"]] == ["yield-T-07-setting", "yield-T-02-pace", "yield-T-08-density"]
    setting, pace, density = page["opportunities"]
    assert "S-02 is empty" in setting["why"]
    assert "240 µm" in setting["steps"][0]["how"] and "2.0M" in setting["steps"][0]["how"]
    assert pace["title"] == "T-02 is losing larvae 2.1× as fast as T-01"
    assert pace["stat_text"].startswith("+") and pace["steps"][0]["action"] == "screen"
    assert "measured under" in pace["steps"][0]["how"]
    assert density["stat_text"] == "31,000"
    assert "T-09 once it's clean" in density["steps"][0]["how"] and "15,500" in density["steps"][0]["how"]


def test_answering_a_suggestion_keeps_it_off_the_waiting_list(client):
    before = client.get("/api/floor").json()["metrics"]["decisions_waiting"]
    step = client.get("/api/advisor").json()["opportunities"][0]["steps"][0]
    assert step["id"] is None and step["status"] == "pending"
    answer = client.post("/api/advisor/answer", json={"action": "move_to_setting", "tank_id": "T-07", "verb": "approve"})
    assert answer.status_code == 200, answer.text
    row = answer.json()
    assert row["status"] == "approved" and row["decided_by"] == "Dana Ortiz" and row["done_text"] == "Grading scheduled"
    assert client.get("/api/floor").json()["metrics"]["decisions_waiting"] == before
    after = client.get("/api/advisor").json()["opportunities"][0]["steps"][0]
    assert after["id"] == row["id"] and after["status"] == "approved"
    # It's in the record
    decided = client.get("/api/decisions?status=decided").json()["groups"]
    assert any(item["action"] == "move_to_setting" for group in decided for item in group["items"])


def test_answering_twice_keeps_the_first_answer(client):
    first = client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-08", "verb": "dismiss"}).json()
    second = client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-08", "verb": "approve"}).json()
    assert first["id"] == second["id"] and second["status"] == "dismissed"


def test_undo_takes_a_suggestion_back_to_unanswered(client):
    before = client.get("/api/floor").json()["metrics"]["decisions_waiting"]
    row = client.post("/api/advisor/answer", json={"action": "move_to_setting", "tank_id": "T-07", "verb": "approve"}).json()
    undone = client.post(f"/api/decisions/{row['id']}/undo")
    assert undone.status_code == 200 and undone.json()["status"] == "pending"
    assert client.get("/api/floor").json()["metrics"]["decisions_waiting"] == before
    assert client.get("/api/advisor").json()["opportunities"][0]["steps"][0]["id"] is None


def test_an_answer_belongs_to_the_batch_it_was_given_for(client):
    row = client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-08", "verb": "approve"}).json()
    assert client.get("/api/tanks/T-08").json()["suggestions"][0]["status"] == "approved"
    # The same tank with a later batch: the old answer no longer counts, and a new one makes a new row
    with Session(db.get_engine()) as session:
        batch = session.exec(select(models.Batch).where(models.Batch.tank_id == "T-08")).one()
        decision = session.get(models.Decision, row["id"])
        decision.created_at = datetime.combine(batch.spawn_date - timedelta(days=30), datetime.min.time())
        session.add(decision)
        session.commit()
    step = client.get("/api/tanks/T-08").json()["suggestions"][0]
    assert step["status"] == "pending" and step["id"] is None
    fresh = client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-08", "verb": "approve"}).json()
    assert fresh["id"] != row["id"]


def test_how_text_for_actions_the_example_data_doesnt_trigger():
    tank = _facts(_steady(), tank_id="T-01")
    hot = replace(tank, checks=(*tank.checks[:-1], replace(tank.checks[-1], temp_c=28.4)))
    empty = replace(tank, id="S-02", kind="setting", batch_code=None, volume_l=400.0)
    water = {"T-01": WaterReading(25.0, 29.0, 7.6, 1.3)}
    book = Playbook(plant=DEFAULTS["plant"], tanks={"T-01": hot, "S-02": empty}, water=water, cfg=DEFAULTS)
    assert "28.4 °C" in advice_for("temp_check", "T-01", None, book)[0]
    assert "6 mg/L" in advice_for("aerate", "T-01", None, book)[0]
    assert "two slides" in advice_for("recount", "T-01", None, book)[0]
    assert "hypochlorite" in advice_for("discard", "T-01", None, book)[0]
    assert "Compare drain timing" in advice_for("review_handling", "T-01", None, book)[0]
    how, dose = advice_for("buffer_tank", "T-01", None, book)
    assert "this tank" in how and dose["total_text"].endswith("T-01 (2,000 L)")
    assert advice_for("anything_else", "T-01", None, book) == (None, None)
    assert advice_for("isolate", "T-01", None, None) == (None, None)  # no playbook, no how


def test_a_tank_with_no_free_setting_tank_says_so():
    tank = _facts(_steady(), tank_id="T-01")
    book = Playbook(plant=DEFAULTS["plant"], tanks={"T-01": tank}, water={}, cfg=DEFAULTS)
    assert "No setting tank is free" in advice_for("move_to_setting", "T-01", None, book)[0]
    assert "No larval tank is free" in advice_for("split_tank", "T-01", None, book)[0]
    how, dose = advice_for("buffer_tank", "T-01", None, book)  # no water reading, so no dose rather than a guess
    assert how and dose is None


def test_the_answer_endpoint_only_takes_suggestions(client):
    assert client.post("/api/advisor/answer", json={"action": "isolate", "tank_id": "T-03", "verb": "approve"}).status_code == 422
    assert client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-99", "verb": "approve"}).status_code == 404
    assert client.post("/api/advisor/answer", json={"action": "claude_suggestion", "tank_id": "T-03", "verb": "approve"}).status_code == 422


def test_the_floor_says_what_to_do_next(client):
    step = client.get("/api/floor").json()["advisor"]["next_step"]
    assert step == {"title": "Buffer line 2 water to bring Ω aragonite to 3 or higher", "card_id": "line-L2"}
    for group in client.get("/api/decisions?status=pending").json()["groups"]:
        for item in group["items"]:
            client.post(f"/api/decisions/{item['id']}/approve", json={})
    assert client.get("/api/floor").json()["advisor"]["next_step"] is None


def test_the_floor_and_tank_page_show_suggestions(client):
    floor = client.get("/api/floor").json()
    assert floor["advisor"]["n_yield"] == 3 and floor["advisor"]["n_risks"] == 3
    assert [c["id"] for c in floor["advisor"]["yield_chips"]] == ["T-07", "T-02", "T-08"]
    t07 = client.get("/api/tanks/T-07").json()
    assert [s["action"] for s in t07["suggestions"]] == ["move_to_setting"] and t07["actions_left"] == 1
    assert client.get("/api/tanks/T-01").json()["suggestions"] == []
    # T-02's screen step is already one of its recommended actions, so it isn't listed twice
    assert client.get("/api/tanks/T-02").json()["suggestions"] == []


def test_every_action_says_how_to_carry_it_out(full_client):
    page = full_client.get("/api/advisor").json()
    for card in page["risks"] + page["opportunities"]:
        for step in card["steps"]:
            assert step["how"], step["action"]


# ------------------------------------------------------------------ the forecast


def test_the_forecast_is_rules_based_arithmetic(client):
    forecast = client.get("/api/advisor").json()["forecast"]
    assert forecast["pace"]["tank_id"] == "T-01"
    rows = {r["tank_id"]: r for r in forecast["rows"]}
    assert "S-01" not in rows  # already in the setting room
    assert rows["T-07"]["when_text"] == "Ready now" and rows["T-07"]["gain"] == 0
    assert rows["T-04"]["when_text"] == "Not on course" and rows["T-04"]["on_course"] == 0
    assert rows["T-04"]["possible"] > 0
    for row in rows.values():
        assert row["possible"] >= row["on_course"]
        assert row["possible"] <= row["live"]
    assert forecast["possible"] > forecast["on_course"] > 0
    assert forecast["on_course"] == pytest.approx(sum(r["on_course"] for r in rows.values()))


def _steady(n=4, start=19_000_000.0, daily=0.97, length=100.0, growth=10.0):
    return [
        CheckData(sampled_at=datetime(2026, 10, 2 + 2 * i, 12), live_est=start * daily ** (2 * i), pct_dead=2.0, pct_abnormal=2.0,
                  mean_len_um=length + 2 * growth * i, cv=0.08, gut=0.8)
        for i in range(n)
    ]


def test_pace_comes_from_healthy_batches_with_enough_checks():
    steady = _facts(_steady(), tank_id="T-01")
    too_few = _facts(_steady(n=2, daily=0.999), tank_id="T-02")
    pace = pace_batch([steady, too_few], DEFAULTS)
    assert pace.tank_id == "T-01"
    assert pace.loss_per_day == pytest.approx(batch_loss_per_day(steady, DEFAULTS))
    crash = CheckData(sampled_at=datetime(2026, 10, 8, 12), live_est=9e6, pct_dead=30.0, mean_len_um=146.0, gut=0.1)
    sick = _facts([*_steady(n=3), crash], tank_id="T-03")
    assert sick.level == "critical"
    assert pace_batch([sick], DEFAULTS) is None


def test_projection_arithmetic():
    tank = _facts(_steady())
    pace = Pace("T-01", 0.01)
    projection = project(tank, pace, DEFAULTS)
    days = (DEFAULTS["eyed_um"] - tank.length_um) / 10.0
    assert projection.days_to_eyed == pytest.approx(days)
    assert projection.eyed_on_course < tank.live
    assert projection.eyed_possible >= projection.eyed_on_course
    assert project(_facts(_steady(), kind="setting"), pace, DEFAULTS) is None


def test_a_stalled_tank_isnt_on_course():
    checks = _steady(n=2, length=100.0, growth=0.5)
    projection = project(_facts(checks), Pace("T-01", 0.01), DEFAULTS)
    assert projection.days_to_eyed is None and projection.eyed_on_course == 0 and projection.eyed_possible > 0


def test_fao_ration_table():
    assert feed_cells_per_larva_day(100.0, DEFAULTS) == 2800
    assert feed_cells_per_larva_day(150.0, DEFAULTS) == pytest.approx(22350, abs=100)  # FAO table: 22,300
    assert feed_cells_per_larva_day(200.0, DEFAULTS) == 41900
    assert feed_cells_per_larva_day(280.0, DEFAULTS) == 73100
    assert feed_cells_per_larva_day(50.0, DEFAULTS) == 2800
    assert feed_cells_per_larva_day(400.0, DEFAULTS) == 73100
    assert feed_cells_per_larva_day(None, DEFAULTS) is None


def test_size_below_share_reads_the_histogram():
    hist = [0] * 38
    hist[6] = 50  # 100-110 µm
    hist[10] = 50  # 140-150 µm
    assert size_below_share(hist, 0.25) == pytest.approx(105.0)
    assert size_below_share(hist, 0.75) == pytest.approx(145.0)
    assert size_below_share([0, 0], 0.5) is None
    assert size_below_share(None, 0.5) is None


# ------------------------------------------------------------------ things a review caught


def _latest_check(tank_id: str, session: Session) -> models.Check:
    return session.exec(select(models.Check).where(models.Check.tank_id == tank_id).order_by(models.Check.sampled_at.desc())).first()


def test_impossible_water_doesnt_take_the_pages_down(client):
    """Salinity 0 is allowed on the check form, and used to divide by zero on every page that builds a dose."""
    with Session(db.get_engine()) as session:
        for tank_id in ("T-04", "T-05", "T-06"):
            check = _latest_check(tank_id, session)
            check.salinity_ppt = 0.0
            session.add(check)
        session.commit()
    for url in ("/api/floor", "/api/advisor", "/api/tanks/T-04", "/api/decisions?status=pending"):
        assert client.get(url).status_code == 200, url
    step = _buffer_step(client.get("/api/advisor").json())
    assert step["dose"] is None and "sodium carbonate" in step["how"]


def test_a_setting_tank_being_cleaned_isnt_called_empty(client):
    with Session(db.get_engine()) as session:
        tank = session.get(models.Tank, "S-02")
        tank.status = "cleaning"
        session.add(tank)
        session.commit()
    card = client.get("/api/advisor").json()["opportunities"][0]
    assert "S-02 is free once it's clean" in card["why"] and "is empty" not in card["why"]
    assert "S-02 is free once it's clean" in card["steps"][0]["how"]


def test_an_overcount_isnt_a_pace_to_match_or_a_negative_loss():
    over = _facts(_steady(start=25_000_000.0), tank_id="T-01")  # more than the 20M stocked
    assert batch_loss_per_day(over, DEFAULTS) < 0
    assert pace_batch([over], DEFAULTS) is None
    good = _facts(_steady(), tank_id="T-02")
    assert pace_batch([over, good], DEFAULTS).tank_id == "T-02"
    projection = project(good, pace_batch([over, good], DEFAULTS), DEFAULTS)
    assert projection.eyed_possible <= good.live


def test_a_rising_count_on_an_eyed_tank_doesnt_say_losing_a_negative_amount():
    same = dict(pct_dead=2.0, pct_abnormal=2.0, cv=0.07, gut=0.8)
    checks = [
        CheckData(sampled_at=datetime(2026, 10, 10, 12), live_est=6_000_000.0, mean_len_um=270.0, **same),
        CheckData(sampled_at=datetime(2026, 10, 12, 12), live_est=6_500_000.0, mean_len_um=285.0, **same),
    ]
    tank = _facts(checks, stocked=7_000_000, volume_l=1000.0)
    card = yield_opportunities([tank], None, lambda _tank: [], DEFAULTS)[0]
    assert "losing" not in card.why and "-" not in card.stat_text
    assert card.stat_label == "average shell length"


def test_undo_keeps_the_record_of_a_closed_batch(client):
    row = client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-08", "verb": "approve"}).json()
    batch_id = client.get("/api/tanks/T-08").json()["batch"]["id"]
    assert client.post(f"/api/batches/{batch_id}/close", json={"outcome": "harvested"}).status_code == 200
    response = client.post(f"/api/decisions/{row['id']}/undo")
    assert response.status_code == 409 and "closed" in response.json()["detail"]
    with Session(db.get_engine()) as session:
        assert session.get(models.Decision, row["id"]) is not None


def test_undo_keeps_the_record_when_a_new_batch_has_started(client):
    row = client.post("/api/advisor/answer", json={"action": "split_tank", "tank_id": "T-08", "verb": "approve"}).json()
    with Session(db.get_engine()) as session:
        decision = session.get(models.Decision, row["id"])
        decision.created_at = datetime(2020, 1, 1)
        session.add(decision)
        session.commit()
    assert client.post(f"/api/decisions/{row['id']}/undo").status_code == 409


def test_a_yield_card_lists_only_its_own_steps(client):
    with Session(db.get_engine()) as session:
        session.add(models.Decision(scope="tank", tank_id="T-07", action="recount", status="pending", created_at=datetime.now()))
        session.commit()
    card = client.get("/api/advisor").json()["opportunities"][0]
    assert [s["action"] for s in card["steps"]] == ["move_to_setting"]
    assert card["steps_left"] == 1


def test_a_step_shown_on_two_cards_counts_once(client):
    with Session(db.get_engine()) as session:
        check = _latest_check("T-06", session)
        check.omega_arag, check.temp_c = 2.9, 29.5  # a temperature problem of its own, on a line with an alert
        session.add(check)
        session.commit()
    page = client.get("/api/advisor").json()
    cards = {r["id"]: r for r in page["risks"]}
    shared = {s["action"] for s in cards["line-L2"]["steps"]} & {s["action"] for s in cards["tank-T-06"]["steps"]}
    assert shared == {"buffer_line", "hold_spawn"}
    seen = {(s["scope"], s["tank_id"], s["line_id"], s["action"], s["title"])
            for card in page["risks"] + page["opportunities"] for s in card["steps"] if s["status"] == "pending"}
    assert page["totals"]["steps_waiting"] == len(seen)
    assert page["totals"]["steps_waiting"] < sum(c["steps_left"] for c in page["risks"] + page["opportunities"])


def test_a_recommended_step_with_no_row_isnt_offered_as_a_button_that_cant_work(client):
    with Session(db.get_engine()) as session:
        for row in session.exec(select(models.Decision).where(models.Decision.tank_id == "T-02")):
            session.delete(row)
        session.commit()
    assert client.get("/api/tanks/T-02").json()["suggestions"] == []


# ------------------------------------------------------------------ wording and honesty


def test_the_page_never_says_diagnosis_and_labels_nothing_as_equipment_action(full_client):
    text = json.dumps(full_client.get("/api/advisor").json()).lower()
    assert "diagnos" not in text
    assert "antibiotic" not in text


def test_guidance_is_sourced(client):
    page = client.get("/api/advisor").json()
    assert "Barton" in page["risks"][0]["source"]
    assert all("FAO" in o["source"] for o in page["opportunities"])


def test_the_page_works_without_a_key(client):
    page = client.get("/api/advisor").json()
    assert page["claude"]["enabled"] is False
    assert page["analysis"] is None and page["analysis_running"] is False
    assert page["risks"] and page["opportunities"]


def test_the_page_doesnt_create_rows(client):
    with Session(db.get_engine()) as session:
        before = len(session.exec(select(models.Decision)).all())
    client.get("/api/advisor")
    client.get("/api/floor")
    client.get("/api/tanks/T-07")
    with Session(db.get_engine()) as session:
        assert len(session.exec(select(models.Decision)).all()) == before


def test_an_empty_database_doesnt_break_the_page(tmp_path, monkeypatch):
    monkeypatch.setenv("THETIS_DATA_DIR", str(tmp_path))
    with TestClient(app) as test_client:
        response = test_client.get("/api/advisor")
    assert response.status_code == 200
    page = response.json()
    assert page["seeded"] is False and page["risks"] == [] and page["opportunities"] == []
