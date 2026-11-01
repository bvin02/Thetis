"""Seawater chemistry and buffer doses. The reference values are from the DOE best-practices guide (Dickson et al. 2007)."""
from __future__ import annotations

import math

import pytest

from app.config import DEFAULTS
from app.rules.water import BUFFERS, WaterReading, constants, dose_for, omega_from, ph_from


def test_constants_match_the_published_check_values():
    k = constants(25.0, 35.0)
    assert -math.log10(k.k1) == pytest.approx(5.8472, abs=0.0005)
    assert -math.log10(k.k2) == pytest.approx(8.9660, abs=0.0005)
    assert math.log(k.kb) == pytest.approx(-19.7964, abs=0.0005)
    assert math.log(k.kw) == pytest.approx(-30.434, abs=0.005)
    assert math.log10(k.ksp_aragonite) == pytest.approx(-6.19, abs=0.01)


def test_reference_seawater():
    """Typical surface seawater: alkalinity 2300, DIC 2000 µmol/kg, 25 °C, salinity 35."""
    k = constants(25.0, 35.0)
    ph = ph_from(2300e-6, 2000e-6, k)
    assert ph == pytest.approx(8.05, abs=0.03)
    assert omega_from(ph, 2000e-6, k) == pytest.approx(3.4, abs=0.2)


LINE2 = WaterReading(temp_c=25.2, salinity_ppt=29.0, ph=7.62, omega_arag=1.4)


def test_dose_reaches_the_target_from_the_measured_water():
    dose = dose_for(LINE2, "sodium_carbonate", DEFAULTS)
    assert dose is not None
    assert dose.from_omega == pytest.approx(1.4, abs=0.001)
    assert dose.from_ph == pytest.approx(7.62, abs=0.001)
    assert dose.to_omega == pytest.approx(DEFAULTS["buffer_target_omega"], abs=0.001)
    assert dose.to_ph > dose.from_ph
    assert dose.assumed_alkalinity is False
    # The same order as the one published figure we found: 31 g per 1,000 L of Na2CO3 in a 2025 Eastern oyster study
    assert 5 < dose.g_per_1000l < 60


def test_each_product_has_its_own_dose_and_the_chemistry_behind_it():
    carbonate = dose_for(LINE2, "sodium_carbonate", DEFAULTS)
    hydroxide = dose_for(LINE2, "sodium_hydroxide", DEFAULTS)
    bicarbonate = dose_for(LINE2, "sodium_bicarbonate", DEFAULTS)
    assert hydroxide.g_per_1000l < carbonate.g_per_1000l < bicarbonate.g_per_1000l
    assert hydroxide.to_ph > carbonate.to_ph  # hydroxide adds no carbon
    assert bicarbonate.to_ph < bicarbonate.from_ph  # bicarbonate lifts Ω by adding carbon, and doesn't fix pH
    assert bicarbonate.g_per_1000l > 10 * carbonate.g_per_1000l


def test_worse_water_takes_more():
    worse = dose_for(WaterReading(25.2, 29.0, 7.5, 1.1), "sodium_carbonate", DEFAULTS)
    assert worse.g_per_1000l > dose_for(LINE2, "sodium_carbonate", DEFAULTS).g_per_1000l


@pytest.mark.parametrize("reading", [WaterReading(25.2, 29.0, 7.62, None), WaterReading(25.2, 29.0, None, 1.4)])
def test_one_reading_still_gives_a_dose_but_says_so(reading):
    dose = dose_for(reading, "sodium_carbonate", DEFAULTS)
    assert dose is not None and dose.assumed_alkalinity is True
    assert dose.to_omega == pytest.approx(DEFAULTS["buffer_target_omega"], abs=0.001)


def test_no_dose_without_a_reading_or_when_water_is_already_fine():
    assert dose_for(WaterReading(25.0, 29.0, None, None), "sodium_carbonate", DEFAULTS) is None
    assert dose_for(WaterReading(25.0, 29.0, 8.2, 3.5), "sodium_carbonate", DEFAULTS) is None


def test_missing_temperature_and_salinity_use_the_settings():
    assert dose_for(WaterReading(None, None, 7.62, 1.4), "sodium_carbonate", DEFAULTS) is not None


def test_an_unreachable_target_gives_no_dose_rather_than_a_wrong_one():
    assert dose_for(LINE2, "sodium_bicarbonate", {**DEFAULTS, "buffer_target_omega": 500.0}) is None


def test_every_product_is_described():
    for buffer in BUFFERS.values():
        assert buffer.label and buffer.short and buffer.handling and buffer.molar_mass > 0


@pytest.mark.parametrize("reading", [
    WaterReading(25.0, 0.0, 7.6, 1.4),  # a salinity of 0 passes the check form
    WaterReading(25.0, 60.0, 7.6, 1.4),
    WaterReading(60.0, 29.0, 7.6, 1.4),
    WaterReading(25.0, 29.0, 0.0, 1.4),
    WaterReading(25.0, 29.0, 14.0, None),
    WaterReading(25.0, 29.0, 7.6, 0.0),
    WaterReading(25.0, 29.0, None, 0.0),
])
def test_a_reading_that_isnt_plausible_seawater_gives_no_dose_and_no_crash(reading):
    for buffer in BUFFERS:
        assert dose_for(reading, buffer, DEFAULTS) is None

