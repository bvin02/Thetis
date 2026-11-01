"""Claude features with a fake client: nothing here calls the real API (SPEC §8, §13)."""
from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app import config, db, models
from app.main import app
from app.seed import run_seed
from app.services import claude

FAKE_KEY = "sk-ant-fake-key-for-tests"


class FakeMessages:
    def __init__(self):
        self.parse_calls = []
        self.create_calls = []
        self.next_opinions = None
        self.raises = None
        self.stop_reason = "end_turn"
        self.explain_text = "Dead larvae rose to 24%. The numbers fit the pattern. The actions isolate the tank."

    def parse(self, **kwargs):
        if self.raises:
            raise self.raises
        self.parse_calls.append(kwargs)
        ids = [int(b["text"].split()[1].rstrip(":")) for b in kwargs["messages"][0]["content"] if b["type"] == "text"]
        parsed = self.next_opinions or claude.Opinions(
            opinions=[claude.Opinion(object=i, cls="dead", confidence="high", reason="Empty shell, outline only") for i in ids]
        )
        return SimpleNamespace(
            parsed_output=parsed if self.stop_reason == "end_turn" else None,
            usage=SimpleNamespace(input_tokens=1200, output_tokens=90),
            stop_reason=self.stop_reason,
        )

    def create(self, **kwargs):
        if self.raises:
            raise self.raises
        self.create_calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.explain_text)],
            usage=SimpleNamespace(input_tokens=500, output_tokens=60),
            stop_reason=self.stop_reason,
        )


@pytest.fixture()
def fake(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    messages = FakeMessages()
    monkeypatch.setattr(claude, "_make_client", lambda: SimpleNamespace(messages=messages))
    return messages


@pytest.fixture()
def client():
    run_seed(full=False, reset=True)
    with Session(db.get_engine()) as session:  # the call log survives a re-seed, so clear it by hand
        session.exec(delete(models.ClaudeCall))
        session.commit()
    with TestClient(app) as test_client:
        yield test_client


def test_reseeding_keeps_the_call_log():
    run_seed(full=False, reset=True)
    with Session(db.get_engine()) as session:
        session.exec(delete(models.ClaudeCall))
        session.add(models.ClaudeCall(kind="opinion", input_hash="abc", model="m", created_at=datetime.now(),
                                      result={"opinions": {}}))
        session.commit()
    run_seed(full=True, reset=True)
    with Session(db.get_engine()) as session:
        assert session.exec(select(models.ClaudeCall)).one().input_hash == "abc"
        session.exec(delete(models.ClaudeCall))
        session.commit()


def _analysis(client):
    result = client.post("/api/samples/t03-today/analyze").json()
    ids = [d["id"] for d in result["detections"] if d["unsure"]]
    return result, ids


def test_everything_is_off_without_a_key(client):
    assert claude.is_enabled() is False
    status = client.get("/api/claude/status").json()
    assert status["enabled"] is False
    assert set(status) == {"enabled", "model", "used_today", "limit"}
    assert client.post("/api/claude/second-opinion", json={"photo": "0" * 32, "detection_ids": [1]}).status_code == 503
    assert client.post("/api/claude/explain", json={"tank_id": "T-03"}).status_code == 503


def test_status_never_contains_the_key(client, fake):
    response = client.get("/api/claude/status")
    assert response.json()["enabled"] is True
    assert "sk-ant" not in response.text


def test_model_and_limit_come_from_the_environment(client, fake, monkeypatch):
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_DAILY_LIMIT", raising=False)
    status = client.get("/api/claude/status").json()
    assert status["model"] == "claude-sonnet-5-5" and status["limit"] == 100
    monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-5-5")
    monkeypatch.setenv("CLAUDE_DAILY_LIMIT", "7")
    status = client.get("/api/claude/status").json()
    assert status["model"] == "claude-haiku-5-5" and status["limit"] == 7


def test_second_opinion_request_shape(client, fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    result, ids = _analysis(client)
    assert ids
    response = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cached"] is False
    assert set(body["opinions"]) == {str(i) for i in ids}
    assert body["opinions"][str(ids[0])] == {"cls": "dead", "confidence": "high", "reason": "Empty shell, outline only"}

    call = fake.parse_calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["max_tokens"] == config.CLAUDE_OPINION_MAX_TOKENS
    assert call["system"] == claude.OPINION_SYSTEM
    assert call["output_format"] is claude.Opinions
    assert call["thinking"] == {"type": "between_tools"}
    blocks = call["messages"][0]["content"]
    assert len(blocks) == 2 * len(ids)
    for text, image in zip(blocks[::2], blocks[1::2], strict=True):
        assert text["type"] == "text" and text["text"].startswith("Object ")
        assert "automatic call" in text["text"] and "µm" in text["text"]
        assert image["type"] == "image" and image["source"]["media_type"] == "image/jpeg"


def test_crop_size_and_padding():
    import base64

    import cv2
    import numpy as np

    from app.analysis.models import Detection

    picture = np.full((1200, 1600, 3), 200, dtype=np.uint8)
    contour = [(100.0, 100.0), (700.0, 100.0), (700.0, 700.0), (100.0, 700.0)]
    det = Detection(id=1, cx=400, cy=400, contour=contour, length_px=600, area_px=360000, cls="dead")
    decoded = cv2.imdecode(np.frombuffer(base64.b64decode(claude._crop(picture, det)), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert max(decoded.shape[:2]) == 256
    small = Detection(id=2, cx=800, cy=600, contour=[(780.0, 580.0), (820.0, 580.0), (820.0, 620.0), (780.0, 620.0)],
                      length_px=40, area_px=1600, cls="live")
    decoded = cv2.imdecode(np.frombuffer(base64.b64decode(claude._crop(picture, small)), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[0] == 64 and decoded.shape[1] == 64  # 40 px + 30% on each side


def test_at_most_twelve_objects(client, fake):
    result, _ = _analysis(client)
    ids = [d["id"] for d in result["detections"]][:13]
    response = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    assert response.status_code == 422
    assert not fake.parse_calls


def test_identical_input_is_answered_from_the_cache(client, fake):
    result, ids = _analysis(client)
    payload = {"photo": result["token"], "detection_ids": ids}
    first = client.post("/api/claude/second-opinion", json=payload).json()
    second = client.post("/api/claude/second-opinion", json=payload).json()
    assert second["cached"] is True and second["opinions"] == first["opinions"]
    assert len(fake.parse_calls) == 1
    assert client.get("/api/claude/status").json()["used_today"] == 1


def test_daily_cap_returns_429_and_cached_answers_still_work(client, fake, monkeypatch):
    result, ids = _analysis(client)
    payload = {"photo": result["token"], "detection_ids": ids[:1]}
    assert client.post("/api/claude/second-opinion", json=payload).status_code == 200
    monkeypatch.setenv("CLAUDE_DAILY_LIMIT", "1")
    over = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids[1:2]})
    assert over.status_code == 429 and over.json()["detail"] == "Daily Claude limit reached"
    assert client.post("/api/claude/second-opinion", json=payload).status_code == 200  # cached
    assert client.post("/api/claude/explain", json={"tank_id": "T-03"}).status_code == 429
    assert len(fake.parse_calls) == 1


def test_every_call_is_logged_with_tokens(client, fake):
    result, ids = _analysis(client)
    client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    client.post("/api/claude/explain", json={"tank_id": "T-03"})
    with Session(db.get_engine()) as session:
        rows = list(session.exec(select(models.ClaudeCall).order_by(models.ClaudeCall.id)))
    assert [r.kind for r in rows] == ["opinion", "explain"]
    assert (rows[0].input_tokens, rows[0].output_tokens) == (1200, 90)
    assert (rows[1].input_tokens, rows[1].output_tokens) == (500, 60)
    assert rows[0].result and rows[0].error is None and rows[0].input_hash


def test_logs_hold_no_key_and_no_prompt(client, fake, caplog):
    caplog.set_level(logging.DEBUG, logger="thetis.claude")
    result, ids = _analysis(client)
    client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    client.post("/api/claude/explain", json={"tank_id": "T-03"})
    assert "input_tokens=1200" in caplog.text
    assert "sk-ant" not in caplog.text
    assert "shellfish" not in caplog.text and "Object " not in caplog.text and "Dead larvae rose" not in caplog.text


def test_failures_are_safe_and_logged(client, fake):
    import anthropic
    import httpx

    result, ids = _analysis(client)
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake.raises = anthropic.AuthenticationError(
        f"bad key {FAKE_KEY}", response=httpx.Response(401, request=request), body=None
    )
    response = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    assert response.status_code == 502
    assert "sk-ant" not in response.text and "API key" in response.json()["detail"]
    with Session(db.get_engine()) as session:
        row = session.exec(select(models.ClaudeCall)).one()
    assert row.error == "AuthenticationError" and row.result is None and "sk-ant" not in row.error
    fake.raises = None  # a failed call isn't cached, so a retry reaches the API
    assert client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids}).status_code == 200


def test_refusal_and_truncation_are_reported(client, fake):
    result, ids = _analysis(client)
    fake.stop_reason = "refusal"
    response = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    assert response.status_code == 502 and "declined" in response.json()["detail"]
    fake.stop_reason = "max_tokens"
    response = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids})
    assert response.status_code == 502 and "out of room" in response.json()["detail"]


def test_opinions_outside_the_request_are_dropped(client, fake):
    result, ids = _analysis(client)
    fake.next_opinions = claude.Opinions(opinions=[
        claude.Opinion(object=ids[0], cls="live", confidence="low", reason="Can't tell"),
        claude.Opinion(object=9999, cls="dead", confidence="high", reason="Not one we asked about"),
    ])
    body = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids}).json()
    assert set(body["opinions"]) == {str(ids[0])}


def test_second_opinion_on_a_saved_photo(client, fake):
    tank = client.get("/api/tanks/T-04").json()
    photo = tank["latest_check"]["photo"]
    ids = [d["id"] for d in photo["detections"]][:2]
    response = client.post("/api/claude/second-opinion", json={"photo": photo["id"], "detection_ids": ids})
    assert response.status_code == 200, response.text
    assert client.post("/api/claude/second-opinion", json={"photo": 999999, "detection_ids": ids}).status_code == 404


def test_accepted_opinion_is_saved_on_the_detection(client, fake):
    result, ids = _analysis(client)
    opinions = client.post("/api/claude/second-opinion", json={"photo": result["token"], "detection_ids": ids}).json()["opinions"]
    target = next(d for d in result["detections"] if d["id"] == ids[0])
    target["cls"] = "dead"
    target["source"] = "corrected"
    target["unsure"] = False
    target["claude"] = {**opinions[str(ids[0])], "decided": "accepted"}
    saved = client.post("/api/checks", json={
        "tank_id": "T-03", "photos": [{"token": result["token"], "detections": result["detections"]}],
        "sample": {"bucket_l": 20, "concentration": 50},
    })
    assert saved.status_code == 201, saved.text
    detail = client.get(f"/api/checks/{saved.json()['check_id']}").json()
    stored = next(d for d in detail["photos"][0]["detections"] if d["id"] == ids[0])
    assert stored["source"] == "corrected"
    assert stored["claude"]["decided"] == "accepted" and stored["claude"]["reason"]


def test_explain_request_and_cache(client, fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5-5")
    body = client.post("/api/claude/explain", json={"tank_id": "T-04"})
    assert body.status_code == 200, body.text
    assert body.json()["text"].startswith("Dead larvae rose") and body.json()["cached"] is False
    assert client.post("/api/claude/explain", json={"tank_id": "T-04"}).json()["cached"] is True
    assert len(fake.create_calls) == 1
    call = fake.create_calls[0]
    assert call["max_tokens"] == config.CLAUDE_EXPLAIN_MAX_TOKENS
    assert "never 'diagnosis'" in call["system"]
    data = call["messages"][0]["content"]
    assert "T-04" in data and "last_checks" in data and "Buffer line 2 water" in data
    assert client.post("/api/claude/explain", json={"tank_id": "T-09"}).status_code == 422
    assert client.post("/api/claude/explain", json={"tank_id": "T-99"}).status_code == 404


@pytest.mark.parametrize("model,thinking,tokens", [
    ("claude-sonnet-5-5", {"type": "between_tools"}, 400),
    ("claude-haiku-5-5", {"type": "disabled"}, 400),
    ("claude-opus-5", {"type": "disabled"}, 400),
    ("claude-opus-5-5", None, 400 + config.CLAUDE_THINKING_HEADROOM_TOKENS),
    ("claude-fable-5-1", None, 400 + config.CLAUDE_THINKING_HEADROOM_TOKENS),
])
def test_request_options_per_model(model, thinking, tokens):
    options = claude._request_options(model, 400, "low")
    assert options.get("thinking") == thinking
    assert options["max_tokens"] == tokens
    assert options["output_config"] == {"effort": "low"}


def test_unknown_older_models_get_plain_options():
    assert claude._request_options("claude-haiku-4-5", 400, "low") == {"max_tokens": 400}
