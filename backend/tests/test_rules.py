"""Rules engine: every signal, every rung, every pattern, every text (SPEC §13)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlmodel import Session

from app import config, db
from app.rules.actions import CATALOG, action_text, actions_for
from app.rules.assess import LineAlert, assess, level_for, line_alert, pattern_for
from app.rules.history import BatchHistory, history_days, tank_history
from app.rules.series import BatchData, CheckData, baseline_index, day_of, rates_at, stage_for
from app.rules.signals import Signal, compute_signals
from app.rules.text import (
    TankBrief,
    chip_for,
    condition_rows,
    fmt_clock,
    fmt_count,
    fmt_since,
    fmt_when,
    headline_for,
    join_names,
    next_check_text,
    reason_for,
    summary_for,
    title_for,
)
from app.seed import run_seed
from app.services.world import load_world

CFG = dict(config.DEFAULTS)
T0 = datetime(2026, 10, 20, 12, 0)
SPAWN = date(2026, 10, 18)
BATCH = BatchData(spawn_date=SPAWN, stocked=1_000_000)


def check(hours: float = 48, **kwargs) -> CheckData:
    defaults = dict(sampled_at=T0 + timedelta(hours=hours))
    return CheckData(**{**defaults, **kwargs})


def severity(key: str, **values) -> str | None:
    """Severity of one signal on a check where only that measure is set."""
    current = check(**values)
    rates = rates_at([current], 0, BATCH, "larval", CFG)
    for signal in compute_signals(current, rates, CFG):
        if signal.key == key:
            return signal.severity
    return None


# ------------------------------------------------------------------ §7.1 signals at thresholds


@pytest.mark.parametrize("value,want", [
    (9.99, None), (10.0, "watch"), (10.01, "watch"), (14.99, "watch"), (15.0, "risk"), (15.01, "risk"),
    (19.99, "risk"), (20.0, "critical"), (20.01, "critical"),
])
def test_dead_thresholds(value, want):
    assert severity("dead", pct_dead=value) == want


@pytest.mark.parametrize("value,want", [
    (11.99, None), (12.0, "watch"), (12.01, "watch"), (19.99, "watch"), (20.0, "risk"), (20.01, "risk"),
    (29.99, "risk"), (30.0, "critical"), (30.01, "critical"),
])
def test_abnormal_thresholds(value, want):
    assert severity("abnormal", pct_abnormal=value) == want


@pytest.mark.parametrize("value,want", [
    (0.35, None), (0.34, "watch"), (0.3501, None), (0.25, "watch"), (0.2499, "risk"), (0.2501, "watch"), (0.0, "risk"),
])
def test_gut_thresholds(value, want):
    assert severity("gut", gut=value) == want


@pytest.mark.parametrize("value,want", [
    (0.1799, None), (0.18, "watch"), (0.1801, "watch"), (0.2599, "watch"), (0.26, "risk"), (0.2601, "risk"),
])
def test_spread_thresholds(value, want):
    assert severity("spread", cv=value) == want


@pytest.mark.parametrize("value,want", [
    (2.01, None), (2.0, None), (1.99, "watch"), (1.51, "watch"), (1.5, "watch"), (1.49, "risk"),
])
def test_omega_thresholds(value, want):
    assert severity("omega", omega_arag=value) == want


@pytest.mark.parametrize("value,want", [
    (7.81, None), (7.8, None), (7.79, "watch"), (7.66, "watch"), (7.65, "watch"), (7.64, "risk"),
])
def test_ph_thresholds(value, want):
    assert severity("ph", ph=value) == want


@pytest.mark.parametrize("value,want", [
    (25.0, None), (27.0, None), (27.01, "watch"), (23.0, None), (22.99, "watch"),
    (28.5, "watch"), (28.51, "risk"), (21.5, "watch"), (21.49, "risk"),
])
def test_temp_thresholds(value, want):
    assert severity("temp", temp_c=value) == want


@pytest.mark.parametrize("value,want", [
    (6.01, None), (6.0, None), (5.99, "watch"), (5.01, "watch"), (5.0, "watch"), (4.99, "risk"),
])
def test_oxygen_thresholds(value, want):
    assert severity("oxygen", do_mgl=value) == want


def _two_checks(first: dict, second: dict, days: float = 2.0):
    a = CheckData(sampled_at=T0, **first)
    b = CheckData(sampled_at=T0 + timedelta(days=days), **second)
    rates = rates_at([a, b], 1, BATCH, "larval", CFG)
    return {s.key: s.severity for s in compute_signals(b, rates, CFG)}


@pytest.mark.parametrize("ratio,want", [
    (0.50, None), (0.5001, None), (0.4999, "watch"), (0.35, "watch"), (0.3499, "risk"), (0.3501, "watch"),
    (0.20, "risk"), (0.1999, "critical"), (0.2001, "risk"), (-0.5, "critical"),
])
def test_growth_thresholds(ratio, want):
    gain = ratio * CFG["expected_growth_um_day"] * 2.0
    signals = _two_checks({"mean_len_um": 100.0}, {"mean_len_um": 100.0 + gain})
    assert signals.get("growth") == want


@pytest.mark.parametrize("k,want", [
    (0.10, None), (0.0999, None), (0.1001, "watch"), (0.15, "watch"), (0.1499, "watch"), (0.1501, "risk"),
])
def test_loss_thresholds(k, want):
    import math

    signals = _two_checks({"live_est": 1_000_000.0}, {"live_est": 1_000_000.0 * math.exp(-k * 2.0)})
    assert signals.get("loss") == want


@pytest.mark.parametrize("prev,now,want", [
    (0.0, 7.99, None), (0.0, 8.0, "watch"), (0.0, 8.01, "watch"), (1.0, 8.99, None), (1.0, 9.0, "watch"),
])
def test_dead_jump_is_a_watch(prev, now, want):
    assert _two_checks({"pct_dead": prev}, {"pct_dead": now}).get("dead") == want


@pytest.mark.parametrize("prev,now,want", [
    (0.0, 7.99, None), (0.0, 8.0, "watch"), (2.0, 10.0, "watch"), (2.0, 9.99, None),
])
def test_abnormal_jump_is_a_watch(prev, now, want):
    assert _two_checks({"pct_abnormal": prev}, {"pct_abnormal": now}).get("abnormal") == want


@pytest.mark.parametrize("prev,now,want", [
    (0.10, 0.1599, None), (0.10, 0.16, "watch"), (0.10, 0.1601, "watch"),
])
def test_spread_jump_is_a_watch(prev, now, want):
    assert _two_checks({"cv": prev}, {"cv": now}).get("spread") == want


def test_missing_data_means_no_signal():
    current = check()
    assert compute_signals(current, rates_at([current], 0, BATCH, "larval", CFG), CFG) == []


def test_jump_needs_a_previous_value():
    assert severity("dead", pct_dead=9.0) is None


# ------------------------------------------------------------------ §6 tank math


def test_survival_and_day():
    current = check(live_est=410_000.0)
    assert rates_at([current], 0, BATCH, "larval", CFG).survival == pytest.approx(0.41)
    assert day_of(datetime(2026, 10, 27, 8, 40), SPAWN) == 9


def test_loss_against_stocking_when_there_is_no_baseline():
    import math

    current = CheckData(sampled_at=datetime(2026, 10, 19, 12, 0), live_est=900_000.0)  # exactly one day after noon
    rates = rates_at([current], 0, BATCH, "larval", CFG)
    assert rates.loss_per_day == pytest.approx(-math.log(0.9))
    assert rates.growth_um_day is None


def test_baseline_skips_checks_less_than_half_a_day_older():
    checks = [check(0), check(40), check(48)]  # 8 h apart: too close; 48 h: the baseline
    assert baseline_index(checks, 2, CFG) == 0
    checks = [check(0), check(36), check(48)]  # exactly 12 h = 0.5 days counts
    assert baseline_index(checks, 2, CFG) == 1


def test_a_check_with_no_estimate_does_not_hide_a_loss():
    import math

    first = CheckData(sampled_at=T0, live_est=800_000.0, mean_len_um=100.0)
    no_scale = CheckData(sampled_at=T0 + timedelta(days=2))  # a photo with no scale: no estimate, no sizes
    now = CheckData(sampled_at=T0 + timedelta(days=4), live_est=200_000.0, mean_len_um=104.0)
    rates = rates_at([first, no_scale, now], 2, BATCH, "larval", CFG)
    assert rates.loss_per_day == pytest.approx(math.log(4) / 4)
    assert rates.growth_um_day == pytest.approx(1.0)
    assert assess([first, no_scale, now], BATCH, "larval", CFG).at_least("loss", "risk")


def test_growth_skipped_in_setting_tanks_and_past_260_um():
    a = CheckData(sampled_at=T0, mean_len_um=200.0)
    b = CheckData(sampled_at=T0 + timedelta(days=2), mean_len_um=220.0)
    assert rates_at([a, b], 1, BATCH, "larval", CFG).growth_um_day == pytest.approx(10.0)
    assert rates_at([a, b], 1, BATCH, "setting", CFG).growth_um_day is None
    eyed = CheckData(sampled_at=T0, mean_len_um=260.0)
    assert rates_at([eyed, b], 1, BATCH, "larval", CFG).growth_um_day is None


@pytest.mark.parametrize("mean,kind,want", [
    (119.9, "larval", "D-stage"), (120.0, "larval", "Early umbo"), (179.9, "larval", "Early umbo"),
    (180.0, "larval", "Late umbo"), (259.9, "larval", "Late umbo"), (260.0, "larval", "Eyed"),
    (120.0, "setting", "Setting"), (None, "larval", None),
])
def test_stage(mean, kind, want):
    assert stage_for(mean, kind) == want


# ------------------------------------------------------------------ §7.2 ladder


def sig(key: str, severity: str) -> Signal:
    kind = "water" if key in ("omega", "ph", "temp", "oxygen") else ("count" if key == "loss" else "larvae")
    return Signal(key, severity, 0.0, None, kind)


@pytest.mark.parametrize("signals,want", [
    ([], "ok"),
    ([sig("spread", "watch")], "watch"),
    ([sig("omega", "risk")], "watch"),  # water alone never goes above Watch
    ([sig("ph", "risk"), sig("omega", "risk")], "watch"),
    ([sig("temp", "risk")], "watch"),
    ([sig("oxygen", "risk")], "watch"),
    ([sig("loss", "risk")], "watch"),  # loss alone never goes above Watch
    ([sig("loss", "watch")], "watch"),
    ([sig("dead", "risk")], "risk"),
    ([sig("abnormal", "risk")], "risk"),
    ([sig("growth", "risk")], "risk"),
    ([sig("gut", "risk")], "risk"),
    ([sig("spread", "risk")], "risk"),
    ([sig("omega", "risk"), sig("abnormal", "watch")], "risk"),  # the water is hurting the larvae
    ([sig("omega", "watch"), sig("abnormal", "watch")], "watch"),
    ([sig("loss", "risk"), sig("gut", "watch")], "risk"),
    ([sig("loss", "watch"), sig("gut", "watch")], "watch"),
    ([sig("dead", "critical")], "critical"),
    ([sig("abnormal", "critical")], "critical"),
    ([sig("growth", "critical")], "critical"),
    ([sig("dead", "risk"), sig("loss", "risk")], "critical"),
    ([sig("dead", "watch"), sig("loss", "risk")], "risk"),
])
def test_level_ladder(signals, want):
    assert level_for(signals) == want


# ------------------------------------------------------------------ §7.3 patterns


@pytest.mark.parametrize("signals,want", [
    ([sig("dead", "watch"), sig("gut", "watch")], "bacterial"),
    ([sig("loss", "watch"), sig("growth", "watch")], "bacterial"),
    ([sig("dead", "critical"), sig("growth", "critical"), sig("gut", "risk")], "bacterial"),
    ([sig("omega", "watch"), sig("abnormal", "watch")], "corrosive"),
    ([sig("ph", "risk"), sig("growth", "watch")], "corrosive"),
    ([sig("omega", "watch"), sig("dead", "watch"), sig("gut", "watch")], "corrosive"),  # water bad: not bacterial
    ([sig("omega", "watch")], "corrosive_early"),
    ([sig("ph", "risk")], "corrosive_early"),
    ([sig("omega", "risk"), sig("loss", "watch")], "corrosive_early"),
    ([sig("gut", "watch")], "underfed"),
    ([sig("growth", "risk")], "underfed"),
    ([sig("spread", "watch")], "splitting"),
    ([sig("spread", "risk"), sig("temp", "watch")], "splitting"),
    ([sig("temp", "watch")], "temperature"),
    ([sig("oxygen", "watch")], "oxygen"),
    ([sig("loss", "watch")], "unexplained_loss"),
    ([sig("dead", "watch")], "early_warning"),
    ([sig("abnormal", "watch")], "early_warning"),
])
def test_patterns(signals, want):
    assert pattern_for(signals, level_for(signals)) == want


def test_no_pattern_when_normal():
    assert pattern_for([], "ok") is None


# ------------------------------------------------------------------ assess and history replay


def test_assess_ignores_checks_after_upto():
    healthy = [CheckData(sampled_at=T0 + timedelta(days=d), live_est=900_000.0 - d * 10_000, pct_dead=2.0,
                         pct_abnormal=1.0, mean_len_um=100.0 + d * 9, cv=0.1, gut=0.7) for d in range(3)]
    before = assess(healthy, BATCH, "larval", CFG, upto=2)
    crash = CheckData(sampled_at=T0 + timedelta(days=4), live_est=100_000.0, pct_dead=60.0, pct_abnormal=20.0,
                      mean_len_um=118.0, cv=0.4, gut=0.05)
    after = assess([*healthy, crash], BATCH, "larval", CFG, upto=2)
    assert after.level == before.level == "ok"
    assert after.signals == before.signals
    assert after.survival == before.survival
    assert assess([*healthy, crash], BATCH, "larval", CFG).level == "critical"


def test_assess_without_checks():
    result = assess([], BATCH, "larval", CFG)
    assert result.level == "ok" and result.signals == [] and result.survival is None


# ------------------------------------------------------------------ §7.3–7.5 texts


def _assessed(signals_check: CheckData, prev: CheckData | None = None, kind: str = "larval"):
    series = [prev, signals_check] if prev else [signals_check]
    return assess(series, BATCH, kind, CFG)


def test_titles_and_chips():
    normal = _assessed(check(mean_len_um=100.0))
    assert title_for(normal) == "Tracking normally"
    assert title_for(_assessed(check(mean_len_um=280.0))) == "Ready to set"
    assert title_for(_assessed(check(mean_len_um=280.0), kind="setting")) == "Setting"
    assert chip_for("bacterial", "L1", False) == "Bacterial pattern"
    assert chip_for("corrosive_early", "L2", True) == "On line 2"
    assert chip_for("corrosive_early", "L2", False) == "Corrosive water"
    assert chip_for(None, "L1", False) == ""


def test_normal_reasons():
    assert reason_for(_assessed(check(mean_len_um=100.0)), "L1", False, 1, CFG) == "First check done. Tracking normally."
    assert reason_for(_assessed(check(mean_len_um=100.0)), "L1", False, 3, CFG) == "Tracking normally."
    assert (reason_for(_assessed(check(mean_len_um=280.0)), "L1", False, 3, CFG)
            == "Eyed larvae. Ready to move to setting in 1–2 days.")
    assert reason_for(_assessed(check(mean_len_um=280.0), kind="setting"), "L1", False, 3, CFG) == "Setting on cultch."


@pytest.mark.parametrize("values,alert,want", [
    (dict(pct_dead=12.0), False, "Dead larvae 12%."),
    (dict(omega_arag=1.4), True, "Line 2 water is corrosive (Ω 1.4)."),
    (dict(omega_arag=1.4), False, "Water is corrosive (Ω 1.4)."),
    (dict(ph=7.6), False, "Water is corrosive (pH 7.60)."),
    (dict(omega_arag=1.4, ph=7.6), False, "Water is corrosive (Ω 1.4)."),  # pH only if Ω wasn't used
    (dict(pct_abnormal=25.4), False, "Abnormal shells are up to 25%."),
    (dict(gut=0.2), False, "Guts are nearly empty."),
    (dict(gut=0.3), False, "Guts look light."),
    (dict(cv=0.2), False, "Size spread is widening: CV 0.20."),
    (dict(temp_c=28.0), False, "Water is 28.0 °C, 3.0 °C off target."),
    (dict(do_mgl=5.5), False, "Oxygen is low (5.5 mg/L)."),
])
def test_single_signal_reasons(values, alert, want):
    # On a Normal-pattern-free tank with a line alert, corrosive_early has its own sentence; test it below
    result = _assessed(check(**values))
    if result.pattern == "corrosive_early" and alert:
        assert reason_for(result, "L2", True, 2, CFG).startswith("On line 2 (Ω 1.4)")
    else:
        assert reason_for(result, "L2", alert, 2, CFG) == want


def test_loss_reason_and_growth_reasons():
    prev = CheckData(sampled_at=T0, live_est=800_000.0, mean_len_um=100.0)
    now = CheckData(sampled_at=T0 + timedelta(days=2), live_est=500_000.0, mean_len_um=108.0)
    result = _assessed(now, prev)
    assert "Survival fell from 80% to 50% since the last check." in reason_for(result, "L1", False, 2, CFG)
    slow = CheckData(sampled_at=T0 + timedelta(days=2), mean_len_um=108.2)
    assert ("Growth is 4.1 µm a day, below the 9 expected."
            in reason_for(_assessed(slow, CheckData(sampled_at=T0, mean_len_um=100.0)), "L1", False, 2, CFG))
    stalled = CheckData(sampled_at=T0 + timedelta(days=2), mean_len_um=101.0)
    assert reason_for(_assessed(stalled, CheckData(sampled_at=T0, mean_len_um=100.0)), "L1", False, 2, CFG) == "Growth has stalled."


def test_condition_table_for_bacterial_pattern():
    prev = CheckData(sampled_at=T0, live_est=700_000.0, pct_dead=8.62, pct_abnormal=5.0, mean_len_um=126.0, gut=0.71)
    now = CheckData(sampled_at=T0 + timedelta(days=1.68), live_est=410_000.0, pct_dead=23.8, pct_abnormal=7.9,
                    mean_len_um=128.0, gut=0.18, omega_arag=2.9, ph=7.96)
    rows = condition_rows(_assessed(now, prev), CFG)
    assert [(r["label"], r["now"], r["cmp"], r["severity"]) for r in rows] == [
        ("Dead larvae", "24%", "9% at last check", "critical"),
        ("Growth", "1.2 µm/day", "9 µm/day expected", "critical"),
        ("Gut fullness", "0.18", "0.71 at last check", "risk"),
        ("Ω aragonite", "2.9", "target ≥ 2", "context"),
        ("Live larvae (est.)", "410k", "700k at last check", "risk"),
        ("Shell length", "128 µm", "126 µm at last check", None),
    ]


def test_condition_table_for_corrosive_early():
    now = CheckData(sampled_at=T0, omega_arag=1.4, pct_abnormal=3.1, mean_len_um=79.4, live_est=900_000.0)
    rows = condition_rows(_assessed(now), CFG)
    assert [(r["label"], r["now"], r["cmp"]) for r in rows] == [
        ("Ω aragonite", "1.4", "target ≥ 2"),
        ("Abnormal shells", "3%", "normal range"),
        ("Live larvae (est.)", "900k", "of 1.0M stocked"),
        ("Shell length", "79 µm", "first check"),
    ]


def test_condition_rows_for_water_units():
    now = CheckData(sampled_at=T0, ph=7.7, temp_c=28.0, do_mgl=5.5, omega_arag=None)
    rows = {r["label"]: (r["now"], r["cmp"]) for r in condition_rows(_assessed(now), CFG)}
    assert rows["pH"] == ("7.70", "target ≥ 7.8")
    assert rows["Water temperature"] == ("28.0 °C", "target 25 °C")
    assert rows["Oxygen"] == ("5.5 mg/L", "target ≥ 6 mg/L")


@pytest.mark.parametrize("value,want", [
    (4_100_000, "4.1M"), (850_000, "850k"), (135_609_000, "135.6M"), (999, "999"), (None, "—"),
])
def test_count_format(value, want):
    assert fmt_count(value) == want


def test_time_formats():
    now = datetime(2026, 10, 31, 9, 12)
    assert fmt_when(datetime(2026, 10, 31, 8, 40), now) == "Today, 8:40 AM"
    assert fmt_when(datetime(2026, 10, 30, 16, 10), now) == "Yesterday, 4:10 PM"
    assert fmt_when(datetime(2026, 10, 29, 14, 0), now) == "Oct 29, 2:00 PM"
    assert fmt_when(datetime(2026, 10, 31, 0, 5), now) == "Today, 12:05 AM"
    assert fmt_when(datetime(2026, 10, 31, 12, 0), now) == "Today, 12:00 PM"
    assert fmt_clock(now) == "Sat, Oct 31 · 9:12 AM"
    assert fmt_since(datetime(2026, 10, 31, 1, 0), now) == "today"
    assert fmt_since(datetime(2026, 10, 30, 1, 0), now) == "yesterday"
    assert fmt_since(datetime(2026, 10, 27, 1, 0), now) == "Tuesday"
    assert fmt_since(datetime(2026, 10, 24, 1, 0), now) == "Oct 24"


def test_join_names():
    assert join_names(["T-04"]) == "T-04"
    assert join_names(["T-04", "T-05"]) == "T-04 and T-05"
    assert join_names(["T-04", "T-05", "T-06"]) == "T-04, T-05 and T-06"


def test_next_check_text():
    now = datetime(2026, 10, 31, 9, 0)
    assert next_check_text(datetime(2026, 10, 29, 14, 0), 48, now) == ("2:00 PM", False)
    assert next_check_text(datetime(2026, 10, 29, 8, 0), 48, now) == ("Overdue", True)
    assert next_check_text(datetime(2026, 10, 30, 8, 0), 48, now) == ("Tomorrow", False)
    assert next_check_text(datetime(2026, 10, 31, 8, 0), 48, now) == ("Mon, Nov 2", False)


# ------------------------------------------------------------------ headline and summary


def brief(tank_id, level, pattern=None, line="L1", active=True):
    return TankBrief(tank_id, level, pattern, line, active)


def test_headlines():
    assert headline_for([brief("A", "critical"), brief("B", "risk")]) == "2 tanks need attention now"
    assert headline_for([brief("A", "critical"), brief("B", "ok")]) == "1 tank needs attention now"
    assert headline_for([brief("A", "watch"), brief("B", "watch")]) == "2 tanks on watch"
    assert headline_for([brief("A", "watch")]) == "1 tank on watch"
    assert headline_for([brief("A", "ok"), brief("B", "empty", active=False)]) == "All tanks tracking normally"


def test_summary_sentences():
    now = datetime(2026, 10, 31, 9, 0)
    assert summary_for([brief("A", "ok")], {}, now) == "All tanks are tracking normally."
    assert summary_for([brief("A", "watch"), brief("B", "watch")], {}, now) == (
        "2 tanks are on watch. Nothing needs action right now."
    )
    assert summary_for([brief("T-03", "critical", "bacterial")], {}, now) == (
        "T-03 shows a pattern that matches a bacterial outbreak."
    )
    alert = {"L2": LineAlert("L2", datetime(2026, 10, 31, 8, 0), ("T-04", "T-05"))}
    tanks = [brief("T-04", "risk", "corrosive", "L2"), brief("T-05", "risk", "corrosive", "L2"),
             brief("T-06", "watch", "corrosive_early", "L2"), brief("T-07", "watch", "corrosive_early", "L2")]
    assert summary_for(tanks, alert, now) == (
        "Line 2 water has been corrosive since today. It now affects T-04 and T-05, and T-06 and T-07 are on the "
        "same line."
    )
    assert summary_for(tanks[:2], alert, now) == "Line 2 water has been corrosive since today. It now affects T-04 and T-05."
    only_watch = [brief("T-06", "watch", "corrosive_early", "L2"), brief("T-07", "watch", "corrosive_early", "L2")]
    assert summary_for(only_watch, alert, now).startswith("Line 2 water has been corrosive since today. T-06 and T-07 are")


# ------------------------------------------------------------------ §7.6 line alerts


def _water(day: int, omega: float | None = None, ph: float | None = None) -> CheckData:
    return CheckData(sampled_at=T0 + timedelta(days=day), omega_arag=omega, ph=ph)


def test_line_alert_needs_two_tanks():
    now = T0 + timedelta(days=5)
    assert line_alert("L2", {"T-04": [_water(5, omega=1.4)], "T-05": [_water(5, omega=2.9)]}, now, CFG) is None
    alert = line_alert("L2", {"T-04": [_water(5, omega=1.4)], "T-05": [_water(5, ph=7.7)]}, now, CFG)
    assert alert is not None and alert.tank_ids == ("T-04", "T-05")


def test_line_alert_latest_check_must_be_recent():
    now = T0 + timedelta(days=5)
    stale = {"T-04": [_water(1, omega=1.4)], "T-05": [_water(5, omega=1.4)]}
    assert line_alert("L2", stale, now, CFG) is None
    edge = {"T-04": [_water(2, omega=1.4)], "T-05": [_water(5, omega=1.4)]}
    assert line_alert("L2", edge, now, CFG) is not None


def test_line_alert_since_is_the_start_of_the_current_run():
    now = T0 + timedelta(days=5)
    checks = {
        "T-04": [_water(0, omega=1.4), _water(1, omega=2.9), _water(3, omega=1.8), _water(5, omega=1.4)],
        "T-05": [_water(1, omega=2.8), _water(4, omega=1.5), _water(5)],  # latest has no water reading
        "T-06": [_water(2, omega=1.9), _water(5, omega=1.4)],
    }
    alert = line_alert("L2", checks, now, CFG)
    assert alert is not None
    assert alert.since == T0 + timedelta(days=2)
    assert alert.tank_ids == ("T-04", "T-06")


# ------------------------------------------------------------------ §7.7 actions


def planned(check_values: dict, tank="T-03", line="L1", alert=False):
    result = _assessed(check(**check_values))
    return [(p.scope, p.action, p.tank_id, p.line_id) for p in actions_for(result, tank, line, alert, CFG)]


def test_actions_per_pattern():
    assert [p[1] for p in planned(dict(pct_dead=24.0, gut=0.18))] == ["isolate", "sample_vibrio", "restock"]
    assert [p[1] for p in planned(dict(pct_dead=40.0, gut=0.18))] == ["isolate", "sample_vibrio", "restock", "discard"]
    assert [p[1] for p in planned(dict(pct_dead=39.9, gut=0.18))] == ["isolate", "sample_vibrio", "restock"]
    assert planned(dict(omega_arag=1.4), line="L2", alert=True) == [
        ("line", "buffer_line", None, "L2"), ("line", "hold_spawn", None, "L2"),
    ]
    assert planned(dict(omega_arag=1.4), line="L2", alert=False) == [("line", "buffer_line", None, "L2")]
    assert planned(dict(omega_arag=1.4), line=None) == [("tank", "buffer_tank", "T-03", None)]
    assert [p[1] for p in planned(dict(gut=0.3))] == ["feed_check"]
    assert [p[1] for p in planned(dict(cv=0.2))] == ["screen"]
    assert [p[1] for p in planned(dict(temp_c=28.0))] == ["temp_check"]
    assert [p[1] for p in planned(dict(do_mgl=5.5))] == ["aerate"]
    assert [p[1] for p in planned(dict(pct_dead=11.0))] == ["recount"]
    assert planned(dict(mean_len_um=100.0)) == []


def test_action_catalog_text():
    assert set(CATALOG) == {"isolate", "sample_vibrio", "restock", "discard", "buffer_line", "hold_spawn", "buffer_tank",
                            "screen", "feed_check", "recount", "temp_check", "aerate"}
    assert action_text("isolate", "T-03", None)["title"] == "Isolate T-03. Use separate screens, buckets and hoses."
    assert action_text("buffer_line", None, "L2")["title"] == "Buffer line 2 water to bring Ω aragonite to 3 or higher"
    assert action_text("hold_spawn", None, "L2") == {
        "title": "Hold the next spawn until line 2 water recovers", "cta": "Hold next spawn", "done": "Next spawn on hold",
    }


# ------------------------------------------------------------------ §7.8 history grid


def test_history_grid_levels_and_empties():
    today = date(2026, 10, 31)
    batch = BatchHistory(
        spawn_date=date(2026, 10, 25),
        closed_on=None,
        checks=[(datetime(2026, 10, 26, 16, 0), "ok"), (datetime(2026, 10, 29, 16, 0), "watch"),
                (datetime(2026, 10, 31, 8, 0), "critical")],
    )
    cells = tank_history([batch], today)
    assert len(cells) == 14
    assert cells[0]["date"] == "2026-10-18" and cells[-1]["date"] == "2026-10-31"
    assert [c["level"] for c in cells[:7]] == [None] * 7
    assert cells[0]["change"] == "No batch in this tank"
    assert cells[7]["level"] == "ok"  # spawned, not checked yet: Normal
    assert [c["level"] for c in cells[8:]] == ["ok", "ok", "ok", "watch", "watch", "critical"]
    assert cells[-1]["change"] == "Worsened from Watch"
    assert cells[-1]["date_text"] == "Sat, Oct 31 (today)"


def test_history_grid_emptied_tank():
    today = date(2026, 10, 31)
    batch = BatchHistory(spawn_date=date(2026, 10, 11), closed_on=date(2026, 10, 27), checks=[(datetime(2026, 10, 16, 15, 0), "ok")])
    cells = tank_history([batch], today)
    assert cells[9]["date"] == "2026-10-27" and cells[9]["level"] == "ok"  # still in the tank on the closing day
    assert cells[10]["level"] is None and cells[10]["change"] == "Tank emptied"
    assert cells[13]["level"] is None


def test_history_days_axis():
    days = history_days(date(2026, 10, 31))
    assert days[0] == {"date": "2026-10-18", "num": "18", "sub": "Oct", "is_today": False}
    assert days[1]["sub"] == "M"
    assert days[-1] == {"date": "2026-10-31", "num": "Today", "sub": "S", "is_today": True}


# ------------------------------------------------------------------ exact reason texts for the full seed


REASONS = {
    "T-02": "Size spread is widening: CV 0.21, up from 0.14 at the last check.",
    "T-03": "Dead larvae 24%, up from 9% at the last check. Growth has stalled.",
    "T-04": "Line 2 water is corrosive (Ω 1.4). Abnormal shells are up to 19%.",
    "T-05": "Line 2 water is corrosive (Ω 1.4). Abnormal shells are up to 13%.",
    "T-06": "On line 2 (Ω 1.4). Larvae look normal so far.",
    "T-10": "Growth is 4.1 µm a day, below the 9 expected. Guts look light.",
    "T-01": "Tracking normally.",
    "T-07": "Eyed larvae. Ready to move to setting in 1–2 days.",
    "T-08": "First check done. Tracking normally.",
    "S-01": "Setting on cultch.",
}


def test_exact_reasons_on_the_full_seed():
    run_seed(full=True, reset=True)
    with Session(db.get_engine()) as session:
        world = load_world(session)
    for tank_id, want in REASONS.items():
        state = world.tanks[tank_id]
        got = reason_for(state.assessment, state.line_id, state.alert is not None, len(state.checks), world.cfg)
        assert got == want, tank_id
