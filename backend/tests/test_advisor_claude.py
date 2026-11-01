"""The Advisor's live features with a fake client: nothing here calls the real API (SPEC §16)."""
from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app import config, db, models
from app.main import app
from app.seed import run_seed
from app.services import advisor as service
from app.services import claude

FAKE_KEY = "sk-ant-fake-key-for-advisor-tests"


def _good_analysis() -> dict:
    return {
        "headline": "Buffer line 2 now.",
        "brief": "Line 2 is corrosive and 56.9M larvae are at stake.",
        "do_first": [
            {"ref": "line-L2", "action": "Buffer line 2.", "why": "Ω 1.4."},
            {"ref": "yield-T-07-setting", "action": "Grade T-07.", "why": "Losing 344k a day."},
            {"ref": "made-up-card", "action": "Check T-10's feed.", "why": "Gut 0.32."},
        ],
        "insights": [
            {
                "kind": "crash_risk", "title": "T-10 looks like T-03", "tank_ids": ["T-10", "T-03"],
                "body": "Both slowed down.", "suggestion": "Sample T-10 today.", "confidence": "medium",
                "evidence": [
                    {"tank_id": "T-10", "metric": "gut", "value": 0.32},
                    {"tank_id": "T-03", "metric": "growth_um_day", "value": 3.5},
                ],
            },
            {
                "kind": "yield", "title": "Invented numbers", "tank_ids": ["T-01"],
                "body": "This reading doesn't exist.", "suggestion": "Do nothing.", "confidence": "high",
                "evidence": [{"tank_id": "T-01", "metric": "ph", "value": 6.1}],
            },
            {
                "kind": "yield", "title": "A tank that isn't there", "tank_ids": ["T-77"],
                "body": "No such tank.", "suggestion": "Do nothing.", "confidence": "high",
                "evidence": [{"tank_id": "T-77", "metric": "gut", "value": 0.5}],
            },
        ],
    }


class FakeStream:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield SimpleNamespace(type="thinking", snapshot="Comparing T-10 with T-03 and T-07")
        if self.owner.gate is not None:
            self.owner.gate.wait(timeout=5)
        text = self.owner.text
        yield SimpleNamespace(type="text", snapshot=text[: len(text) // 2])
        yield SimpleNamespace(type="text", snapshot=text)

    @property
    def text_stream(self):
        for word in self.owner.text.split(" "):
            if self.owner.raises_midway:
                raise self.owner.raises_midway
            yield word + " "

    def get_final_message(self):
        return SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking="..."), SimpleNamespace(type="text", text=self.owner.text)],
            usage=SimpleNamespace(input_tokens=700, output_tokens=2000, cache_creation_input_tokens=9000, cache_read_input_tokens=0),
            stop_reason=self.owner.stop_reason,
        )


class FakeMessages:
    def __init__(self):
        self.calls = []
        self.text = json.dumps(_good_analysis())
        self.stop_reason = "end_turn"
        self.raises = None
        self.raises_midway = None
        self.gate = None

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return FakeStream(self)


@pytest.fixture()
def fake(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("CLAUDE_DAILY_LIMIT", "100")
    messages = FakeMessages()
    monkeypatch.setattr(claude, "_make_client", lambda *args: SimpleNamespace(messages=messages))
    return messages


@pytest.fixture()
def client():
    run_seed(full=False, reset=True)
    with Session(db.get_engine()) as session:
        session.exec(delete(models.ClaudeCall))
        session.commit()
    with claude._jobs_lock:
        claude._jobs.clear()
    with TestClient(app) as test_client:
        yield test_client
    with claude._jobs_lock:
        claude._jobs.clear()


def _events(response) -> list[dict]:
    return [json.loads(line[len("data: "):]) for line in response.text.splitlines() if line.startswith("data: ")]


def _analyze(client, **body) -> list[dict]:
    response = client.post("/api/advisor/analyze", json=body)
    assert response.status_code == 200, response.text
    return _events(response)


def _calls(kind: str | None = None) -> list[models.ClaudeCall]:
    with Session(db.get_engine()) as session:
        rows = session.exec(select(models.ClaudeCall)).all()
    return [r for r in rows if kind is None or r.kind == kind]


# ------------------------------------------------------------------ off, and over the limit


def test_off_without_a_key(client):
    assert client.post("/api/advisor/analyze", json={}).status_code == 503
    assert client.post("/api/advisor/ask", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 503
    assert _calls() == []


def test_over_the_daily_limit_makes_no_call(client, fake, monkeypatch):
    monkeypatch.setenv("CLAUDE_DAILY_LIMIT", "0")
    response = client.post("/api/advisor/analyze", json={})
    assert response.status_code == 429
    assert response.json()["detail"] == "Daily Claude limit reached"
    assert fake.calls == []
    events = _events(client.post("/api/advisor/ask", json={"messages": [{"role": "user", "content": "hi"}]}))
    assert events == [{"type": "error", "message": "Daily Claude limit reached"}]
    assert fake.calls == []


# ------------------------------------------------------------------ the analysis


def test_analysis_streams_progress_then_a_checked_result(client, fake):
    events = _analyze(client)
    assert events[-1]["done"] is True and events[-1]["cached"] is False
    assert any(e.get("looking_at") == ["T-10", "T-03", "T-07"] for e in events)
    assert not any("Comparing" in json.dumps(e) for e in events)  # Claude's raw reasoning never reaches the page
    result = events[-1]["analysis"]
    assert result["headline"] == "Buffer line 2 now."
    assert [p["ref"] for p in result["do_first"]] == ["line-L2", "yield-T-07-setting", ""]  # an unknown card isn't linked
    assert [i["title"] for i in result["insights"]] == ["T-10 looks like T-03"]
    assert result["dropped"] == 2


def _verify(client, insights: list[dict]) -> dict:
    with Session(db.get_engine()) as session:
        snapshot = service.build_snapshot(session)
    return service.verify_analysis({"headline": "", "brief": "", "do_first": [], "insights": insights}, snapshot)


def _insight(evidence: list[dict], tank_ids: list[str] | None = None) -> dict:
    return {
        "kind": "yield", "title": "", "tank_ids": tank_ids or ["T-04"], "body": "", "suggestion": "", "confidence": "low",
        "evidence": evidence,
    }


def test_one_reading_that_doesnt_check_out_drops_the_whole_insight(client):
    """Its text may lean on the same wrong number, and the text can't be checked."""
    good = {"tank_id": "T-04", "metric": "ph", "value": 7.62}
    bad = {"tank_id": "T-04", "metric": "ph", "value": 7.10}
    assert len(_verify(client, [_insight([good])])["insights"]) == 1
    result = _verify(client, [_insight([good, bad])])
    assert result["insights"] == [] and result["dropped"] == 1
    assert _verify(client, [_insight([])])["insights"] == []


def test_a_free_tank_can_be_named_but_a_made_up_one_cant(client):
    good = {"tank_id": "T-07", "metric": "length_um", "value": 288.0}
    assert len(_verify(client, [_insight([good], ["T-07", "S-02"])])["insights"]) == 1
    assert _verify(client, [_insight([good], ["T-07", "T-77"])])["insights"] == []
    # A free tank has no readings to cite
    assert _verify(client, [_insight([{"tank_id": "S-02", "metric": "ph", "value": 7.9}], ["S-02"])])["insights"] == []


def test_evidence_shown_is_the_records_value(client, fake):
    result = _analyze(client)[-1]["analysis"]
    evidence = result["insights"][0]["evidence"]
    assert {"tank_id": "T-10", "label": "gut fullness", "value_text": "0.32", "when_text": "yesterday"} in evidence
    assert evidence[1]["tank_id"] == "T-03" and evidence[1]["value_text"] == "3.5 µm/day" and evidence[1]["when_text"] == "2 days ago"


def test_near_misses_from_rounding_pass_but_wrong_numbers_dont(client):
    with Session(db.get_engine()) as session:
        snapshot = service.build_snapshot(session)

    def kept(metric, value):
        raw = {"headline": "", "brief": "", "do_first": [], "insights": [{
            "kind": "yield", "title": "", "tank_ids": ["T-04"], "body": "", "suggestion": "", "confidence": "low",
            "evidence": [{"tank_id": "T-04", "metric": metric, "value": value}],
        }]}
        return len(service.verify_analysis(raw, snapshot)["insights"]) == 1

    assert kept("live_est", 16_500_000)
    assert kept("live_est", 16_450_000)  # 16.5M written roundly
    assert kept("pct_abnormal", 18.8)
    assert kept("pct_abnormal", 19.0)
    assert kept("ph", 7.62)
    assert kept("density_per_l", 8250)
    assert not kept("pct_abnormal", 25.0)
    assert not kept("ph", 7.40)
    assert not kept("ph", 7.70)  # close in percent, and far off in pH
    assert not kept("omega_arag", 1.6)
    assert not kept("do_mgl", 3.0)
    assert not kept("cv", 0.9)


def test_the_request_uses_the_cached_snapshot_and_a_schema(client, fake):
    _analyze(client)
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_format"] is claude.Analysis
    assert call["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert call["output_config"] == {"effort": "medium"}
    assert call["max_tokens"] == config.CLAUDE_ANALYSIS_MAX_TOKENS
    role, data = call["system"]
    assert role["text"] == claude.ADVISOR_SYSTEM
    assert data["cache_control"] == {"type": "ephemeral"}
    snapshot = json.loads(data["text"].split("\n", 1)[1])
    assert snapshot["hatchery"] == "Northwind Shellfish"
    assert {t["id"] for t in snapshot["running_tanks"]} >= {"T-01", "T-04", "S-01"}
    assert snapshot["plant_chemicals"]["buffer"].startswith("Sodium carbonate")
    dose = next(s for s in snapshot["rules_found"]["crash_risks"][0]["steps"] if "dose" in s)["dose"]
    assert "16 g per 1,000 L" in dose


def test_the_rules_claude_is_given(client, fake):
    rules = " ".join(claude.ADVISOR_SYSTEM.split())
    assert "Never change one or give a dose of your own" in rules
    assert 'never "diagnosis"' in rules
    assert "Nothing acts on equipment" in rules
    assert "never suggest antibiotics" in rules


def test_a_snapshot_has_no_dates_so_a_re_seed_hits_the_cache(client, fake):
    with Session(db.get_engine()) as session:
        first = service.build_snapshot(session)
    run_seed(full=False, reset=True)
    with Session(db.get_engine()) as session:
        second = service.build_snapshot(session)
    assert service.analysis_key(first) == service.analysis_key(second)


def test_the_same_data_returns_the_stored_analysis_and_force_runs_it_again(client, fake):
    _analyze(client)
    assert len(fake.calls) == 1
    again = _analyze(client)
    assert len(fake.calls) == 1 and again[-1]["cached"] is True and again[-1]["analysis"]["headline"] == "Buffer line 2 now."
    fresh = _analyze(client, force=True)
    assert len(fake.calls) == 2 and fresh[-1]["cached"] is False
    assert len(_calls("analysis")) == 2


def test_tokens_are_logged_including_cached_input(client, fake):
    _analyze(client)
    row = _calls("analysis")[0]
    assert row.input_tokens == 9700 and row.output_tokens == 2000 and row.error is None and row.model == "claude-opus-5-5"


def test_the_page_shows_the_stored_analysis_with_steps(client, fake):
    assert client.get("/api/advisor").json()["analysis"] is None
    _analyze(client)
    page = client.get("/api/advisor").json()
    assert page["analysis_fresh"] is True and page["analysis_running"] is False
    assert page["analysis"]["when_text"].startswith("Today")
    insight = page["analysis"]["insights"][0]
    assert insight["step"]["title"] == "Sample T-10 today."
    assert insight["step"]["action"] == "claude_suggestion" and insight["step"]["id"] is None
    assert insight["step"]["tank_id"] == "T-10"


def test_approving_doesnt_make_the_analysis_stale_but_a_new_check_does(client, fake):
    _analyze(client)
    pending = client.get("/api/decisions?status=pending").json()["groups"][0]["items"][0]
    client.post(f"/api/decisions/{pending['id']}/approve", json={})
    assert client.get("/api/advisor").json()["analysis_fresh"] is True

    with Session(db.get_engine()) as session:
        check = session.exec(select(models.Check).where(models.Check.tank_id == "T-04").order_by(models.Check.id.desc())).first()
        check.pct_dead = 44.0
        session.add(check)
        session.commit()
    page = client.get("/api/advisor").json()
    assert page["analysis_fresh"] is False
    assert page["analysis"]["headline"] == "Buffer line 2 now."  # still shown, marked out of date


def test_approving_a_claude_suggestion(client, fake):
    _analyze(client)
    answer = client.post("/api/advisor/answer", json={
        "action": "claude_suggestion", "tank_id": "T-10", "verb": "approve", "text": "Sample T-10 today.",
    })
    assert answer.status_code == 200, answer.text
    row = answer.json()
    assert row["title"] == "Sample T-10 today." and row["status"] == "approved" and row["done_text"] == "Approved"
    step = client.get("/api/advisor").json()["analysis"]["insights"][0]["step"]
    assert step["id"] == row["id"] and step["status"] == "approved"
    # It's in T-10's history, in its own words, and the waiting count hasn't moved
    tank = client.get("/api/tanks/T-10").json()
    assert any(h["title"] == "Sample T-10 today." for h in tank["decision_history"])
    assert client.get("/api/floor").json()["metrics"]["decisions_waiting"] == 4
    # Two different suggestions on the same tank stay separate
    other = client.post("/api/advisor/answer", json={
        "action": "claude_suggestion", "tank_id": "T-10", "verb": "dismiss", "text": "Something else.",
    }).json()
    assert other["id"] != row["id"]


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_an_unfinished_answer_is_an_error_not_a_result(client, fake, stop_reason):
    fake.stop_reason = stop_reason
    events = _analyze(client)
    assert events[-1]["error"] and not events[-1]["done"]
    row = _calls("analysis")[0]
    assert row.error and row.result is None
    assert client.get("/api/advisor").json()["analysis"] is None


def test_malformed_output_is_an_error(client, fake):
    fake.text = '{"headline": "cut off'
    events = _analyze(client)
    assert events[-1]["error"] == "Claude's answer couldn't be read. Try again."


def test_api_errors_are_reported_plainly_and_never_leak_the_key(client, fake):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake.raises = anthropic.AuthenticationError("bad key " + FAKE_KEY, response=httpx.Response(401, request=request), body=None)
    response = client.post("/api/advisor/analyze", json={})
    assert "sk-ant" not in response.text
    assert _events(response)[-1]["error"] == "Claude rejected the API key in .env."
    assert _calls("analysis")[0].error == "AuthenticationError"


def test_a_job_always_ends_even_when_the_log_cant_be_written(client, fake, monkeypatch):
    def locked(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(claude, "_log_call", locked)
    with Session(db.get_engine()) as session:
        snapshot = service.build_snapshot(session)
        job = claude.start_analysis(session, service.analysis_key(snapshot), snapshot, service.verify_analysis)
    states = [s for s in job.follow(keepalive_s=5) if s is not None]
    assert states[-1]["done"] is True and states[-1]["analysis"]["headline"] == "Buffer line 2 now."
    assert claude.running_job() is None


def test_a_job_ends_when_checking_the_result_fails(client, fake):
    def broken(raw, snapshot):
        raise KeyError("oops")

    with Session(db.get_engine()) as session:
        snapshot = service.build_snapshot(session)
        job = claude.start_analysis(session, service.analysis_key(snapshot), snapshot, broken)
    states = [s for s in job.follow(keepalive_s=5) if s is not None]
    assert states[-1]["error"] == "Claude's answer couldn't be read. Try again."
    assert claude.running_job() is None


def test_a_new_analysis_doesnt_forget_one_still_running(client, fake):
    fake.gate = threading.Event()
    with Session(db.get_engine()) as session:
        snapshot = service.build_snapshot(session)
        first = claude.start_analysis(session, service.analysis_key(snapshot), snapshot, service.verify_analysis)
        other = {**service.analysis_key(snapshot), "free_tanks": []}
        second = claude.start_analysis(session, other, snapshot, service.verify_analysis)
        assert first is not second
        assert claude.start_analysis(session, service.analysis_key(snapshot), snapshot, service.verify_analysis) is first
    fake.gate.set()
    for job in (first, second):
        assert [s for s in job.follow(keepalive_s=5) if s is not None][-1]["done"] is True


def test_a_second_request_joins_the_running_analysis(client, fake):
    fake.gate = threading.Event()
    with Session(db.get_engine()) as session:
        snapshot = service.build_snapshot(session)
        key = service.analysis_key(snapshot)
        first = claude.start_analysis(session, key, snapshot, service.verify_analysis)
        second = claude.start_analysis(session, key, snapshot, service.verify_analysis)
    assert first is second
    assert client.get("/api/advisor").json()["analysis_running"] is True
    fake.gate.set()
    states = [s for s in first.follow(keepalive_s=5) if s is not None]
    assert states[-1]["done"] is True
    assert len(fake.calls) == 1
    assert client.get("/api/advisor").json()["analysis_running"] is False


# ------------------------------------------------------------------ ask


def _ask(client, *messages, **kwargs):
    body = {"messages": [{"role": role, "content": text} for role, text in messages]}
    return client.post("/api/advisor/ask", json=body, **kwargs)


def test_ask_streams_an_answer(client, fake):
    fake.text = "Buffer line 2 first. It has 56.9M larvae."
    response = _ask(client, ("user", "What should I do first?"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response)
    assert "".join(e["text"] for e in events if e["type"] == "delta").strip() == fake.text
    assert events[-1] == {"type": "done", "cached": False, "model": "claude-opus-5-5"}
    call = fake.calls[0]
    assert call["messages"] == [{"role": "user", "content": "What should I do first?"}]
    assert call["output_config"] == {"effort": "low"} and call["max_tokens"] == config.CLAUDE_ASK_MAX_TOKENS
    assert call["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert call["system"][2]["text"] == claude.ASK_TASK
    row = _calls("ask")[0]
    assert row.result == {"text": fake.text + " "} and row.input_tokens == 9700


def test_ask_sends_the_conversation_and_repeats_are_free(client, fake):
    fake.text = "Answer."
    turns = (("user", "First?"), ("assistant", "One."), ("user", "Second?"))
    _ask(client, *turns)
    assert [m["role"] for m in fake.calls[0]["messages"]] == ["user", "assistant", "user"]
    again = _events(_ask(client, *turns))
    assert len(fake.calls) == 1
    assert again[0] == {"type": "delta", "text": "Answer. "} and again[-1]["cached"] is True


@pytest.mark.parametrize("messages", [
    [],
    [("assistant", "No question.")],
    [("user", "   ")],
    [("user", "x" * (config.CLAUDE_ASK_MAX_CHARS + 1))],
    [("user", "again")] * (config.CLAUDE_ASK_MAX_TURNS + 1),
])
def test_ask_checks_its_input(client, fake, messages):
    assert _ask(client, *messages).status_code == 422
    assert fake.calls == []


def test_ask_reports_failures_and_logs_them(client, fake):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake.raises = anthropic.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    events = _events(_ask(client, ("user", "Hello?")))
    assert events == [{"type": "error", "message": "Claude is rate limiting this key. Try again in a minute."}]
    assert _calls("ask")[0].error == "RateLimitError"


def test_an_answer_that_ran_out_of_room_isnt_stored(client, fake):
    fake.text = "This answer stops halfway through a"
    fake.stop_reason = "max_tokens"
    events = _events(_ask(client, ("user", "Tell me everything.")))
    assert events[-1] == {"type": "error", "message": "Claude ran out of room before finishing. Try again."}
    assert _calls("ask")[0].result is None
    fake.stop_reason = "end_turn"
    fake.text = "A whole answer."
    events = _events(_ask(client, ("user", "Tell me everything.")))
    assert events[-1]["type"] == "done" and events[-1]["cached"] is False


def test_an_empty_turn_is_never_sent_to_claude(client, fake):
    fake.text = "Answer."
    _ask(client, ("user", "First?"), ("assistant", ""), ("user", "Second?"))
    assert fake.calls[0]["messages"] == [{"role": "user", "content": "First?"}, {"role": "user", "content": "Second?"}]


def test_a_stream_cut_short_is_an_error_and_isnt_cached(client, fake):
    fake.text = "Half an answer"
    fake.raises_midway = ConnectionError("gone")
    events = _events(_ask(client, ("user", "Hello?")))
    assert events[-1]["type"] == "error"
    fake.raises_midway = None
    events = _events(_ask(client, ("user", "Hello?")))
    assert events[-1]["type"] == "done" and events[-1]["cached"] is False


def test_nothing_in_the_logs_but_token_counts(client, fake, caplog):
    fake.text = "A private answer."
    with caplog.at_level("INFO", logger="thetis.claude"):
        _ask(client, ("user", "A private question?"))
    text = caplog.text
    assert "input_tokens=" in text
    assert "private" not in text and FAKE_KEY not in text
