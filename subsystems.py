# =============================================================================
# subsystems.py — LUMINIH2 Auxiliary Subsystems
# Water treatment · O₂ management · H₂ dryer · Electrolyzer warm-up
# Version: 4.1
# =============================================================================
#
# SUBSYSTEMS MODELLED:
#   WaterTreatment      — DIN ISO 3696 Type 1 deionised water for S30/30
#   OxygenHandler       — O₂ flow, pressure, venting / recovery
#   HydrogenDryer       — PSA/desiccant dryer to < 5 ppm moisture (AIRCELL req.)
#   ElectrolyzerWarmup  — thermal model for cold-start efficiency penalty
#   SubsystemManager    — unified tick interface for all four subsystems
#
# DATASHEET REFERENCES:
#   Water quality : DIN ISO 3696 Type 1 — resistance > 10 MΩ·cm
#   H₂ moisture   : AIRCELL 3000 requirement — < 5 ppm water
#   O₂ pressure   : ITM S30/30 output — < 0.5 bar
#   Stack temp    : ITM S30/30 operating range — 20–70°C, optimal ~55°C
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import logging

logger = logging.getLogger("Subsystems")


# =============================================================================
# Result dataclasses
# =============================================================================

@dataclass
class WaterResult:
    """Output of one WaterTreatment.process() call."""
    raw_water_l_h:        float   # Raw feed water input [L/h]
    purified_l_h:         float   # Treated water output [L/h]
    conductivity_us_cm:   float   # Electrical conductivity — target < 0.1 µS/cm
    resistance_mohm_cm:   float   # Specific resistance — target > 10 MΩ·cm
    quality_ok:           bool    # True if within DIN ISO 3696 Type 1 spec
    resin_saturation_pct: float   # Ion exchange resin saturation [%]
    resin_warning:        bool    # True if saturation > 80% — replace soon
    power_kw:             float   # Pump + UV power consumption [kW]


@dataclass
class O2Result:
    """Output of one OxygenHandler.process() call."""
    o2_flow_nm3_h:    float   # O₂ production rate [Nm³/h]
    o2_pressure_bar:  float   # O₂ outlet pressure — must be < 0.5 bar
    vented_nm3_h:     float   # O₂ vented to atmosphere [Nm³/h]
    recovered_nm3_h:  float   # O₂ recovered (if recovery system fitted) [Nm³/h]
    safety_ok:        bool    # False if pressure ≥ 0.5 bar safety limit


@dataclass
class DryerResult:
    """Output of one HydrogenDryer.process() call."""
    h2_in_kg_h:         float   # Wet H₂ inlet flow [kg/h]
    h2_out_kg_h:        float   # Dry H₂ outlet flow [kg/h]
    moisture_ppm:       float   # Outlet moisture content — target < 5 ppm
    dew_point_c:        float   # Dew point temperature [°C]
    desiccant_pct:      float   # Desiccant saturation [%]
    desiccant_warning:  bool    # True if saturation > 85% — regenerate
    h2_loss_pct:        float   # H₂ lost in drying process [%]
    power_kw:           float   # Dryer heater + auxiliary power [kW]


@dataclass
class WarmupResult:
    """Output of one ElectrolyzerWarmup.update() call."""
    is_warm:           bool    # True if stack is ready for rated operation
    warmup_time_min:   float   # Estimated minutes remaining to reach optimal temp
    current_temp_c:    float   # Current stack temperature [°C]
    target_temp_c:     float   # Optimal operating temperature [°C]
    efficiency_factor: float   # Efficiency multiplier (1.0 = full rated efficiency)
    power_consumed_kw: float   # Heater element power draw [kW]
    cold_start:        bool    # True if starting from near-ambient temperature


# =============================================================================
# 1. Water Treatment — DIN ISO 3696 Type 1
# =============================================================================

class WaterTreatment:
    """
    Deionised water treatment system for the ITM S30/30 electrolyzer.

    Requirement (from S30/30 datasheet):
        Resistance  > 10 MΩ·cm  (DIN ISO 3696 Type 1)
        Conductance < 0.1 µS/cm

    Process chain:
        Raw tap water → Ion exchange resin → UV steriliser → Pump → Electrolyzer

    Degradation model:
        As the resin saturates, outgoing conductivity rises and resistance falls.
        Above 80% saturation a warning is raised; above 100% quality falls below spec.

    Power draw:
        Pump: 0.05 kW + UV steriliser: 0.02 kW = 0.07 kW total
    """

    TARGET_RESISTANCE_MOHM: float = 10.0    # MΩ·cm — minimum spec
    TARGET_CONDUCTANCE_US:  float = 0.1     # µS/cm — maximum spec
    RESIN_CAPACITY_L:       float = 50.0    # Ion exchange cartridge volume [L]
    RESIN_EXCHANGE_CAP:     float = 500.0   # Resin water processing capacity [L]
    PUMP_POWER_KW:          float = 0.05
    UV_POWER_KW:            float = 0.02

    def __init__(self) -> None:
        self._water_processed_l: float = 0.0
        self._resin_used_l:      float = 0.0

    def process(
        self,
        demand_l_h:           float,
        ambient_temp_c:       float = 20.0,
        feed_conductivity_us: float = 500.0,
    ) -> WaterResult:
        """
        Treat raw water to DIN ISO 3696 Type 1 standard.

        Args:
            demand_l_h           : water demand from electrolyzer [L/h]
            ambient_temp_c       : ambient temperature [°C]
            feed_conductivity_us : raw feed water conductivity [µS/cm]
                                   typical Zagreb tap water: 300–600 µS/cm

        Returns:
            WaterResult with quality metrics and power draw
        """
        if demand_l_h <= 0:
            return WaterResult(
                raw_water_l_h=0.0, purified_l_h=0.0,
                conductivity_us_cm=0.05, resistance_mohm_cm=20.0,
                quality_ok=True,
                resin_saturation_pct=self._resin_saturation(),
                resin_warning=self._resin_saturation() > 80.0,
                power_kw=0.0,
            )

        # Accumulate resin usage (per second, not per hour)
        dt_h = 1.0 / 3600.0
        self._resin_used_l      += demand_l_h * dt_h
        self._water_processed_l += demand_l_h * dt_h

        resin_sat = self._resin_saturation()

        # As resin saturates, treatment quality degrades
        quality_factor  = max(0.1, 1.0 - (resin_sat / 100.0) * 0.9)
        conductivity    = self.TARGET_CONDUCTANCE_US / quality_factor
        conductivity    = float(np.clip(conductivity, 0.01, feed_conductivity_us))
        # Specific resistance = 1 / (conductivity in S/cm) converted to MΩ·cm
        resistance      = 1.0 / max(conductivity * 1e-6, 1e-12) / 1e6

        # Accept water if it is within 1.5× spec (slight margin)
        quality_ok = (conductivity <= self.TARGET_CONDUCTANCE_US * 1.5
                      and resistance >= self.TARGET_RESISTANCE_MOHM * 0.5)

        # ~8% loss to backwash and rinsing
        purified = demand_l_h * 0.92

        return WaterResult(
            raw_water_l_h=round(demand_l_h, 3),
            purified_l_h=round(purified, 3),
            conductivity_us_cm=round(conductivity, 4),
            resistance_mohm_cm=round(resistance, 2),
            quality_ok=quality_ok,
            resin_saturation_pct=round(resin_sat, 1),
            resin_warning=resin_sat > 80.0,
            power_kw=round(self.PUMP_POWER_KW + self.UV_POWER_KW, 3),
        )

    def replace_resin(self) -> None:
        """Reset resin usage counter — call when maintenance is performed."""
        self._resin_used_l = 0.0
        logger.info("Ion exchange resin replaced — quality reset")

    def _resin_saturation(self) -> float:
        return min(100.0, (self._resin_used_l / self.RESIN_EXCHANGE_CAP) * 100.0)


# =============================================================================
# 2. Oxygen Handler
# =============================================================================

class OxygenHandler:
    """
    Manages O₂ by-product from the S30/30 electrolyzer.

    Stoichiometry:
        2 H₂O → 2 H₂ + O₂
        1 kg H₂ produces 8 kg O₂ = 5.6 Nm³ O₂

    Safety limit (from S30/30 datasheet):
        O₂ outlet pressure < 0.5 bar

    Disposition options:
        has_recovery_system=False : 100% vented to atmosphere (safe)
        has_recovery_system=True  : 85% recovered, 15% vented
    """

    O2_MAX_PRESSURE_BAR: float = 0.5    # Safety limit from datasheet
    O2_NM3_PER_KG_H2:   float = 5.6    # Stoichiometric ratio

    def __init__(self, has_recovery_system: bool = False) -> None:
        self._has_recovery   = has_recovery_system
        self._total_o2_nm3:  float = 0.0

    def process(
        self,
        h2_production_kg_h:   float,
        ambient_pressure_bar: float = 1.013,
    ) -> O2Result:
        """
        Calculate O₂ flow and manage disposal for one timestep.

        Args:
            h2_production_kg_h   : H₂ production rate [kg/h]
            ambient_pressure_bar : atmospheric pressure [bar]

        Returns:
            O2Result with flow, pressure, and safety status
        """
        o2_flow = h2_production_kg_h * self.O2_NM3_PER_KG_H2
        self._total_o2_nm3 += o2_flow / 3600.0

        # O₂ outlet pressure — well below 0.5 bar safety limit
        o2_pressure = min(0.45, ambient_pressure_bar * 0.44)
        safety_ok   = o2_pressure < self.O2_MAX_PRESSURE_BAR

        if self._has_recovery:
            recovered = o2_flow * 0.85
            vented    = o2_flow * 0.15
        else:
            recovered = 0.0
            vented    = o2_flow

        return O2Result(
            o2_flow_nm3_h=round(o2_flow, 4),
            o2_pressure_bar=round(o2_pressure, 3),
            vented_nm3_h=round(vented, 4),
            recovered_nm3_h=round(recovered, 4),
            safety_ok=safety_ok,
        )

    @property
    def total_o2_nm3(self) -> float:
        """Cumulative O₂ produced this session [Nm³]."""
        return round(self._total_o2_nm3, 3)


# =============================================================================
# 3. Hydrogen Dryer
# =============================================================================

class HydrogenDryer:
    """
    Desiccant H₂ dryer to meet AIRCELL 3000 purity requirement.

    Requirement (from AIRCELL 3000 datasheet):
        Moisture content < 5 ppm water

    Process:
        Wet H₂ from electrolyzer (20 bar) → PSA/desiccant bed → dry H₂
        Desiccant regenerated periodically (requires heat, ~0.15 kW)

    H₂ loss:
        ~0.5% of throughput lost during regeneration purge cycles

    Desiccant capacity:
        Modelled as a 2 kg H₂ equivalent bed.
        Above 85% saturation: moisture rises above 5 ppm — regenerate.
    """

    TARGET_MOISTURE_PPM:   float = 5.0    # AIRCELL 3000 requirement
    DESICCANT_CAPACITY_KG: float = 2.0    # Effective bed capacity [kg H₂]
    H2_LOSS_FRACTION:      float = 0.005  # ~0.5% H₂ loss per cycle
    REGEN_POWER_KW:        float = 0.15   # Regeneration heater power
    STANDBY_POWER_KW:      float = 0.02   # Standby instrument power

    def __init__(self) -> None:
        self._h2_processed_kg: float = 0.0
        self._desiccant_used:  float = 0.0

    def process(
        self,
        h2_kg_h:             float,
        inlet_pressure_bar:  float = 20.0,
        ambient_temp_c:      float = 20.0,
    ) -> DryerResult:
        """
        Dry wet H₂ from electrolyzer to AIRCELL specification.

        Args:
            h2_kg_h            : wet H₂ inlet flow rate [kg/h]
            inlet_pressure_bar : H₂ inlet pressure (20 bar from S30/30)
            ambient_temp_c     : ambient temperature [°C]

        Returns:
            DryerResult with moisture, dew point, and desiccant status
        """
        if h2_kg_h <= 0:
            return DryerResult(
                h2_in_kg_h=0.0, h2_out_kg_h=0.0,
                moisture_ppm=0.5, dew_point_c=-60.0,
                desiccant_pct=self._desiccant_sat(),
                desiccant_warning=self._desiccant_sat() > 85.0,
                h2_loss_pct=self.H2_LOSS_FRACTION * 100.0,
                power_kw=self.STANDBY_POWER_KW,
            )

        self._h2_processed_kg += h2_kg_h / 3600.0
        self._desiccant_used  += h2_kg_h / 3600.0
        desiccant_sat          = self._desiccant_sat()

        # Moisture rises as desiccant saturates
        if desiccant_sat < 70.0:
            moisture_ppm = 0.5 + desiccant_sat * 0.03
        elif desiccant_sat < 85.0:
            moisture_ppm = 3.0 + (desiccant_sat - 70.0) * 0.2
        else:
            moisture_ppm = 6.0 + (desiccant_sat - 85.0) * 0.5
        moisture_ppm = float(np.clip(moisture_ppm, 0.1, 20.0))

        # Approximate dew point from moisture content
        dew_point = float(np.clip(-50.0 + (moisture_ppm / 5.0) * 30.0, -80.0, 20.0))

        # H₂ throughput loss
        h2_loss    = h2_kg_h * self.H2_LOSS_FRACTION
        h2_out     = h2_kg_h - h2_loss

        # Power: regeneration heater when desiccant > 80%
        power = self.REGEN_POWER_KW if desiccant_sat > 80.0 else self.STANDBY_POWER_KW

        return DryerResult(
            h2_in_kg_h=round(h2_kg_h, 5),
            h2_out_kg_h=round(h2_out, 5),
            moisture_ppm=round(moisture_ppm, 3),
            dew_point_c=round(dew_point, 1),
            desiccant_pct=round(desiccant_sat, 1),
            desiccant_warning=desiccant_sat > 85.0,
            h2_loss_pct=round(self.H2_LOSS_FRACTION * 100.0, 2),
            power_kw=round(power, 3),
        )

    def regenerate_desiccant(self) -> None:
        """Reset desiccant saturation counter — call when regeneration is complete."""
        self._desiccant_used = 0.0
        logger.info("H₂ dryer desiccant regenerated")

    def _desiccant_sat(self) -> float:
        return min(100.0,
                   (self._desiccant_used / max(self.DESICCANT_CAPACITY_KG, 1e-9)) * 100.0)


# =============================================================================
# 4. Electrolyzer Warm-Up — Cold Start Thermal Model
# =============================================================================

class ElectrolyzerWarmup:
    """
    Thermal model for the ITM S30/30 PEM electrolyzer cold-start behaviour.

    Operating temperature range (from datasheet):
        Minimum    : 20°C
        Maximum    : 70°C
        Optimal    : ~55°C
        Warm-up    : ~5 minutes from cold

    Efficiency penalty:
        Below 20°C : 70% efficiency (severe cold penalty)
        20–30°C    : 85% (warming up)
        30–55°C    : 85–100% (linear improvement to optimal)
        55–70°C    : 100–95% (slight reduction at high temperature)
        >70°C      : 80% (overtemperature — automatic protection)

    Heat sources:
        Electrochemical reaction waste heat (~22% of input power)
        Internal heater element (0.3 kW) during warm-up
    """

    OPTIMAL_TEMP_C:  float = 55.0
    MIN_TEMP_C:      float = 20.0
    MAX_TEMP_C:      float = 70.0
    HEATING_POWER_KW: float = 0.30
    THERMAL_MASS:    float = 50.0    # Approximate stack thermal mass [kJ/°C]
    COOLING_RATE:    float = 0.02    # Natural cooling rate at rest [°C/min]

    def __init__(self, initial_temp_c: float = 20.0) -> None:
        self._stack_temp: float = float(initial_temp_c)
        self._is_running: bool  = False
        self._run_minutes: float = 0.0

    def update(
        self,
        ambient_temp_c: float,
        power_input_kw: float,
        timestep_sec:   int = 10,
    ) -> WarmupResult:
        """
        Update stack thermal state for one timestep.

        Args:
            ambient_temp_c : ambient air temperature [°C]
            power_input_kw : electrolyzer electrical input [kW]
            timestep_sec   : simulation timestep [s]

        Returns:
            WarmupResult with temperature, efficiency factor, and warm status
        """
        dt_min    = timestep_sec / 60.0
        cold_start = self._stack_temp < self.MIN_TEMP_C + 5.0

        if power_input_kw >= 0.74:   # Running at or above P_MIN
            self._is_running   = True
            self._run_minutes += dt_min

            # Heat sources
            heat_gen_kw   = power_input_kw * 0.22   # ~22% waste heat
            heater_kw     = (self.HEATING_POWER_KW
                             if self._stack_temp < self.OPTIMAL_TEMP_C else 0.0)
            heat_loss_kw  = max(0.0, (self._stack_temp - ambient_temp_c) * 0.05)

            # ΔT = (Q_net × dt) / thermal_mass
            delta_t = ((heat_gen_kw + heater_kw - heat_loss_kw)
                       * 60.0 * dt_min / (self.THERMAL_MASS / 1000.0))
            self._stack_temp += delta_t
            self._stack_temp  = float(np.clip(
                self._stack_temp, ambient_temp_c, self.MAX_TEMP_C))

        else:   # Idle — natural cooling
            self._is_running = False
            cooling          = self.COOLING_RATE * dt_min
            self._stack_temp = max(ambient_temp_c, self._stack_temp - cooling)

        is_warm            = self._stack_temp >= self.MIN_TEMP_C + 5.0
        warmup_remaining   = max(
            0.0, (self.OPTIMAL_TEMP_C - self._stack_temp) / 6.0)

        # Efficiency factor vs temperature
        t = self._stack_temp
        if t < self.MIN_TEMP_C:
            eff = 0.70
        elif t < self.MIN_TEMP_C + 10.0:
            eff = 0.85
        elif t <= self.OPTIMAL_TEMP_C:
            eff = 0.85 + 0.15 * ((t - self.MIN_TEMP_C)
                                  / (self.OPTIMAL_TEMP_C - self.MIN_TEMP_C))
        elif t <= self.MAX_TEMP_C:
            eff = 1.0 - 0.05 * ((t - self.OPTIMAL_TEMP_C)
                                  / (self.MAX_TEMP_C - self.OPTIMAL_TEMP_C))
        else:
            eff = 0.80   # Overtemperature protection

        power_consumed = self.HEATING_POWER_KW if not is_warm else 0.0

        return WarmupResult(
            is_warm=is_warm,
            warmup_time_min=round(warmup_remaining, 1),
            current_temp_c=round(self._stack_temp, 1),
            target_temp_c=self.OPTIMAL_TEMP_C,
            efficiency_factor=round(float(eff), 3),
            power_consumed_kw=round(power_consumed, 3),
            cold_start=cold_start,
        )

    def reset(self, ambient_temp_c: float = 20.0) -> None:
        """Reset stack to ambient temperature (shutdown)."""
        self._stack_temp  = float(ambient_temp_c)
        self._is_running  = False
        self._run_minutes = 0.0

    @property
    def stack_temp(self) -> float:
        """Current stack temperature [°C]."""
        return round(self._stack_temp, 1)


# =============================================================================
# 5. Subsystem Manager — unified tick interface
# =============================================================================

class SubsystemManager:
    """
    Unified interface for all four LUMINIH2 auxiliary subsystems.

    Called once per simulation tick by TickEngine (via main.py).
    Returns a single dict with all subsystem results for the dashboard.

    Usage:
        mgr = SubsystemManager()
        result = mgr.tick(h2_kg_h=0.059, elec_power_kw=3.0, ambient_temp_c=20.0)
    """

    def __init__(self, has_o2_recovery: bool = False) -> None:
        self.water  = WaterTreatment()
        self.oxygen = OxygenHandler(has_recovery_system=has_o2_recovery)
        self.dryer  = HydrogenDryer()
        self.warmup = ElectrolyzerWarmup(initial_temp_c=20.0)

    def tick(
        self,
        h2_kg_h:        float,
        elec_power_kw:  float,
        ambient_temp_c: float,
        timestep_sec:   int = 10,
    ) -> dict:
        """
        Advance all subsystems by one simulation timestep.

        Args:
            h2_kg_h        : H₂ production rate from electrolyzer [kg/h]
            elec_power_kw  : electrical power to electrolyzer [kW]
            ambient_temp_c : ambient temperature [°C]
            timestep_sec   : simulation timestep [s]

        Returns:
            dict with keys: water, oxygen, dryer, warmup,
                            h2_final_kg_h, aux_power_kw, elec_eff_factor,
                            maintenance, h2_dry_ok, water_ok, o2_safe, stack_temp
        """
        # Water demand: 11.13 L per kg H₂ (from Config.WATER_CONSUMPTION_L_KG)
        water_demand = h2_kg_h * 11.13

        wr = self.water.process(water_demand, ambient_temp_c)
        o2 = self.oxygen.process(h2_kg_h, 1.013)
        dr = self.dryer.process(h2_kg_h, 20.0, ambient_temp_c)
        wu = self.warmup.update(ambient_temp_c, elec_power_kw, timestep_sec)

        # Final H₂ output after drying
        h2_final_kg_h = dr.h2_out_kg_h

        # Total auxiliary power
        total_aux_kw = wr.power_kw + dr.power_kw + wu.power_consumed_kw

        # Maintenance messages
        maintenance: list[str] = []
        if wr.resin_warning:
            maintenance.append(
                f"Water treatment resin at {wr.resin_saturation_pct:.0f}% — replace soon")
        if dr.desiccant_warning:
            maintenance.append(
                f"H₂ dryer desiccant at {dr.desiccant_pct:.0f}% — regenerate")
        if not wr.quality_ok:
            maintenance.append(
                f"⚠ Water quality out of spec ({wr.conductivity_us_cm:.3f} µS/cm) "
                f"— membrane risk!")

        return {
            "water":           wr,
            "oxygen":          o2,
            "dryer":           dr,
            "warmup":          wu,
            "h2_final_kg_h":   h2_final_kg_h,
            "aux_power_kw":    round(total_aux_kw, 3),
            "elec_eff_factor": wu.efficiency_factor,
            "maintenance":     maintenance,
            "h2_dry_ok":       dr.moisture_ppm <= 5.0,
            "water_ok":        wr.quality_ok,
            "o2_safe":         o2.safety_ok,
            "stack_temp":      wu.current_temp_c,
        }

    def reset_electrolyzer(self, ambient_temp_c: float = 20.0) -> None:
        """Reset electrolyzer thermal state (call after shutdown)."""
        self.warmup.reset(ambient_temp_c)


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    print("=" * 58)
    print("  subsystems.py v4.1 — Smoke test")
    print("=" * 58)

    mgr = SubsystemManager(has_o2_recovery=False)

    # Simulate 30 minutes of operation from cold (Zagreb winter, 5°C)
    print("\n[1] 30-minute cold-start simulation (ambient = 5°C, nominal load)")
    for i in range(180):
        result = mgr.tick(
            h2_kg_h=0.0593,
            elec_power_kw=3.0,
            ambient_temp_c=5.0,
            timestep_sec=10,
        )
        if i in [0, 30, 60, 90, 120, 179]:
            wu = result["warmup"]
            dr = result["dryer"]
            print(f"  t={i*10:4}s  Stack {wu.current_temp_c:5.1f}°C  "
                  f"η×{wu.efficiency_factor:.3f}  "
                  f"H₂ moisture {dr.moisture_ppm:.2f} ppm  "
                  f"Warm: {wu.is_warm}")

    print(f"\n[2] Final subsystem state:")
    wr = result["water"]
    o2 = result["oxygen"]
    dr = result["dryer"]
    wu = result["warmup"]
    print(f"  Water      : {wr.conductivity_us_cm:.4f} µS/cm  "
          f"(spec < 0.1)  {'✅' if wr.quality_ok else '❌'}")
    print(f"  Resistance : {wr.resistance_mohm_cm:.2f} MΩ·cm  "
          f"(spec > 10)   {'✅' if wr.resistance_mohm_cm >= 10 else '❌'}")
    print(f"  Resin      : {wr.resin_saturation_pct:.1f}%  "
          f"{'⚠ Replace soon' if wr.resin_warning else 'OK'}")
    print(f"  O₂ flow    : {o2.o2_flow_nm3_h:.4f} Nm³/h  "
          f"pressure {o2.o2_pressure_bar:.3f} bar  "
          f"safe: {'✅' if o2.safety_ok else '❌'}")
    print(f"  H₂ moisture: {dr.moisture_ppm:.3f} ppm  "
          f"(spec < 5)    {'✅' if dr.moisture_ppm <= 5 else '❌'}")
    print(f"  H₂ loss    : {dr.h2_loss_pct:.2f}%")
    print(f"  Stack temp : {wu.current_temp_c:.1f}°C  "
          f"η×{wu.efficiency_factor:.3f}  warm: {wu.is_warm}")
    print(f"  Aux power  : {result['aux_power_kw']:.3f} kW")
    print(f"  Maintenance: {result['maintenance'] or ['None needed']}")

    # Verify key specs
    assert o2.safety_ok,           "O₂ pressure safety violation"
    assert result["aux_power_kw"] < 1.0, "Aux power too high"
    assert 0.0 <= wu.efficiency_factor <= 1.0, "Efficiency factor out of range"
    print("\n✅ subsystems.py v4.1 — all tests passed")
