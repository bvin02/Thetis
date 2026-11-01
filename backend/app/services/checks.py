"""The save flow: turn reviewed photos into a check, assess it, and create decisions (SPEC §7.7)."""
from __future__ import annotations

import shutil
from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlmodel import Session, select

from app import config, models
from app.analysis.models import Detection as Det
from app.analysis.summary import estimate_live, summarize
from app.rules.assess import LEVEL_LABEL, assess
from app.services import decisions as decision_service
from app.services import uploads
from app.services.world import TankState, batch_data, check_data, load_world, settings_for


class CheckError(ValueError):
    """Something about a save request the user can fix. Becomes a 4xx with this message."""


def _stocked_estimate(live_est: float | None, stocked: int | None, cfg: dict) -> dict:
    """The "Estimate for the tank" block, as numbers the UI can show."""
    survival = live_est / stocked if live_est is not None and stocked else None
    over = bool(live_est is not None and stocked and live_est > cfg["overstock_warning_ratio"] * stocked)
    return {"live_est": live_est, "survival": survival, "stocked": stocked, "over_stocked": over}


def compute_estimate(dets: Sequence[Det], volume_ml: float | None, sample: dict, stocked: int | None, cfg: dict) -> dict:
    summary = summarize(dets, 1.0 if any(d.length_um is not None for d in dets) else None, cfg)
    bucket_l = float(sample.get("bucket_l") or cfg["bucket_l"])
    concentration = float(sample.get("concentration") or cfg["concentration"])
    live_est = estimate_live(summary.count_for_estimate, volume_ml, bucket_l, concentration)
    return {"summary": summary.model_dump(), "estimate": _stocked_estimate(live_est, stocked, cfg)}


def _detection_row(photo_id: int, det: Det) -> models.Detection:
    return models.Detection(
        photo_id=photo_id,
        number=det.id,
        cx=det.cx,
        cy=det.cy,
        contour=[list(point) for point in det.contour],
        length_px=det.length_px,
        length_um=det.length_um,
        area_px=det.area_px,
        solidity=det.solidity,
        defect=det.defect,
        hollowness=det.hollowness,
        gut=det.gut,
        interior=det.interior,
        larva_cls=det.cls,
        auto_cls=det.auto_cls,
        unsure=det.unsure,
        unsure_reason=det.unsure_reason,
        clump_n=det.clump_n,
        touches_edge=det.touches_edge,
        source=det.source,
        claude=det.claude,
    )


def det_from_row(row: models.Detection) -> Det:
    return Det(
        id=row.number, cx=row.cx, cy=row.cy, contour=[tuple(point) for point in row.contour or []],
        length_px=row.length_px, length_um=row.length_um, area_px=row.area_px, solidity=row.solidity,
        defect=row.defect, hollowness=row.hollowness, gut=row.gut, interior=row.interior, cls=row.larva_cls,
        auto_cls=row.auto_cls, unsure=row.unsure, unsure_reason=row.unsure_reason, clump_n=row.clump_n,
        touches_edge=row.touches_edge, source=row.source, claude=row.claude,
    )


def _apply_summary(check: models.Check, dets: Iterable[Det], um_per_px: float | None, cfg: dict) -> float:
    """Copy counts and sizes onto the check. Returns count_for_estimate."""
    summary = summarize(list(dets), um_per_px, cfg)
    check.n_live = summary.n_live
    check.n_abnormal = summary.n_abnormal
    check.n_dead = summary.n_dead
    check.n_unsure = summary.n_unsure
    counted = summary.n_live + summary.n_abnormal + summary.n_dead
    check.pct_dead = summary.pct_dead if counted else None
    check.pct_abnormal = summary.pct_abnormal if counted else None
    check.mean_len_um = summary.mean_len_um
    check.sd_len_um = summary.sd_len_um
    check.cv = summary.cv
    check.gut = summary.gut
    check.stage = summary.stage
    check.hist = summary.hist
    return summary.count_for_estimate


def reassess_batch(session: Session, batch: models.Batch, tank_kind: str, cfg: dict, from_time: datetime | None = None) -> None:
    """Refresh the risk snapshot of the batch's checks at or after `from_time`. Earlier ones stay as they were."""
    checks = list(session.exec(
        select(models.Check).where(models.Check.batch_id == batch.id).order_by(models.Check.sampled_at, models.Check.id)
    ))
    series = [check_data(c) for c in checks]
    for index, check in enumerate(checks):
        if from_time is not None and check.sampled_at < from_time:
            continue
        result = assess(series, batch_data(batch), tank_kind, cfg, upto=index)
        check.level = result.level
        check.pattern = result.pattern
        check.signals = [s.to_json() for s in result.signals]
        check.growth_um_day = result.growth_um_day
        check.loss_per_day = result.loss_per_day
        check.survival = result.survival
        check.rules_version = result.rules_version
        session.add(check)
    session.flush()


def _save_message(state: TankState, world_decisions: Iterable[models.Decision]) -> str:
    waiting = sum(1 for d in world_decisions if d.status == "pending" and decision_service.touches_tank(d, state))
    text = f"Check saved. {state.id} is now {LEVEL_LABEL[state.level]}."
    if waiting == 1:
        text += " 1 decision waiting."
    elif waiting > 1:
        text += f" {waiting} decisions waiting."
    return text


def _result(check: models.Check, state: TankState, created: list[models.Decision], all_rows: Iterable[models.Decision],
            duplicate: bool = False) -> dict:
    return {
        "check_id": check.id,
        "tank_id": check.tank_id,
        "level": state.level,
        "pattern": state.assessment.pattern if state.assessment else None,
        "new_decisions": [
            {"id": d.id, "action": d.action, "scope": d.scope, "tank_id": d.tank_id, "line_id": d.line_id} for d in created
        ],
        "message": _save_message(state, all_rows),
        "duplicate": duplicate,
    }


def save_check(session: Session, *, tank_id: str, sampled_at: datetime | None, photos: list[dict], sample: dict,
               water: dict, notes: str | None, live_est: float | None = None) -> dict:
    """Save one check. `photos` holds {token, detections}; with none, `live_est` makes a manual check."""
    tank = session.get(models.Tank, tank_id)
    if tank is None:
        raise CheckError(f"No tank called {tank_id}.")
    batch = session.exec(
        select(models.Batch).where(models.Batch.tank_id == tank_id, models.Batch.status == "active")
    ).first()
    if batch is None:
        raise CheckError(f"{tank_id} has no active batch. Start one first.")
    if not photos and live_est is None:
        raise CheckError("A check needs a reviewed photo.")

    hatchery = session.get(models.Hatchery, 1)
    cfg = settings_for(hatchery)
    room = session.get(models.Room, tank.room_id)
    now = datetime.now()
    when = sampled_at or now
    if when > now.replace(microsecond=0) and (when - now).total_seconds() > 300:
        raise CheckError("Sampled at can't be in the future.")
    if when.date() < batch.spawn_date:
        raise CheckError(f"Sampled at is before batch {batch.code} was spawned.")

    tokens = [str(p.get("token") or "") for p in photos]
    if tokens:
        already = session.exec(select(models.Photo).where(models.Photo.upload_token.in_(tokens))).first()
        if already is not None:
            # The same upload was saved already, for example by a double click: never make a second check
            check = session.get(models.Check, already.check_id)
            world = load_world(session)
            return _result(check, world.tanks[check.tank_id], [], decision_service.all_decisions(session), duplicate=True)

    metas = []
    for token in tokens:
        meta = uploads.read_meta(token)
        if meta is None:
            raise CheckError("That photo has expired. Upload it again.")
        metas.append(meta)

    all_dets: list[Det] = []
    photo_dets: list[list[Det]] = []
    for item in photos:
        dets = [d if isinstance(d, Det) else Det.model_validate(d) for d in item.get("detections", [])]
        photo_dets.append(dets)
        all_dets.extend(dets)

    bucket_l = float(sample.get("bucket_l") or cfg["bucket_l"])
    concentration = float(sample.get("concentration") or cfg["concentration"])
    total_volume = None
    um_per_px_any = None
    for meta in metas:
        if meta.get("photo_volume_ml"):
            total_volume = (total_volume or 0.0) + float(meta["photo_volume_ml"])
        if meta.get("um_per_px"):
            um_per_px_any = float(meta["um_per_px"])

    check = models.Check(
        batch_id=batch.id,
        tank_id=tank_id,
        sampled_at=when,
        source="photo" if photos else "manual",
        bucket_l=bucket_l,
        concentration=concentration,
        photo_volume_ml=total_volume,
        temp_c=water.get("temp_c"),
        salinity_ppt=water.get("salinity_ppt"),
        ph=water.get("ph"),
        omega_arag=water.get("omega_arag"),
        do_mgl=water.get("do_mgl"),
        notes=(notes or "").strip() or None,
        engine_version=config.ENGINE_VERSION if photos else None,
        created_by=hatchery.user_name if hatchery else None,
        is_example=False,
    )
    if photos:
        count = _apply_summary(check, all_dets, um_per_px_any, cfg)
        check.live_est = estimate_live(count, total_volume, bucket_l, concentration)
    else:
        check.live_est = live_est
    session.add(check)
    session.flush()

    for meta, dets, token in zip(metas, photo_dets, tokens, strict=True):
        photo = models.Photo(
            check_id=check.id,
            width=meta["width"],
            height=meta["height"],
            um_per_px=meta.get("um_per_px"),
            calibration=meta.get("calibration") or "none",
            grid_spacing_px=meta.get("grid_spacing_px"),
            volume_ml=meta.get("photo_volume_ml"),
            engine_version=config.ENGINE_VERSION,
            synthetic=bool(meta.get("synthetic")),
            source_name=meta.get("source_name"),
            upload_token=token,
        )
        session.add(photo)
        session.flush()
        folder = config.photos_dir() / str(check.id)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{photo.id}.jpg"
        shutil.move(str(uploads.image_path(token)), target)
        photo.path = str(target.relative_to(config.data_dir()))
        session.add(photo)
        for det in dets:
            session.add(_detection_row(photo.id, det))
    session.flush()

    reassess_batch(session, batch, room.kind if room else "larval", cfg, from_time=when)
    session.flush()

    # Rules first, line alerts next, then every decision that isn't already pending
    session.expire_all()
    world = load_world(session)
    state = world.tanks[tank_id]
    created = decision_service.create_missing(session, state, world, check.id, now=now)
    session.commit()
    session.refresh(check)
    for decision in created:
        session.refresh(decision)
    for token in tokens:
        (config.uploads_dir() / f"{token}.json").unlink(missing_ok=True)
    return _result(check, state, created, decision_service.all_decisions(session))


def update_detections(session: Session, check: models.Check, photo: models.Photo, dets: list[Det]) -> None:
    """Save corrections on a saved photo, then recompute the summary and re-assess forward (SPEC §10)."""
    hatchery = session.get(models.Hatchery, 1)
    cfg = settings_for(hatchery)
    for row in session.exec(select(models.Detection).where(models.Detection.photo_id == photo.id)):
        session.delete(row)
    session.flush()
    for det in dets:
        session.add(_detection_row(photo.id, det))
    session.flush()

    all_photos = list(session.exec(select(models.Photo).where(models.Photo.check_id == check.id)))
    every: list[Det] = []
    for each in all_photos:
        rows = session.exec(select(models.Detection).where(models.Detection.photo_id == each.id))
        every.extend(det_from_row(row) for row in rows)

    old_count = (check.n_live or 0) + (check.n_abnormal or 0)
    um_per_px = next((p.um_per_px for p in all_photos if p.um_per_px), None)
    new_count = _apply_summary(check, every, um_per_px, cfg)
    if check.live_est is not None and old_count > 0:
        # Scale, so a seeded check (whose estimate stands for a full count) keeps its meaning
        check.live_est = check.live_est * new_count / old_count
    elif check.bucket_l and check.concentration:
        check.live_est = estimate_live(new_count, check.photo_volume_ml, check.bucket_l, check.concentration)
    session.add(check)
    session.flush()

    batch = session.get(models.Batch, check.batch_id)
    tank = session.get(models.Tank, check.tank_id)
    room = session.get(models.Room, tank.room_id) if tank else None
    reassess_batch(session, batch, room.kind if room else "larval", cfg, from_time=check.sampled_at)
    session.flush()
    session.expire_all()

    world = load_world(session)
    state = world.tanks.get(check.tank_id)
    if state is not None and state.batch is not None and state.batch.id == check.batch_id:
        decision_service.create_missing(session, state, world, state.latest.id if state.latest else check.id)
    session.commit()
