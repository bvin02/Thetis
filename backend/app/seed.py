"""Load the example hatchery (SPEC §12). Every row is flagged is_example; the UI labels it.

  python -m app.seed --reset          demo state: T-03 starts at Watch
  python -m app.seed --reset --full   the designed Floor's state: T-03 already Critical

Rules: photos come from tools/gen_slides.make_slide and are cached; each check's stats come from
`summarize` over the truth file's detections; each check keeps the file's live_est; decisions are
exactly the file's list; each check's risk snapshot comes from replaying `assess` in time order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time as clock
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, time, timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlmodel import Session, delete

from app import config, db, models
from app.analysis.models import Detection as Det
from app.analysis.summary import summarize
from app.rules.assess import assess
from app.services.world import batch_data, check_data, settings_for


def _relative(today: date, day: int, hhmm: str) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime.combine(today + timedelta(days=day), time(int(hour), int(minute)))


def _photo_key(check: dict) -> str:
    params = {
        "photo": check["photo"], "counts": check["counts"], "mean_len_um": check["mean_len_um"],
        "sd_len_um": check["sd_len_um"], "gut": check["gut"],
    }
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:20]


def _render_one(job: tuple[str, str, dict]) -> str:
    """Render one seed photo into the cache. Runs in a worker process."""
    key, cache, check = job
    sys.path.insert(0, str(config.TOOLS_DIR))
    from gen_slides import make_slide  # noqa: PLC0415

    photo = check["photo"]
    arguments = dict(
        stage=photo["stage"], grid=photo["grid"], clumps=photo["clumps"], counts=check["counts"],
        mean_len_um=check["mean_len_um"], sd_len_um=check["sd_len_um"], gut=check["gut"],
    )
    try:
        make_slide(key, cache, seed=photo["seed"], **arguments)
    except RuntimeError:  # "no room" under a different numpy: documented retry
        make_slide(key, cache, seed=photo["seed"] + 1000, **arguments)
    return key


def _ensure_photos(checks: list[dict]) -> Path:
    """Make sure every seed photo is in the cache, rendering the missing ones in parallel."""
    cache = config.seed_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    missing: dict[str, dict] = {}
    for check in checks:
        key = _photo_key(check)
        if not (cache / f"{key}.jpg").exists() or not (cache / f"{key}.json").exists():
            missing[key] = check
    if missing:
        started = clock.perf_counter()
        print(f"Rendering {len(missing)} example photos (first run only)...", flush=True)
        jobs = [(key, str(cache), check) for key, check in missing.items()]
        with ProcessPoolExecutor(max_workers=6) as pool:
            for _ in pool.map(_render_one, jobs):
                pass
        print(f"Rendered in {clock.perf_counter() - started:.1f} s", flush=True)
    return cache


def _detections_from_truth(truth: dict) -> list[Det]:
    """Seeded detections come from the truth file, with source = auto."""
    um_per_px = truth["um_per_px"]
    dets = []
    for number, item in enumerate(truth["truth"], start=1):
        contour = [(float(x), float(y)) for x, y in item["poly"]]
        area = float(cv2.contourArea(np.array(contour, dtype=np.float32).reshape(-1, 1, 2)))
        dets.append(
            Det(
                id=number, cx=item["x"], cy=item["y"], contour=contour,
                length_px=round(item["len_um"] / um_per_px, 2), length_um=item["len_um"], area_px=round(area, 1),
                gut=item["gut"], interior=0.0, hollowness=0.3 if item["cls"] == "dead" else 1.5,
                cls=item["cls"], auto_cls=item["cls"], clump_n=1, touches_edge=False, source="auto",
            )
        )
    return dets


def _clear_everything() -> None:
    db.init_db()
    db.drop_hatchery_tables()
    db.init_db()
    for folder in (config.photos_dir(), config.uploads_dir()):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)


def run_seed(full: bool = False, reset: bool = True, today: date | None = None) -> dict:
    """Load the seed file. Returns a small report."""
    source = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))
    today = today or date.today()

    if reset:
        _clear_everything()
    else:
        db.init_db()

    def wanted(row: dict) -> bool:
        return full or not row.get("demo_live")

    all_checks = [c for b in source["batches"] for c in b["checks"] if wanted(c)]
    cache = _ensure_photos(all_checks)

    with Session(db.get_engine()) as session:
        if not reset:
            session.exec(delete(models.Hatchery))
        hatchery = models.Hatchery(
            id=1, name=source["hatchery"]["name"], species=source["hatchery"]["species"],
            user_name=source["user"]["name"], user_initials=source["user"]["initials"],
            user_role=source["user"]["role"], settings=source["settings"], is_example=True,
        )
        session.add(hatchery)
        for room in source["plan"]["rooms"]:
            session.add(models.Room(id=room["id"], name=room["name"], kind=room["kind"], label_xy=room["label_xy"],
                                    caption=room["caption"]))
        for line in source["plan"]["lines"]:
            session.add(models.Line(id=line["id"], name=line["name"], card_xy=line["card_xy"]))
        session.flush()

        active_tanks = {b["tank"] for b in source["batches"] if b["status"] == "active"}
        for tank in source["tanks"]:
            geom = {"cx": tank["cx"], "cy": tank["cy"], "r": tank["r"]} if tank["shape"] == "circle" else {
                "x": tank["x"], "y": tank["y"], "w": tank["w"], "h": tank["h"]}
            status = tank.get("status") or ("active" if tank["id"] in active_tanks else "empty")
            session.add(models.Tank(id=tank["id"], room_id=tank["room"], line_id=tank["line"], shape=tank["shape"],
                                    geom=geom, volume_l=tank["volume_l"], status=status, is_example=True))
        session.flush()

        cfg = settings_for(hatchery)
        kinds = {r["id"]: r["kind"] for r in source["plan"]["rooms"]}
        tank_room = {t["id"]: t["room"] for t in source["tanks"]}
        latest_by_tank: dict[str, list[models.Check]] = {}

        for spec in source["batches"]:
            batch = models.Batch(
                code=spec["code"], tank_id=spec["tank"], species=spec["species"],
                spawn_date=today + timedelta(days=spec["spawn_day"]), stocked=spec["stocked"], status=spec["status"],
                outcome=spec.get("outcome"),
                closed_on=today + timedelta(days=spec["closed_day"]) if spec.get("closed_day") is not None else None,
                is_example=True,
            )
            session.add(batch)
            session.flush()
            tank_kind = kinds[tank_room[spec["tank"]]]

            rows: list[models.Check] = []
            for item in sorted((c for c in spec["checks"] if wanted(c)), key=lambda c: (c["day"], c["time"])):
                truth = json.loads((cache / f"{_photo_key(item)}.json").read_text())
                dets = _detections_from_truth(truth)
                summary = summarize(dets, truth["um_per_px"], cfg)
                water = item.get("water", {})
                sample = item.get("sample", {})
                row = models.Check(
                    batch_id=batch.id, tank_id=spec["tank"], sampled_at=_relative(today, item["day"], item["time"]),
                    source="photo", n_live=summary.n_live, n_abnormal=summary.n_abnormal, n_dead=summary.n_dead,
                    n_unsure=summary.n_unsure, pct_dead=summary.pct_dead, pct_abnormal=summary.pct_abnormal,
                    mean_len_um=summary.mean_len_um, sd_len_um=summary.sd_len_um, cv=summary.cv,
                    gut=summary.gut, stage=summary.stage, hist=summary.hist,
                    live_est=float(item["live_est"]),  # stands for a full count: never recomputed from the photo
                    bucket_l=sample.get("bucket_l"), concentration=sample.get("concentration"),
                    photo_volume_ml=truth["photo_volume_ml"],
                    temp_c=water.get("temp_c"), salinity_ppt=water.get("salinity_ppt"), ph=water.get("ph"),
                    omega_arag=water.get("omega_arag"), do_mgl=water.get("do_mgl"),
                    engine_version="seed", rules_version=config.RULES_VERSION,
                    created_by=source["user"]["name"], is_example=True,
                )
                session.add(row)
                session.flush()
                rows.append(row)

                photo = models.Photo(
                    check_id=row.id, width=truth["w"], height=truth["h"], um_per_px=truth["um_per_px"],
                    calibration="grid" if truth["grid"] else "none",
                    grid_spacing_px=truth["grid"]["spacing_px"] if truth["grid"] else None,
                    volume_ml=truth["photo_volume_ml"], engine_version="seed", synthetic=True,
                    source_name=f"example-{item['photo']['seed']}",
                )
                session.add(photo)
                session.flush()
                folder = config.photos_dir() / str(row.id)
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / f"{photo.id}.jpg"
                shutil.copyfile(cache / f"{_photo_key(item)}.jpg", target)
                photo.path = str(target.relative_to(config.data_dir()))
                session.add(photo)
                for det in dets:
                    session.add(
                        models.Detection(
                            photo_id=photo.id, number=det.id, cx=det.cx, cy=det.cy,
                            contour=[list(point) for point in det.contour], length_px=det.length_px,
                            length_um=det.length_um, area_px=det.area_px, solidity=det.solidity, defect=det.defect,
                            hollowness=det.hollowness, gut=det.gut, interior=det.interior, larva_cls=det.cls,
                            auto_cls=det.auto_cls, unsure=False, clump_n=1, touches_edge=False, source="auto",
                        )
                    )

            # Each check's risk snapshot comes from replaying assess in time order
            series = [check_data(r) for r in rows]
            for index, row in enumerate(rows):
                result = assess(series, batch_data(batch), tank_kind, cfg, upto=index)
                row.level, row.pattern = result.level, result.pattern
                row.signals = [s.to_json() for s in result.signals]
                row.growth_um_day, row.loss_per_day = result.growth_um_day, result.loss_per_day
                row.survival = result.survival
                session.add(row)
            if spec["status"] == "active":
                latest_by_tank[spec["tank"]] = rows
        session.flush()

        # Decisions: exactly the file's list, never the save flow
        n_decisions = 0
        for item in source["decisions"]:
            if not wanted(item):
                continue
            created = _relative(today, item["created"]["day"], item["created"]["time"])
            check_id = None
            if item["scope"] == "tank":
                candidates = [c for c in latest_by_tank.get(item["target"], []) if c.sampled_at <= created]
                check_id = candidates[-1].id if candidates else None
            decided = item.get("decided")
            session.add(
                models.Decision(
                    scope=item["scope"],
                    tank_id=item["target"] if item["scope"] == "tank" else None,
                    line_id=item["target"] if item["scope"] == "line" else None,
                    check_id=check_id, action=item["action"], status=item["status"], created_at=created,
                    decided_at=_relative(today, decided["day"], decided["time"]) if decided else None,
                    decided_by=item.get("decided_by"), note=item.get("note"), is_example=True,
                )
            )
            n_decisions += 1
        session.commit()
    return {"mode": "full" if full else "demo", "checks": len(all_checks), "decisions": n_decisions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete all rows and saved photos first")
    parser.add_argument("--full", action="store_true", help="load the demo-live rows too (T-03 already Critical)")
    args = parser.parse_args()
    if not args.reset and config.db_path().exists():
        parser.error(f"{config.db_path()} already exists. Use --reset to replace it.")
    started = clock.perf_counter()
    report = run_seed(full=args.full, reset=True)
    print(f"Seeded {report['mode']} state: {report['checks']} checks, {report['decisions']} decisions "
          f"in {clock.perf_counter() - started:.1f} s.")


if __name__ == "__main__":
    main()
