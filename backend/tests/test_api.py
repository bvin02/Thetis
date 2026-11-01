"""The API on a demo-seeded temp database (SPEC §13)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import config, db, models
from app.main import app
from app.seed import run_seed

DEMO_PHOTO = config.FIXTURES_DIR / "demo" / "t03-today.jpg"
FAKE_KEY = "sk-ant-test-this-must-never-appear"


@pytest.fixture()
def client():
    run_seed(full=False, reset=True)
    with TestClient(app) as test_client:
        yield test_client


def _analyze(client: TestClient) -> dict:
    with DEMO_PHOTO.open("rb") as handle:
        response = client.post("/api/analyze", files={"file": ("t03-today.jpg", handle, "image/jpeg")})
    assert response.status_code == 200, response.text
    return response.json()


def _line1_water(client: TestClient) -> dict:
    floor = client.get("/api/floor").json()
    water = next(line for line in floor["lines"] if line["id"] == "L1")["water"]
    return {k: water[k] for k in ("temp_c", "salinity_ppt", "ph", "omega_arag", "do_mgl")}


def _save_payload(analysis: dict, water: dict) -> dict:
    return {
        "tank_id": "T-03",
        "sampled_at": datetime.now().replace(microsecond=0).isoformat(),
        "photos": [{"token": analysis["token"], "detections": analysis["detections"]}],
        "sample": {"bucket_l": 20, "concentration": 50},
        "water": water,
        "notes": "From the test",
    }


def _pending(client: TestClient) -> list[str]:
    groups = client.get("/api/decisions", params={"status": "pending"}).json()["groups"]
    return sorted(f"{item['line_id'] or item['tank_id']}:{item['action']}" for group in groups for item in group["items"])


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_demo_floor_starts_with_two_tanks_needing_attention(client):
    floor = client.get("/api/floor").json()
    assert floor["headline"] == "2 tanks need attention now"
    assert floor["is_example"] is True
    assert [c["id"] for c in floor["act_now"]] == ["T-04", "T-05"]
    t03 = next(t for t in floor["tanks"] if t["id"] == "T-03")
    assert t03["level"] == "watch"


def test_the_demo_upload_makes_t03_critical(client):
    analysis = _analyze(client)
    assert analysis["synthetic"] is True  # sha-256 matches fixtures/demo
    assert analysis["calibration"] == "grid"
    assert analysis["um_per_px"] == pytest.approx(1.6, abs=0.02)

    response = client.post("/api/checks", json=_save_payload(analysis, _line1_water(client)))
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["level"] == "critical"
    assert saved["pattern"] == "bacterial"
    assert sorted(d["action"] for d in saved["new_decisions"]) == ["isolate", "restock", "sample_vibrio"]
    assert saved["message"] == "Check saved. T-03 is now Critical. 3 decisions waiting."

    floor = client.get("/api/floor").json()
    assert floor["headline"] == "3 tanks need attention now"
    assert [c["id"] for c in floor["act_now"]] == ["T-03", "T-04", "T-05"]
    assert floor["metrics"]["decisions_waiting"] == 7
    assert floor["summary"].endswith("Separately, T-03 shows a pattern that matches a bacterial outbreak.")

    tank = client.get("/api/tanks/T-03").json()
    assert tank["title"] == "Pattern matches a bacterial outbreak"
    assert tank["actions_left"] == 3
    assert [a["cta"] for a in tank["actions"]] == ["Approve isolation", "Request sampling", "Approve drain and restock"]


def test_saved_check_detail_and_photo(client):
    analysis = _analyze(client)
    saved = client.post("/api/checks", json=_save_payload(analysis, _line1_water(client))).json()
    detail = client.get(f"/api/checks/{saved['check_id']}").json()
    assert detail["level"] == "critical"
    assert detail["snapshot"]["title"] == "Pattern matches a bacterial outbreak"
    assert detail["photos"][0]["synthetic"] is True
    assert len(detail["photos"][0]["detections"]) == len(analysis["detections"])
    assert detail["water"]["omega_arag"] == pytest.approx(2.9)
    assert detail["notes"] == "From the test"
    image = client.get(detail["photos"][0]["url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert client.get(analysis["url"]).status_code == 404  # moved out of uploads


def test_approve_then_undo(client):
    analysis = _analyze(client)
    saved = client.post("/api/checks", json=_save_payload(analysis, _line1_water(client))).json()
    decision_id = next(d["id"] for d in saved["new_decisions"] if d["action"] == "isolate")

    approved = client.post(f"/api/decisions/{decision_id}/approve", json={"note": "Done"}).json()
    assert approved["status"] == "approved"
    assert approved["decided_by"] == "Dana Ortiz"
    assert approved["note"] == "Done"
    assert approved["done_text"] == "Isolation approved"
    assert approved["decided_text"].startswith("Dana Ortiz · Today")
    assert "T-03:isolate" not in _pending(client)

    undone = client.post(f"/api/decisions/{decision_id}/undo").json()
    assert undone["status"] == "pending"
    assert undone["decided_by"] is None and undone["decided_at"] is None and undone["note"] is None
    assert "T-03:isolate" in _pending(client)


def test_dismiss(client):
    decision_id = client.get("/api/decisions", params={"status": "pending"}).json()["groups"][0]["items"][0]["id"]
    dismissed = client.post(f"/api/decisions/{decision_id}/dismiss", json={}).json()
    assert dismissed["status"] == "dismissed"
    assert dismissed["decided_at"] is not None


def test_saving_the_same_check_twice_does_not_duplicate_decisions(client):
    water = _line1_water(client)
    first = client.post("/api/checks", json=_save_payload(_analyze(client), water)).json()
    before = _pending(client)
    # Same photo analyzed again and saved as a new check
    second = client.post("/api/checks", json=_save_payload(_analyze(client), water)).json()
    assert second["check_id"] != first["check_id"]
    assert second["new_decisions"] == []
    assert _pending(client) == before


def test_the_same_upload_token_saved_twice_makes_one_check(client):
    water = _line1_water(client)
    payload = _save_payload(_analyze(client), water)
    first = client.post("/api/checks", json=payload).json()
    again = client.post("/api/checks", json=payload)
    assert again.status_code == 201
    assert again.json()["check_id"] == first["check_id"]
    assert again.json()["duplicate"] is True
    with Session(db.get_engine()) as session:
        batch = session.exec(select(models.Batch).where(models.Batch.code == "NW-1021")).one()
        assert len(list(session.exec(select(models.Check).where(models.Check.batch_id == batch.id)))) == 5


def test_no_api_response_contains_the_key(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    analysis = _analyze(client)
    saved = client.post("/api/checks", json=_save_payload(analysis, _line1_water(client)))
    responses = [
        saved,
        client.get("/api/health"),
        client.get("/api/floor"),
        client.get("/api/tanks"),
        client.get("/api/tanks/T-03"),
        client.get("/api/checks"),
        client.get(f"/api/checks/{saved.json()['check_id']}"),
        client.get("/api/decisions"),
        client.get("/api/samples"),
        client.get("/api/openapi.json"),
        client.post("/api/summarize", json={"detections": [], "sample": {}}),
    ]
    for path in ("/api/claude/status", "/api/photos/tree"):
        responses.append(client.get(path))
    for response in responses:
        assert "sk-ant" not in response.text, response.request.url
    assert FAKE_KEY == os.environ["ANTHROPIC_API_KEY"]


def test_summarize_updates_counts_and_the_estimate(client):
    analysis = _analyze(client)
    body = {
        "detections": analysis["detections"], "um_per_px": analysis["um_per_px"],
        "photo_volume_ml": analysis["photo_volume_ml"], "sample": {"bucket_l": 20, "concentration": 50}, "tank_id": "T-03",
    }
    before = client.post("/api/summarize", json=body).json()
    assert before["summary"]["n_dead"] >= 14
    assert before["estimate"]["stocked"] == 10_000_000
    assert 3.5e6 < before["estimate"]["live_est"] < 4.5e6

    live = next(d for d in body["detections"] if d["cls"] == "live" and d["clump_n"] == 1)
    live["cls"] = "dead"
    live["source"] = "corrected"
    after = client.post("/api/summarize", json=body).json()
    assert after["summary"]["n_dead"] == before["summary"]["n_dead"] + 1
    assert after["estimate"]["live_est"] < before["estimate"]["live_est"]

    body["sample"]["concentration"] = 5
    assert client.post("/api/summarize", json=body).json()["estimate"]["over_stocked"] is True


def test_patch_corrections_recompute_and_reassess(client):
    water = _line1_water(client)
    saved = client.post("/api/checks", json=_save_payload(_analyze(client), water)).json()
    detail = client.get(f"/api/checks/{saved['check_id']}").json()
    photo = detail["photos"][0]
    dets = photo["detections"]
    for det in dets:
        if det["cls"] == "dead":
            det["cls"] = "live"
            det["source"] = "corrected"
    patched = client.patch(f"/api/checks/{saved['check_id']}/photos/{photo['id']}/detections", json={"detections": dets})
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["n_dead"] == 0
    assert body["pct_dead"] == 0
    assert body["level"] != "critical" or "dead" not in body["severities"]
    corrected = [d for d in body["photos"][0]["detections"] if d["source"] == "corrected"]
    assert corrected and all(d["auto_cls"] == "dead" for d in corrected)


def test_correcting_an_earlier_check_only_changes_it_and_later_ones(client):
    with Session(db.get_engine()) as session:
        batch = session.exec(select(models.Batch).where(models.Batch.code == "NW-1021")).one()
        rows = list(session.exec(select(models.Check).where(models.Check.batch_id == batch.id).order_by(models.Check.sampled_at)))
        first, second = rows[0], rows[1]
        first_level, first_signals = first.level, first.signals
        second_id = second.id
    detail = client.get(f"/api/checks/{second_id}").json()
    photo = detail["photos"][0]
    dets = photo["detections"]
    for det in dets[:30]:
        det["cls"] = "dead"
        det["source"] = "corrected"
    assert client.patch(f"/api/checks/{second_id}/photos/{photo['id']}/detections", json={"detections": dets}).status_code == 200
    with Session(db.get_engine()) as session:
        batch = session.exec(select(models.Batch).where(models.Batch.code == "NW-1021")).one()
        rows = list(session.exec(select(models.Check).where(models.Check.batch_id == batch.id).order_by(models.Check.sampled_at)))
        assert rows[0].level == first_level and rows[0].signals == first_signals
        assert rows[1].level == "critical"


def test_samples(client):
    samples = client.get("/api/samples").json()["samples"]
    names = {s["name"] for s in samples}
    assert names == {"t03-today", "slide-healthy-umbo", "slide-vibrio-suspect", "slide-low-omega", "slide-d-stage", "slide-eyed"}
    result = client.post("/api/samples/slide-low-omega/analyze").json()
    assert result["synthetic"] is True
    assert result["calibration"] == "none"
    assert result["um_per_px"] is None
    assert client.get("/api/samples/slide-eyed/image").status_code == 200
    assert client.get("/api/samples/nope/image").status_code == 404
    assert client.post("/api/samples/..%2F..%2Freal/analyze").status_code == 404


def test_manual_scale_on_an_uncalibrated_photo(client):
    result = client.post("/api/samples/slide-low-omega/analyze").json()
    scaled = client.post(f"/api/analyze/{result['token']}/scale", json={"um_per_px": 1.6}).json()
    assert scaled["calibration"] == "manual"
    assert scaled["um_per_px"] == pytest.approx(1.6)
    assert scaled["photo_volume_ml"] == pytest.approx(0.0049152)
    assert any(d["length_um"] for d in scaled["detections"])


def test_a_file_that_is_not_a_photo_is_refused(client):
    response = client.post("/api/analyze", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 422
    assert "JPG or PNG" in response.json()["detail"]


def test_a_png_is_accepted(client):
    import cv2
    import numpy as np

    canvas = np.full((400, 600, 3), 225, dtype=np.uint8)
    cv2.circle(canvas, (300, 200), 50, (60, 90, 120), -1)
    ok, encoded = cv2.imencode(".png", canvas)
    assert ok
    response = client.post("/api/analyze", files={"file": ("x.png", encoded.tobytes(), "image/png")})
    assert response.status_code == 200
    assert response.json()["synthetic"] is False
    assert client.get(response.json()["url"]).headers["content-type"] == "image/jpeg"


def test_save_refusals(client):
    assert client.post("/api/checks", json={"tank_id": "T-99", "photos": []}).status_code == 422
    empty = client.post("/api/checks", json={"tank_id": "T-09", "photos": []})
    assert empty.status_code == 422 and "no active batch" in empty.json()["detail"]
    no_photo = client.post("/api/checks", json={"tank_id": "T-03", "photos": []})
    assert no_photo.status_code == 422
    expired = client.post("/api/checks", json={"tank_id": "T-03", "photos": [{"token": "0" * 32, "detections": []}]})
    assert expired.status_code == 422 and "expired" in expired.json()["detail"]
    future = (datetime.now() + timedelta(days=2)).isoformat()
    analysis = _analyze(client)
    payload = _save_payload(analysis, {})
    payload["sampled_at"] = future
    assert client.post("/api/checks", json=payload).status_code == 422


def test_batches_start_and_close(client):
    started = client.post("/api/batches", json={"tank_id": "S-02", "code": "NW-2000", "spawn_date": "2026-01-01", "stocked": 1000000})
    assert started.status_code == 201, started.text
    assert client.post("/api/batches", json={"tank_id": "S-02", "code": "X", "spawn_date": "2026-01-01", "stocked": 5}).status_code == 409
    batch_id = started.json()["id"]
    closed = client.post(f"/api/batches/{batch_id}/close", json={"outcome": "harvested"})
    assert closed.status_code == 200, closed.text
    assert client.post(f"/api/batches/{batch_id}/close", json={"outcome": "harvested"}).status_code == 409
    floor = client.get("/api/floor").json()
    assert next(t for t in floor["tanks"] if t["id"] == "S-02")["level"] == "empty"


def test_closing_a_batch_ends_its_open_tank_decisions_but_not_the_line_ones(client):
    tank = client.get("/api/tanks/T-04").json()
    client.post(f"/api/batches/{tank['batch']['id']}/close", json={"outcome": "crashed", "note": "Lost it"})
    pending = _pending(client)
    assert "L2:buffer_line" in pending
    other = client.get("/api/tanks/T-02").json()
    client.post(f"/api/batches/{other['batch']['id']}/close", json={"outcome": "discarded"})
    assert "T-02:screen" not in _pending(client)


def test_the_database_is_not_served(client):
    assert client.get("/api/files/thetis.db").status_code == 404
    assert client.get("/api/files/photos/../thetis.db").status_code == 404
    assert client.get("/api/files/uploads/../thetis.db").status_code == 404


def test_old_uploads_are_deleted(client):
    import time

    from app.services.uploads import clean_old_uploads

    analysis = _analyze(client)
    path = config.uploads_dir() / f"{analysis['token']}.jpg"
    assert path.exists()
    removed = clean_old_uploads(now=time.time() + 25 * 3600)
    assert removed >= 2 and not path.exists()


def test_photo_tree(client):
    tree = client.get("/api/photos/tree").json()
    assert [room["name"] for room in tree["rooms"]] == ["Larval room A", "Larval room B", "Setting room"]
    room_a = tree["rooms"][0]
    t03 = next(t for t in room_a["tanks"] if t["id"] == "T-03")
    assert t03["n_checks"] == 4 and t03["n_photos"] == 4
    assert t03["footer"].startswith("Spawned ") and t03["footer"].endswith("stocked 10.0M larvae")
    newest = t03["checks"][0]
    assert newest["summary"] == "9% dead · 126 µm"
    assert newest["level"] == "watch"
    assert newest["thumb_url"].startswith("/api/files/photos/")
    assert client.get(newest["thumb_url"]).status_code == 200
    assert room_a["n_photos"] == sum(t["n_photos"] for t in room_a["tanks"])
    notes = {t["id"]: t["note"] for room in tree["rooms"] for t in room["tanks"]}
    assert notes["T-04"] == "Day 6 · Ω 1.4"
    assert notes["T-06"] == "Day 3 · line 2"
    assert notes["T-02"] == "Day 11 · size spread"
    assert notes["T-10"] == "Day 8 · slow growth"
    assert notes["T-01"] == "Day 14 · 231 µm"
    assert notes["T-09"] == "Cleaning"


def test_checks_list_filters(client):
    everything = client.get("/api/checks").json()["checks"]
    assert len(everything) == 49
    assert everything[0]["sampled_at"] >= everything[-1]["sampled_at"]
    t03 = client.get("/api/checks", params={"tank": "T-03"}).json()["checks"]
    assert len(t03) == 4 and all(row["tank_id"] == "T-03" for row in t03)
    room_b = client.get("/api/checks", params={"room": "B"}).json()["checks"]
    assert room_b and all(row["room_id"] == "B" for row in room_b)


def test_tank_detail_of_an_empty_tank(client):
    tank = client.get("/api/tanks/T-09").json()
    assert tank["level"] == "empty"
    assert tank["reason"] == "Empty. Being cleaned."
    assert tank["forecast"] == "No batch in this tank."
    assert tank["batch"] is None and tank["latest_check"] is None and tank["condition"] == []
    assert tank["past_batches"][0]["outcome"] == "moved_to_setting"
    assert client.get("/api/tanks/T-99").status_code == 404


def test_correcting_a_saved_check_keeps_the_estimate_formula(client):
    """Edge objects count 0.5, so an untouched re-save must leave the estimate exactly as it was."""
    analysis = client.post("/api/samples/slide-healthy-umbo/analyze").json()
    payload = _save_payload(analysis, {})
    # Force some edge objects, so count_for_estimate differs from live + abnormal
    alive = [d for d in analysis["detections"] if d["cls"] in ("live", "abnormal")]
    for det in alive[:3]:
        det["touches_edge"] = True
    saved = client.post("/api/checks", json=payload).json()
    detail = client.get(f"/api/checks/{saved['check_id']}").json()
    photo = detail["photos"][0]
    before = detail["live_est"]
    patched = client.patch(f"/api/checks/{saved['check_id']}/photos/{photo['id']}/detections", json={"detections": photo["detections"]})
    assert patched.status_code == 200
    assert patched.json()["live_est"] == pytest.approx(before)

    expected = sum(0.5 if d["touches_edge"] else d["clump_n"] for d in photo["detections"] if d["cls"] in ("live", "abnormal"))
    volume, bucket, concentration = detail["photo_volume_ml"], detail["bucket_l"], detail["concentration"]
    assert before == pytest.approx(expected / (volume * concentration) * bucket * 1000)


def test_floor_on_an_empty_database_does_not_crash():
    db.init_db()
    db.drop_hatchery_tables()
    db.init_db()
    with TestClient(app) as test_client:
        floor = test_client.get("/api/floor")
        assert floor.status_code == 200, floor.text
        body = floor.json()
        assert body["seeded"] is False and body["tanks"] == [] and body["default_tank"] is None
        assert body["headline"] == "All tanks tracking normally"
        assert test_client.get("/api/checks").json() == {"checks": []}
        assert test_client.get("/api/decisions").json()["counts"]["all"] == 0
        assert test_client.get("/api/photos/tree").json() == {"rooms": []}
