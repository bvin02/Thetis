"""Analyze photos, review them live, save checks, and correct saved checks."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import config, models
from app.analysis.models import Detection as Det
from app.db import get_session
from app.rules.assess import LEVEL_LABEL, assess
from app.rules.text import FORECAST, condition_rows, fmt_count, fmt_when, title_for
from app.services import checks as check_service
from app.services import uploads
from app.services.views import check_row, photo_view, photos_of_check
from app.services.world import batch_data, check_data, load_world, settings_for

router = APIRouter(prefix="/api", tags=["checks"])


def _settings(session: Session) -> dict:
    return settings_for(session.get(models.Hatchery, 1))


@router.post("/analyze")
async def analyze_upload(file: UploadFile = File(...), session: Session = Depends(get_session)) -> dict:
    data = await file.read()
    if len(data) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(413, "That photo is larger than 40 MB.")
    settings = _settings(session)
    try:
        token, meta, result = await run_in_threadpool(uploads.store_and_analyze, data, file.filename, settings)
    except uploads.NotAPhoto as error:
        raise HTTPException(422, str(error)) from error
    return uploads.analysis_payload(token, meta, result)


@router.get("/samples")
def list_samples() -> dict:
    return {"samples": uploads.sample_list()}


@router.get("/samples/{name}/image")
def sample_image(name: str) -> FileResponse:
    path = uploads.sample_files().get(name)
    if path is None:
        raise HTTPException(404, "No such sample")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/samples/{name}/analyze")
async def analyze_sample(name: str, session: Session = Depends(get_session)) -> dict:
    path = uploads.sample_files().get(name)
    if path is None:
        raise HTTPException(404, "No such sample")
    data = path.read_bytes()
    settings = _settings(session)
    token, meta, result = await run_in_threadpool(uploads.store_and_analyze, data, path.name, settings)
    return uploads.analysis_payload(token, meta, result)


class ScaleRequest(BaseModel):
    um_per_px: float = Field(gt=0, lt=1000)


@router.post("/analyze/{token}/scale")
async def apply_manual_scale(token: str, body: ScaleRequest) -> dict:
    try:
        meta, result = await run_in_threadpool(uploads.reanalyze_with_scale, token, body.um_per_px)
    except FileNotFoundError as error:
        raise HTTPException(404, "That photo has expired. Upload it again.") from error
    return uploads.analysis_payload(token, meta, result)


class Sample(BaseModel):
    bucket_l: float | None = Field(default=None, gt=0)
    concentration: float | None = Field(default=None, gt=0)


class SummarizeRequest(BaseModel):
    detections: list[Det]
    um_per_px: float | None = None
    photo_volume_ml: float | None = None
    sample: Sample = Sample()
    tank_id: str | None = None
    estimate_detections: list[Det] | None = None  # from photos with a scale, when some photos have none


@router.post("/summarize")
def summarize_detections(body: SummarizeRequest, session: Session = Depends(get_session)) -> dict:
    """Counts, sizes and the tank estimate, recomputed live while correcting."""
    settings = _settings(session)
    stocked = None
    if body.tank_id:
        batch = session.exec(
            select(models.Batch).where(models.Batch.tank_id == body.tank_id, models.Batch.status == "active")
        ).first()
        stocked = batch.stocked if batch else None
    return check_service.compute_estimate(
        body.detections, body.photo_volume_ml, body.sample.model_dump(), stocked, settings, body.estimate_detections
    )


class Water(BaseModel):
    temp_c: float | None = Field(default=None, ge=-5, le=60)
    salinity_ppt: float | None = Field(default=None, ge=0, le=60)
    ph: float | None = Field(default=None, ge=0, le=14)
    omega_arag: float | None = Field(default=None, ge=0, le=20)
    do_mgl: float | None = Field(default=None, ge=0, le=40)


class CheckPhoto(BaseModel):
    token: str
    detections: list[Det] = []


class SaveCheck(BaseModel):
    tank_id: str
    sampled_at: datetime | None = None
    photos: list[CheckPhoto] = []
    sample: Sample = Sample()
    water: Water = Water()
    notes: str | None = None
    live_est: float | None = Field(default=None, gt=0)


@router.post("/checks", status_code=201)
def create_check(body: SaveCheck, session: Session = Depends(get_session)) -> dict:
    try:
        return check_service.save_check(
            session,
            tank_id=body.tank_id,
            sampled_at=body.sampled_at,
            photos=[p.model_dump() for p in body.photos],
            sample=body.sample.model_dump(),
            water=body.water.model_dump(),
            notes=body.notes,
            live_est=body.live_est,
        )
    except check_service.CheckError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/checks")
def list_checks(
    tank: str | None = Query(default=None),
    room: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    world = load_world(session)
    statement = select(models.Check).order_by(models.Check.sampled_at.desc(), models.Check.id.desc())
    if tank:
        statement = statement.where(models.Check.tank_id == tank)
    if room:
        tank_ids = [s.id for s in world.tanks.values() if s.tank.room_id == room]
        statement = statement.where(models.Check.tank_id.in_(tank_ids))
    rows = list(session.exec(statement))
    batches = {b.id: b for b in session.exec(select(models.Batch))}
    counts: dict[int, int] = {}
    for photo in session.exec(select(models.Photo)):
        counts[photo.check_id] = counts.get(photo.check_id, 0) + 1
    views = []
    for check in rows:
        view = check_row(check, batches.get(check.batch_id), world, counts.get(check.id, 0))
        state = world.tanks.get(check.tank_id)
        view["room_id"] = state.tank.room_id if state else None
        view["room_name"] = state.room.name if state else None
        views.append(view)
    return {"checks": views}


def build_check_detail(check: models.Check, session: Session) -> dict:
    world = load_world(session)
    settings = world.cfg
    batch = session.get(models.Batch, check.batch_id)
    state = world.tanks.get(check.tank_id)
    photos = photos_of_check(check.id, session)
    row = check_row(check, batch, world, len(photos))

    # The risk snapshot as it stood at this check: replay using nothing after it
    series_rows = list(session.exec(
        select(models.Check).where(models.Check.batch_id == batch.id).order_by(models.Check.sampled_at, models.Check.id)
    ))
    series = [check_data(c) for c in series_rows]
    index = next(i for i, c in enumerate(series_rows) if c.id == check.id)
    kind = state.kind if state else "larval"
    replay = assess(series, batch_data(batch), kind, settings, upto=index)

    previous = series_rows[index - 1] if index > 0 else None
    return row | {
        "room_name": state.room.name if state else None,
        "line_id": state.line_id if state else None,
        "line_name": state.line.name if state and state.line else None,
        "stocked": batch.stocked,
        "stocked_text": fmt_count(batch.stocked),
        "bucket_l": check.bucket_l,
        "concentration": check.concentration,
        "photo_volume_ml": check.photo_volume_ml,
        "water": {
            "temp_c": check.temp_c, "salinity_ppt": check.salinity_ppt, "ph": check.ph,
            "omega_arag": check.omega_arag, "do_mgl": check.do_mgl,
        },
        "notes": check.notes,
        "created_by": check.created_by,
        "engine_version": check.engine_version,
        "rules_version": check.rules_version,
        "summary": {
            "n_live": check.n_live, "n_abnormal": check.n_abnormal, "n_dead": check.n_dead, "n_unsure": check.n_unsure,
            "n_ignored": sum(
                1 for p in photos
                for d in session.exec(select(models.Detection).where(models.Detection.photo_id == p.id))
                if d.larva_cls == "ignore"
            ),
            "pct_dead": check.pct_dead or 0, "pct_abnormal": check.pct_abnormal or 0,
            "mean_len_um": check.mean_len_um, "sd_len_um": check.sd_len_um, "cv": check.cv, "hist": check.hist,
            "stage": check.stage, "gut": check.gut, "count_for_estimate": 0,
        },
        "previous_hist": previous.hist if previous else None,
        "previous": {
            "pct_dead": previous.pct_dead, "pct_abnormal": previous.pct_abnormal, "mean_len_um": previous.mean_len_um,
            "cv": previous.cv, "gut": previous.gut,
            "days_ago": round((check.sampled_at - previous.sampled_at).total_seconds() / 86400.0, 2),
        } if previous else None,
        "snapshot": {
            "level": check.level or "ok",
            "level_label": LEVEL_LABEL.get(check.level or "ok", "Normal"),
            "pattern": check.pattern,
            "title": title_for(replay),
            "forecast": FORECAST.get(check.level or "ok", ""),
            "condition": condition_rows(replay, settings),
            "growth_um_day": check.growth_um_day,
            "loss_per_day": check.loss_per_day,
            "survival": check.survival,
        },
        "photos": [photo_view(p, session) for p in photos],
        "created_text": fmt_when(check.sampled_at, world.now),
    }


@router.get("/checks/{check_id}")
def get_check(check_id: int, session: Session = Depends(get_session)) -> dict:
    check = session.get(models.Check, check_id)
    if check is None:
        raise HTTPException(404, "No such check")
    return build_check_detail(check, session)


class DetectionsPatch(BaseModel):
    detections: list[Det]


@router.patch("/checks/{check_id}/photos/{photo_id}/detections")
def patch_detections(check_id: int, photo_id: int, body: DetectionsPatch, session: Session = Depends(get_session)) -> dict:
    check = session.get(models.Check, check_id)
    photo = session.get(models.Photo, photo_id)
    if check is None or photo is None or photo.check_id != check.id:
        raise HTTPException(404, "No such photo on that check")
    check_service.update_detections(session, check, photo, body.detections)
    fresh = session.get(models.Check, check_id)
    return build_check_detail(fresh, session)
