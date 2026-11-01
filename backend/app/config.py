"""Configuration: paths, env vars and every threshold or parameter the app uses.

Nothing in here reads or holds ANTHROPIC_API_KEY: only services/claude.py does.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

FIXTURES_DIR = REPO_ROOT / "fixtures"
SAMPLE_DIRS = (FIXTURES_DIR / "demo", FIXTURES_DIR / "slides")
SEED_FILE = REPO_ROOT / "seed" / "example_hatchery.json"
TOOLS_DIR = REPO_ROOT / "tools"


def data_dir() -> Path:
    """Runtime data folder. THETIS_DATA_DIR overrides the default <repo>/data."""
    configured = os.environ.get("THETIS_DATA_DIR")
    return Path(configured) if configured else REPO_ROOT / "data"


def db_path() -> Path:
    return data_dir() / "thetis.db"


def photos_dir() -> Path:
    return data_dir() / "photos"


def uploads_dir() -> Path:
    return data_dir() / "uploads"


def seed_cache_dir() -> Path:
    """Rendered seed photos. Shared between data folders so tests never re-render them."""
    configured = os.environ.get("THETIS_SEED_CACHE")
    return Path(configured) if configured else REPO_ROOT / "data" / "cache" / "seed-photos"


UPLOAD_MAX_AGE_H = 24
UPLOAD_MAX_BYTES = 40 * 1024 * 1024
FUTURE_SAMPLE_TOLERANCE_S = 300  # a clock a few minutes off shouldn't block a save
ENGINE_VERSION = "cv-0.1"
RULES_VERSION = "rules-0.1"


@dataclass(frozen=True)
class EngineParams:
    """Every number in the image analysis pipeline (SPEC §5)."""

    max_long_side: int = 1600
    gray_r: float = 0.25
    gray_g: float = 0.45
    gray_b: float = 0.30
    # Background estimate
    bg_downsample: int = 4
    bg_kernel_frac: float = 0.2
    bg_sigma_div: float = 6.0
    # Threshold
    mad_to_sigma: float = 1.4826
    thresh_sigma: float = 4.0
    otsu_floor_sigma: float = 3.0
    otsu_frac: float = 0.5
    # Mask cleanup
    close_iters: int = 2
    open_iters: int = 1
    min_component_px: int = 40
    # Open-rim repair
    rim_min_area_px: int = 300
    rim_hull_frac_of_median: float = 0.3
    rim_max_fill_ratio: float = 0.5
    rim_hull_max_frac_of_median: float = 3.0  # a far bigger hull is a scratch or a grid corner, not a shell
    # Features
    contour_epsilon_px: float = 0.6
    contour_max_points: int = 48
    feret_edge_correction_px: float = 3.0
    opened_kernel_frac: float = 0.14
    opened_keep_frac: float = 0.5
    hollow_inner_frac: float = 0.35
    hollow_ring_frac: float = 0.2
    gut_core_frac: float = 0.25
    gut_gain: float = 0.94
    # Classification
    ref_min_area_px: int = 300
    ref_min_solidity: float = 0.9
    ref_max_aspect: float = 1.6
    ref_min_frac_of_largest: float = 0.25  # small round debris must not drag the size reference down
    ignore_min_area_px: int = 60
    ignore_max_aspect: float = 2.6
    bubble_sigma: float = 3.0
    bubble_bright_ratio: float = 1.12  # brighter than the image's typical gray by this factor
    bubble_bright_frac: float = 0.03  # a dark-ringed air bubble has a bright core; tissue never does
    ignore_min_len_um: float = 45.0
    ignore_max_len_um: float = 420.0
    ignore_small_ref_frac: float = 0.35
    ignore_big_ref_frac: float = 4.0
    ignore_big_min_solidity: float = 0.93
    clump_ref_frac: float = 1.35
    clump_max_solidity: float = 0.93
    clump_min_defect: float = 0.12
    debris_max_solidity: float = 0.90  # rougher than any malformed shell, and not a clump
    dead_max_hollowness: float = 0.6
    abnormal_max_solidity: float = 0.955
    unsure_hollow_lo: float = 0.45
    unsure_hollow_hi: float = 0.8
    unsure_solidity_lo: float = 0.945
    unsure_solidity_hi: float = 0.965
    # Grid (Sedgewick-Rafter, 1 mm squares)
    grid_square_um: float = 1000.0
    grid_border_skip_px: int = 4
    grid_peak_mad: float = 8.0
    grid_peak_sigma: float = 4.0
    grid_group_gap_px: int = 2
    grid_max_line_px: int = 15
    grid_min_lines: int = 2
    grid_max_spacing_cv: float = 0.05
    grid_min_spacing_px: float = 100.0
    grid_axis_agree: float = 0.05
    grid_band_pad_px: int = 3
    # Photo volume
    chamber_depth_mm: float = 1.0
    # Summary
    hist_lo_um: int = 40
    hist_hi_um: int = 420
    hist_bin_um: int = 10
    edge_count_weight: float = 0.5


DEFAULT_ENGINE = EngineParams()


# Shell-length stage bands for Pacific oyster (SPEC §6), in micrometres.
STAGE_BANDS_UM = (
    ("D-stage", 0.0, 120.0),
    ("Early umbo", 120.0, 180.0),
    ("Late umbo", 180.0, 260.0),
    ("Eyed", 260.0, float("inf")),
)


# Hatchery settings and rule thresholds (SPEC §6, §7). A hatchery's `settings` JSON overrides
# the first group. Signal rows are (watch, risk, critical); None means "that rung does not exist".
DEFAULTS: dict = {
    "bucket_l": 20.0,
    "concentration": 50.0,
    "chamber_depth_mm": 1.0,
    "expected_growth_um_day": 9.0,
    "target_temp_c": 25.0,
    "check_interval_h": 48,
    "microscope_presets": {},
    # Series
    "baseline_min_days": 0.5,
    "growth_skip_baseline_um": 260.0,
    "spawn_hour": 12,
    # Signals
    "dead_pct": (10.0, 15.0, 20.0),
    "dead_rise_points": 8.0,
    "abnormal_pct": (12.0, 20.0, 30.0),
    "abnormal_rise_points": 8.0,
    "growth_ratio": (0.50, 0.35, 0.20),
    "gut_index": (0.35, 0.25, None),
    "spread_cv": (0.18, 0.26, None),
    "spread_rise": 0.06,
    "loss_per_day": (0.10, 0.15, None),
    "omega_arag": (2.0, 1.5, None),
    "ph": (7.8, 7.65, None),
    "temp_off_c": (2.0, 3.5, None),
    "do_mgl": (6.0, 5.0, None),
    # Line alerts and actions
    "line_alert_min_tanks": 2,
    "line_alert_window_days": 3,
    "line_reading_window_h": 24,  # readings older than this don't fill gaps in a line's latest water values
    "discard_dead_pct": 40.0,
    # Save-time estimate warning
    "overstock_warning_ratio": 1.1,
    # What this plant uses. Doses and steps name these. A hatchery's `settings` JSON overrides them.
    "plant": {"buffer": "sodium_carbonate", "disinfectant": "sodium_hypochlorite"},
    # Advisor: buffering
    "buffer_target_omega": 3.0,
    "assumed_alkalinity_umol_kg_at_35": 2300.0,  # used only when one of pH and Ω is missing
    "default_salinity_ppt": 30.0,
    # Readings outside these aren't seawater a dose can be worked out for (a typo, or a salinity of 0): no dose, no guess
    "dose_valid_salinity_ppt": (5.0, 45.0),
    "dose_valid_temp_c": (0.0, 40.0),
    "dose_valid_ph": (6.5, 9.5),
    "dose_valid_omega": (0.05, 15.0),
    # Advisor: yield. Guidance figures are from FAO Fisheries Technical Paper 471 (Helm & Bourne, 2004).
    "eyed_um": 260.0,
    "density_limit_per_l": 20000.0,  # §5.1.3: top of the 15,000 to 20,000 per L range for oyster D-larvae
    "density_range_low_per_l": 15000.0,
    "setting_density_per_l": 5000.0,  # §5.4.3: top of the 2,000 to 5,000 per L range at settlement
    "grade_mesh_um": 240,  # §5.4.3: retains the largest larvae, ready to settle
    "feed_cells_per_larva_day": ((100, 2800), (200, 41900), (280, 73100)),  # Table 13, C. gigas, by shell length in µm
    "cull_quantile": 0.15,
    "pace_min_checks": 3,  # a batch needs this many checks before it can set the pace for others
    "slow_pace_ratio": 1.5,  # losing this many times as fast as the pace batch is worth raising
    "project_max_days": 21,  # beyond this a batch isn't on course to reach the eyed stage
    "forecast_min_gain": 50000,  # a smaller gap isn't worth showing against a rough forecast
}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


# Claude budget guard (SPEC §8). The API key is not here on purpose.
CLAUDE_DEFAULT_MODEL = "claude-sonnet-5-5"
CLAUDE_DAILY_LIMIT_DEFAULT = 100
CLAUDE_MAX_OBJECTS = 12
CLAUDE_CROP_PADDING = 0.30
CLAUDE_CROP_MAX_PX = 256
CLAUDE_CROP_JPEG_QUALITY = 85
CLAUDE_OPINION_MAX_TOKENS = 1500
CLAUDE_EXPLAIN_MAX_TOKENS = 400
CLAUDE_ANALYSIS_MAX_TOKENS = 8000  # includes thinking
CLAUDE_ASK_MAX_TOKENS = 3000  # includes thinking
CLAUDE_ASK_MAX_TURNS = 20
CLAUDE_ASK_MAX_CHARS = 2000
CLAUDE_STREAM_TIMEOUT_S = 300.0
CLAUDE_STREAM_UPDATE_S = 0.12  # how often a running analysis updates the page
CLAUDE_MAX_INSIGHTS = 3
CLAUDE_MAX_PRIORITIES = 3
# How far a reading Claude cites may be from the record: enough for rounding as the app shows it, and no more
CLAUDE_EVIDENCE_TOLERANCE = {
    "pct_dead": 0.6, "pct_abnormal": 0.6, "survival_pct": 0.6, "length_um": 0.6, "cv": 0.006, "gut": 0.006, "growth_um_day": 0.06,
    "loss_pct_per_day": 0.06, "ph": 0.006, "omega_arag": 0.06, "temp_c": 0.06, "do_mgl": 0.06,
}
CLAUDE_EVIDENCE_COUNT_TOLERANCE = 0.01  # counts are often written roundly: 16.5M for 16,482,000
# Models that always think spend part of max_tokens on thinking. This keeps the visible answer whole.
CLAUDE_THINKING_HEADROOM_TOKENS = 1500
CLAUDE_TIMEOUT_S = 60.0
CLAUDE_MAX_RETRIES = 1
# Outline colours on crops, BGR (the same colours as the UI's larva outlines)
CLAUDE_OUTLINE_BGR = {
    "live": (87, 139, 46),
    "abnormal": (14, 98, 194),
    "dead": (43, 54, 194),
    "ignore": (192, 185, 174),
}
