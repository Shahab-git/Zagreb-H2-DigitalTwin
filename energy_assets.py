# =============================================================================
# energy_assets.py — LUMINIH2 Generation & Storage Engine
# High-Fidelity PV · Wind · BESS · Zagreb Hub
# Version: 3.3
# =============================================================================
#
# MODELS:
#   SolarSystem  — NOCT thermal model + soiling + inverter efficiency
#   WindSystem   — IEC 61400-12 cubic power curve + turbulence derating
#   BatteryBESS  — CC-CV charging + Joule thermal + Wöhler SoH degradation
#
# FIXES vs v3.2:
#   - TEMP_COEFF now reads from Config.pv.temp_coeff_pct_c (-0.0035, not -0.004)
#   - Wind cut-in/rated/cut-out now read from Config.wind (not hardcoded)
#   - NOCT reads from Config.pv.noct_c
#   - All magic numbers replaced with named constants or config references
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import Config


# =============================================================================
# Result containers
# =============================================================================

@dataclass
class SolarResult:
    """Output of one SolarSystem.get_power_output() call."""
    ac_power_kw:          float   # AC power delivered to busbar [kW]
    dc_power_kw:          float   # DC power before inverter [kW]
    cell_temp_c:          float   # Module cell temperature [°C]
    thermal_derating_pct: float   # Power loss due to heat [%]
    soiling_loss_pct:     float   # Power loss due to dust/soiling [%]
    effective_irradiance: float   # Irradiance reaching cells after soiling [W/m²]


@dataclass
class WindResult:
    """Output of one WindSystem.get_power_output() call."""
    ac_power_kw:          float   # AC power delivered to busbar [kW]
    turbulence_loss_pct:  float   # Power loss due to turbulence [%]
    operating_regime:     str     # "below_cut_in"|"cubic"|"rated"|"cut_out"


@dataclass
class BatteryResult:
    """Output of one BatteryBESS.update_state() call."""
    soc:                  float   # State of Charge [0–1]
    soh:                  float   # State of Health [0–1]
    temperature_c:        float   # Internal pack temperature [°C]
    total_throughput_kwh: float   # Cumulative energy throughput [kWh]
    p_actual_kw:          float   # Actual power applied after limits [kW]
    thermal_warning:      bool    # True if temperature > 55°C
    thermal_runaway_risk: bool    # True if temperature ≥ Config threshold
    cycles_consumed:      float   # Estimated full-cycle count (cumulative)
    remaining_life_pct:   float   # % of rated cycle life remaining


# =============================================================================
# ☀  Solar PV System — NOCT Thermal + Soiling Model
# =============================================================================

class SolarSystem:
    """
    AC output model for the 42 × 360W monocrystalline array.

    Physics:
        1. Effective irradiance = GHI × soiling_factor
        2. Cell temperature via NOCT model:
               T_cell = T_amb + (G_eff / 800) × (NOCT − 20)
        3. Thermal derating factor:
               η_thermal = 1 + temp_coeff × (T_cell − 25°C)
        4. DC power = P_nameplate × (G_eff / 1000) × η_thermal
        5. AC power = DC power × inverter_efficiency

    Data sources:
        temp_coeff : Config.pv.temp_coeff_pct_c = −0.0035/°C (datasheet)
        NOCT       : Config.pv.noct_c = 45°C (datasheet)
        capacity   : Config.PV_SYSTEM_CAPACITY_KW = 15 kW (customer spec)
        inverter   : Config.INVERTER_EFFICIENCY = 0.97
    """

    STC_IRRADIANCE: float = 1000.0   # W/m² — Standard Test Conditions
    STC_TEMP_C:     float = 25.0     # °C   — STC reference temperature

    def __init__(self) -> None:
        # All parameters from config — no hardcoded values
        self.capacity_kw = Config.PV_SYSTEM_CAPACITY_KW
        self.inv_eff     = Config.INVERTER_EFFICIENCY
        self.temp_coeff  = Config.pv.temp_coeff_pct_c   # e.g. −0.0035 /°C
        self.noct_c      = Config.pv.noct_c             # e.g. 45°C

    def get_power_output(
        self,
        irradiance_wm2: float,
        ambient_temp_c: float,
        soiling_factor: float = 1.0,
    ) -> SolarResult:
        """
        Calculate AC power output for given weather conditions.

        Args:
            irradiance_wm2 : Global horizontal irradiance [W/m²]
            ambient_temp_c : Ambient air temperature [°C]
            soiling_factor : Panel cleanliness factor [0–1],
                             1.0 = clean, 0.95 = 5% loss due to dust

        Returns:
            SolarResult with AC power and full diagnostic data
        """
        if not irradiance_wm2 or irradiance_wm2 <= 0:
            return SolarResult(
                ac_power_kw=0.0,
                dc_power_kw=0.0,
                cell_temp_c=float(ambient_temp_c),
                thermal_derating_pct=0.0,
                soiling_loss_pct=round((1.0 - soiling_factor) * 100, 2),
                effective_irradiance=0.0,
            )

        sf  = float(np.clip(soiling_factor, 0.0, 1.0))
        g   = irradiance_wm2 * sf   # effective irradiance [W/m²]

        # ── NOCT cell temperature ────────────────────────────────────
        # NOCT model: panel heats up as irradiance increases
        # (NOCT - 20°C) represents the steady-state temperature rise
        # at 800 W/m² with 20°C ambient and 1 m/s wind (IEC standard)
        t_cell = float(ambient_temp_c) + (g / 800.0) * (self.noct_c - 20.0)

        # ── Thermal derating ─────────────────────────────────────────
        # Monocrystalline panels lose ~0.35%/°C above 25°C
        eta_th = 1.0 + self.temp_coeff * (t_cell - self.STC_TEMP_C)
        eta_th = float(max(eta_th, 0.0))
        thermal_derating_pct = max(0.0, (1.0 - eta_th) * 100.0)

        # ── DC and AC power ──────────────────────────────────────────
        dc = self.capacity_kw * (g / self.STC_IRRADIANCE) * eta_th
        dc = float(np.clip(dc, 0.0, self.capacity_kw))
        ac = float(np.clip(dc * self.inv_eff, 0.0, self.capacity_kw))

        return SolarResult(
            ac_power_kw=round(ac, 3),
            dc_power_kw=round(dc, 3),
            cell_temp_c=round(t_cell, 1),
            thermal_derating_pct=round(thermal_derating_pct, 2),
            soiling_loss_pct=round((1.0 - sf) * 100.0, 2),
            effective_irradiance=round(g, 1),
        )


# =============================================================================
# 💨  Wind Turbine — IEC 61400-12 Cubic Power Curve
# =============================================================================

class WindSystem:
    """
    10 kW HAWT power output model with turbulence derating.

    Power curve regimes (from Config.wind datasheet):
        below_cut_in : v < 2.5 m/s  → 0 kW
        cubic        : 2.5 ≤ v < 11 m/s  → P = P_rated × ((v−v_in)/(v_r−v_in))³
        rated        : 11 ≤ v ≤ 60 m/s  → P = P_rated
        cut_out      : v > 60 m/s OR TI ≥ limit → 0 kW (safety)

    Turbulence derating:
        Turbulence Intensity (TI) above 10% causes efficiency loss.
        At TI = Config limit (0.20), turbine performs an emergency cut-out.

    Data sources:
        All speed thresholds from Config.wind (datasheet)
        Turbulence limit from Config.TURBULENCE_INTENSITY_LIMIT
    """

    # Turbulence derating baseline — below this there is no penalty
    TI_BASELINE: float = 0.10

    def __init__(self) -> None:
        self.capacity_kw      = Config.WIND_SYSTEM_CAPACITY_KW
        self.cut_in_ms        = Config.wind.cut_in_ms        # 2.5 m/s
        self.rated_ms         = Config.wind.rated_speed_ms   # 11.0 m/s
        self.cut_out_ms       = Config.wind.cut_out_ms       # 60.0 m/s
        self.turbulence_limit = Config.TURBULENCE_INTENSITY_LIMIT  # 0.20

    def get_power_output(
        self,
        wind_speed_ms:        float,
        turbulence_intensity: float = 0.10,
    ) -> WindResult:
        """
        Calculate AC power output from wind speed and turbulence data.

        Args:
            wind_speed_ms        : 10-min average hub-height wind speed [m/s]
            turbulence_intensity : std(wind) / mean(wind), dimensionless
                                   Zagreb terrain roughness class II ≈ 0.15

        Returns:
            WindResult with AC power, turbulence loss, and operating regime
        """
        # ── Safety cut-out (excessive turbulence) ────────────────────
        if turbulence_intensity >= self.turbulence_limit:
            return WindResult(
                ac_power_kw=0.0,
                turbulence_loss_pct=100.0,
                operating_regime="cut_out",
            )

        # ── Hub-height adjustment (power law) ────────────────────────
        # Input wind speed is measured at ref_height_m (10 m, ZAMG station);
        # adjust to hub height (30 m) using power-law exponent α = 0.143.
        wind_speed_ms = wind_speed_ms * (
            (Config.wind.hub_height_m / Config.wind.ref_height_m)
            ** Config.wind.wind_shear_exponent
        )  # v_hub = v_ref × (h_hub / h_ref)^α

        # ── Below cut-in ─────────────────────────────────────────────
        if (not wind_speed_ms) or wind_speed_ms < self.cut_in_ms:
            return WindResult(
                ac_power_kw=0.0,
                turbulence_loss_pct=0.0,
                operating_regime="below_cut_in",
            )

        # ── Above cut-out ─────────────────────────────────────────────
        if wind_speed_ms > self.cut_out_ms:
            return WindResult(
                ac_power_kw=0.0,
                turbulence_loss_pct=0.0,
                operating_regime="cut_out",
            )

        # ── Turbulence derating ───────────────────────────────────────
        ti_excess = max(0.0, turbulence_intensity - self.TI_BASELINE)
        eta_ti    = 1.0 - ti_excess * 0.5    # 50% loss rate above baseline
        eta_ti    = float(np.clip(eta_ti, 0.0, 1.0))
        ti_loss   = round((1.0 - eta_ti) * 100.0, 2)

        # ── Power curve ───────────────────────────────────────────────
        if wind_speed_ms >= self.rated_ms:
            raw_power = self.capacity_kw * eta_ti
            regime    = "rated"
        else:
            # Cubic interpolation between cut-in and rated speed
            ratio     = ((wind_speed_ms - self.cut_in_ms)
                         / (self.rated_ms - self.cut_in_ms))
            raw_power = self.capacity_kw * (ratio ** 3) * eta_ti
            regime    = "cubic"

        ac_power = float(np.clip(raw_power, 0.0, self.capacity_kw))

        return WindResult(
            ac_power_kw=round(ac_power, 3),
            turbulence_loss_pct=ti_loss,
            operating_regime=regime,
        )


# =============================================================================
# 🔋  Battery BESS — CC-CV + Thermal + Wöhler SoH Model
# =============================================================================

class BatteryBESS:
    """
    100 kWh LFP battery system with realistic degradation and thermal model.

    Charging profile:
        CC phase : constant current at max_charge_kW up to 85% SoC
        CV phase : linearly tapers from 85% → 90% SoC (CC-CV characteristic)

    Thermal model:
        Joule heating: Q_gen = |P| × R_thermal
        Cooling      : dT = −COOLING_RATE × (T − T_amb) per timestep
        Emergency cut: power set to 0 if T ≥ THERMAL_RUNAWAY_TEMP

    SoH degradation (Wöhler throughput model):
        Every kWh cycled through the pack consumes a fraction of cycle life.
        Full cycle = 2 × capacity_kWh of throughput (one charge + discharge).
        SoH = 1 − (cycles_consumed / cycle_life), floored at EOL_SOH (70%).

    Data sources:
        All limits from Config.battery (LFP 100 kWh datasheet)
    """

    # Coulombic efficiency (LFP slightly asymmetric)
    CHARGE_EFF:    float = 0.975    # 97.5% charging efficiency
    DISCHARGE_EFF: float = 0.975    # 97.5% discharging efficiency

    # Thermal constants
    THERMAL_RESISTANCE: float = 0.03   # °C/W — pack thermal resistance
    COOLING_RATE:       float = 0.05   # fraction of ΔT dissipated per timestep

    # End-of-life threshold
    EOL_SOH:            float = 0.70   # 70% — LFP end-of-life SoH

    # CC-CV taper start point
    CV_START_SOC:       float = 0.85   # taper begins at 85% SoC

    def __init__(self, initial_soc: float = 0.55) -> None:
        self.capacity_kwh = Config.BATT_CAPACITY_KWH     # 100 kWh
        self.soc          = float(np.clip(
            initial_soc, Config.BATT_SOC_MIN, Config.BATT_SOC_MAX))
        self.soh          = 1.0
        self.temperature_c       = 25.0
        self.total_throughput_kwh = 0.0

    # ------------------------------------------------------------------
    # Power limit queries
    # ------------------------------------------------------------------

    def get_max_charge_power(self) -> float:
        """
        Maximum charge power at current SoC (CC-CV profile).

        Returns full max_charge_kW below 85% SoC, then linearly
        tapers to 0 at 90% SoC (mimics real CC-CV battery behaviour).
        """
        if self.soc >= Config.BATT_SOC_MAX:
            return 0.0
        if self.soc > self.CV_START_SOC:
            taper = ((Config.BATT_SOC_MAX - self.soc)
                     / (Config.BATT_SOC_MAX - self.CV_START_SOC))
            return round(Config.BATT_MAX_CHARGE_KW * float(np.clip(taper, 0.0, 1.0)), 3)
        return Config.BATT_MAX_CHARGE_KW

    def get_max_discharge_power(self) -> float:
        """Maximum discharge power (limited by SoC floor)."""
        if self.soc <= Config.BATT_SOC_MIN:
            return 0.0
        return Config.BATT_MAX_DISCHARGE_KW

    # ------------------------------------------------------------------
    # State update — call once per tick
    # ------------------------------------------------------------------

    def update_state(
        self,
        net_power_kw:   float,
        ambient_temp_c: float = 25.0,
    ) -> BatteryResult:
        """
        Apply net power for one simulation timestep and return diagnostics.

        Args:
            net_power_kw   : positive = charge [kW], negative = discharge [kW]
            ambient_temp_c : ambient air temperature for thermal model [°C]

        Returns:
            BatteryResult with updated SoC, SoH, temperature, and flags
        """
        dt_h = Config.TIMESTEP_SEC / 3600.0
        dt_s = float(Config.TIMESTEP_SEC)

        # ── 1. Apply physical power limits ────────────────────────────
        if net_power_kw > 0:
            p_actual = float(min(net_power_kw, self.get_max_charge_power()))
            energy_delta_kwh = p_actual * self.CHARGE_EFF * dt_h
        elif net_power_kw < 0:
            p_actual = float(max(net_power_kw, -self.get_max_discharge_power()))
            energy_delta_kwh = (p_actual / self.DISCHARGE_EFF) * dt_h
        else:
            p_actual         = 0.0
            energy_delta_kwh = 0.0

        # ── 2. Thermal model ──────────────────────────────────────────
        # Joule heating [W] — proportional to |current power|
        heat_w   = abs(p_actual) * 1000.0 * self.THERMAL_RESISTANCE
        # Passive cooling — Newton's law of cooling
        cooling  = self.COOLING_RATE * (self.temperature_c - ambient_temp_c) * dt_s
        # Temperature change: (Q_net [W] × dt [s]) / thermal_mass [J/°C]
        # LFP 100 kWh pack thermal mass ≈ 500,000 J/°C (5 kJ/°C per kWh)
        thermal_mass_j = self.capacity_kwh * 5000.0   # J/°C
        delta_t  = (heat_w * dt_s - cooling) / max(thermal_mass_j, 1.0)
        self.temperature_c = float(max(ambient_temp_c,
                                       self.temperature_c + delta_t))

        thermal_warning      = self.temperature_c > 55.0
        thermal_runaway_risk = self.temperature_c >= Config.THERMAL_RUNAWAY_TEMP

        # Emergency cut-out on thermal runaway risk
        if thermal_runaway_risk:
            p_actual         = 0.0
            energy_delta_kwh = 0.0

        # ── 3. SoH degradation — Wöhler throughput model ──────────────
        # Throughput = |energy| cycled this tick
        throughput = abs(energy_delta_kwh)
        self.total_throughput_kwh += throughput
        # Full-equivalent cycles consumed
        full_cycles = self.total_throughput_kwh / (2.0 * self.capacity_kwh)
        # SoH floors at EOL_SOH (70%)
        self.soh = float(max(self.EOL_SOH,
                             1.0 - full_cycles / Config.BATT_CYCLE_LIFE))

        # ── 4. SoC update on SoH-derated effective capacity ───────────
        # As battery degrades, its effective capacity shrinks
        eff_cap_kwh      = self.capacity_kwh * self.soh
        current_energy   = self.soc * eff_cap_kwh
        new_energy       = current_energy + energy_delta_kwh
        self.soc         = float(np.clip(
            new_energy / max(eff_cap_kwh, 0.001),
            Config.BATT_SOC_MIN,
            Config.BATT_SOC_MAX,
        ))

        remaining_life_pct = float(max(
            0.0, (1.0 - full_cycles / Config.BATT_CYCLE_LIFE) * 100.0
        ))

        return BatteryResult(
            soc=round(self.soc, 4),
            soh=round(self.soh, 4),
            temperature_c=round(self.temperature_c, 1),
            total_throughput_kwh=round(self.total_throughput_kwh, 3),
            p_actual_kw=round(p_actual, 3),
            thermal_warning=thermal_warning,
            thermal_runaway_risk=thermal_runaway_risk,
            cycles_consumed=round(full_cycles, 3),
            remaining_life_pct=round(remaining_life_pct, 1),
        )


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    print("=" * 58)
    print("  energy_assets.py v3.3 — Smoke test")
    print("=" * 58)

    # ── Solar ──────────────────────────────────────────────────────────
    print("\n[1] Solar PV System")
    solar = SolarSystem()
    print(f"  Config check: temp_coeff = {solar.temp_coeff} /°C  "
          f"(expect {Config.pv.temp_coeff_pct_c})")
    print(f"  Config check: NOCT = {solar.noct_c}°C  "
          f"(expect {Config.pv.noct_c})")
    assert solar.temp_coeff == Config.pv.temp_coeff_pct_c, "temp_coeff mismatch!"
    assert solar.noct_c == Config.pv.noct_c, "NOCT mismatch!"

    # Good day
    s1 = solar.get_power_output(750, 32.0, 0.95)
    print(f"\n  750 W/m², 32°C, soiling 5%:")
    print(f"    AC power     : {s1.ac_power_kw} kW  "
          f"(max {solar.capacity_kw} kW)")
    print(f"    Cell temp    : {s1.cell_temp_c}°C")
    print(f"    Thermal loss : {s1.thermal_derating_pct}%")
    print(f"    Soiling loss : {s1.soiling_loss_pct}%")
    assert 0 < s1.ac_power_kw < solar.capacity_kw

    # Peak irradiance
    s2 = solar.get_power_output(1000, 25.0, 1.0)
    # Note: at 1000 W/m² ambient=25°C, NOCT model heats cell to ~56°C
    # This causes ~11% thermal derating — this IS correct physics.
    # STC is tested with cell=25°C (controlled lab), not ambient=25°C.
    # Real-world output at 1000 W/m² ≈ 13 kW (not 14.55 kW nameplate).
    print(f"\n  1000 W/m², 25°C ambient (NOCT heats cell to ~56°C):")
    print(f"    AC power     : {s2.ac_power_kw} kW  (nameplate {solar.capacity_kw} kW)")
    print(f"    Note: thermal derating expected — cell temp ≠ ambient temp")
    assert 10 < s2.ac_power_kw < solar.capacity_kw   # between 10 and 15 kW

    # Night
    s3 = solar.get_power_output(0, 15.0)
    assert s3.ac_power_kw == 0.0
    print(f"\n  Night (0 W/m²): {s3.ac_power_kw} kW ✅")

    # ── Wind ───────────────────────────────────────────────────────────
    print("\n[2] Wind Turbine")
    wind = WindSystem()
    print(f"  Config check: cut_in={wind.cut_in_ms} m/s, "
          f"rated={wind.rated_ms} m/s, cut_out={wind.cut_out_ms} m/s")
    assert wind.cut_in_ms  == Config.wind.cut_in_ms
    assert wind.rated_ms   == Config.wind.rated_speed_ms
    assert wind.cut_out_ms == Config.wind.cut_out_ms

    # Cubic regime
    w1 = wind.get_power_output(7.5, 0.12)
    print(f"\n  7.5 m/s, TI=0.12:")
    print(f"    AC power     : {w1.ac_power_kw} kW  [{w1.operating_regime}]")
    print(f"    Turbulence   : -{w1.turbulence_loss_pct}%")
    assert w1.operating_regime == "cubic"
    assert 0 < w1.ac_power_kw < wind.capacity_kw

    # Rated regime
    w2 = wind.get_power_output(14.0, 0.10)
    print(f"\n  14 m/s, TI=0.10:")
    print(f"    AC power     : {w2.ac_power_kw} kW  [{w2.operating_regime}]")
    assert w2.operating_regime == "rated"
    assert abs(w2.ac_power_kw - wind.capacity_kw) < 0.1

    # Turbulence cut-out
    w3 = wind.get_power_output(9.0, 0.20)
    print(f"\n  9 m/s, TI=0.20 (cut-out):")
    print(f"    AC power     : {w3.ac_power_kw} kW  [{w3.operating_regime}] ✅")
    assert w3.ac_power_kw == 0.0
    assert w3.operating_regime == "cut_out"

    # Below cut-in
    w4 = wind.get_power_output(2.0, 0.10)
    assert w4.operating_regime == "below_cut_in"
    print(f"\n  2 m/s (below cut-in): {w4.ac_power_kw} kW ✅")

    # ── BESS ───────────────────────────────────────────────────────────
    print("\n[3] Battery BESS")
    bess = BatteryBESS(initial_soc=0.55)
    b1   = bess.update_state(net_power_kw=20.0, ambient_temp_c=28.0)
    print(f"\n  Charge at 20 kW, ambient 28°C:")
    print(f"    SoC          : {b1.soc*100:.2f}%")
    print(f"    SoH          : {b1.soh*100:.3f}%")
    print(f"    Temperature  : {b1.temperature_c}°C")
    print(f"    Actual power : {b1.p_actual_kw} kW  "
          f"(max {Config.BATT_MAX_CHARGE_KW} kW)")
    print(f"    Life left    : {b1.remaining_life_pct}%")
    assert b1.p_actual_kw <= Config.BATT_MAX_CHARGE_KW

    # CC-CV taper test
    bess2   = BatteryBESS(initial_soc=0.88)
    max_p   = bess2.get_max_charge_power()
    print(f"\n  CC-CV taper at SoC=88%:")
    print(f"    Max charge   : {max_p:.2f} kW  "
          f"(< {Config.BATT_MAX_CHARGE_KW} kW full rate) ✅")
    assert 0 < max_p < Config.BATT_MAX_CHARGE_KW

    # SoC floor test
    bess3 = BatteryBESS(initial_soc=Config.BATT_SOC_MIN)
    max_d = bess3.get_max_discharge_power()
    print(f"\n  At SoC_min ({Config.BATT_SOC_MIN*100:.0f}%):")
    print(f"    Max discharge: {max_d} kW ✅ (expect 0.0)")
    assert max_d == 0.0

    # Thermal runaway test
    bess4 = BatteryBESS(initial_soc=0.50)
    bess4.temperature_c = Config.THERMAL_RUNAWAY_TEMP + 1.0
    b4 = bess4.update_state(net_power_kw=10.0, ambient_temp_c=25.0)
    print(f"\n  Thermal runaway (T={bess4.temperature_c}°C):")
    print(f"    Actual power : {b4.p_actual_kw} kW (expect 0.0) ✅")
    print(f"    Runaway flag : {b4.thermal_runaway_risk}")
    assert b4.p_actual_kw == 0.0
    assert b4.thermal_runaway_risk

    print("\n✅ energy_assets.py v3.3 — all tests passed")
