"""Engine acceptance tests against the synthetic slides with known answers (SPEC §13)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.analysis.engine import analyze
from app.analysis.models import Detection
from app.analysis.summary import summarize
from app.config import FIXTURES_DIR

SLIDES = sorted((FIXTURES_DIR / "slides").glob("*.jpg")) + sorted((FIXTURES_DIR / "demo").glob("*.jpg"))
GRID_SPACING_PX = 625.0


def _contains(det: Detection, x: float, y: float) -> bool:
    contour = np.array(det.contour, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0


def _load(path: Path):
    truth = json.loads(path.with_suffix(".json").read_text())
    return cv2.imread(str(path)), truth


def _evaluate(path: Path) -> dict:
    image, truth = _load(path)
    result = analyze(image)
    counted = [d for d in result.detections if d.cls != "ignore"]
    summary = summarize(result.detections, result.um_per_px)

    hit = {}  # truth id -> detection
    for item in truth["truth"]:
        for det in result.detections:
            if _contains(det, item["x"], item["y"]):
                hit[item["id"]] = det
                break

    def score(name: str) -> tuple[int, int, int]:
        """True positives, false positives and false negatives for one class."""
        wanted = {t["id"] for t in truth["truth"] if t["cls"] == name}
        tp = sum(1 for i in wanted if i in hit and hit[i].cls == name)
        fn = len(wanted) - tp
        fp = 0
        for det in counted:
            if det.cls != name:
                continue
            inside = [t for t in truth["truth"] if _contains(det, t["x"], t["y"])]
            if not any(t["cls"] == name for t in inside):
                fp += 1
        return tp, fp, fn

    errors = []
    for item in truth["truth"]:
        det = hit.get(item["id"])
        if item["clump"] is not None or det is None or det.touches_edge or det.clump_n > 1 or det.length_um is None:
            continue
        if det.cls == "ignore":
            continue
        errors.append(abs(det.length_um - item["len_um"]))

    total = summary.n_live + summary.n_abnormal + summary.n_dead
    return {
        "name": path.stem,
        "truth_n": len(truth["truth"]),
        "count": total,
        "count_err_pct": 100.0 * (total - len(truth["truth"])) / len(truth["truth"]),
        "dead": score("dead"),
        "abnormal": score("abnormal"),
        "len_abs_errors": errors,
        "len_mae": float(np.mean(errors)) if errors else None,
        "grid_truth": truth["grid"] is not None,
        "grid_spacing_px": result.grid_spacing_px,
        "ms": result.ms,
        "n_unsure": summary.n_unsure,
    }


def _pr(tp: int, fp: int, fn: int) -> tuple[float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return precision, recall


@pytest.fixture(scope="module")
def results() -> list[dict]:
    rows = [_evaluate(path) for path in SLIDES]
    print("\n\nslide                    truth  count  err%   dead P/R     abn P/R     MAE µm   grid px     ms  unsure")
    for r in rows:
        dp, dr = _pr(*r["dead"])
        ap, ar = _pr(*r["abnormal"])
        mae = f"{r['len_mae']:.2f}" if r["len_mae"] is not None else "-"
        grid = f"{r['grid_spacing_px']:.1f}" if r["grid_spacing_px"] else "-"
        print(f"{r['name']:<24} {r['truth_n']:>5} {r['count']:>6} {r['count_err_pct']:>5.1f}  "
              f"{dp:.2f}/{dr:.2f}  {ap:.2f}/{ar:.2f}  {mae:>6}  {grid:>7} {r['ms']:>6} {r['n_unsure']:>6}")
    dead = np.sum([r["dead"] for r in rows], axis=0)
    abnormal = np.sum([r["abnormal"] for r in rows], axis=0)
    errors = [e for r in rows for e in r["len_abs_errors"]]
    print(f"pooled dead P/R {_pr(*dead)[0]:.3f}/{_pr(*dead)[1]:.3f}  "
          f"abnormal P/R {_pr(*abnormal)[0]:.3f}/{_pr(*abnormal)[1]:.3f}  "
          f"length MAE {np.mean(errors):.2f} µm over {len(errors)} larvae\n")
    return rows


def test_there_are_six_slides():
    assert len(SLIDES) == 6


def test_total_count_within_5_percent(results):
    for r in results:
        assert abs(r["count_err_pct"]) <= 5.0, f"{r['name']}: {r['count']} vs {r['truth_n']}"


def test_dead_precision_and_recall(results):
    precision, recall = _pr(*np.sum([r["dead"] for r in results], axis=0))
    assert precision >= 0.9
    assert recall >= 0.9


def test_abnormal_precision_and_recall(results):
    precision, recall = _pr(*np.sum([r["abnormal"] for r in results], axis=0))
    assert precision >= 0.75
    assert recall >= 0.75


def test_length_mae(results):
    errors = [e for r in results for e in r["len_abs_errors"]]
    assert np.mean(errors) <= 4.0


def test_grid_spacing(results):
    for r in results:
        if r["grid_truth"]:
            assert r["grid_spacing_px"] is not None, r["name"]
            assert abs(r["grid_spacing_px"] - GRID_SPACING_PX) / GRID_SPACING_PX <= 0.01, r["name"]
        else:
            assert r["grid_spacing_px"] is None, r["name"]


def test_speed(results):
    for r in results:
        assert r["ms"] <= 1000, f"{r['name']}: {r['ms']} ms"


def test_photo_volume_at_known_scale():
    from app.analysis.calibrate import photo_volume_ml

    assert photo_volume_ml(1600, 1200, 1.6) == pytest.approx(0.0049152)
    assert photo_volume_ml(1600, 1200, None) is None


def test_summary_rules():
    det = dict(cx=0, cy=0, contour=[(0, 0)], length_px=10, area_px=10)
    dets = [
        Detection(id=1, length_um=100.0, gut=0.5, cls="live", **det),
        Detection(id=2, length_um=120.0, gut=0.7, cls="live", **det),
        Detection(id=3, length_um=999.0, gut=0.9, cls="live", touches_edge=True, **det),
        Detection(id=4, length_um=140.0, gut=0.1, cls="abnormal", **det),
        Detection(id=5, length_um=120.0, cls="dead", unsure=True, **det),
        Detection(id=6, length_um=120.0, cls="ignore", **det),
        Detection(id=7, length_um=150.0, cls="live", clump_n=3, unsure=True, **det),
    ]
    s = summarize(dets, 1.6)
    assert (s.n_live, s.n_abnormal, s.n_dead, s.n_unsure, s.n_ignored) == (6, 1, 1, 2, 1)
    assert s.pct_dead == pytest.approx(12.5)
    assert s.pct_abnormal == pytest.approx(12.5)
    assert s.mean_len_um == pytest.approx(120.0)  # singles only, no edge objects
    assert s.sd_len_um == pytest.approx(20.0)
    assert s.cv == pytest.approx(20.0 / 120.0, abs=1e-3)
    assert s.gut == pytest.approx(0.7)  # every live single, edge ones included (SPEC §5.3)
    assert s.count_for_estimate == pytest.approx(2 + 0.5 + 1 + 3)
    assert s.stage == "Early umbo"
    assert sum(s.hist) == 3


def test_uncalibrated_summary_has_no_sizes():
    det = dict(cx=0, cy=0, contour=[(0, 0)], length_px=10, area_px=10)
    s = summarize([Detection(id=1, cls="live", gut=0.4, **det)], None)
    assert s.mean_len_um is None and s.hist is None and s.stage is None and s.gut == pytest.approx(0.4)
