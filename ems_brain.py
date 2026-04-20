# =============================================================================
# ems_brain.py — LUMINIH2 EMS Brain
# Economic & Strategy Engine: LCOH, Carbon Credits, Smart Power Switching
# Version: 3.2 (Streamlit-Ready · Power-Switching Optimised)
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
    source: Literal["Solar (PV)", "Wind Turbine", "Hybrid (PV+Wind)", "National Grid"]
    available_kw: float
    reason: str


@dataclass
class PowerFlowResult:
    power_to_battery_kw: float
    power_to_electrolyzer_kw: float
    power_to_ev_kw: float
    grid_export_kw: float
    grid_import_kw: float
    switching_event: str          # Human-readable log for Streamlit


@dataclass
class H2LogisticsResult:
    compressor_status: Literal["ON", "OFF"]
    dispatch_target: Literal["Storage", "Refueling Station (HRS)", "Fuel Cell (FC)"]
    buffer_fill_pct: float
    main_tank_fill_pct: float


@dataclass
class EconomicsResult:
    lcoh_eur_kg: float
    carbon_revenue_eur: float
    net_co2_saved_kg: float
    subsidy_earned_eur: float
    total_revenue_eur: float
    is_profitable: bool


@dataclass
class DownstreamResult:
    p_ev_kw: float
    p_grid_kw: float
    grid_revenue_eur: float
    ev_sessions_supported: int


# ---------------------------------------------------------------------------
# EMS Brain
# ---------------------------------------------------------------------------

class EMSBrain:
    """
    Five-phase smart energy dispatch engine for LUMINIH2.

    Power switching priority (from Config.power_switching):
        1 → Charge BESS          (security)
        2 → Feed Electrolyzer    (green H₂)
        3 → Supply EV chargers   (via FC if needed)
        4 → Export to grid       (revenue)
        5 → Import from grid     (emergency only, SoC < trigger)
    """

    def __init__(self) -> None:
        self._cfg = Config
        self._ps = Config.power_switching
        # Electrolyzer ramp state
        self._elec_current_kw: float = 0.0
        # Compressor runtime accumulator (seconds)
        self._compressor_runtime_sec: int = 0
        self._compressor_on: bool = False

    # ------------------------------------------------------------------
    # Phase 1 — Dynamic source selection
    # ------------------------------------------------------------------

    def decide_energy_source(
        self,
        pv_available_kw: float,
        wind_available_kw: float,
        battery_soc: float,
    ) -> SourceDecision:
        """
        Selects the cheapest/greenest available source.
        Both PV and Wind can be used simultaneously (Hybrid).
        Grid is last-resort only.
        """
        combined = pv_available_kw + wind_available_kw
        min_load = self._cfg.ELEC_P_MIN_KW

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

        # Grid fallback — only if BESS cannot cover demand alone
        if battery_soc > self._cfg.BATT_SOC_MIN + 0.05:
            return SourceDecision(
                source="National Grid",
                available_kw=min_load,
                reason=f"Renewables insufficient; BESS at {battery_soc*100:.0f}% — grid emergency import",
            )

        return SourceDecision(
            source="National Grid",
            available_kw=min_load,
            reason="All renewables insufficient; BESS critically low — grid fallback",
        )

    # ------------------------------------------------------------------
    # Phase 2 — Power flow & switching with hysteresis + ramp control
    # ------------------------------------------------------------------

    def manage_power_flow(
        self,
        incoming_power_kw: float,
        current_soc: float,
        ev_demand_kw: float = 0.0,
        timestep_sec: int = 10,
    ) -> PowerFlowResult:
        """
        Dispatches power according to priority order with:
        - BESS charge/discharge hysteresis band
        - Electrolyzer ramp-rate limiting
        - Minimum surplus threshold before grid export
        - Grid import only below trigger SoC
        """
        remaining = incoming_power_kw
        events: list[str] = []

        # ── Priority 1: Charge BESS ────────────────────────────────────
        p_bess = 0.0
        headroom = self._cfg.BATT_SOC_MAX - current_soc
        if headroom > 0 and remaining > self._ps.bess_charge_hysteresis_kw:
            p_bess = min(
                remaining,
                self._cfg.BATT_MAX_CHARGE_KW,
                headroom * self._cfg.BATT_CAPACITY_KWH,  # don't overshoot
            )
            remaining -= p_bess
            events.append(f"BESS ← {p_bess:.2f} kW (SoC {current_soc*100:.0f}%)")

        # ── Priority 2: Electrolyzer (with ramp-rate control) ──────────
        p_elec_target = 0.0
        if remaining > self._ps.elec_start_hysteresis_kw:
            p_elec_target = min(remaining, self._cfg.ELEC_P_MAX_KW)
            p_elec_target = max(p_elec_target, self._cfg.ELEC_P_MIN_KW)

        p_elec = self._ramp_electrolyzer(p_elec_target, timestep_sec)
        remaining = max(0.0, remaining - p_elec)
        if p_elec > 0:
            events.append(f"Elec ← {p_elec:.2f} kW (ramp)")

        # ── Priority 3: EV chargers ────────────────────────────────────
        p_ev = 0.0
        if ev_demand_kw > self._cfg.EV_MIN_POWER_KW and remaining > 0:
            p_ev = min(remaining, ev_demand_kw, self._cfg.EV_CHARGER_POWER_KW)
            remaining -= p_ev
            events.append(f"EV ← {p_ev:.2f} kW")

        # ── Priority 4: Grid export (only meaningful surplus) ──────────
        p_export = 0.0
        if remaining >= self._ps.grid_export_min_surplus_kw:
            p_export = remaining
            remaining = 0.0
            events.append(f"Grid export → {p_export:.2f} kW")

        # ── Priority 5: Grid import (emergency SoC only) ──────────────
        p_import = 0.0
        if current_soc < self._ps.grid_import_trigger_soc:
            p_import = self._cfg.BATT_MAX_CHARGE_KW * 0.5   # soft import
            events.append(f"Grid IMPORT {p_import:.2f} kW (SoC critical!)")

        return PowerFlowResult(
            power_to_battery_kw=round(p_bess, 3),
            power_to_electrolyzer_kw=round(p_elec, 3),
            power_to_ev_kw=round(p_ev, 3),
            grid_export_kw=round(p_export, 3),
            grid_import_kw=round(p_import, 3),
            switching_event=" | ".join(events) if events else "Standby",
        )

    # ------------------------------------------------------------------
    # Phase 3 — H₂ logistics (compressor + dispatch)
    # ------------------------------------------------------------------

    def hydrogen_logistics_control(
        self,
        buffer_level_kg: float,
        main_tank_kg: float,
        hrs_tank_kg: float,
        timestep_sec: int = 10,
    ) -> H2LogisticsResult:
        """
        Compressor hysteresis with minimum runtime guard.
        Dispatch priority: HRS refuelling > Fuel Cell power generation.
        """
        buffer_pct = buffer_level_kg / self._cfg.BUFFER_TANK_CAPACITY_KG
        main_pct = main_tank_kg / self._cfg.MAIN_TANK_CAPACITY_KG

        # Compressor hysteresis
        if buffer_pct >= self._cfg.BUFFER_START_THRESHOLD:
            self._compressor_on = True
            self._compressor_runtime_sec = 0
        elif (
            self._compressor_on
            and self._compressor_runtime_sec < self._cfg.COMPRESSOR_MIN_RUNTIME_SEC
        ):
            # Keep ON until minimum runtime satisfied (prevents rapid cycling)
            self._compressor_runtime_sec += timestep_sec
        elif buffer_pct <= self._cfg.BUFFER_STOP_THRESHOLD:
            self._compressor_on = False

        compressor_status: Literal["ON", "OFF"] = "ON" if self._compressor_on else "OFF"

        # Dispatch decision
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
    # Phase 4 — LCOH & carbon economics
    # ------------------------------------------------------------------

    def calculate_economics(
        self,
        h2_kg_produced: float,
        power_used_kw: float,
        source: str,
    ) -> EconomicsResult:
        """
        Real-time LCOH with stack depreciation + EU ETS carbon credits.
        """
        if h2_kg_produced <= 0:
            return EconomicsResult(0.0, 0.0, 0.0, 0.0, 0.0, False)

        # Energy cost
        if source == "National Grid":
            energy_cost_eur = power_used_kw * self._cfg.GRID_PRICE_BUY
        else:
            energy_cost_eur = power_used_kw * 0.02   # renewables O&M rate

        # Stack depreciation (pro-rated by load fraction)
        load_fraction = power_used_kw / self._cfg.ELEC_P_MAX_KW
        stack_depr_eur = load_fraction * (
            self._cfg.STACK_REPLACEMENT_COST / (self._cfg.ELEC_P_MAX_KW * 8760)
        )

        total_cost_eur = energy_cost_eur + stack_depr_eur
        lcoh = total_cost_eur / h2_kg_produced

        # Carbon accounting
        co2_avoided_kg = h2_kg_produced * self._cfg.CO2_SAVED_PER_KG_H2
        co2_emitted_kg = (
            power_used_kw * self._cfg.GRID_CO2_INTENSITY
            if source == "National Grid"
            else 0.0
        )
        net_co2_saved_kg = co2_avoided_kg - co2_emitted_kg
        carbon_revenue_eur = (net_co2_saved_kg / 1000.0) * self._cfg.CARBON_TAX_EUR_TON

        # EU green H₂ subsidy
        subsidy_eur = h2_kg_produced * self._cfg.GREEN_H2_SUBSIDY
        total_revenue_eur = carbon_revenue_eur + subsidy_eur

        return EconomicsResult(
            lcoh_eur_kg=round(lcoh, 4),
            carbon_revenue_eur=round(carbon_revenue_eur, 4),
            net_co2_saved_kg=round(net_co2_saved_kg, 3),
            subsidy_earned_eur=round(subsidy_eur, 4),
            total_revenue_eur=round(total_revenue_eur, 4),
            is_profitable=(lcoh <= self._cfg.LCOH_TARGET_EURO_KG),
        )

    # ------------------------------------------------------------------
    # Phase 5 — Downstream: FC → EV / Grid
    # ------------------------------------------------------------------

    def manage_fc_and_grid(
        self,
        fc_power_output_kw: float,
        ev_demand_kw: float,
    ) -> DownstreamResult:
        """
        Allocates fuel-cell output: EV charging first, surplus to grid.
        """
        p_ev = min(fc_power_output_kw, max(ev_demand_kw, 0.0))
        p_ev = max(p_ev, 0.0)
        p_grid = max(0.0, fc_power_output_kw - p_ev)
        grid_revenue_eur = p_grid * self._cfg.GRID_PRICE_SELL

        ev_sessions = int(p_ev // self._cfg.EV_CHARGER_POWER_KW)

        return DownstreamResult(
            p_ev_kw=round(p_ev, 3),
            p_grid_kw=round(p_grid, 3),
            grid_revenue_eur=round(grid_revenue_eur, 4),
            ev_sessions_supported=ev_sessions,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ramp_electrolyzer(self, target_kw: float, timestep_sec: int) -> float:
        """Apply ramp-rate limits to prevent sharp load transients on PEM stack."""
        max_step_up = self._ps.electrolyzer_ramp_up_kw_s * timestep_sec
        max_step_dn = self._ps.electrolyzer_ramp_down_kw_s * timestep_sec

        if target_kw > self._elec_current_kw:
            self._elec_current_kw = min(target_kw, self._elec_current_kw + max_step_up)
        else:
            self._elec_current_kw = max(target_kw, self._elec_current_kw - max_step_dn)

        # Clamp to valid operating window
        if self._elec_current_kw < self._cfg.ELEC_P_MIN_KW:
            self._elec_current_kw = 0.0   # below min → fully off

        return round(self._elec_current_kw, 3)

    def reset_ramp_state(self) -> None:
        """Call when restarting simulation to clear ramp history."""
        self._elec_current_kw = 0.0
        self._compressor_runtime_sec = 0
        self._compressor_on = False


# ---------------------------------------------------------------------------
# Quick smoke-test (python ems_brain.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ems = EMSBrain()

    src = ems.decide_energy_source(
        pv_available_kw=35.0, wind_available_kw=18.0, battery_soc=0.55
    )
    print(f"\nSource  : {src.source}")
    print(f"Reason  : {src.reason}")

    flow = ems.manage_power_flow(
        incoming_power_kw=src.available_kw,
        current_soc=0.55,
        ev_demand_kw=15.0,
        timestep_sec=10,
    )
    print(f"\nFlow    : {flow.switching_event}")
    print(f"  BESS  : {flow.power_to_battery_kw} kW")
    print(f"  Elec  : {flow.power_to_electrolyzer_kw} kW")
    print(f"  EV    : {flow.power_to_ev_kw} kW")
    print(f"  Export: {flow.grid_export_kw} kW")

    econ = ems.calculate_economics(
        h2_kg_produced=0.05,
        power_used_kw=flow.power_to_electrolyzer_kw,
        source=src.source,
    )
    print(f"\nEcon    : LCOH={econ.lcoh_eur_kg:.3f} €/kg | "
          f"CO₂ saved={econ.net_co2_saved_kg:.2f} kg | "
          f"Profitable={econ.is_profitable}")

    print("\n✅ ems_brain.py v3.2 — all phases OK")
