"""Counts and size statistics from a list of detections (SPEC §5.3). Pure functions.

Separate from `analyze` so corrections recompute the summary without re-running segmentation.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from app.analysis.models import Detection, Summary
from app.config import DEFAULT_ENGINE, DEFAULTS, STAGE_BANDS_UM


def stage_for_length(mean_len_um: float | None) -> str | None:
    if mean_len_um is None:
        return None
    for name, lo, hi in STAGE_BANDS_UM:
        if lo <= mean_len_um < hi:
            return name
    return None


def summarize(dets: Sequence[Detection], um_per_px: float | None,
              settings: Mapping | None = None) -> Summary:
    """Counts, percentages, sizes, stage and gut. `settings` is accepted for parity with the SPEC
    interface; the histogram bins and edge weight live in EngineParams."""
    _ = settings if settings is not None else DEFAULTS
    p = DEFAULT_ENGINE

    n_live = n_abnormal = n_dead = n_unsure = n_ignored = 0
    count_for_estimate = 0.0
    size_values: list[float] = []
    gut_values: list[float] = []

    for det in dets:
        if det.cls == "ignore":
            n_ignored += 1
            continue
        if det.unsure:
            n_unsure += 1
        if det.cls == "dead":
            n_dead += 1
            continue
        weight = float(det.clump_n)
        if det.touches_edge:
            weight = p.edge_count_weight * det.clump_n
        count_for_estimate += weight
        if det.cls == "live":
            n_live += det.clump_n
        else:
            n_abnormal += det.clump_n
        is_single = det.clump_n == 1
        # A manual larva's length is a placeholder (the median), not a measurement
        if is_single and not det.touches_edge and det.source != "manual" and um_per_px and det.length_um is not None:
            size_values.append(det.length_um)
        if det.cls == "live" and is_single and det.gut is not None:
            gut_values.append(det.gut)

    counted = n_live + n_abnormal + n_dead
    summary = Summary(
        n_live=n_live,
        n_abnormal=n_abnormal,
        n_dead=n_dead,
        n_unsure=n_unsure,
        n_ignored=n_ignored,
        pct_dead=round(100.0 * n_dead / counted, 2) if counted else 0.0,
        pct_abnormal=round(100.0 * n_abnormal / counted, 2) if counted else 0.0,
        count_for_estimate=count_for_estimate,
    )

    if size_values:
        values = np.asarray(size_values, dtype=np.float64)
        mean = float(values.mean())
        summary.mean_len_um = round(mean, 2)
        if values.size > 1:
            sd = float(values.std(ddof=1))
            summary.sd_len_um = round(sd, 2)
            summary.cv = round(sd / mean, 4) if mean > 0 else None
        edges = np.arange(p.hist_lo_um, p.hist_hi_um + p.hist_bin_um, p.hist_bin_um)
        counts, _ = np.histogram(values, bins=edges)
        summary.hist = [int(c) for c in counts]
        summary.stage = stage_for_length(mean)
    if gut_values:
        summary.gut = round(float(np.mean(gut_values)), 3)
    return summary


def estimate_live(count_for_estimate: float, total_volume_ml: float | None, bucket_l: float,
                  concentration: float) -> float | None:
    """Live larvae left in the tank from a concentrated bucket sample (SPEC §6)."""
    if not total_volume_ml or concentration <= 0:
        return None
    return count_for_estimate / (total_volume_ml * concentration) * bucket_l * 1000.0
