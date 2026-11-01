"""How to carry out each recommended action, in this plant's terms. Pure functions.

A title says what to do. The text here says how, with the plant's own chemicals and this tank's numbers. Guidance
comes from FAO Fisheries Technical Paper 471 (Helm & Bourne, 2004) and Barton et al. 2015 (Oceanography 28:2). Doses
come only from rules/water.py.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.rules.actions import line_number
from app.rules.facts import TankFacts, feed_cells_per_larva_day, size_below_share
from app.rules.text import fmt_count, fmt_trim, join_names, round_half_up
from app.rules.water import BUFFERS, DISINFECTANT_LABELS, DISINFECTANTS, Dose, WaterReading, dose_for


@dataclass(frozen=True)
class Playbook:
    plant: Mapping[str, str]
    tanks: Mapping[str, TankFacts]
    water: Mapping[str, WaterReading]  # newest readings by line id, and by tank id for a tank with no line
    cfg: Mapping

    @property
    def buffer(self) -> str:
        wanted = self.plant.get("buffer", "")
        return wanted if wanted in BUFFERS else "sodium_carbonate"

    @property
    def disinfectant(self) -> str:
        wanted = self.plant.get("disinfectant", "")
        return DISINFECTANTS[wanted] if wanted in DISINFECTANTS else DISINFECTANTS["sodium_hypochlorite"]

    def free_tanks(self, kind: str) -> list[TankFacts]:
        """Tanks of this kind with no batch, emptiest state first: an empty tank is ready now, a cleaning one soon."""
        free = [t for t in self.tanks.values() if t.kind == kind and not t.active]
        return sorted(free, key=lambda t: (t.status != "empty", t.id))


def _thousands(value: float) -> str:
    return f"{round_half_up(value):,}"


def _grams(value: float) -> str:
    """Grams to a sensible precision; kilograms once it gets large."""
    if value >= 1000:
        return f"{value / 1000:.1f} kg"
    if value >= 100:
        return f"{round_half_up(value / 10) * 10:,} g"
    return f"{round_half_up(value)} g"


def _dose_view(dose: Dose, scope_tanks: list[TankFacts], book: Playbook) -> dict:
    buffer = BUFFERS[dose.buffer]
    volume = sum(t.volume_l for t in scope_tanks)
    names = [t.id for t in scope_tanks]
    basis = (
        "Estimated from pH, Ω, temperature and salinity."
        if not dose.assumed_alkalinity
        else "Estimated from one water reading and a typical alkalinity for this salinity, so measure both pH and Ω if you can."
    )
    return {
        "buffer": dose.buffer,
        "label": buffer.label,
        "per_1000l_text": f"{_grams(dose.g_per_1000l)} per 1,000 L",
        "per_1000l_g": round(dose.g_per_1000l, 1),
        "total_text": f"{_grams(dose.g_per_1000l * volume / 1000)} across {join_names(names)} ({_thousands(volume)} L)" if volume else None,
        "effect_text": f"Ω {dose.from_omega:.1f} to {dose.to_omega:.1f}, pH {dose.from_ph:.2f} to {dose.to_ph:.2f}",
        "note": f"{basis} Try it in a jar first, then re-measure 30 minutes after dosing. {buffer.handling}",
        "options": [{"key": b.key, "label": b.label} for b in BUFFERS.values()],
    }


def plant_options() -> dict:
    return {
        "buffers": [{"key": b.key, "label": b.label} for b in BUFFERS.values()],
        "disinfectants": [{"key": key, "label": label} for key, label in DISINFECTANT_LABELS.items()],
    }


def _buffer_advice(tank_id: str | None, line_id: str | None, book: Playbook) -> tuple[str | None, dict | None]:
    if line_id is not None:
        reading = book.water.get(line_id)
        scope = [t for t in book.tanks.values() if t.line_id == line_id and t.active]
        where = f"line {line_number(line_id)}"
    else:
        reading = book.water.get(tank_id or "")
        scope = [book.tanks[tank_id]] if tank_id in book.tanks else []
        where = "this tank"
    how = f"Use {BUFFERS[book.buffer].short} on {where}. Buffering buys time: also find out why the water changed."
    if reading is None:
        return how, None
    dose = dose_for(reading, book.buffer, book.cfg)
    if dose is None:
        return how, None
    return how, _dose_view(dose, scope, book)


def _feed_how(tank: TankFacts | None, book: Playbook) -> str:
    base = "Count the feed and check the algae cultures for contamination."
    if tank is None:
        return base
    cells = feed_cells_per_larva_day(tank.length_um, book.cfg)
    if cells is None:
        return base
    rounded = round_half_up(cells / 100) * 100
    guide = f"FAO's guide at {round_half_up(tank.length_um)} µm is about {rounded:,} cells per larva a day"
    if tank.live and tank.volume_l:
        per_ul = cells * tank.live / (tank.volume_l * 1e6)
        guide += f", or about {round_half_up(per_ul)} cells per µL in this tank"
    return f"{guide}. {base} Raise the ration in steps: overfeeding does more harm than underfeeding."


def _screen_how(tank: TankFacts | None, book: Playbook) -> str:
    base = "Wash the batch through a stack of sieves at the next drain, and discard the fractions that are mostly dead or slow."
    if tank is None:
        return base
    share = book.cfg["cull_quantile"]
    cutoff = size_below_share(tank.hist, share)
    if cutoff is None:
        return base
    return f"{base} In the last sample, {round_half_up(share * 100)}% measured under {round_half_up(cutoff)} µm."


def _move_how(tank: TankFacts | None, book: Playbook) -> str:
    mesh = book.cfg["grade_mesh_um"]
    density = book.cfg["setting_density_per_l"]
    base = f"Grade on a {mesh} µm mesh and move what stays on it. Leave the rest to grow on."
    free = book.free_tanks("setting")
    if not free:
        return f"{base} No setting tank is free yet, so clear one first."
    target = free[0]
    capacity = target.volume_l * density
    ready = "is empty" if target.status != "cleaning" else "is free once it's clean"
    return f"{base} {target.id} {ready} and takes about {fmt_count(capacity)} at {_thousands(density)} larvae per L."


def _split_how(tank: TankFacts | None, book: Playbook) -> str:
    free = book.free_tanks("larval")
    if tank is None or not free or tank.live is None:
        return "No larval tank is free yet. Plan the split for the next one that comes clean."
    target = free[0]
    when = "once it's clean" if target.status == "cleaning" else "now"
    after = tank.live / (tank.volume_l + target.volume_l)
    return f"Use {target.id} {when}. That takes both tanks to about {_thousands(after)} larvae per L."


def _temp_how(tank: TankFacts | None, book: Playbook) -> str:
    target = f"Target is {fmt_trim(book.cfg['target_temp_c'])} °C"
    latest = tank.latest if tank else None
    if latest is not None and latest.temp_c is not None:
        target += f", and this tank last read {latest.temp_c:.1f} °C"
    return f"{target}. Bring it back over a few hours rather than all at once."


def advice_for(action: str, tank_id: str | None, line_id: str | None, book: Playbook | None) -> tuple[str | None, dict | None]:
    """The (how, dose) for one recommended action. Dose is set only for buffering."""
    if book is None:
        return None, None
    tank = book.tanks.get(tank_id or "")
    if action in ("buffer_line", "buffer_tank"):
        return _buffer_advice(tank_id, line_id, book)
    if action == "isolate":
        return f"Work this tank last each day and keep its gear apart. Clean anything shared with {book.disinfectant}.", None
    if action == "sample_vibrio":
        return "Plate on TCBS and read at 24 hours. Compare with a healthy tank: a jump in colonies supports this pattern.", None
    if action == "restock":
        return f"Wash the survivors on a sieve, clean the tank with {book.disinfectant}, rinse well, and refill from treated water.", None
    if action == "discard":
        return f"Clean the tank and its gear with {book.disinfectant} before anything else goes in.", None
    if action == "hold_spawn":
        return "If you must spawn, use a tank on a healthy line and afternoon water, when pH and oxygen usually peak.", None
    if action == "screen":
        return _screen_how(tank, book), None
    if action == "feed_check":
        return _feed_how(tank, book), None
    if action == "recount":
        return "Mix the drain bucket well, then count two slides from the middle of it. One slide can mislead.", None
    if action == "temp_check":
        return _temp_how(tank, book), None
    if action == "aerate":
        minimum = fmt_trim(book.cfg["do_mgl"][0])
        return f"Aim for at least {minimum} mg/L. Check the blower and air lines first, and keep the bubbling gentle.", None
    if action == "move_to_setting":
        return _move_how(tank, book), None
    if action == "split_tank":
        return _split_how(tank, book), None
    if action == "review_handling":
        return "Compare drain timing, ration and sieve sizes with the best batch on this line.", None
    return None, None
