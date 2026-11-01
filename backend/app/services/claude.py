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
from collections.abc import Sequence
from datetime import datetime, time
from typing import Literal

import anthropic
import cv2
import numpy as np
from pydantic import BaseModel, SecretStr
from sqlmodel import Session, func, select

from app import config, models
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


class Opinion(BaseModel):
    object: int
    cls: Literal["live", "abnormal", "dead", "not_larva"]
    confidence: Literal["low", "medium", "high"]
    reason: str


class Opinions(BaseModel):
    opinions: list[Opinion]


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


def _make_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=_api_key().get_secret_value(), timeout=config.CLAUDE_TIMEOUT_S, max_retries=config.CLAUDE_MAX_RETRIES
    )


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


def _log_call(session: Session, kind: str, input_hash: str, model: str, usage: object | None, result: dict | None,
              error: str | None) -> models.ClaudeCall:
    row = models.ClaudeCall(
        kind=kind,
        input_hash=input_hash,
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
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
