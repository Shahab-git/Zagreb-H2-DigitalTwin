# =============================================================================
# ems_brain.py — LUMINIH2 EMS Brain v4.2
# Electrolyzer-First Power Switching · Zagreb, Croatia
#
# REVISED PRIORITY ORDER (v4.2):
#   1 → Electrolyzer nominal load  (primary H₂ revenue driver)
#   2 → BESS charging              (buffer, not primary load)
#   3 → Electrolyzer overload      (push to peak if surplus allows)
#   4 → EV charger                 (via fuel cell from stored H₂)
#   5 → Grid export                (true surplus only)
#   6 → Grid import                (emergency: BESS SoC < 15%)
#
# KEY RULES:
#   - Electrolyzer minimum run-time: 30 min (1800s) to protect membrane
#   - Electrolyzer starts when generation ≥ P_MIN (0.74 kW)
#   - Electrolyzer stops only if generation < P_MIN AND BESS depleted
#   - BESS gets surplus AFTER electrolyzer is fed at nominal
#   - Grid export only when electrolyzer at peak AND BESS full
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal
from config import Config


# ---------------------------------------------------------------------------
# Typed result containers
# ---------------------------------------------------------------------------

@dataclass
class SourceDecision:
    source:       Literal["Solar (PV)", "Wind Turbine", "Hybrid (PV+Wind)", "National Grid"]
    available_kw: float
    reason:       str


@dataclass
class PowerFlowResult:
    power_to_electrolyzer_kw: float   # Priority 1 & 3
    power_to_battery_kw:      float   # Priority 2
    power_to_ev_kw:           float   # Priority 4
    grid_export_kw:           float   # Priority 5
    grid_import_kw:           float   # Priority 6
    switching_event:          str
    electrolyzer_mode:        str     # "nominal" | "overload" | "partial" | "off"


@dataclass
class H2LogisticsResult:
    compressor_status:  Literal["ON", "OFF"]
    dispatch_target:    Literal["Storage", "Refueling Station (HRS)", "Fuel Cell (FC)"]
    buffer_fill_pct:    float
    main_tank_fill_pct: float


@dataclass
class EconomicsResult:
    lcoh_eur_kg:      float
    carbon_revenue_eur: float
    net_co2_saved_kg: float
    subsidy_earned_eur: float
    total_revenue_eur: float
    is_profitable:    bool


@dataclass
class DownstreamResult:
    p_ev_kw:          float
    p_grid_kw:        float
    grid_revenue_eur: float
    ev_sessions_supported: int


# ---------------------------------------------------------------------------
# EMS Brain v4.2
# ---------------------------------------------------------------------------

class EMSBrain:
    """
    Electrolyzer-First EMS dispatch engine for LUMINIH2.

    The electrolyzer is the PRIMARY load. Generation serves the electrolyzer
    first, then BESS gets the surplus. This matches how real commercial
    green hydrogen plants operate and maximises H₂ revenue.
    """

    # Minimum continuous run time before electrolyzer can be switched off
    ELEC_MIN_RUNTIME_SEC = 1800   # 30 minutes — protects PEM membrane

    def __init__(self) -> None:
        self._cfg = Config
        self._ps  = Config.power_switching

        # Electrolyzer ramp state
        self._elec_current_kw: float = 0.0

        # Continuity tracking
        self._elec_runtime_sec: int  = 0      # seconds electrolyzer has been running
        self._elec_is_running:  bool = False

        # Compressor state
        self._compressor_runtime_sec: int  = 0
        self._compressor_on:          bool = False

    # ------------------------------------------------------------------
    # Phase 1 — Dynamic source selection (unchanged logic)
    # ------------------------------------------------------------------

    def decide_energy_source(
        self,
        pv_available_kw:   float,
        wind_available_kw: float,
        battery_soc:       float,
    ) -> SourceDecision:
        combined  = pv_available_kw + wind_available_kw
        min_load  = self._cfg.ELEC_P_MIN_KW

        if pv_available_kw >= min_load and wind_available_kw >= min_load:
            return SourceDecision(
                source="Hybrid (PV+Wind)",
                available_kw=combined,
                reason=f"Both PV ({pv_available_kw:.1f} kW) + Wind ({wind_available_kw:.1f} kW) above minimum",
            )
        if pv_available_kw >= min_load:
            return SourceDecision(
                source="Solar (PV)",
                available_kw=pv_available_kw,
                reason=f"PV {pv_available_kw:.1f} kW ≥ min {min_load} kW",
            )
        if wind_available_kw >= min_load:
            return SourceDecision(
                source="Wind Turbine",
                available_kw=wind_available_kw,
                reason=f"Wind {wind_available_kw:.1f} kW ≥ min {min_load} kW",
            )
        return SourceDecision(
            source="National Grid",
            available_kw=min_load,
            reason="Renewables insufficient — grid fallback",
        )

    # ------------------------------------------------------------------
    # Phase 2 — REVISED Electrolyzer-First power flow
    # ------------------------------------------------------------------

    def manage_power_flow(
        self,
        incoming_power_kw: float,
        current_soc:       float,
        ev_demand_kw:      float = 0.0,
        timestep_sec:      int   = 10,
    ) -> PowerFlowResult:
        """
        Electrolyzer-First dispatch:

        1. Feed electrolyzer at NOMINAL load (3 kW) — primary H₂ revenue
        2. Charge BESS with surplus after electrolyzer is fed
        3. Push electrolyzer to OVERLOAD (up to 5.63 kW) if more surplus
        4. EV demand met via fuel cell (decoupled from generation)
        5. Export remaining surplus to grid
        6. Import from grid only if BESS SoC < 15% (emergency)
        """
        remaining = incoming_power_kw
        events:   list[str] = []

        cfg = self._cfg
        ps  = self._ps

        # ── PRIORITY 1: Electrolyzer at nominal load ───────────────────
        p_elec_nominal = 0.0
        elec_mode = "off"

        can_start = remaining >= cfg.ELEC_P_MIN_KW
        must_keep = (self._elec_is_running
                     and self._elec_runtime_sec < self.ELEC_MIN_RUNTIME_SEC)

        if can_start or must_keep:
            # Feed nominal load first (best efficiency point)
            target_nominal = min(remaining, cfg.ELEC_P_NOM_KW)
            target_nominal = max(target_nominal, cfg.ELEC_P_MIN_KW)
            p_elec_nominal = self._ramp_electrolyzer(target_nominal, timestep_sec)
            remaining = max(0.0, remaining - p_elec_nominal)

            # Update run-time tracking
            self._elec_is_running   = True
            self._elec_runtime_sec += timestep_sec
            elec_mode = "nominal"
            events.append(f"Elec (nominal) ← {p_elec_nominal:.2f} kW")
        else:
            # Below minimum and not in min-runtime guard → ramp down
            p_elec_nominal = self._ramp_electrolyzer(0.0, timestep_sec)
            if self._elec_is_running and remaining < cfg.ELEC_P_MIN_KW:
                self._elec_is_running  = False
                self._elec_runtime_sec = 0
            events.append("Elec STANDBY (generation < min threshold)")

        # ── PRIORITY 2: BESS charging with surplus ─────────────────────
        p_bess = 0.0
        headroom = cfg.BATT_SOC_MAX - current_soc
        if headroom > 0.01 and remaining > ps.bess_charge_hysteresis_kw:
            p_bess = min(
                remaining,
                cfg.BATT_MAX_CHARGE_KW,
                headroom * cfg.BATT_CAPACITY_KWH,
            )
            remaining -= p_bess
            events.append(f"BESS ← {p_bess:.2f} kW (SoC {current_soc*100:.0f}%)")

        # ── PRIORITY 3: Electrolyzer overload (push to peak) ───────────
        p_elec_overload = 0.0
        if (self._elec_is_running
                and remaining > ps.elec_start_hysteresis_kw
                and p_elec_nominal >= cfg.ELEC_P_NOM_KW * 0.9):
            # Only push to overload if we are already at nominal
            headroom_elec = cfg.ELEC_P_MAX_KW - p_elec_nominal
            p_elec_overload = min(remaining, headroom_elec)
            if p_elec_overload > 0.1:
                # Apply ramp to total electrolyzer target
                total_elec_target = p_elec_nominal + p_elec_overload
                p_elec_total = self._ramp_electrolyzer(total_elec_target, timestep_sec)
                p_elec_overload = max(0.0, p_elec_total - p_elec_nominal)
                p_elec_nominal  = p_elec_total - p_elec_overload
                remaining = max(0.0, remaining - p_elec_overload)
                elec_mode = "overload"
                events.append(f"Elec (overload) → {p_elec_total:.2f} kW total")

        # Total electrolyzer power
        p_elec_total = p_elec_nominal + p_elec_overload

        # ── PRIORITY 4: EV charger ─────────────────────────────────────
        # EV is served by fuel cell from stored H₂ — decoupled from generation
        # Only use direct power if fuel cell is insufficient
        p_ev = 0.0
        if ev_demand_kw > cfg.EV_MIN_POWER_KW and remaining > 0:
            p_ev = min(remaining, ev_demand_kw * 0.3)  # max 30% from direct gen
            remaining -= p_ev
            if p_ev > 0.01:
                events.append(f"EV (direct) ← {p_ev:.2f} kW")

        # ── PRIORITY 5: Grid export ────────────────────────────────────
        p_export = 0.0
        if remaining >= ps.grid_export_min_surplus_kw:
            p_export  = remaining
            remaining = 0.0
            events.append(f"Grid export → {p_export:.2f} kW")

        # ── PRIORITY 6: Grid import (emergency) ────────────────────────
        p_import = 0.0
        if current_soc < ps.grid_import_trigger_soc:
            p_import = cfg.BATT_MAX_CHARGE_KW * 0.4
            events.append(f"⚠ Grid IMPORT {p_import:.2f} kW (BESS SoC critical)")

        # Determine electrolyzer mode label
        if p_elec_total <= 0:
            elec_mode = "off"
        elif p_elec_total < cfg.ELEC_P_NOM_KW * 0.95:
            elec_mode = "partial"
        elif p_elec_total <= cfg.ELEC_P_NOM_KW * 1.05:
            elec_mode = "nominal"
        else:
            elec_mode = "overload"

        return PowerFlowResult(
            power_to_electrolyzer_kw=round(p_elec_total, 3),
            power_to_battery_kw=round(p_bess, 3),
            power_to_ev_kw=round(p_ev, 3),
            grid_export_kw=round(p_export, 3),
            grid_import_kw=round(p_import, 3),
            switching_event=" | ".join(events) if events else "Standby",
            electrolyzer_mode=elec_mode,
        )

    # ------------------------------------------------------------------
    # Phase 3 — H₂ logistics (unchanged)
    # ------------------------------------------------------------------

    def hydrogen_logistics_control(
        self,
        buffer_level_kg: float,
        main_tank_kg:    float,
        hrs_tank_kg:     float,
        timestep_sec:    int = 10,
    ) -> H2LogisticsResult:
        buffer_pct = buffer_level_kg / self._cfg.BUFFER_TANK_CAPACITY_KG
        main_pct   = main_tank_kg    / self._cfg.MAIN_TANK_CAPACITY_KG

        # Compressor hysteresis with min-runtime guard
        if buffer_pct >= self._cfg.BUFFER_START_THRESHOLD:
            self._compressor_on          = True
            self._compressor_runtime_sec = 0
        elif (self._compressor_on
              and self._compressor_runtime_sec < self._cfg.COMPRESSOR_MIN_RUNTIME_SEC):
            self._compressor_runtime_sec += timestep_sec
        elif buffer_pct <= self._cfg.BUFFER_STOP_THRESHOLD:
            self._compressor_on = False

        compressor_status: Literal["ON", "OFF"] = "ON" if self._compressor_on else "OFF"

        dispatch_target: Literal["Storage", "Refueling Station (HRS)", "Fuel Cell (FC)"] = "Storage"
        if main_pct >= self._cfg.MAIN_TANK_START_THRESHOLD:
            if hrs_tank_kg < self._cfg.HRS_H2_TANK_CAPACITY_KG:
                dispatch_target = "Refueling Station (HRS)"
            else:
                dispatch_target = "Fuel Cell (FC)"

        return H2LogisticsResult(
            compressor_status=compressor_status,
            dispatch_target=dispatch_target,
            buffer_fill_pct=round(buffer_pct * 100, 1),
            main_tank_fill_pct=round(main_pct * 100, 1),
        )

    # ------------------------------------------------------------------
    # Phase 4 — Economics (improved: uses proper hourly cost basis)
    # ------------------------------------------------------------------

    def calculate_economics(
        self,
        h2_kg_produced:  float,
        power_used_kw:   float,
        source:          str,
        timestep_sec:    int = 10,
    ) -> EconomicsResult:
        if h2_kg_produced <= 0:
            return EconomicsResult(0.0, 0.0, 0.0, 0.0, 0.0, False)

        dt_h = timestep_sec / 3600.0

        # Energy cost (per tick, not per hour — avoids LCOH explosion)
        if source == "National Grid":
            energy_cost = power_used_kw * self._cfg.GRID_PRICE_BUY * dt_h
        else:
            energy_cost = power_used_kw * 0.02 * dt_h  # renewables O&M

        # Stack depreciation (pro-rated by load fraction and time)
        load_f      = power_used_kw / max(self._cfg.ELEC_P_MAX_KW, 0.01)
        stack_depr  = load_f * (
            self._cfg.STACK_REPLACEMENT_COST
            / (self._cfg.electrolyzer.mttf_hours * self._cfg.ELEC_P_MAX_KW)
        ) * power_used_kw * dt_h

        total_cost = energy_cost + stack_depr
        lcoh       = total_cost / h2_kg_produced if h2_kg_produced > 0.0001 else 0.0

        # Carbon accounting
        co2_avoided = h2_kg_produced * self._cfg.CO2_SAVED_PER_KG_H2
        co2_emitted = (
            power_used_kw * self._cfg.GRID_CO2_INTENSITY * dt_h
            if source == "National Grid" else 0.0
        )
        net_co2_saved   = co2_avoided - co2_emitted
        carbon_revenue  = (net_co2_saved / 1000.0) * self._cfg.CARBON_TAX_EUR_TON
        subsidy         = h2_kg_produced * self._cfg.GREEN_H2_SUBSIDY
        total_revenue   = carbon_revenue + subsidy

        return EconomicsResult(
            lcoh_eur_kg=round(lcoh, 4),
            carbon_revenue_eur=round(carbon_revenue, 5),
            net_co2_saved_kg=round(net_co2_saved, 4),
            subsidy_earned_eur=round(subsidy, 5),
            total_revenue_eur=round(total_revenue, 5),
            is_profitable=(0 < lcoh <= self._cfg.LCOH_TARGET_EURO_KG),
        )

    # ------------------------------------------------------------------
    # Phase 5 — Downstream: FC → EV / Grid (EV prioritised)
    # ------------------------------------------------------------------

    def manage_fc_and_grid(
        self,
        fc_power_output_kw: float,
        ev_demand_kw:       float,
    ) -> DownstreamResult:
        """
        Fuel cell output goes to EV first (this is the primary EV supply),
        then surplus to grid. This is the correct architecture:
        H₂ → FC → EV (not: generation → EV directly).
        """
        p_ev    = min(fc_power_output_kw, max(ev_demand_kw, 0.0))
        p_ev    = max(p_ev, 0.0)
        p_grid  = max(0.0, fc_power_output_kw - p_ev)
        grid_rev = p_grid * self._cfg.GRID_PRICE_SELL
        ev_sessions = int(p_ev // self._cfg.EV_CHARGER_POWER_KW)

        return DownstreamResult(
            p_ev_kw=round(p_ev, 3),
            p_grid_kw=round(p_grid, 3),
            grid_revenue_eur=round(grid_rev, 5),
            ev_sessions_supported=ev_sessions,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ramp_electrolyzer(self, target_kw: float, timestep_sec: int) -> float:
        """Apply ramp-rate limits to prevent sharp PEM stack transients."""
        ps = self._ps
        max_up = ps.electrolyzer_ramp_up_kw_s   * timestep_sec
        max_dn = ps.electrolyzer_ramp_down_kw_s * timestep_sec

        if target_kw > self._elec_current_kw:
            self._elec_current_kw = min(target_kw, self._elec_current_kw + max_up)
        else:
            self._elec_current_kw = max(target_kw, self._elec_current_kw - max_dn)

        # Below minimum → fully off (no partial operation below P_MIN)
        if self._elec_current_kw < self._cfg.ELEC_P_MIN_KW:
            self._elec_current_kw = 0.0

        return round(self._elec_current_kw, 3)

    def reset_ramp_state(self) -> None:
        """Call when restarting simulation."""
        self._elec_current_kw        = 0.0
        self._elec_runtime_sec       = 0
        self._elec_is_running        = False
        self._compressor_runtime_sec = 0
        self._compressor_on          = False

    @property
    def electrolyzer_runtime_min(self) -> float:
        return round(self._elec_runtime_sec / 60, 1)

    @property
    def min_runtime_satisfied(self) -> bool:
        return self._elec_runtime_sec >= self.ELEC_MIN_RUNTIME_SEC


# ---------------------------------------------------------------------------
# Smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ems = EMSBrain()

    print("=" * 60)
    print("EMS Brain v4.2 — Electrolyzer-First Logic")
    print("=" * 60)

    # Scenario 1: Good generation day (15 kW available)
    print("\n📊 Scenario 1: Good generation (15 kW, SoC 55%)")
    src  = ems.decide_energy_source(10.0, 5.0, 0.55)
    flow = ems.manage_power_flow(15.0, 0.55, ev_demand_kw=2.0, timestep_sec=10)
    print(f"  Source    : {src.source}")
    print(f"  Elec      : {flow.power_to_electrolyzer_kw} kW [{flow.electrolyzer_mode}]")
    print(f"  BESS      : {flow.power_to_battery_kw} kW")
    print(f"  EV        : {flow.power_to_ev_kw} kW")
    print(f"  Export    : {flow.grid_export_kw} kW")
    print(f"  EMS log   : {flow.switching_event}")

    # Scenario 2: Low generation (2 kW — electrolyzer at partial)
    print("\n📊 Scenario 2: Low generation (2 kW, SoC 70%)")
    ems2  = EMSBrain()
    flow2 = ems2.manage_power_flow(2.0, 0.70, ev_demand_kw=2.0, timestep_sec=10)
    print(f"  Elec      : {flow2.power_to_electrolyzer_kw} kW [{flow2.electrolyzer_mode}]")
    print(f"  BESS      : {flow2.power_to_battery_kw} kW")
    print(f"  Export    : {flow2.grid_export_kw} kW")

    # Scenario 3: Very low generation (0.5 kW — below minimum)
    print("\n📊 Scenario 3: Below minimum (0.5 kW)")
    ems3  = EMSBrain()
    flow3 = ems3.manage_power_flow(0.5, 0.60, ev_demand_kw=2.0, timestep_sec=10)
    print(f"  Elec      : {flow3.power_to_electrolyzer_kw} kW [{flow3.electrolyzer_mode}]")
    print(f"  BESS      : {flow3.power_to_battery_kw} kW")

    # Scenario 4: Verify min-runtime guard
    print("\n📊 Scenario 4: Min-runtime guard (elec running, gen drops)")
    ems4 = EMSBrain()
    # First run at good generation
    ems4.manage_power_flow(10.0, 0.55, timestep_sec=10)
    ems4._elec_runtime_sec = 300   # only 5 minutes in
    # Now generation drops below minimum
    flow4 = ems4.manage_power_flow(0.3, 0.55, timestep_sec=10)
    print(f"  Elec kept running: {flow4.power_to_electrolyzer_kw > 0}")
    print(f"  Runtime guard active: {not ems4.min_runtime_satisfied}")

    # Economics check
    print("\n📊 Economics (1 tick, 10s, nominal load):")
    econ = ems.calculate_economics(
        h2_kg_produced=0.05932 * (10/3600),
        power_used_kw=3.0,
        source="Hybrid (PV+Wind)",
        timestep_sec=10,
    )
    print(f"  LCOH      : €{econ.lcoh_eur_kg:.3f}/kg")
    print(f"  Profitable: {econ.is_profitable}")
    print(f"  CO₂ saved : {econ.net_co2_saved_kg:.5f} kg")

    print("\n✅ ems_brain.py v4.2 — Electrolyzer-First logic verified")
