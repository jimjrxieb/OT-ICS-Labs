#!/usr/bin/env python3
"""Psychrometric primitives for the Building 822 model.

US customary units, sea-level pressure, standard library only. Teaching-grade:
accurate to roughly 1% against ASHRAE tables over the range this lab uses
(40-110 F), which is far tighter than the model's other assumptions.
"""

from __future__ import annotations

import math
import sys

P_ATM_PSIA = 14.696


def _f_to_c(t_f: float) -> float:
    return (t_f - 32.0) * 5.0 / 9.0


def _c_to_f(t_c: float) -> float:
    return t_c * 9.0 / 5.0 + 32.0


def sat_pressure_psia(t_f: float) -> float:
    """Saturation vapor pressure, psia. Magnus formula.

    Celsius appears only inside this function because the Magnus coefficients
    are defined in Celsius. Everything else in this codebase is Fahrenheit.
    """
    t_c = _f_to_c(t_f)
    kpa = 0.61078 * math.exp(17.27 * t_c / (t_c + 237.3))
    return kpa * 0.145038


def humidity_ratio(t_f: float, rh_pct: float) -> float:
    """Humidity ratio W, lb moisture per lb dry air."""
    rh = max(0.0, min(100.0, rh_pct))
    pv = min(rh / 100.0 * sat_pressure_psia(t_f), P_ATM_PSIA * 0.99)
    return 0.621945 * pv / (P_ATM_PSIA - pv)


def humidity_ratio_saturated(t_f: float) -> float:
    """W at saturation for a given dry bulb — used for apparatus dew point."""
    return humidity_ratio(t_f, 100.0)


def rh_from_w(t_f: float, w: float) -> float:
    """Relative humidity percent from dry bulb and humidity ratio."""
    w = max(0.0, w)
    pv = P_ATM_PSIA * w / (0.621945 + w)
    return max(0.0, min(100.0, 100.0 * pv / sat_pressure_psia(t_f)))


def enthalpy(t_f: float, w: float) -> float:
    """Moist air enthalpy, Btu per lb dry air."""
    return 0.240 * t_f + w * (1061.0 + 0.444 * t_f)


def dew_point(t_f: float, rh_pct: float) -> float:
    """Dew point temperature, F. Inverse Magnus."""
    pv_kpa = (max(1e-6, rh_pct) / 100.0 * sat_pressure_psia(t_f)) / 0.145038
    ln_ratio = math.log(pv_kpa / 0.61078)
    return _c_to_f(237.3 * ln_ratio / (17.27 - ln_ratio))


def self_test() -> int:
    """Verify against published ASHRAE psychrometric values at sea level."""
    cases = [
        # (dry bulb F, RH %, expected W, expected h, expected dew point F)
        (80.0, 50.0, 0.0110, 31.5, 59.7),
        (75.0, 50.0, 0.00927, 28.1, 55.1),
        (95.0, 60.0, 0.0215, 46.3, 79.4),
    ]
    for t, rh, w_exp, h_exp, dp_exp in cases:
        w = humidity_ratio(t, rh)
        assert abs(w - w_exp) < 0.0005, f"W at {t}F/{rh}%: {w:.5f} vs {w_exp}"
        assert abs(enthalpy(t, w) - h_exp) < 0.5, f"h at {t}F/{rh}%"
        assert abs(dew_point(t, rh) - dp_exp) < 1.0, f"DP at {t}F/{rh}%"
        assert abs(rh_from_w(t, w) - rh) < 0.5, f"RH round-trip at {t}F"

    # Monotonicity — these must hold everywhere, not just at the sample points.
    assert sat_pressure_psia(90.0) > sat_pressure_psia(70.0)
    assert humidity_ratio(80.0, 80.0) > humidity_ratio(80.0, 40.0)
    assert humidity_ratio_saturated(60.0) > humidity_ratio_saturated(45.0)
    assert enthalpy(80.0, 0.012) > enthalpy(80.0, 0.008)

    # Guard rails
    assert rh_from_w(75.0, 0.0) == 0.0
    assert humidity_ratio(75.0, 0.0) == 0.0
    assert 0.0 <= rh_from_w(50.0, 0.050) <= 100.0, "RH must clamp, not exceed 100"

    print("SELF-TEST PASS (psychro: 3 ASHRAE cases, monotonicity, guard rails)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
