"""Seawater carbonate chemistry and buffer doses. Pure functions.

Doses always come from here, never from Claude. Constants are the ones in the DOE best-practices guide
(Dickson et al. 2007): K1 and K2 from Lueker et al. 2000, KB from Dickson 1990, KW from Millero 1995, aragonite
solubility from Mucci 1983. Concentrations are mol/kg of seawater, and pH is on the total scale.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Buffer:
    key: str
    label: str
    short: str
    molar_mass: float  # g/mol
    alkalinity_per_mol: float
    carbon_per_mol: float
    handling: str


BUFFERS: dict[str, Buffer] = {
    "sodium_carbonate": Buffer(
        "sodium_carbonate", "Sodium carbonate (soda ash)", "sodium carbonate", 105.99, 2.0, 1.0,
        "Dissolve it fully in a bucket of line water first, and add it upstream of the tanks.",
    ),
    "sodium_hydroxide": Buffer(
        "sodium_hydroxide", "Sodium hydroxide (caustic soda)", "sodium hydroxide", 40.00, 1.0, 0.0,
        "Caustic. Dilute it first and dose slowly upstream of the tanks: a local pH spike can kill larvae.",
    ),
    "sodium_bicarbonate": Buffer(
        "sodium_bicarbonate", "Sodium bicarbonate (baking soda)", "sodium bicarbonate", 84.01, 1.0, 1.0,
        "Takes far more product than carbonate, because it adds carbon as well as alkalinity.",
    ),
}

DISINFECTANTS: dict[str, str] = {
    "sodium_hypochlorite": "sodium hypochlorite",
    "peracetic_acid": "peracetic acid",
    "hydrogen_peroxide": "hydrogen peroxide",
}
DISINFECTANT_LABELS: dict[str, str] = {
    "sodium_hypochlorite": "Sodium hypochlorite (bleach)",
    "peracetic_acid": "Peracetic acid",
    "hydrogen_peroxide": "Hydrogen peroxide",
}

_PH_LOW, _PH_HIGH = 5.0, 11.0
_MAX_ADDED_MOL_KG = 0.05  # far beyond any real dose: past this, the target can't be reached with this product
_BISECTION_STEPS = 80


@dataclass(frozen=True)
class Constants:
    k1: float
    k2: float
    kb: float
    kw: float
    ksp_aragonite: float
    total_boron: float
    calcium: float


def constants(temp_c: float, salinity_ppt: float) -> Constants:
    t = temp_c + 273.15
    s = salinity_ppt
    root_s = math.sqrt(s)
    log_t = math.log(t)
    pk1 = 3633.86 / t - 61.2172 + 9.67770 * log_t - 0.011555 * s + 0.0001152 * s * s
    pk2 = 471.78 / t + 25.9290 - 3.16967 * log_t - 0.01781 * s + 0.0001122 * s * s
    ln_kb = (
        (-8966.90 - 2890.53 * root_s - 77.942 * s + 1.728 * s * root_s - 0.0996 * s * s) / t
        + 148.0248 + 137.1942 * root_s + 1.62142 * s
        - (24.4344 + 25.085 * root_s + 0.2474 * s) * log_t
        + 0.053105 * root_s * t
    )
    ln_kw = 148.96502 - 13847.26 / t - 23.6521 * log_t + (118.67 / t - 5.977 + 1.0495 * log_t) * root_s - 0.01615 * s
    log_ksp = (
        -171.945 - 0.077993 * t + 2903.293 / t + 71.595 * math.log10(t)
        + (-0.068393 + 0.0017276 * t + 88.135 / t) * root_s
        - 0.10018 * s + 0.0059415 * s * root_s
    )
    return Constants(
        k1=10.0 ** -pk1, k2=10.0 ** -pk2, kb=math.exp(ln_kb), kw=math.exp(ln_kw), ksp_aragonite=10.0 ** log_ksp,
        total_boron=0.000416 * s / 35.0, calcium=0.0102821 * s / 35.0,
    )


def _carbonate_ion(ph: float, dic: float, k: Constants) -> float:
    h = 10.0 ** -ph
    return dic * k.k1 * k.k2 / (h * h + k.k1 * h + k.k1 * k.k2)


def _alkalinity(ph: float, dic: float, k: Constants) -> float:
    h = 10.0 ** -ph
    denominator = h * h + k.k1 * h + k.k1 * k.k2
    bicarbonate = dic * k.k1 * h / denominator
    carbonate = dic * k.k1 * k.k2 / denominator
    borate = k.total_boron * k.kb / (k.kb + h)
    return bicarbonate + 2.0 * carbonate + borate + k.kw / h - h


def omega_from(ph: float, dic: float, k: Constants) -> float:
    return _carbonate_ion(ph, dic, k) * k.calcium / k.ksp_aragonite


def ph_from(alkalinity: float, dic: float, k: Constants) -> float:
    """Alkalinity rises with pH, so bisection is safe."""
    low, high = _PH_LOW, _PH_HIGH
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2.0
        if _alkalinity(middle, dic, k) < alkalinity:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def _dic_from_ph_omega(ph: float, omega: float, k: Constants) -> float:
    h = 10.0 ** -ph
    carbonate = omega * k.ksp_aragonite / k.calcium
    bicarbonate = h * carbonate / k.k2
    carbon_dioxide = h * bicarbonate / k.k1
    return carbon_dioxide + bicarbonate + carbonate


def _dic_from_alkalinity_ph(alkalinity: float, ph: float, k: Constants) -> float:
    """Alkalinity is linear in DIC at a fixed pH."""
    at_zero = _alkalinity(ph, 0.0, k)
    per_dic = _alkalinity(ph, 1.0, k) - at_zero
    return (alkalinity - at_zero) / per_dic


def _dic_from_alkalinity_omega(alkalinity: float, omega: float, k: Constants) -> float | None:
    """Find the pH at which this alkalinity gives this Ω. Ω rises with pH at a fixed alkalinity."""
    low, high = _PH_LOW, _PH_HIGH
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2.0
        dic = _dic_from_alkalinity_ph(alkalinity, middle, k)
        if dic <= 0 or omega_from(middle, dic, k) > omega:
            high = middle
        else:
            low = middle
    dic = _dic_from_alkalinity_ph(alkalinity, low, k)
    return dic if dic > 0 else None


@dataclass(frozen=True)
class WaterReading:
    temp_c: float | None = None
    salinity_ppt: float | None = None
    ph: float | None = None
    omega_arag: float | None = None


@dataclass(frozen=True)
class Dose:
    buffer: str
    added_mol_kg: float
    g_per_1000l: float
    from_omega: float
    to_omega: float
    from_ph: float
    to_ph: float
    assumed_alkalinity: bool  # True when only one of pH and Ω was measured


def _within(value: float | None, limits: tuple[float, float]) -> bool:
    return value is None or limits[0] <= value <= limits[1]


def dose_for(reading: WaterReading, buffer_key: str, cfg: Mapping) -> Dose | None:
    """How much of this product lifts this water to the target Ω. None when it can't be worked out or isn't needed.

    A check can hold any number a tech typed. One that isn't plausible seawater gives no dose, rather than a wrong one.
    """
    buffer = BUFFERS[buffer_key]
    if reading.ph is None and reading.omega_arag is None:
        return None
    temp_c = reading.temp_c if reading.temp_c is not None else cfg["target_temp_c"]
    salinity = reading.salinity_ppt if reading.salinity_ppt is not None else cfg["default_salinity_ppt"]
    plausible = (
        _within(salinity, cfg["dose_valid_salinity_ppt"]) and _within(temp_c, cfg["dose_valid_temp_c"])
        and _within(reading.ph, cfg["dose_valid_ph"]) and _within(reading.omega_arag, cfg["dose_valid_omega"])
    )
    if not plausible:
        return None
    k = constants(temp_c, salinity)

    assumed = reading.ph is None or reading.omega_arag is None
    if not assumed:
        dic = _dic_from_ph_omega(reading.ph, reading.omega_arag, k)
        alkalinity = _alkalinity(reading.ph, dic, k)
    else:
        alkalinity = cfg["assumed_alkalinity_umol_kg_at_35"] * 1e-6 * salinity / 35.0
        if reading.ph is not None:
            dic = _dic_from_alkalinity_ph(alkalinity, reading.ph, k)
        else:
            dic = _dic_from_alkalinity_omega(alkalinity, reading.omega_arag, k)
            if dic is None:
                return None

    from_ph = ph_from(alkalinity, dic, k)
    from_omega = omega_from(from_ph, dic, k)
    target = cfg["buffer_target_omega"]
    if from_omega >= target:
        return None

    def omega_after(added: float) -> float:
        new_alkalinity = alkalinity + buffer.alkalinity_per_mol * added
        new_dic = dic + buffer.carbon_per_mol * added
        return omega_from(ph_from(new_alkalinity, new_dic, k), new_dic, k)

    if omega_after(_MAX_ADDED_MOL_KG) < target:
        return None
    low, high = 0.0, _MAX_ADDED_MOL_KG
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2.0
        if omega_after(middle) < target:
            low = middle
        else:
            high = middle
    added = high
    density_kg_per_l = 1.0 + 0.00076 * salinity
    new_alkalinity = alkalinity + buffer.alkalinity_per_mol * added
    new_dic = dic + buffer.carbon_per_mol * added
    return Dose(
        buffer=buffer_key,
        added_mol_kg=added,
        g_per_1000l=added * buffer.molar_mass * density_kg_per_l * 1000.0,
        from_omega=from_omega,
        to_omega=omega_after(added),
        from_ph=from_ph,
        to_ph=ph_from(new_alkalinity, new_dic, k),
        assumed_alkalinity=assumed,
    )
