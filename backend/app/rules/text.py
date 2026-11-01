"""Every sentence and number format the rules produce (SPEC §7.3–§7.6). Pure functions.

Say "pattern matches", never "diagnosis".
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.rules.actions import line_number
from app.rules.assess import Assessment, LineAlert
from app.rules.signals import SEVERITY_RANK, Signal

# ---------------------------------------------------------------- numbers


def round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def fmt_count(value: float | None) -> str:
    """"4.1M", "850k", "420"."""
    if value is None:
        return "—"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.1f}M"
    if abs(value) >= 1e3:
        return f"{round_half_up(value / 1e3)}k"
    return str(round_half_up(value))


def fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{round_half_up(value)}%"


def fmt_survival(value: float | None) -> str:
    return "—" if value is None else f"{round_half_up(value * 100)}%"


def fmt_trim(value: float) -> str:
    """Expected growth without a trailing ".0", so "9"."""
    return f"{value:g}"


def fmt_len(value: float | None) -> str:
    return "—" if value is None else f"{round_half_up(value)} µm"


# ---------------------------------------------------------------- times


def fmt_time(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{hour}:{moment.minute:02d} {suffix}"


def fmt_day_month(day: date) -> str:
    return f"{day.strftime('%b')} {day.day}"


def fmt_when(moment: datetime | None, now: datetime) -> str:
    """"Today, 8:40 AM", "Yesterday, 4:10 PM", "Oct 29, 2:00 PM"."""
    if moment is None:
        return "—"
    delta = (now.date() - moment.date()).days
    if delta == 0:
        return f"Today, {fmt_time(moment)}"
    if delta == 1:
        return f"Yesterday, {fmt_time(moment)}"
    return f"{fmt_day_month(moment.date())}, {fmt_time(moment)}"


def fmt_since(moment: datetime, now: datetime) -> str:
    """"today", "yesterday", a weekday within 7 days, or "Oct 24"."""
    delta = (now.date() - moment.date()).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if delta < 7:
        return moment.strftime("%A")
    return fmt_day_month(moment.date())


def fmt_clock(now: datetime) -> str:
    """"Sat, Oct 31 · 9:12 AM"."""
    return f"{now.strftime('%a')}, {fmt_day_month(now.date())} · {fmt_time(now)}"


def join_names(names: Sequence[str]) -> str:
    """"T-04 and T-05"; "T-01, T-02 and T-03"."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


# ---------------------------------------------------------------- patterns

PATTERN_TITLE = {
    "bacterial": "Pattern matches a bacterial outbreak",
    "corrosive": "Pattern matches corrosive water",
    "corrosive_early": "Water is corrosive; larvae not affected yet",
    "underfed": "Growing slower than expected",
    "splitting": "Batch is splitting into fast and slow growers",
    "temperature": "Water temperature is off target",
    "oxygen": "Oxygen is low",
    "unexplained_loss": "Fewer larvae than expected",
    "early_warning": "An early warning sign",
}

PATTERN_CHIP = {
    "bacterial": "Bacterial pattern",
    "corrosive": "Corrosive water",
    "corrosive_early": "Corrosive water",
    "underfed": "Slow growth",
    "splitting": "Size spread widening",
    "temperature": "Temperature off",
    "oxygen": "Low oxygen",
    "unexplained_loss": "Unexplained loss",
    "early_warning": "Early warning",
}

PATTERN_NOUN = {
    "bacterial": "a bacterial outbreak",
    "corrosive": "corrosive water",
    "corrosive_early": "corrosive water",
    "underfed": "underfeeding",
    "splitting": "a splitting batch",
    "temperature": "a temperature problem",
    "oxygen": "low oxygen",
    "unexplained_loss": "unexplained losses",
    "early_warning": "an early warning",
}

FORECAST = {
    "ok": "No warning signs at the last check.",
    "watch": "An early warning sign. Re-check at the next drain.",
    "risk": "Elevated chance of a crash in the next 1–3 days.",
    "critical": "High chance this batch crashes in the next 1–3 days if nothing changes.",
    "empty": "No batch in this tank.",
}


def title_for(a: Assessment) -> str:
    if a.pattern:
        return PATTERN_TITLE[a.pattern]
    if a.tank_kind == "setting":
        return "Setting"
    if a.stage == "Eyed":
        return "Ready to set"
    return "Tracking normally"


def empty_title(tank_kind: str) -> str:
    return "Empty downweller" if tank_kind == "setting" else "Empty tank"


def chip_for(pattern: str | None, line_id: str | None, line_alert_on: bool) -> str:
    if pattern is None:
        return ""
    if pattern == "corrosive_early" and line_alert_on:
        return f"On line {line_number(line_id)}"
    return PATTERN_CHIP[pattern]


# ---------------------------------------------------------------- reasons

REASON_ORDER = ("dead", "loss", "omega", "ph", "growth", "abnormal", "gut", "spread", "temp", "oxygen")
CONDITION_ORDER = ("dead", "growth", "gut", "abnormal", "spread", "omega", "ph", "temp", "oxygen")


def _by_severity(signals: Iterable[Signal], order: Sequence[str]) -> list[Signal]:
    return sorted(signals, key=lambda s: (-SEVERITY_RANK[s.severity], order.index(s.key)))


def _water_value(signal: Signal) -> str:
    return f"Ω {signal.value:.1f}" if signal.key == "omega" else f"pH {signal.value:.2f}"


def _reason_sentence(s: Signal, a: Assessment, line_id: str | None, line_alert_on: bool, cfg: Mapping) -> str:
    if s.key == "dead":
        v, p = round_half_up(s.value), s.prev
        if p is not None and s.value > p:
            return f"Dead larvae {v}%, up from {round_half_up(p)}% at the last check."
        return f"Dead larvae {v}%."
    if s.key == "loss":
        previous = a.previous
        was = previous.live_est / a.stocked if previous and previous.live_est is not None and a.stocked else 1.0
        return f"Survival fell from {round_half_up(was * 100)}% to {round_half_up((a.survival or 0) * 100)}% since the last check."
    if s.key in ("omega", "ph"):
        if line_alert_on and line_id:
            return f"Line {line_number(line_id)} water is corrosive ({_water_value(s)})."
        return f"Water is corrosive ({_water_value(s)})."
    if s.key == "growth":
        if s.severity == "critical":
            return "Growth has stalled."
        return f"Growth is {s.value:.1f} µm a day, below the {fmt_trim(cfg['expected_growth_um_day'])} expected."
    if s.key == "abnormal":
        return f"Abnormal shells are up to {round_half_up(s.value)}%."
    if s.key == "gut":
        return "Guts are nearly empty." if s.severity == "risk" else "Guts look light."
    if s.key == "spread":
        if s.prev is not None:
            return f"Size spread is widening: CV {s.value:.2f}, up from {s.prev:.2f} at the last check."
        return f"Size spread is widening: CV {s.value:.2f}."
    if s.key == "temp":
        off = abs(s.value - cfg["target_temp_c"])
        return f"Water is {s.value:.1f} °C, {off:.1f} °C off target."
    if s.key == "oxygen":
        return f"Oxygen is low ({s.value:.1f} mg/L)."
    raise KeyError(s.key)


def reason_for(a: Assessment, line_id: str | None, line_alert_on: bool, n_checks: int, cfg: Mapping) -> str:
    """One sentence or two: the first two signals by severity, then in REASON_ORDER."""
    if a.level == "ok":
        if a.tank_kind == "setting":
            return "Setting on cultch."
        if a.stage == "Eyed":
            return "Eyed larvae. Ready to move to setting in 1–2 days."
        if n_checks <= 1:
            return "First check done. Tracking normally." if n_checks == 1 else "No checks yet."
        return "Tracking normally."

    ordered = _by_severity(a.signals, REASON_ORDER)
    if a.pattern == "corrosive_early" and line_alert_on and line_id:
        water = next(s for s in ordered if s.key in ("omega", "ph"))
        return f"On line {line_number(line_id)} ({_water_value(water)}). Larvae look normal so far."

    picked: list[Signal] = []
    used_water = False
    for signal in ordered:
        if signal.key in ("omega", "ph"):
            if used_water:
                continue
            used_water = True
        picked.append(signal)
        if len(picked) == 2:
            break
    return " ".join(_reason_sentence(s, a, line_id, line_alert_on, cfg) for s in picked)


def empty_reason(status: str) -> str:
    return "Empty. Being cleaned." if status == "cleaning" else "Empty."


# ---------------------------------------------------------------- condition table

CONDITION_LABEL = {
    "dead": "Dead larvae", "growth": "Growth", "gut": "Gut fullness", "abnormal": "Abnormal shells",
    "spread": "Size spread (CV)", "omega": "Ω aragonite", "ph": "pH", "temp": "Water temperature",
    "oxygen": "Oxygen",
}


def _at_last_check(text: str | None) -> str:
    return f"{text} at last check" if text is not None else "first check"


def _condition_row(s: Signal, cfg: Mapping) -> dict:
    if s.key == "dead" or s.key == "abnormal":
        now, cmp = fmt_pct(s.value), _at_last_check(fmt_pct(s.prev) if s.prev is not None else None)
    elif s.key == "growth":
        now, cmp = f"{s.value:.1f} µm/day", f"{fmt_trim(cfg['expected_growth_um_day'])} µm/day expected"
    elif s.key == "gut" or s.key == "spread":
        now, cmp = f"{s.value:.2f}", _at_last_check(f"{s.prev:.2f}" if s.prev is not None else None)
    elif s.key == "omega":
        now, cmp = f"{s.value:.1f}", f"target ≥ {fmt_trim(cfg['omega_arag'][0])}"
    elif s.key == "ph":
        now, cmp = f"{s.value:.2f}", f"target ≥ {fmt_trim(cfg['ph'][0])}"
    elif s.key == "temp":
        now, cmp = f"{s.value:.1f} °C", f"target {fmt_trim(cfg['target_temp_c'])} °C"
    elif s.key == "oxygen":
        now, cmp = f"{s.value:.1f} mg/L", f"target ≥ {fmt_trim(cfg['do_mgl'][0])} mg/L"
    else:
        raise KeyError(s.key)
    return {"key": s.key, "label": CONDITION_LABEL[s.key], "now": now, "cmp": cmp, "severity": s.severity}


def condition_rows(a: Assessment, cfg: Mapping) -> list[dict]:
    """The inspector's Condition table, in the order of SPEC §7.5."""
    check = a.check
    if check is None:
        return []
    shown = [s for s in a.signals if s.key != "loss"]
    rows = [_condition_row(s, cfg) for s in _by_severity(shown, CONDITION_ORDER)]

    if a.pattern == "bacterial" and check.omega_arag is not None:
        rows.append({
            "key": "omega", "label": CONDITION_LABEL["omega"], "now": f"{check.omega_arag:.1f}",
            "cmp": f"target ≥ {fmt_trim(cfg['omega_arag'][0])}", "severity": "context",
        })
    if a.pattern == "corrosive_early" and check.pct_abnormal is not None:
        rows.append({
            "key": "abnormal", "label": CONDITION_LABEL["abnormal"], "now": fmt_pct(check.pct_abnormal),
            "cmp": "normal range", "severity": "context",
        })

    loss_sev = a.sev("loss")
    previous_live = a.previous.live_est if a.previous else None
    live_cmp = (
        f"{fmt_count(previous_live)} at last check"
        if loss_sev is not None and previous_live is not None
        else f"of {fmt_count(a.stocked)} stocked"
    )
    rows.append({"key": "live", "label": "Live larvae (est.)", "now": fmt_count(check.live_est), "cmp": live_cmp,
                 "severity": loss_sev})

    previous_len = a.previous.mean_len_um if a.previous else None
    if a.sev("growth") is not None and previous_len is not None:
        length_cmp = f"{round_half_up(previous_len)} µm at last check"
    elif a.growth_um_day is not None:
        length_cmp = f"growing {a.growth_um_day:.1f} µm/day"
    elif a.previous is None:
        length_cmp = "first check"
    else:
        length_cmp = "no growth rate"
    rows.append({"key": "length", "label": "Shell length", "now": fmt_len(check.mean_len_um), "cmp": length_cmp,
                 "severity": None})
    return rows


# ---------------------------------------------------------------- the Floor's words


@dataclass(frozen=True)
class TankBrief:
    """What the headline and summary need to know about a tank."""

    id: str
    level: str
    pattern: str | None
    line_id: str | None
    active: bool


def headline_for(tanks: Sequence[TankBrief]) -> str:
    urgent = sum(1 for t in tanks if t.level in ("critical", "risk"))
    if urgent == 1:
        return "1 tank needs attention now"
    if urgent > 1:
        return f"{urgent} tanks need attention now"
    watching = sum(1 for t in tanks if t.level == "watch")
    if watching == 1:
        return "1 tank on watch"
    if watching > 1:
        return f"{watching} tanks on watch"
    return "All tanks tracking normally"


def summary_for(tanks: Sequence[TankBrief], alerts: Mapping[str, LineAlert], now: datetime) -> str:
    """The Floor's summary paragraph (SPEC §7.6)."""
    sentences: list[str] = []
    for line_id in sorted(alerts):
        alert = alerts[line_id]
        on_line = [t for t in tanks if t.line_id == line_id and t.active]
        hit = [t.id for t in on_line if t.level in ("critical", "risk")]
        others = [t.id for t in on_line if t.level not in ("critical", "risk")]
        opening = f"Line {line_number(line_id)} water has been corrosive since {fmt_since(alert.since, now)}."
        verb = "is" if len(others) == 1 else "are"
        if hit and others:
            sentences.append(f"{opening} It now affects {join_names(hit)}, and {join_names(others)} {verb} on the same line.")
        elif hit:
            sentences.append(f"{opening} It now affects {join_names(hit)}.")
        elif others:
            sentences.append(f"{opening} {join_names(others)} {verb} on this line.")
        else:
            sentences.append(opening)

    after_line_sentence = bool(sentences)
    separately_used = False
    for tank in tanks:
        if tank.level not in ("critical", "risk") or tank.line_id in alerts:
            continue
        noun = PATTERN_NOUN.get(tank.pattern or "", "an early warning")
        lead = "Separately, " if after_line_sentence and not separately_used else ""
        separately_used = True
        sentences.append(f"{lead}{tank.id} shows a pattern that matches {noun}.")

    if not any(t.level in ("critical", "risk") for t in tanks):
        watching = sum(1 for t in tanks if t.level == "watch")
        if watching == 1:
            sentences.append("1 tank is on watch. Nothing needs action right now.")
        elif watching > 1:
            sentences.append(f"{watching} tanks are on watch. Nothing needs action right now.")
        else:
            sentences.append("All tanks are tracking normally.")
    return " ".join(sentences)


def next_check_text(last_check: datetime, interval_h: float, now: datetime) -> tuple[str, bool]:
    """When a tank's next check is due: a time today, "Overdue", or the day. Returns (text, overdue)."""
    due = last_check + timedelta(hours=interval_h)
    if due < now:
        return "Overdue", True
    if due.date() == now.date():
        return fmt_time(due), False
    if (due.date() - now.date()).days == 1:
        return "Tomorrow", False
    return f"{due.strftime('%a')}, {fmt_day_month(due.date())}", False
