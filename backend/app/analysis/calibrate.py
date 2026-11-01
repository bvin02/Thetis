"""Scale calibration from a counting-slide grid (SPEC §5.4). Pure functions."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.config import DEFAULT_ENGINE, EngineParams


@dataclass
class AxisGrid:
    """Lines found along one axis. Bands are inclusive (start, end) in processing px."""

    bands: list[tuple[int, int]] = field(default_factory=list)
    centres: list[int] = field(default_factory=list)
    spacing_px: float | None = None
    valid: bool = False


@dataclass
class GridResult:
    x: AxisGrid
    y: AxisGrid
    spacing_px: float | None = None  # processing px

    @property
    def found(self) -> bool:
        return self.spacing_px is not None


def _find_lines(profile: np.ndarray, sigma: float, p: EngineParams) -> AxisGrid:
    """Find grid lines in a per-column or per-row median profile of the difference image."""
    n = len(profile)
    skip = p.grid_border_skip_px
    median = float(np.median(profile))
    mad = float(np.median(np.abs(profile - median)))
    threshold = max(median + p.grid_peak_mad * mad, p.grid_peak_sigma * sigma)
    above = np.flatnonzero(profile > threshold)
    above = above[(above >= skip) & (above < n - skip)]

    groups: list[list[int]] = []
    for index in above:
        if groups and index - groups[-1][-1] <= p.grid_group_gap_px:
            groups[-1].append(int(index))
        else:
            groups.append([int(index)])

    axis = AxisGrid()
    for group in groups:
        start, end = group[0], group[-1]
        if end - start + 1 > p.grid_max_line_px:
            continue
        axis.bands.append((start, end))
        segment = profile[start : end + 1]
        axis.centres.append(start + int(np.argmax(segment)))

    if len(axis.centres) >= p.grid_min_lines:
        gaps = np.diff(axis.centres).astype(np.float64)
        mean_gap = float(gaps.mean())
        cv = float(gaps.std() / mean_gap) if mean_gap > 0 else 1.0
        if cv < p.grid_max_spacing_cv and mean_gap >= p.grid_min_spacing_px:
            axis.spacing_px = mean_gap
            axis.valid = True
    return axis


def find_grid(diff: np.ndarray, sigma: float, p: EngineParams = DEFAULT_ENGINE) -> GridResult:
    """Look for a square grid in the difference image. Spacing is in the image's own px."""
    x_axis = _find_lines(np.median(diff, axis=0), sigma, p)
    y_axis = _find_lines(np.median(diff, axis=1), sigma, p)
    result = GridResult(x=x_axis, y=y_axis)
    if x_axis.valid and y_axis.valid:
        sx, sy = x_axis.spacing_px, y_axis.spacing_px
        if abs(sx - sy) / max(sx, sy) <= p.grid_axis_agree:
            result.spacing_px = (sx + sy) / 2
    elif x_axis.valid:
        result.spacing_px = x_axis.spacing_px
    elif y_axis.valid:
        result.spacing_px = y_axis.spacing_px
    return result


def remove_grid(image: np.ndarray, grid: GridResult, p: EngineParams = DEFAULT_ENGINE) -> np.ndarray:
    """Replace each grid band by a linear blend of its two edges, so larvae on a line stay whole."""
    out = image.astype(np.float32, copy=True)
    h, w = out.shape
    pad = p.grid_band_pad_px
    for start, end in grid.x.bands:
        a, b = max(0, start - pad), min(w - 1, end + pad)
        if b - a < 2:
            continue
        t = np.linspace(0.0, 1.0, b - a + 1, dtype=np.float32)[None, :]
        out[:, a : b + 1] = out[:, [a]] * (1 - t) + out[:, [b]] * t
    for start, end in grid.y.bands:
        a, b = max(0, start - pad), min(h - 1, end + pad)
        if b - a < 2:
            continue
        t = np.linspace(0.0, 1.0, b - a + 1, dtype=np.float32)[:, None]
        out[a : b + 1, :] = out[[a], :] * (1 - t) + out[[b], :] * t
    return out


def photo_volume_ml(width: int, height: int, um_per_px: float | None,
                    chamber_depth_mm: float = DEFAULT_ENGINE.chamber_depth_mm) -> float | None:
    """Volume of slide in view: width × height × (µm/px)² / 10⁶ mm² × depth mm / 1000 mL."""
    if not um_per_px:
        return None
    area_mm2 = width * height * um_per_px**2 / 1e6
    return area_mm2 * chamber_depth_mm / 1000.0
