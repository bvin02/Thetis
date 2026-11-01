"""Claude endpoints (SPEC §8). Every one is off when there is no API key."""
from __future__ import annotations

import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlmodel import Session, select

from app import config, models
from app.analysis.models import Detection as Det
from app.db import get_session
from app.rules.assess import LEVEL_LABEL
from app.rules.text import FORECAST, title_for
from app.services import claude, uploads
from app.services.checks import det_from_row
from app.services.decisions import actions_for_tank, all_decisions, decision_view
from app.services.world import load_world

router = APIRouter(prefix="/api/claude", tags=["claude"])


@router.get("/status")
def get_status(session: Session = Depends(get_session)) -> dict:
    return claude.status(session)


class SecondOpinionRequest(BaseModel):
    photo: str | int  # an upload token while reviewing, or a saved photo id
    detection_ids: list[int]


def _load_photo(photo: str | int, session: Session) -> tuple[object, list[Det]]:
    """The image and its detections, from an upload waiting to be saved or from a saved photo."""
    if isinstance(photo, str):
        meta = uploads.read_meta(photo)
        if meta is None:
            raise HTTPException(404, "That photo has expired. Upload it again.")
        image = cv2.imread(str(uploads.image_path(photo)), cv2.IMREAD_COLOR)
        return image, [Det.model_validate(d) for d in meta.get("detections", [])]
    row = session.get(models.Photo, photo)
    if row is None:
        raise HTTPException(404, "No such photo")
    image = cv2.imread(str(config.data_dir() / row.path), cv2.IMREAD_COLOR)
    rows = session.exec(select(models.Detection).where(models.Detection.photo_id == row.id))
    return image, [det_from_row(d) for d in rows]


def _call(function, *args):
    try:
        return function(*args)
    except claude.ClaudeOff as error:
        raise HTTPException(503, str(error)) from None
    except claude.OverDailyLimit as error:
        raise HTTPException(429, str(error)) from None
    except claude.ClaudeFailed as error:
        raise HTTPException(502, str(error)) from None


@router.post("/second-opinion")
async def second_opinion(body: SecondOpinionRequest, session: Session = Depends(get_session)) -> dict:
    if not claude.is_enabled():
        raise HTTPException(503, "Claude isn't set up on this computer.")
    if not body.detection_ids:
        raise HTTPException(422, "Choose at least one object.")
    if len(body.detection_ids) > config.CLAUDE_MAX_OBJECTS:
        raise HTTPException(422, f"At most {config.CLAUDE_MAX_OBJECTS} objects per call.")
    image, detections = _load_photo(body.photo, session)
    if image is None:
        raise HTTPException(404, "That photo's file is missing.")
    by_id = {d.id: d for d in detections}
    missing = [i for i in body.detection_ids if i not in by_id]
    if missing:
        raise HTTPException(422, f"Those objects aren't in this photo: {missing}")
    chosen = [by_id[i] for i in body.detection_ids]
    return await run_in_threadpool(_call, claude.second_opinion, session, image, chosen)


class ExplainRequest(BaseModel):
    tank_id: str


def _explain_data(tank_id: str, session: Session) -> tuple[dict, dict]:
    """The assessment, the last 3 checks' key numbers and the recommended actions. Returns (cache key, data)."""
    world = load_world(session)
    state = world.tanks.get(tank_id)
    if state is None:
        raise HTTPException(404, f"No tank called {tank_id}")
    if state.assessment is None or state.latest is None:
        raise HTTPException(422, f"{tank_id} has no checks to explain.")
    a = state.assessment
    actions = actions_for_tank(state, world, all_decisions(session))
    data = {
        "tank": tank_id,
        "batch": state.batch.code,
        "day": state.day(world.now),
        "stocked": state.batch.stocked,
        "level": LEVEL_LABEL[a.level],
        "pattern": title_for(a),
        "forecast": FORECAST[a.level],
        "signals": [s.to_json() for s in a.signals],
        "growth_um_day": a.growth_um_day,
        "expected_growth_um_day": world.cfg["expected_growth_um_day"],
        "loss_per_day": a.loss_per_day,
        "survival": a.survival,
        "last_checks": [
            {
                "sampled_at": c.sampled_at.isoformat(timespec="minutes"), "live_est": c.live_est, "pct_dead": c.pct_dead,
                "pct_abnormal": c.pct_abnormal, "mean_len_um": c.mean_len_um, "cv": c.cv, "gut": c.gut,
                "omega_arag": c.omega_arag, "ph": c.ph, "temp_c": c.temp_c, "do_mgl": c.do_mgl,
            }
            for c in state.checks[-3:]
        ],
        "recommended_actions": [decision_view(d, world.now)["title"] for d in actions],
    }
    return {"check_id": state.latest.id, "rules_version": a.rules_version}, data


@router.post("/explain")
def explain_tank(body: ExplainRequest, session: Session = Depends(get_session)) -> dict:
    if not claude.is_enabled():
        raise HTTPException(503, "Claude isn't set up on this computer.")
    cache_key, data = _explain_data(body.tank_id, session)
    return _call(claude.explain, session, cache_key, data)
