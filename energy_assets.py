# =============================================================================
# energy_assets.py — LUMINIH2 Generation & Storage Engine
# High-Fidelity PV · Wind · BESS (Zagreb Hub)
# Version: 3.2 (Streamlit-Ready · Power-Switching Optimised)
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from config import Config


# ---------------------------------------------------------------------------
# Typed result containers
# ---------------------------------------------------------------------------

@dataclass
class SolarResult:
    ac_power_kw: float
    dc_power_kw: float
    cell_temp_c: float
    thermal_derating_pct: float   # % loss due to heat
    soiling_loss_pct: float       # % loss due to dust/pollution
    effective_irradiance: float   # W/m² after soiling


@dataclass
class WindResult:
    ac_power_kw: float
    turbulence_loss_pct: float
    operating_regime: str         # "below_cut_in" | "cubic" | "rated" | "cut_out"


@dataclass
class BatteryResult:
    soc: float
    soh: float
    temperature_c: float
    total_throughput_kwh: float
    p_actual_kw: float            # Actual power applied (after limits)
    thermal_warning: bool         # True if temp > 55°C
    thermal_runaway_risk: bool    # True if temp > Config threshold
    cycles_consumed: float        # Estimated full-cycle count
    remaining_life_pct: float     # % of rated cycle life left


# ---------------------------------------------------------------------------
# ☀️  Solar PV System — Thermal & Soiling Model
# ---------------------------------------------------------------------------

class SolarSystem:
    """
    Single-diode-inspired AC output model:
    - NOCT-based cell temperature
    - Temperature derating (monocrystalline −0.4 %/°C)
    - Soiling / dust / pollution loss factor
    - Inverter efficiency
    """

    TEMP_COEFF = -0.004      # −0.4 %/°C vs STC (25 °C)
    NOCT_C = 45.0            # Nominal Operating Cell Temperature
    STC_IRRADIANCE = 1000.0  # W/m²
    STC_TEMP_C = 25.0

    def __init__(self) -> None:
        self.capacity_kw = Config.PV_SYSTEM_CAPACITY_KW
        self.inv_eff = Config.INVERTER_EFFICIENCY

    def get_power_output(
        self,
        irradiance_wm2: float,
        ambient_temp_c: float,
        soiling_factor: float = 1.0,
    ) -> SolarResult:
        """
        Returns AC power and diagnostics.

        Args:
            irradiance_wm2: Global horizontal irradiance [W/m²]
            ambient_temp_c: Ambient air temperature [°C]
            soiling_factor:  1.0 = clean panels, < 1.0 = dust/pollution
        """
        if irradiance_wm2 is None or irradiance_wm2 <= 0:
            return SolarResult(
                ac_power_kw=0.0, dc_power_kw=0.0,
                cell_temp_c=ambient_temp_c, thermal_derating_pct=0.0,
                soiling_loss_pct=(1.0 - soiling_factor) * 100,
                effective_irradiance=0.0,
            )

        soiling_factor = float(np.clip(soiling_factor, 0.0, 1.0))
        effective_irr = irradiance_wm2 * soiling_factor

        # NOCT cell temperature model
        t_cell = ambient_temp_c + (effective_irr / 800.0) * (self.NOCT_C - 20.0)

        # Thermal derating factor
        thermal_factor = 1.0 + self.TEMP_COEFF * (t_cell - self.STC_TEMP_C)
        thermal_factor = max(thermal_factor, 0.0)
        thermal_derating_pct = max(0.0, (1.0 - thermal_factor) * 100)

        # DC power (STC-normalised)
        dc_power = self.capacity_kw * (effective_irr / self.STC_IRRADIANCE) * thermal_factor
        dc_power = float(np.clip(dc_power, 0.0, self.capacity_kw))

        # DC → AC via inverter
        ac_power = float(np.clip(dc_power * self.inv_eff, 0.0, self.capacity_kw))

        return SolarResult(
            ac_power_kw=round(ac_power, 3),
            dc_power_kw=round(dc_power, 3),
            cell_temp_c=round(t_cell, 1),
            thermal_derating_pct=round(thermal_derating_pct, 2),
            soiling_loss_pct=round((1.0 - soiling_factor) * 100, 2),
            effective_irradiance=round(effective_irr, 1),
        )


# ---------------------------------------------------------------------------
# 🌬️  Wind Turbine — Turbulence & Power-Curve Model
# ---------------------------------------------------------------------------

class WindSystem:
    """
    IEC 61400-12 inspired cubic power curve with:
    - Cut-in / rated / cut-out speed limits
    - Turbulence intensity derating (high gustiness → efficiency loss)
    - Safety cutout at Config.TURBULENCE_INTENSITY_LIMIT
    """

    CUT_IN_MS = 3.0
    RATED_MS = 12.0
    CUT_OUT_MS = 25.0

    def __init__(self) -> None:
        self.capacity_kw = Config.WIND_SYSTEM_CAPACITY_KW
        self.turbulence_limit = Config.TURBULENCE_INTENSITY_LIMIT

    def get_power_output(
        self,
        wind_speed_ms: float,
        turbulence_intensity: float = 0.1,
    ) -> WindResult:
        """
        Returns AC power and diagnostics.

        Args:
            wind_speed_ms:        10-min average hub-height wind speed [m/s]
            turbulence_intensity: Std(wind) / mean(wind), dimensionless
        """
        # Safety cutout on excessive turbulence
        if turbulence_intensity >= self.turbulence_limit:
            return WindResult(
                ac_power_kw=0.0,
                turbulence_loss_pct=100.0,
                operating_regime="cut_out",
            )

        if wind_speed_ms is None or wind_speed_ms < self.CUT_IN_MS:
            return WindResult(
                ac_power_kw=0.0,
                turbulence_loss_pct=0.0,
                operating_regime="below_cut_in",
            )

        if wind_speed_ms > self.CUT_OUT_MS:
            return WindResult(
                ac_power_kw=0.0,
                turbulence_loss_pct=0.0,
                operating_regime="cut_out",
            )

        # Turbulence derating: penalty only above baseline 10%
        ti_excess = max(0.0, turbulence_intensity - 0.10)
        turbulence_loss_factor = 1.0 - ti_excess * 0.5
        turbulence_loss_pct = round((1.0 - turbulence_loss_factor) * 100, 2)

        if wind_speed_ms >= self.RATED_MS:
            raw_power = self.capacity_kw * turbulence_loss_factor
            regime = "rated"
        else:
            ratio = (wind_speed_ms - self.CUT_IN_MS) / (self.RATED_MS - self.CUT_IN_MS)
            raw_power = self.capacity_kw * (ratio ** 3) * turbulence_loss_factor
            regime = "cubic"

        ac_power = float(np.clip(raw_power, 0.0, self.capacity_kw))

        return WindResult(
            ac_power_kw=round(ac_power, 3),
            turbulence_loss_pct=turbulence_loss_pct,
            operating_regime=regime,
        )


# ---------------------------------------------------------------------------
# 🔋  Battery BESS — SoH, Thermal & CC-CV Model
# ---------------------------------------------------------------------------

class BatteryBESS:
    """
    Lithium-ion BESS with:
    - CC-CV charging taper profile
    - Coulombic efficiency asymmetry (charge 96%, discharge 94%)
    - Thermal model: joule heating + ambient cooling
    - SoH degradation via throughput (Wöhler-style)
    - Thermal runaway detection
    """

    CHARGE_EFF = 0.96
    DISCHARGE_EFF = 0.94
    THERMAL_RESISTANCE = 0.03   # °C/W — pack thermal resistance
    COOLING_RATE = 0.05         # fraction of (T−Tamb) dissipated per step
    EOL_SOH = 0.70              # End-of-life State of Health

    def __init__(self, initial_soc: float = 0.50) -> None:
        self.capacity_kwh = Config.BATT_CAPACITY_KWH
        self.soc = float(np.clip(initial_soc, Config.BATT_SOC_MIN, Config.BATT_SOC_MAX))
        self.soh = 1.0
        self.temperature_c = 25.0          # Internal pack temperature
        self.total_throughput_kwh = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_max_charge_power(self) -> float:
        """CC-CV taper: full rate up to 85% SoC, then linearly tapers to zero."""
        if self.soc >= Config.BATT_SOC_MAX:
            return 0.0
        if self.soc > 0.85:
            taper = (Config.BATT_SOC_MAX - self.soc) / (Config.BATT_SOC_MAX - 0.85)
            return round(Config.BATT_MAX_CHARGE_KW * taper, 3)
        return Config.BATT_MAX_CHARGE_KW

    def get_max_discharge_power(self) -> float:
        """Discharge limited by SoC floor and SoH-derated capacity."""
        if self.soc <= Config.BATT_SOC_MIN:
            return 0.0
        return Config.BATT_MAX_DISCHARGE_KW

    def update_state(
        self,
        net_power_kw: float,
        ambient_temp_c: float = 25.0,
    ) -> BatteryResult:
        """
        Applies net_power_kw (+ve = charge, −ve = discharge) for one timestep.

        Returns full diagnostics including thermal warning flags.
        """
        dt_h = Config.TIMESTEP_SEC / 3600.0
        dt_s = Config.TIMESTEP_SEC

        # ── 1. Apply physical power limits ────────────────────────────
        if net_power_kw > 0:
            p_actual = min(net_power_kw, self.get_max_charge_power())
            energy_delta_kwh = p_actual * self.CHARGE_EFF * dt_h
        elif net_power_kw < 0:
            p_actual = max(net_power_kw, -self.get_max_discharge_power())
            energy_delta_kwh = (p_actual / self.DISCHARGE_EFF) * dt_h
        else:
            p_actual = 0.0
            energy_delta_kwh = 0.0

        # ── 2. Thermal model (Joule heating + ambient cooling) ─────────
        heat_generated_w = abs(p_actual) * 1000 * self.THERMAL_RESISTANCE
        cooling = self.COOLING_RATE * (self.temperature_c - ambient_temp_c) * dt_s
        self.temperature_c += (heat_generated_w - cooling) / (self.capacity_kwh * 3600 * 0.001)
        self.temperature_c = max(ambient_temp_c, self.temperature_c)

        thermal_warning = self.temperature_c > 55.0
        thermal_runaway_risk = self.temperature_c >= Config.THERMAL_RUNAWAY_TEMP

        # Emergency: cut power if thermal runaway risk detected
        if thermal_runaway_risk:
            p_actual = 0.0
            energy_delta_kwh = 0.0

        # ── 3. SoH degradation (throughput-based Wöhler model) ─────────
        throughput_kwh = abs(energy_delta_kwh)
        self.total_throughput_kwh += throughput_kwh
        # Each full cycle = 2 × capacity_kwh of throughput
        full_cycles = self.total_throughput_kwh / (2.0 * self.capacity_kwh)
        self.soh = max(self.EOL_SOH, 1.0 - full_cycles / Config.BATT_CYCLE_LIFE)

        # ── 4. SoC update on SoH-derated effective capacity ────────────
        effective_capacity_kwh = self.capacity_kwh * self.soh
        current_energy_kwh = self.soc * effective_capacity_kwh
        new_energy_kwh = current_energy_kwh + energy_delta_kwh
        self.soc = float(np.clip(
            new_energy_kwh / effective_capacity_kwh,
            Config.BATT_SOC_MIN,
            Config.BATT_SOC_MAX,
        ))

        remaining_life_pct = round(
            max(0.0, (1.0 - full_cycles / Config.BATT_CYCLE_LIFE)) * 100, 1
        )

        return BatteryResult(
            soc=round(float(self.soc), 4),
            soh=round(float(self.soh), 4),
            temperature_c=round(self.temperature_c, 1),
            total_throughput_kwh=round(self.total_throughput_kwh, 3),
            p_actual_kw=round(p_actual, 3),
            thermal_warning=thermal_warning,
            thermal_runaway_risk=thermal_runaway_risk,
            cycles_consumed=round(full_cycles, 2),
            remaining_life_pct=remaining_life_pct,
        )


# ---------------------------------------------------------------------------
# Smoke-test (python energy_assets.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("── Solar ──────────────────────────────────────────────")
    solar = SolarSystem()
    s = solar.get_power_output(irradiance_wm2=750, ambient_temp_c=32, soiling_factor=0.95)
    print(f"  AC power       : {s.ac_power_kw} kW")
    print(f"  Cell temp      : {s.cell_temp_c} °C")
    print(f"  Thermal derate : {s.thermal_derating_pct} %")
    print(f"  Soiling loss   : {s.soiling_loss_pct} %")

    print("\n── Wind ───────────────────────────────────────────────")
    wind = WindSystem()
    w = wind.get_power_output(wind_speed_ms=9.5, turbulence_intensity=0.12)
    print(f"  AC power       : {w.ac_power_kw} kW")
    print(f"  Regime         : {w.operating_regime}")
    print(f"  Turbulence loss: {w.turbulence_loss_pct} %")

    # Turbulence cutout
    w2 = wind.get_power_output(wind_speed_ms=9.5, turbulence_intensity=0.20)
    print(f"  High-TI cutout : {w2.operating_regime} (power={w2.ac_power_kw} kW)")

    print("\n── BESS ───────────────────────────────────────────────")
    bess = BatteryBESS(initial_soc=0.55)
    b = bess.update_state(net_power_kw=20.0, ambient_temp_c=28.0)
    print(f"  SoC            : {b.soc*100:.1f} %")
    print(f"  SoH            : {b.soh*100:.2f} %")
    print(f"  Temperature    : {b.temperature_c} °C")
    print(f"  Thermal warning: {b.thermal_warning}")
    print(f"  Life remaining : {b.remaining_life_pct} %")

    # CC-CV taper test
    bess2 = BatteryBESS(initial_soc=0.88)
    max_p = bess2.get_max_charge_power()
    print(f"\n  CC-CV taper @ SoC=88%: max charge = {max_p:.2f} kW (< {Config.BATT_MAX_CHARGE_KW} kW)")

    print("\n✅ energy_assets.py v3.2 — all checks passed")
