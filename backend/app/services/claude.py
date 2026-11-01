"""Optional Claude features (SPEC §8). The only module that reads ANTHROPIC_API_KEY.

The key is held as a SecretStr, is never put in a config object, a response or a log line, and is
read fresh from the environment so tests can blank it. With no key every feature here is off.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time as clock
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime, time
from typing import Literal

import anthropic
import cv2
import jiter
import numpy as np
from pydantic import BaseModel, SecretStr
from sqlmodel import Session, func, select

from app import config, db, models
from app.analysis.models import Detection as Det

logger = logging.getLogger("thetis.claude")

OPINION_SYSTEM = (
    "You help a shellfish hatchery technician review a microscope photo of Pacific oyster larvae on a counting "
    "slide. Each numbered crop is one object an automatic counter was unsure about. Classify each: live (shell "
    "filled with brown tissue, smooth D or umbo outline), abnormal (misshapen, indented or asymmetric shell, or "
    "tissue shrunk but still brown), dead (empty or nearly empty pale shell, only the outline dark), not_larva "
    "(bubble, algae, debris, grid line). Give a reason of at most 12 words. If you can't tell, say so with low "
    "confidence."
)

EXPLAIN_SYSTEM = (
    "Write 3 short sentences for a hatchery manager: what changed since the last check, why the numbers match this "
    "pattern, and what the recommended actions do. Use only numbers from the data. Say 'pattern matches', never "
    "'diagnosis'."
)


ADVISOR_SYSTEM = """You are Thetis, the advisor inside a shellfish hatchery's operations app. You help a hatchery manager decide
what to do today: how to head off crashes and how to get more larvae through to the eyed stage.

You will get a JSON snapshot of the hatchery. It has every running tank with each check over time, the free tanks, past batches,
what the rules engine already found, and the log of past decisions. In that snapshot:
- day counts from the batch's spawn, and days_ago counts back from today.
- live_est is the estimated live larvae in the tank. density_per_l is larvae per litre.
- gut is gut fullness from 0 to 1. cv is the size spread. omega_arag is Ω aragonite. Readings that weren't taken are left out, and
  a missing reading is not a zero.
- running_tanks with kind "setting" are already in the setting room.

Rules for everything you write:
- Use only numbers from the snapshot, or simple arithmetic on them. Never invent a reading, a count or a source.
- Chemical doses are calculated by the app and appear under rules_found. Repeat them exactly. Never change one or give a dose of
  your own, and never suggest antibiotics.
- Use the chemicals in plant_chemicals, because those are what this plant uses.
- Say "pattern matches", never "diagnosis". A pattern is not proof, and one check can be noise, so say so when it matters.
- Everything you suggest is for a person to approve. Nothing acts on equipment.
- Write for a busy hatchery manager: plain words, short sentences, specific tanks and numbers. No hype and no filler.
- Write counts the way the app does: 56.9M, 344k."""

ANALYSIS_TASK = """Write today's brief for the manager.

headline: The one thing that matters most today, as a sentence of at most 14 words.

brief: 2 or 3 short sentences on where the hatchery stands and what matters most. Name the larvae at stake.

do_first: The 3 most useful steps today, in order. These can come from rules_found or from your own insights. For each one:
- ref: the id of the matching card under rules_found, or an empty string if it comes from your own insights.
- action: what to do, as an instruction of at most 10 words.
- why: at most 18 words, with the number that makes it urgent.

insights: Up to 3 things the rules have NOT already said, which a busy manager would otherwise miss. Look for:
- a tank that now looks like another tank did just before it went wrong
- a difference between lines, rooms, stocking densities or batches that points to something worth changing
- a clash coming up in the next few days, such as more eyed larvae than free setting tanks, or two suggestions wanting the same
  free tank
- a decision in the log that doesn't seem to have worked
Return fewer if there is nothing real to add. An empty list is fine, and repeating rules_found is not.
For each insight:
- kind: "crash_risk" if it could lead to a crash, "yield" if it would raise yield.
- title: at most 10 words.
- tank_ids: the tanks involved.
- body: at most 2 short sentences, under 45 words in all, on what you noticed and why it matters.
- suggestion: one instruction of at most 20 words, starting with a verb. A manager will press Approve on it, so don't say "approve".
- confidence: low, medium or high, being honest about how few checks it rests on.
- evidence: 2 to 4 readings that back it up. For each one give tank_id, metric and value. Metric must be a field of a check in
  that tank (live_est, pct_dead, pct_abnormal, length_um, cv, gut, growth_um_day, loss_pct_per_day, survival_pct, ph, omega_arag,
  temp_c, do_mgl) or density_per_l. Copy the value exactly as it appears in the snapshot, because the app checks each one against
  the records and removes any insight that fails."""

ASK_TASK = """The manager is asking you questions in a chat beside the hatchery's data. Lead with the answer. Keep it under 120 words unless
they ask for more detail. Name specific tanks and numbers. Use a short numbered list for steps, and otherwise plain sentences,
with no headings. If the snapshot doesn't have what you'd need, say what's missing and what reading or check would settle it. If
you're asked about something outside running this hatchery, say briefly that you can only help with the hatchery."""


class Opinion(BaseModel):
    object: int
    cls: Literal["live", "abnormal", "dead", "not_larva"]
    confidence: Literal["low", "medium", "high"]
    reason: str


class Opinions(BaseModel):
    opinions: list[Opinion]


EvidenceMetric = Literal[
    "live_est", "pct_dead", "pct_abnormal", "length_um", "cv", "gut", "growth_um_day", "loss_pct_per_day", "survival_pct", "ph",
    "omega_arag", "temp_c", "do_mgl", "density_per_l",
]


class Evidence(BaseModel):
    tank_id: str
    metric: EvidenceMetric
    value: float


class Priority(BaseModel):
    ref: str
    action: str
    why: str


class Insight(BaseModel):
    kind: Literal["crash_risk", "yield"]
    title: str
    tank_ids: list[str]
    body: str
    suggestion: str
    confidence: Literal["low", "medium", "high"]
    evidence: list[Evidence]


class Analysis(BaseModel):
    headline: str
    brief: str
    do_first: list[Priority]
    insights: list[Insight]


class ClaudeOff(Exception):
    """No API key: the feature is off."""


class OverDailyLimit(Exception):
    """The day's calls are used up."""


class ClaudeFailed(Exception):
    """The API call failed or gave no usable answer. The message is safe to show."""


# ---------------------------------------------------------------- settings


def _api_key() -> SecretStr:
    return SecretStr(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def is_enabled() -> bool:
    return bool(_api_key().get_secret_value())


def model_name() -> str:
    return os.environ.get("CLAUDE_MODEL", "").strip() or config.CLAUDE_DEFAULT_MODEL


def daily_limit() -> int:
    return config.env_int("CLAUDE_DAILY_LIMIT", config.CLAUDE_DAILY_LIMIT_DEFAULT)


def _make_client(timeout_s: float = config.CLAUDE_TIMEOUT_S) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=_api_key().get_secret_value(), timeout=timeout_s, max_retries=config.CLAUDE_MAX_RETRIES)


def used_today(session: Session, now: datetime | None = None) -> int:
    start = datetime.combine((now or datetime.now()).date(), time.min)
    return session.exec(select(func.count()).select_from(models.ClaudeCall).where(models.ClaudeCall.created_at >= start)).one()


def status(session: Session) -> dict:
    return {"enabled": is_enabled(), "model": model_name(), "used_today": used_today(session), "limit": daily_limit()}


# ---------------------------------------------------------------- request options


def _request_options(model: str, max_tokens: int, effort: str) -> dict:
    """Keep thinking out of the small token budgets the SPEC sets, on whichever model is configured.

    Sonnet 5.5 turns thinking off with "between_tools"; other current models with "disabled". Opus 5.5, Fable
    and Mythos always think, so they get headroom on top of the budget instead.
    """
    if model.startswith(("claude-opus-5-5", "claude-fable", "claude-mythos")):
        return {"max_tokens": max_tokens + config.CLAUDE_THINKING_HEADROOM_TOKENS, "output_config": {"effort": effort}}
    if model == "claude-sonnet-5-5":
        return {"max_tokens": max_tokens, "thinking": {"type": "between_tools"}, "output_config": {"effort": effort}}
    if model.startswith(("claude-haiku-5", "claude-opus-5", "claude-sonnet-5")):
        return {"max_tokens": max_tokens, "thinking": {"type": "disabled"}, "output_config": {"effort": effort}}
    return {"max_tokens": max_tokens}


def _streaming_options(model: str, max_tokens: int, effort: str) -> dict:
    """For the Advisor's streaming calls, which have room to think and show a summary of the reasoning."""
    if model.startswith(("claude-opus-5", "claude-sonnet-5", "claude-haiku-5", "claude-fable", "claude-mythos")):
        return {
            "max_tokens": max_tokens,
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": effort},
        }
    return {"max_tokens": max_tokens}


# ---------------------------------------------------------------- budget guard


def _hash_input(kind: str, model: str, payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(kind.encode() + b"|" + model.encode() + b"|" + blob).hexdigest()


def _cached(session: Session, input_hash: str) -> models.ClaudeCall | None:
    return session.exec(
        select(models.ClaudeCall)
        .where(models.ClaudeCall.input_hash == input_hash, models.ClaudeCall.error == None)  # noqa: E711
        .order_by(models.ClaudeCall.id.desc())
    ).first()


def _guard(session: Session) -> None:
    if not is_enabled():
        raise ClaudeOff("Claude isn't set up on this computer.")
    if used_today(session) >= daily_limit():
        raise OverDailyLimit("Daily Claude limit reached")


_INPUT_TOKEN_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _log_call(session: Session, kind: str, input_hash: str, model: str, usage: object | None, result: dict | None,
              error: str | None) -> models.ClaudeCall:
    row = models.ClaudeCall(
        kind=kind,
        input_hash=input_hash,
        model=model,
        input_tokens=sum(getattr(usage, name, 0) or 0 for name in _INPUT_TOKEN_FIELDS),
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        created_at=datetime.now(),
        result=result,
        error=error,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    # Token counts only. Never the prompt, the reply or the key.
    logger.info("claude call kind=%s model=%s input_tokens=%s output_tokens=%s error=%s", kind, model, row.input_tokens,
                row.output_tokens, error or "none")
    return row


_FAILURE_TEXT: tuple[tuple[type[Exception], str], ...] = (
    (anthropic.AuthenticationError, "Claude rejected the API key in .env."),
    (anthropic.PermissionDeniedError, "This API key isn't allowed to use that model."),
    (anthropic.NotFoundError, "Claude doesn't know the model set in CLAUDE_MODEL."),
    (anthropic.RateLimitError, "Claude is rate limiting this key. Try again in a minute."),
    (anthropic.BadRequestError, "Claude refused that request."),
    (anthropic.APIStatusError, "Claude had a problem. Try again in a minute."),
    (anthropic.APIConnectionError, "Can't reach Claude. Check the internet connection."),
)


def _describe_failure(error: Exception) -> str:
    for kind, text in _FAILURE_TEXT:
        if isinstance(error, kind):
            return text
    return "Claude had a problem. Try again in a minute."


# ---------------------------------------------------------------- second opinion (§8.1)


def _crop(image: np.ndarray, det: Det) -> str:
    """A crop with 30% padding, at most 256 px, the automatic outline drawn 1 px in its class colour."""
    points = np.array(det.contour, dtype=np.float32)
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    pad_x = (x1 - x0) * config.CLAUDE_CROP_PADDING
    pad_y = (y1 - y0) * config.CLAUDE_CROP_PADDING
    height, width = image.shape[:2]
    left, top = max(0, int(x0 - pad_x)), max(0, int(y0 - pad_y))
    right, bottom = min(width, int(np.ceil(x1 + pad_x))), min(height, int(np.ceil(y1 + pad_y)))
    crop = image[top:bottom, left:right]
    scale = min(1.0, config.CLAUDE_CROP_MAX_PX / max(crop.shape[:2]))
    if scale < 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        crop = crop.copy()
    outline = ((points - np.array([left, top], dtype=np.float32)) * scale).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(crop, [outline], True, config.CLAUDE_OUTLINE_BGR[det.cls], 1, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, config.CLAUDE_CROP_JPEG_QUALITY])
    if not ok:
        raise ClaudeFailed("That photo couldn't be cropped.")
    return base64.standard_b64encode(encoded.tobytes()).decode("ascii")


def _object_line(det: Det) -> str:
    length = f"{det.length_um:.0f} µm" if det.length_um is not None else "unknown length"
    reason = det.unsure_reason or "unsure"
    return f"Object {det.id}: automatic call {det.cls} ({reason}), length {length}"


def second_opinion(session: Session, image: np.ndarray, dets: Sequence[Det]) -> dict:
    """Ask Claude about up to 12 unsure objects. Identical input returns the stored answer, with no API call."""
    if len(dets) > config.CLAUDE_MAX_OBJECTS:
        raise ValueError(f"At most {config.CLAUDE_MAX_OBJECTS} objects per call.")
    if not is_enabled():
        raise ClaudeOff("Claude isn't set up on this computer.")
    model = model_name()
    blocks: list[dict] = []
    crops = []
    for det in dets:
        data = _crop(image, det)
        crops.append(hashlib.sha256(data.encode()).hexdigest())
        blocks.append({"type": "text", "text": _object_line(det)})
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    input_hash = _hash_input("opinion", model, {"lines": [_object_line(d) for d in dets], "crops": crops})

    hit = _cached(session, input_hash)
    if hit is not None:
        return {"opinions": hit.result["opinions"], "cached": True, "model": hit.model}
    _guard(session)

    usage = None
    try:
        response = _make_client().messages.parse(
            model=model,
            system=OPINION_SYSTEM,
            messages=[{"role": "user", "content": blocks}],
            output_format=Opinions,
            **_request_options(model, config.CLAUDE_OPINION_MAX_TOKENS, "medium"),
        )
        usage = response.usage
        parsed = response.parsed_output
        if parsed is None:
            raise ClaudeFailed(_empty_answer_text(response.stop_reason))
    except anthropic.APIError as error:
        _log_call(session, "opinion", input_hash, model, usage, None, type(error).__name__)
        raise ClaudeFailed(_describe_failure(error)) from None
    except ClaudeFailed as error:
        _log_call(session, "opinion", input_hash, model, usage, None, str(error))
        raise
    except Exception as error:  # malformed structured output, for example
        _log_call(session, "opinion", input_hash, model, usage, None, type(error).__name__)
        raise ClaudeFailed("Claude's answer couldn't be read. Try again.") from None

    wanted = {d.id for d in dets}
    opinions = {
        str(o.object): {"cls": o.cls, "confidence": o.confidence, "reason": o.reason} for o in parsed.opinions if o.object in wanted
    }
    _log_call(session, "opinion", input_hash, model, usage, {"opinions": opinions}, None)
    return {"opinions": opinions, "cached": False, "model": model}


def _empty_answer_text(stop_reason: str | None) -> str:
    if stop_reason == "refusal":
        return "Claude declined to answer this one."
    if stop_reason == "max_tokens":
        return "Claude ran out of room before finishing. Try again."
    return "Claude gave no usable answer. Try again."


# ---------------------------------------------------------------- explain (§8.2)


def explain(session: Session, cache_key: dict, data: dict) -> dict:
    """Three short sentences from the numbers. Cached by check and rules version (and the numbers themselves)."""
    if not is_enabled():
        raise ClaudeOff("Claude isn't set up on this computer.")
    model = model_name()
    input_hash = _hash_input("explain", model, {**cache_key, "data": data})
    hit = _cached(session, input_hash)
    if hit is not None:
        return {"text": hit.result["text"], "cached": True, "model": hit.model}
    _guard(session)

    usage = None
    try:
        response = _make_client().messages.create(
            model=model,
            system=EXPLAIN_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
            **_request_options(model, config.CLAUDE_EXPLAIN_MAX_TOKENS, "low"),
        )
        usage = response.usage
        text = " ".join(block.text for block in response.content if block.type == "text").strip()
        if not text or response.stop_reason == "refusal":
            raise ClaudeFailed(_empty_answer_text(response.stop_reason))
    except anthropic.APIError as error:
        _log_call(session, "explain", input_hash, model, usage, None, type(error).__name__)
        raise ClaudeFailed(_describe_failure(error)) from None
    except ClaudeFailed as error:
        _log_call(session, "explain", input_hash, model, usage, None, str(error))
        raise

    _log_call(session, "explain", input_hash, model, usage, {"text": text}, None)
    return {"text": text, "cached": False, "model": model}


# ---------------------------------------------------------------- the Advisor's analysis (SPEC §16)


class AnalysisJob:
    """One analysis running in the background. It outlives the page that started it, so someone can click away and
    come back, and a second request joins the first instead of paying twice."""

    def __init__(self, input_hash: str, model: str):
        self.input_hash = input_hash
        self.model = model
        self.state: dict = {"status": "starting", "looking_at": [], "analysis": None, "done": False, "error": None, "model": model}
        self.version = 0
        self._condition = threading.Condition()

    def update(self, **fields: object) -> None:
        with self._condition:
            self.state = {**self.state, **fields}
            self.version += 1
            self._condition.notify_all()

    def follow(self, keepalive_s: float = 10.0) -> Iterator[dict | None]:
        """Yields the job's state each time it changes, and None as a keep-alive."""
        seen = -1
        while True:
            with self._condition:
                if self.version == seen:
                    self._condition.wait(timeout=keepalive_s)
                if self.version == seen:
                    state = None
                else:
                    seen = self.version
                    state = self.state
            yield state
            if state is not None and (state["done"] or state["error"]):
                return


_TANK_ID = re.compile(r"\b[A-Z]-\d{2}\b")
_jobs: dict[str, AnalysisJob] = {}
_jobs_lock = threading.Lock()


def running_job() -> AnalysisJob | None:
    with _jobs_lock:
        return next((job for job in _jobs.values() if not (job.state["done"] or job.state["error"])), None)


def _analysis_hash(model: str, analysis_key: dict) -> str:
    """The data and the instructions: improving the prompt should give a new answer, not the stored one."""
    return _hash_input("analysis", model, {"prompt": ADVISOR_SYSTEM + ANALYSIS_TASK, "data": analysis_key})


def stored_analysis(session: Session, analysis_key: dict) -> tuple[models.ClaudeCall | None, bool]:
    """The analysis to show, and whether it was written from the current data."""
    hit = _cached(session, _analysis_hash(model_name(), analysis_key))
    if hit is not None:
        return hit, True
    newest = session.exec(
        select(models.ClaudeCall)
        .where(models.ClaudeCall.kind == "analysis", models.ClaudeCall.error == None)  # noqa: E711
        .order_by(models.ClaudeCall.id.desc())
    ).first()
    return newest, False


def _snapshot_blocks(snapshot: dict) -> list[dict]:
    """The stable part of the prompt. It's cached, so follow-up questions pay about a tenth for it."""
    return [
        {"type": "text", "text": ADVISOR_SYSTEM},
        {
            "type": "text",
            "text": "Hatchery snapshot:\n" + json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _partial_json(text: str) -> dict | None:
    if not text.strip():
        return None
    try:
        parsed = jiter.from_json(text.encode(), partial_mode="trailing-strings")
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _tanks_in_focus(reasoning: str, limit: int = 3) -> list[str]:
    """Which tanks Claude's reasoning has just mentioned. The page shows these and never the reasoning itself: its
    summaries are a rough sketch and can get details wrong, and nothing on screen should be unchecked."""
    seen: list[str] = []
    for tank_id in reversed(_TANK_ID.findall(reasoning[-400:])):
        if tank_id not in seen:
            seen.append(tank_id)
        if len(seen) == limit:
            break
    return list(reversed(seen))


def _run_analysis(job: AnalysisJob, snapshot: dict, verify: Callable[[dict, dict], dict]) -> None:
    """Whatever goes wrong, the job ends: a page must never wait forever on a thread that has died."""
    try:
        _analyze(job, snapshot, verify)
    except Exception as error:
        logger.error("analysis stopped: %s", type(error).__name__)
    finally:
        if not job.state["done"] and not job.state["error"]:
            job.update(status="failed", error="The analysis stopped before it finished. Try again.")


def _analyze(job: AnalysisJob, snapshot: dict, verify: Callable[[dict, dict], dict]) -> None:
    usage = None
    model = job.model
    try:
        job.update(status="reading")
        last_update = 0.0
        with _make_client(config.CLAUDE_STREAM_TIMEOUT_S).messages.stream(
            model=model,
            system=_snapshot_blocks(snapshot),
            messages=[{"role": "user", "content": ANALYSIS_TASK}],
            output_format=Analysis,
            **_streaming_options(model, config.CLAUDE_ANALYSIS_MAX_TOKENS, "medium"),
        ) as stream:
            for event in stream:
                due = clock.monotonic() - last_update >= config.CLAUDE_STREAM_UPDATE_S
                if event.type == "thinking" and due:
                    job.update(status="reading", looking_at=_tanks_in_focus(event.snapshot))
                    last_update = clock.monotonic()
                elif event.type == "text" and due:
                    partial = _partial_json(event.snapshot)
                    if partial is not None:
                        job.update(status="writing", analysis=partial)
                        last_update = clock.monotonic()
            response = stream.get_final_message()
        usage = response.usage
        if response.stop_reason in ("refusal", "max_tokens"):
            raise ClaudeFailed(_empty_answer_text(response.stop_reason))
        text = "".join(block.text for block in response.content if block.type == "text")
        result = verify(Analysis.model_validate_json(text).model_dump(), snapshot)
    except anthropic.APIError as error:
        _finish_failed(job, usage, type(error).__name__, _describe_failure(error))
        return
    except ClaudeFailed as error:
        _finish_failed(job, usage, str(error), str(error))
        return
    except Exception as error:  # a stream cut short, or an answer that doesn't fit the schema
        _finish_failed(job, usage, type(error).__name__, "Claude's answer couldn't be read. Try again.")
        return

    try:
        with Session(db.get_engine()) as session:
            _log_call(session, "analysis", job.input_hash, model, usage, result, None)
    finally:
        # A paid answer is worth showing even if the log couldn't take it
        job.update(status="done", analysis=result, done=True, looking_at=[], cached=False)


def _finish_failed(job: AnalysisJob, usage: object | None, logged: str, shown: str) -> None:
    try:
        with Session(db.get_engine()) as session:
            _log_call(session, "analysis", job.input_hash, job.model, usage, None, logged)
    finally:
        job.update(status="failed", error=shown)


def start_analysis(session: Session, analysis_key: dict, snapshot: dict, verify: Callable[[dict, dict], dict],
                   force: bool = False) -> AnalysisJob:
    """Join the analysis already running for this data, return the stored one, or start a new one."""
    if not is_enabled():
        raise ClaudeOff("Claude isn't set up on this computer.")
    model = model_name()
    input_hash = _analysis_hash(model, analysis_key)
    with _jobs_lock:
        running = _jobs.get(input_hash)
        if running is not None and not (running.state["done"] or running.state["error"]):
            return running
        hit = None if force else _cached(session, input_hash)
        if hit is not None:
            job = AnalysisJob(input_hash, hit.model)
            job.update(status="done", analysis=hit.result, done=True, cached=True)
            return job
        _guard(session)
        job = AnalysisJob(input_hash, model)
        # Finished jobs have nothing more to give: the result is in the database
        for key in [k for k, old_job in _jobs.items() if old_job.state["done"] or old_job.state["error"]]:
            del _jobs[key]
        _jobs[input_hash] = job
    threading.Thread(target=_run_analysis, args=(job, snapshot, verify), daemon=True, name="thetis-analysis").start()
    return job


# ---------------------------------------------------------------- ask Thetis (SPEC §16)


def stream_answer(snapshot: dict, messages: list[dict]) -> Iterator[dict]:
    """A chat answer as it's written. Identical data and conversation return the stored answer, with no API call."""
    model = model_name()
    input_hash = _hash_input("ask", model, {"prompt": ADVISOR_SYSTEM + ASK_TASK, "snapshot": snapshot, "messages": messages})
    with Session(db.get_engine()) as session:
        hit = _cached(session, input_hash)
        if hit is None:
            try:
                _guard(session)
            except (ClaudeOff, OverDailyLimit) as error:
                yield {"type": "error", "message": str(error)}
                return
    if hit is not None:
        yield {"type": "delta", "text": hit.result["text"]}
        yield {"type": "done", "cached": True, "model": hit.model}
        return

    usage = None
    finished = False
    failure: str | None = "cancelled"
    text = ""
    try:
        with _make_client(config.CLAUDE_STREAM_TIMEOUT_S).messages.stream(
            model=model,
            system=[*_snapshot_blocks(snapshot), {"type": "text", "text": ASK_TASK}],
            messages=messages,
            **_streaming_options(model, config.CLAUDE_ASK_MAX_TOKENS, "low"),
        ) as stream:
            for delta in stream.text_stream:
                text += delta
                yield {"type": "delta", "text": delta}
            response = stream.get_final_message()
        usage = response.usage
        if not text.strip() or response.stop_reason in ("refusal", "max_tokens"):
            raise ClaudeFailed(_empty_answer_text(response.stop_reason))
        failure = None
        finished = True
    except anthropic.APIError as error:
        failure = type(error).__name__
        yield {"type": "error", "message": _describe_failure(error)}
    except ClaudeFailed as error:
        failure = str(error)
        yield {"type": "error", "message": str(error)}
    except GeneratorExit:  # the page went away mid-answer. Still counts against the day's calls
        raise
    except Exception as error:  # a stream cut short
        failure = type(error).__name__
        yield {"type": "error", "message": "Claude's answer was cut off. Try again."}
    finally:
        with Session(db.get_engine()) as session:
            _log_call(session, "ask", input_hash, model, usage, {"text": text} if finished else None, failure)
    if finished:
        yield {"type": "done", "cached": False, "model": model}
