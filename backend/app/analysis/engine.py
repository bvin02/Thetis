"""Find, measure and classify every larva in a microscope photo (SPEC §5.2). Pure functions.

`analyze()` is the seam for a future trained segmenter: anything that returns the same
`Detection` list can replace the classical pipeline.
"""
from __future__ import annotations

import math
import time

import cv2
import numpy as np

from app.analysis import calibrate
from app.analysis.models import AnalysisResult, Calibration, Cls, Detection
from app.config import DEFAULT_ENGINE, ENGINE_VERSION, EngineParams


def _odd(value: float, minimum: int = 3) -> int:
    k = max(minimum, int(round(value)))
    return k if k % 2 == 1 else k + 1


def _ellipse(k: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def _to_gray(img_bgr: np.ndarray, p: EngineParams) -> np.ndarray:
    b, g, r = cv2.split(img_bgr.astype(np.float32))
    return p.gray_r * r + p.gray_g * g + p.gray_b * b


def _background(gray: np.ndarray, p: EngineParams) -> np.ndarray:
    """Closing on a small copy erases dark objects up to about a fifth of the image."""
    h, w = gray.shape
    f = p.bg_downsample
    small = cv2.resize(gray, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_AREA)
    k = _odd(p.bg_kernel_frac * max(h, w) / f)
    closed = cv2.morphologyEx(small, cv2.MORPH_CLOSE, _ellipse(k), borderType=cv2.BORDER_REFLECT)
    blurred = cv2.GaussianBlur(closed, (0, 0), k / p.bg_sigma_div, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(blurred, (w, h), interpolation=cv2.INTER_LINEAR)


def _threshold(diff: np.ndarray, sigma: float, p: EngineParams) -> float:
    floor = p.thresh_sigma * sigma
    candidates = diff[diff > p.otsu_floor_sigma * sigma]
    if candidates.size < 16:
        return floor
    as_u8 = np.clip(candidates, 0, 255).astype(np.uint8).reshape(-1, 1)
    otsu, _ = cv2.threshold(as_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return max(floor, p.otsu_frac * float(otsu))


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """Holes are 4-connected background components that do not touch the border."""
    n, labels = cv2.connectedComponents((mask == 0).astype(np.uint8), connectivity=4)
    if n <= 1:
        return mask
    border = np.unique(np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]]))
    is_hole = np.ones(n, dtype=bool)
    is_hole[border] = False
    is_hole[0] = False
    out = mask.copy()
    out[is_hole[labels]] = 255
    return out


def _segment(diff: np.ndarray, sigma: float, p: EngineParams) -> np.ndarray:
    mask = np.where(diff > _threshold(diff, sigma, p), 255, 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=p.close_iters)
    mask = _fill_holes(mask)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=p.open_iters)


def _repair_open_rims(mask: np.ndarray, p: EngineParams) -> np.ndarray:
    """An empty shell whose rim broke (usually along a grid line) reads as a thin arc: fill its hull."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    large = areas[areas >= p.rim_min_area_px]
    if large.size == 0:
        return mask
    a_med = float(np.median(large))
    out = mask.copy()
    for label in range(1, n):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < p.min_component_px:
            continue
        x, y, w, h = stats[label, :4]
        roi = (labels[y : y + h, x : x + w] == label).astype(np.uint8)
        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            continue
        points = np.vstack(contours)
        hull = cv2.convexHull(points)
        hull_area = float(cv2.contourArea(hull))
        is_shell_sized = p.rim_hull_frac_of_median * a_med < hull_area <= p.rim_hull_max_frac_of_median * a_med
        if is_shell_sized and area / max(hull_area, 1.0) < p.rim_max_fill_ratio:
            cv2.fillConvexPoly(out, hull + np.array([x, y]), 255)
    return out


def _shape_metrics(obj_mask: np.ndarray, feret: float) -> tuple[float, float]:
    """Solidity and deepest convexity defect (relative to Feret) of a binary object."""
    contours, _ = cv2.findContours(obj_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return 1.0, 0.0
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    hull_points = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull_points))
    solidity = area / hull_area if hull_area > 0 else 1.0
    defect = 0.0
    if len(contour) >= 4:
        hull_idx = cv2.convexHull(contour, returnPoints=False)
        try:
            defects = cv2.convexityDefects(contour, hull_idx)
        except cv2.error:
            defects = None
        if defects is not None and len(defects):
            # OpenCV 5 returns N×4 instead of N×1×4
            deepest = float(defects.reshape(-1, 4)[:, 3].max()) / 256.0
            defect = deepest / max(feret, 1.0)
    return solidity, defect


def _simplify(contour: np.ndarray, p: EngineParams) -> np.ndarray:
    epsilon = p.contour_epsilon_px
    approx = cv2.approxPolyDP(contour, epsilon, True)
    while len(approx) > p.contour_max_points:
        epsilon *= 1.25
        approx = cv2.approxPolyDP(contour, epsilon, True)
    return approx.reshape(-1, 2)


def _measure(label_img: np.ndarray, stats_row: np.ndarray, label: int, d: np.ndarray, gray: np.ndarray,
             bright_level: float, p: EngineParams) -> dict | None:
    """All per-object features, in processing px."""
    x, y, w, h, _ = stats_row
    roi = (label_img[y : y + h, x : x + w] == label).astype(np.uint8)
    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = float(roi.sum())

    hull = cv2.convexHull(contour).reshape(-1, 2).astype(np.float32)
    if len(hull) >= 2:
        deltas = hull[:, None, :] - hull[None, :, :]
        feret_raw = float(np.sqrt((deltas**2).sum(axis=2)).max())
    else:
        feret_raw = 1.0
    feret = max(1.0, feret_raw + 1.0)
    length_px = max(1.0, feret - p.feret_edge_correction_px)

    if len(contour) >= 5:
        (_, (rw, rh), _) = cv2.minAreaRect(contour)
        aspect = max(rw, rh) / max(min(rw, rh), 1.0)
    else:
        aspect = 1.0

    # Shape on an opened mask: strips attached algae, debris spikes and grid residue
    k = _odd(p.opened_kernel_frac * feret)
    padded = cv2.copyMakeBorder(roi, k, k, k, k, cv2.BORDER_CONSTANT, value=0)
    opened = cv2.morphologyEx(padded, cv2.MORPH_OPEN, _ellipse(k))
    if opened.sum() > p.opened_keep_frac * area:
        solidity, defect = _shape_metrics(opened, feret)
    else:
        solidity, defect = _shape_metrics(padded, feret)

    # Hollowness, gut and interior darkness from the difference image
    dist = cv2.distanceTransform(roi, cv2.DIST_L2, 5)
    r_eq = math.sqrt(area / math.pi)
    d_roi = d[y : y + h, x : x + w]
    inner = d_roi[dist >= p.hollow_inner_frac * r_eq]
    ring = d_roi[(dist > 0) & (dist < p.hollow_ring_frac * r_eq)]
    core = d_roi[dist >= p.gut_core_frac * r_eq]
    if inner.size == 0:
        inner = d_roi[dist >= dist.max()] if dist.max() > 0 else d_roi[roi > 0]
    if ring.size == 0:
        ring = d_roi[roi > 0]
    if core.size == 0:
        core = inner

    ring_mean = float(ring.mean())
    hollowness = float(inner.mean()) / ring_mean if ring_mean > 1e-6 else 0.0
    ring_median = float(np.median(ring))
    if ring_median > 1e-6:
        gut = float(np.clip(p.gut_gain * (np.percentile(core, 95) - np.median(core)) / ring_median, 0.0, 1.0))
    else:
        gut = 0.0
    interior = float(np.median(inner))
    bright_frac = float((gray[y : y + h, x : x + w][roi > 0] > bright_level).mean())

    im_h, im_w = gray.shape
    touches = bool(x <= 0 or y <= 0 or x + w >= im_w or y + h >= im_h)
    moments = cv2.moments(roi, binaryImage=True)
    if moments["m00"] > 0:
        cx, cy = x + moments["m10"] / moments["m00"], y + moments["m01"] / moments["m00"]
    else:
        cx, cy = x + w / 2, y + h / 2

    return {
        "contour": _simplify(contour, p) + np.array([x, y]),
        "cx": float(cx),
        "cy": float(cy),
        "area": area,
        "length_px": length_px,
        "aspect": aspect,
        "solidity": solidity,
        "defect": defect,
        "hollowness": hollowness,
        "gut": gut,
        "interior": interior,
        "bright_frac": bright_frac,
        "touches": touches,
    }


def _is_bubble(obj: dict, sigma: float, p: EngineParams) -> bool:
    return obj["interior"] < -p.bubble_sigma * sigma or obj["bright_frac"] > p.bubble_bright_frac


def _reference_area(objects: list[dict], sigma: float, p: EngineParams) -> float | None:
    """Median area of round objects that could be larvae: the yardstick for clumps and debris."""
    areas = [
        o["area"] for o in objects
        if o["area"] >= p.ref_min_area_px and o["solidity"] >= p.ref_min_solidity
        and o["aspect"] <= p.ref_max_aspect and not _is_bubble(o, sigma, p)
    ]
    if not areas:
        return None
    floor = p.ref_min_frac_of_largest * max(areas)
    return float(np.median([a for a in areas if a >= floor]))


def _classify(obj: dict, a_ref: float | None, sigma: float, um_per_px_proc: float | None,
              p: EngineParams) -> tuple[Cls, bool, str | None, int]:
    """First match wins. Returns class, unsure, unsure reason and clump size."""
    area, solidity, hollowness = obj["area"], obj["solidity"], obj["hollowness"]

    if area < p.ignore_min_area_px or obj["aspect"] > p.ignore_max_aspect:
        return "ignore", False, None, 1
    if _is_bubble(obj, sigma, p):
        return "ignore", False, None, 1
    if um_per_px_proc is not None:
        length_um = obj["length_px"] * um_per_px_proc
        if length_um < p.ignore_min_len_um or length_um > p.ignore_max_len_um:
            return "ignore", False, None, 1
    elif a_ref is not None:
        if area < p.ignore_small_ref_frac * a_ref:
            return "ignore", False, None, 1
        if area > p.ignore_big_ref_frac * a_ref and solidity >= p.ignore_big_min_solidity:
            return "ignore", False, None, 1

    if a_ref is not None and area > p.clump_ref_frac * a_ref and (
        solidity < p.clump_max_solidity or obj["defect"] > p.clump_min_defect
    ):
        return "live", True, "clump count", max(2, round(area / a_ref))
    if solidity < p.debris_max_solidity:
        return "ignore", False, None, 1

    if hollowness < p.dead_max_hollowness:
        cls: Cls = "dead"
    elif solidity < p.abnormal_max_solidity:
        cls = "abnormal"
    else:
        cls = "live"

    if p.unsure_hollow_lo <= hollowness < p.unsure_hollow_hi:
        return cls, True, "between live and dead", 1
    if cls != "dead" and p.unsure_solidity_lo <= solidity < p.unsure_solidity_hi:
        return cls, True, "shape borderline", 1
    return cls, False, None, 1


def analyze(img_bgr: np.ndarray, *, um_per_px: float | None = None, calibration: Calibration = "preset",
            params: EngineParams = DEFAULT_ENGINE) -> AnalysisResult:
    """Run the full pipeline on a BGR image. `um_per_px` is the fallback when no grid is in view;
    `calibration` names where that fallback came from ("preset" or "manual")."""
    started = time.perf_counter()
    p = params
    orig_h, orig_w = img_bgr.shape[:2]

    # 1. Work at no more than max_long_side
    long_side = max(orig_h, orig_w)
    scale = 1.0
    work = img_bgr
    if long_side > p.max_long_side:
        scale = p.max_long_side / long_side
        work = cv2.resize(img_bgr, (round(orig_w * scale), round(orig_h * scale)), interpolation=cv2.INTER_AREA)
    to_orig = 1.0 / scale

    # 2-4. Difference from the estimated background
    gray = _to_gray(work, p)
    d = _background(gray, p) - gray
    d -= float(np.median(d))
    sigma = max(p.mad_to_sigma * float(np.median(np.abs(d))), 1e-3)

    # 5. Grid lines: calibrate, then remove them so larvae on a line stay whole
    grid = calibrate.find_grid(np.maximum(d, 0), sigma, p)
    grid_spacing_orig: float | None = None
    um_per_px_orig: float | None = None
    calibration_used: Calibration = "none"
    if grid.found:
        grid_spacing_orig = grid.spacing_px * to_orig
        um_per_px_orig = p.grid_square_um / grid_spacing_orig
        calibration_used = "grid"
        d = calibrate.remove_grid(d, grid, p)
    elif um_per_px:
        um_per_px_orig = um_per_px
        calibration_used = calibration
    diff = np.maximum(d, 0)

    # 6-9. Mask, clean up, drop specks, repair open rims
    mask = _segment(diff, sigma, p)
    mask = _repair_open_rims(mask, p)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    # 10. Features
    bright_level = p.bubble_bright_ratio * float(np.median(gray))
    objects = []
    for label in range(1, n):
        if stats[label, cv2.CC_STAT_AREA] < p.min_component_px:
            continue
        obj = _measure(labels, stats[label], label, d, gray, bright_level, p)
        if obj is not None:
            objects.append(obj)

    # 11. Classification relative to the typical round object in this photo
    a_ref = _reference_area(objects, sigma, p)
    um_per_px_proc = um_per_px_orig * to_orig if um_per_px_orig else None

    detections: list[Detection] = []
    for obj in sorted(objects, key=lambda o: (o["cy"], o["cx"])):
        cls, unsure, reason, clump_n = _classify(obj, a_ref, sigma, um_per_px_proc, p)
        length_px = obj["length_px"] * to_orig
        is_body = cls in ("live", "abnormal")
        detections.append(
            Detection(
                id=len(detections) + 1,
                cx=round(obj["cx"] * to_orig, 1),
                cy=round(obj["cy"] * to_orig, 1),
                contour=[(round(float(px) * to_orig, 1), round(float(py) * to_orig, 1)) for px, py in obj["contour"]],
                length_px=round(length_px, 2),
                length_um=round(length_px * um_per_px_orig, 1) if um_per_px_orig else None,
                area_px=round(obj["area"] * to_orig**2, 1),
                solidity=round(obj["solidity"], 4),
                defect=round(obj["defect"], 4),
                hollowness=round(obj["hollowness"], 4),
                gut=round(obj["gut"], 3) if is_body else None,
                interior=round(obj["interior"], 2),
                cls=cls,
                auto_cls=cls,
                unsure=unsure,
                unsure_reason=reason,
                clump_n=clump_n,
                touches_edge=obj["touches"],
            )
        )

    return AnalysisResult(
        width=orig_w,
        height=orig_h,
        um_per_px=round(um_per_px_orig, 4) if um_per_px_orig else None,
        calibration=calibration_used,
        grid_spacing_px=round(grid_spacing_orig, 2) if grid_spacing_orig else None,
        photo_volume_ml=calibrate.photo_volume_ml(orig_w, orig_h, um_per_px_orig, p.chamber_depth_mm),
        detections=detections,
        engine_version=ENGINE_VERSION,
        ms=int((time.perf_counter() - started) * 1000),
    )


def decode_image(data: bytes) -> np.ndarray | None:
    """Decode JPEG or PNG bytes into a BGR array. None when the bytes are not an image."""
    buffer = np.frombuffer(data, dtype=np.uint8)
    if buffer.size == 0:
        return None
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)
