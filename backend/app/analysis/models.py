"""Types the analysis engine returns (SPEC §5.1, §5.3)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Cls = Literal["live", "abnormal", "dead", "ignore"]
Calibration = Literal["grid", "preset", "manual", "none"]


class Detection(BaseModel):
    id: int
    cx: float
    cy: float  # ORIGINAL image px
    contour: list[tuple[float, float]]  # original px, simplified to <= 48 points
    length_px: float  # shell length, original px
    length_um: float | None = None
    area_px: float  # original px^2
    solidity: float = 1.0
    defect: float = 0.0
    hollowness: float = 1.5
    gut: float | None = None  # 0..1, live/abnormal only
    interior: float = 0.0  # median background-minus-gray inside (negative = brighter)
    cls: Cls = "live"
    auto_cls: Cls = "live"
    unsure: bool = False
    unsure_reason: str | None = None  # "between live and dead", "shape borderline", "clump count"
    clump_n: int = 1
    touches_edge: bool = False
    source: Literal["auto", "corrected", "manual"] = "auto"
    claude: dict | None = None


class AnalysisResult(BaseModel):
    width: int
    height: int  # original size
    um_per_px: float | None = None
    calibration: Calibration = "none"
    grid_spacing_px: float | None = None  # original px
    photo_volume_ml: float | None = None
    detections: list[Detection] = []
    engine_version: str = "cv-0.1"
    ms: int = 0


class Summary(BaseModel):
    n_live: int = 0
    n_abnormal: int = 0
    n_dead: int = 0
    n_unsure: int = 0
    n_ignored: int = 0
    pct_dead: float = 0.0
    pct_abnormal: float = 0.0
    mean_len_um: float | None = None
    sd_len_um: float | None = None
    cv: float | None = None
    hist: list[int] | None = None  # 10 µm bins from 40 to 420
    stage: str | None = None
    gut: float | None = None
    count_for_estimate: float = 0.0
