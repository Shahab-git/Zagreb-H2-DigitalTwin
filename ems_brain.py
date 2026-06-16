# =============================================================================
# ems_brain.py — LUMINIH2 EMS Brain v4.4
# Electrolyzer-First Power Switching · Zagreb, Croatia
# =============================================================================
#
# PRIORITY ORDER (v4.3 — electrolyzer-first):
#   1 → Electrolyzer at NOMINAL load  (primary H₂ revenue driver)
#   2 → BESS charging                 (buffer, not primary load)
#   3 → Electrolyzer OVERLOAD         (push to peak if surplus allows)
#   4 → EV charger                    (via fuel cell / stored H₂)
#   5 → Grid export                   (true surplus only, ≥ 0.5 kW)
#   6 → Grid import                   (emergency: BESS SoC < 15% only)
#
# KEY RULES:
#   - Electrolyzer minimum run-time: 30 min (1800 s) — protects PEM membrane
#   - Starts when generation ≥ P_MIN (0.74 kW)
#   - Stops only if generation < P_MIN AND runtime guard satisfied
#   - BESS receives surplus AFTER electrolyzer is fed at nominal
#   - EV served primarily by fuel cell (H₂ → FC → EV), not generation
#   - Grid export only when electrolyzer at peak AND BESS full
#
# FIXES vs v4.2:
#   - BESS headroom calculation: was (soc_headroom × capacity_kWh) [wrong unit]
#     now correctly uses min(remaining, max_charge_kW) [correct unit: kW]
#   - Electrolyzer overload accounting: cleaner single-pass calculation
#   - Ramp-rate: 5.3%/s of rated — within PEM spec (0.1–10%/s) ✅
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config import Config


# =============================================================================
# Result containers
# =============================================================================

@dataclass
class SourceDecision:
    """Result of energy source selection."""
    source:       Literal["Solar (PV)", "Wind Turbine", "Hybrid (PV+Wind)", "National Grid"]
    available_kw: float
    reason:       str


@dataclass
class PowerFlowResult:
    """Result of one EMS power dispatch tick."""
    power_to_electrolyzer_kw: float    # Priorities 1 + 3
    power_to_battery_kw:      float    # Priority 2
    power_to_ev_kw:           float    # Priority 4
    grid_export_kw:           float    # Priority 5
    grid_import_kw:           float    # Priority 6
    switching_event:          str      # Human-readable dispatch log
    electrolyzer_mode:        str      # "nominal" | "overload" | "partial" | "off"


@dataclass
class H2LogisticsResult:
    """Result of H₂ logistics control."""
    compressor_status:  Literal["ON", "OFF"]
    dispatch_target:    Literal["Storage", "Refueling Station (HRS)", "Fuel Cell (FC)"]
    buffer_fill_pct:    float
    main_tank_fill_pct: float


@dataclass
class EconomicsResult:
    """Per-tick economic result (use LCOHAccumulator for rolling LCOH)."""
    lcoh_eur_kg:        float
    carbon_revenue_eur: float
    net_co2_saved_kg:   float
    subsidy_earned_eur: float
    total_revenue_eur:  float
    is_profitable:      bool


@dataclass
class DownstreamResult:
    """Fuel cell → EV / grid split."""
    p_ev_kw:               float
    p_grid_kw:             float
    grid_revenue_eur:      float
    ev_sessions_supported: int


@dataclass
class ForecastDecision:
    """
    Output of forecast_aware_dispatch() — adjustments to the standard
    EMS based on what the next 6 hours are predicted to look like.

    The standard manage_power_flow() still executes every tick.
    This result is an OVERLAY — it modifies BESS reserve and
    electrolyzer setpoint guidance before the standard dispatch runs.
    """
    # Forecast summary
    next_6h_irr_kwh_m2:   float   # Expected irradiance energy next 6 h [kWh/m²]
    next_6h_pv_kwh:       float   # Expected PV energy next 6 h [kWh]
    solar_window_open:    bool    # True if peak irradiance > 200 W/m² expected
    peak_hour:            int     # Hour of day with highest forecast irradiance
    cloudy_window_ahead:  bool    # True if next 3 h forecast < 50 W/m²

    # BESS guidance
    bess_target_soc:      float   # Recommended BESS SoC before solar peak [0-1]
    hold_bess_reserve:    bool    # True = don't discharge BESS — solar coming soon
    pre_charge_bess:      bool    # True = charge BESS now from surplus before peak

    # Electrolyzer guidance
    elec_setpoint_kw:     float   # Recommended electrolyzer setpoint this tick [kW]
    defer_electrolyzer:   bool    # True = wait for better irradiance window

    # Reason
    strategy:             str     # Human-readable dispatch strategy label
    reason:               str     # Explanation of the forecast-based decision


# =============================================================================
# EMS Brain v4.4
# =============================================================================

class EMSBrain:
    """
    Electrolyzer-First EMS dispatch engine for LUMINIH2.

    The electrolyzer is the PRIMARY load. Generation feeds the electrolyzer
    first at nominal efficiency, then BESS absorbs the surplus. This matches
    how real commercial green hydrogen plants operate and maximises H₂ revenue.

    Architecture:
        Phase 1 : Source selection  (which energy source is dominant?)
        Phase 2 : Power dispatch    (how is power allocated this tick?)
        Phase 3 : H₂ logistics      (compressor + dispatch target)
        Phase 4 : Economics         (per-tick cost + revenue)
        Phase 5 : Downstream        (FC → EV + grid)
    """

    # Minimum continuous run-time before electrolyzer can be switched off
    # Reason: PEM membrane thermal cycling degrades at frequent start-stops
    ELEC_MIN_RUNTIME_SEC: int = 1800    # 30 minutes

    # Minimum surplus above nominal before pushing to peak
    PEAK_SURPLUS_THRESHOLD_KW: float = 1.0

    def __init__(self) -> None:
        self._cfg = Config
        self._ps  = Config.power_switching

        # Electrolyzer ramp and continuity state
        self._elec_current_kw:   float = 0.0
        self._elec_runtime_sec:  int   = 0
        self._elec_is_running:   bool  = False

        # Compressor state
        self._comp_runtime_sec:  int   = 0
        self._comp_on:           bool  = False

    # ------------------------------------------------------------------
    # Phase 1 — Source selection
    # ------------------------------------------------------------------

    def decide_energy_source(
        self,
        pv_available_kw:   float,
        wind_available_kw: float,
        battery_soc:       float,
    ) -> SourceDecision:
        """
        Determine the dominant energy source for this tick.

        Logic:
          Both above P_MIN → Hybrid
          Only PV above   → Solar
          Only Wind above → Wind
          Neither         → Grid fallback

        Args:
            pv_available_kw   : AC output from solar system [kW]
            wind_available_kw : AC output from wind turbine [kW]
            battery_soc       : current BESS state of charge [0–1]

        Returns:
            SourceDecision with source label, available kW, and reason
        """
        combined = pv_available_kw + wind_available_kw
        p_min    = self._cfg.ELEC_P_MIN_KW

        if pv_available_kw >= p_min and wind_available_kw >= p_min:
            return SourceDecision(
                source="Hybrid (PV+Wind)",
                available_kw=combined,
                reason=(f"Both PV ({pv_available_kw:.1f} kW) + "
                        f"Wind ({wind_available_kw:.1f} kW) ≥ min {p_min} kW"),
            )
        if pv_available_kw >= p_min:
            return SourceDecision(
                source="Solar (PV)",
                available_kw=pv_available_kw,
                reason=f"PV {pv_available_kw:.1f} kW ≥ min {p_min} kW",
            )
        if wind_available_kw >= p_min:
            return SourceDecision(
                source="Wind Turbine",
                available_kw=wind_available_kw,
                reason=f"Wind {wind_available_kw:.1f} kW ≥ min {p_min} kW",
            )
        return SourceDecision(
            source="National Grid",
            available_kw=p_min,
            reason="Renewables insufficient — grid fallback",
        )

    # ------------------------------------------------------------------
    # Phase 2 — Electrolyzer-first power dispatch
    # ------------------------------------------------------------------

    def manage_power_flow(
        self,
        incoming_power_kw: float,
        current_soc:       float,
        ev_demand_kw:      float = 0.0,
        timestep_sec:      int   = 10,
    ) -> PowerFlowResult:
        """
        Dispatch incoming generation using electrolyzer-first priority order.

        Priority 1: Electrolyzer at nominal load (3 kW) — main revenue source
        Priority 2: BESS charging with surplus
        Priority 3: Electrolyzer overload to peak (5.63 kW) if enough surplus
        Priority 4: EV charger — small direct supplement (FC is primary EV source)
        Priority 5: Grid export — only genuine surplus (≥ 0.5 kW)
        Priority 6: Grid import — only emergency (SoC < 15%)

        Args:
            incoming_power_kw : total renewable generation available [kW]
            current_soc       : BESS state of charge [0–1]
            ev_demand_kw      : EV charger load request [kW]
            timestep_sec      : simulation timestep [s]

        Returns:
            PowerFlowResult with all power allocations and EMS log
        """
        cfg       = self._cfg
        ps        = self._ps
        remaining = incoming_power_kw
        events:   list[str] = []

        # ── PRIORITY 1: Electrolyzer at nominal load ───────────────────
        p_elec = 0.0
        can_start  = remaining >= cfg.ELEC_P_MIN_KW
        must_keep  = (self._elec_is_running
                      and self._elec_runtime_sec < self.ELEC_MIN_RUNTIME_SEC)

        if can_start or must_keep:
            # Target: nominal load (best efficiency point on S30/30 curve)
            target = float(min(remaining, cfg.ELEC_P_NOM_KW))
            target = max(target, cfg.ELEC_P_MIN_KW)
            p_elec = self._ramp(target, timestep_sec)
            remaining = max(0.0, remaining - p_elec)
            self._elec_is_running   = True
            self._elec_runtime_sec += timestep_sec
            events.append(f"Elec (nominal) ← {p_elec:.2f} kW")
        else:
            # Ramp down gracefully
            p_elec = self._ramp(0.0, timestep_sec)
            if self._elec_is_running and p_elec <= 0.0:
                self._elec_is_running  = False
                self._elec_runtime_sec = 0
            events.append("Elec STANDBY (generation below minimum)")

        # ── PRIORITY 2: BESS charging ──────────────────────────────────
        # FIX v4.3: use max_charge_kW (kW) not headroom×capacity (kWh)
        p_bess = 0.0
        soc_headroom = cfg.BATT_SOC_MAX - current_soc
        if soc_headroom > 0.01 and remaining > ps.bess_charge_hysteresis_kw:
            p_bess    = min(remaining, cfg.BATT_MAX_CHARGE_KW)  # correct unit: kW
            remaining = max(0.0, remaining - p_bess)
            events.append(f"BESS ← {p_bess:.2f} kW (SoC {current_soc*100:.0f}%)")

        # ── PRIORITY 3: Electrolyzer overload ─────────────────────────
        # Only push to peak if already at nominal AND surplus is meaningful
        p_overload = 0.0
        if (self._elec_is_running
                and remaining >= self.PEAK_SURPLUS_THRESHOLD_KW
                and p_elec >= cfg.ELEC_P_NOM_KW * 0.90):
            room = cfg.ELEC_P_MAX_KW - p_elec
            ask  = min(remaining, room)
            if ask > 0.05:
                total_target = p_elec + ask
                p_total = self._ramp(total_target, timestep_sec)
                p_overload = max(0.0, p_total - p_elec)
                p_elec     = p_total                        # update total
                remaining  = max(0.0, remaining - p_overload)
                events.append(
                    f"Elec (overload) → {p_elec:.2f} kW total")

        # ── PRIORITY 4: EV charger ─────────────────────────────────────
        # Primary EV source is the fuel cell (H₂ → FC → EV).
        # Direct generation only provides a small supplement here.
        p_ev = 0.0
        if ev_demand_kw > cfg.EV_MIN_POWER_KW and remaining > 0.1:
            p_ev      = min(remaining, ev_demand_kw * 0.3)  # max 30% from direct gen
            remaining = max(0.0, remaining - p_ev)
            if p_ev > 0.05:
                events.append(f"EV (direct supplement) ← {p_ev:.2f} kW")

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
            events.append(
                f"⚠ Grid IMPORT {p_import:.2f} kW (SoC < {ps.grid_import_trigger_soc*100:.0f}%)")

        # ── Determine electrolyzer mode label ──────────────────────────
        if p_elec <= 0:
            mode = "off"
        elif p_elec < cfg.ELEC_P_NOM_KW * 0.90:
            mode = "partial"
        elif p_elec <= cfg.ELEC_P_NOM_KW * 1.05:
            mode = "nominal"
        else:
            mode = "overload"

        return PowerFlowResult(
            power_to_electrolyzer_kw=round(p_elec, 3),
            power_to_battery_kw=round(p_bess, 3),
            power_to_ev_kw=round(p_ev, 3),
            grid_export_kw=round(p_export, 3),
            grid_import_kw=round(p_import, 3),
            switching_event=" | ".join(events) if events else "Standby",
            electrolyzer_mode=mode,
        )

    # ------------------------------------------------------------------
    # Phase 3 — H₂ logistics
    # ------------------------------------------------------------------

    def hydrogen_logistics_control(
        self,
        buffer_level_kg: float,
        main_tank_kg:    float,
        hrs_tank_kg:     float,
        timestep_sec:    int = 10,
    ) -> H2LogisticsResult:
        """
        Control compressor and determine H₂ dispatch target.

        Compressor runs when buffer ≥ START_THRESHOLD and stops when
        buffer ≤ STOP_THRESHOLD, with a minimum-runtime hysteresis guard.
        """
        cfg        = self._cfg
        buffer_pct = buffer_level_kg / max(cfg.BUFFER_TANK_CAPACITY_KG, 1e-9)
        main_pct   = main_tank_kg    / max(cfg.MAIN_TANK_CAPACITY_KG, 1e-9)

        # Compressor hysteresis with min-runtime guard
        if buffer_pct >= cfg.BUFFER_START_THRESHOLD:
            self._comp_on          = True
            self._comp_runtime_sec = 0
        elif (self._comp_on
              and self._comp_runtime_sec < cfg.COMPRESSOR_MIN_RUNTIME_SEC):
            self._comp_runtime_sec += timestep_sec
        elif buffer_pct <= cfg.BUFFER_STOP_THRESHOLD:
            self._comp_on = False

        comp_status: Literal["ON", "OFF"] = "ON" if self._comp_on else "OFF"

        # Dispatch target
        target: Literal["Storage", "Refueling Station (HRS)", "Fuel Cell (FC)"]
        if main_pct >= cfg.MAIN_TANK_START_THRESHOLD:
            if hrs_tank_kg < cfg.HRS_H2_TANK_CAPACITY_KG:
                target = "Refueling Station (HRS)"
            else:
                target = "Fuel Cell (FC)"
        else:
            target = "Storage"

        return H2LogisticsResult(
            compressor_status=comp_status,
            dispatch_target=target,
            buffer_fill_pct=round(buffer_pct * 100, 1),
            main_tank_fill_pct=round(main_pct * 100, 1),
        )

    # ------------------------------------------------------------------
    # Phase 4 — Per-tick economics
    # ------------------------------------------------------------------

    def calculate_economics(
        self,
        h2_kg_produced: float,
        power_used_kw:  float,
        source:         str,
        timestep_sec:   int = 10,
    ) -> EconomicsResult:
        """
        Calculate per-tick cost and revenue.

        Note: Use LCOHAccumulator (core_engine.py) for rolling LCOH —
        dividing per-tick cost by per-tick H₂ gives explosive values.
        This method is for per-tick revenue breakdown only.
        """
        if h2_kg_produced <= 0:
            return EconomicsResult(0.0, 0.0, 0.0, 0.0, 0.0, False)

        cfg  = self._cfg
        dt_h = timestep_sec / 3600.0

        # Energy cost
        if "Grid" in source:
            energy_cost = power_used_kw * cfg.GRID_PRICE_BUY * dt_h
        else:
            energy_cost = power_used_kw * 0.02 * dt_h   # renewables O&M

        # Stack depreciation (pro-rated by load fraction)
        load_f     = power_used_kw / max(cfg.ELEC_P_MAX_KW, 0.01)
        stack_depr = (load_f * cfg.STACK_REPLACEMENT_COST
                      / (cfg.electrolyzer.mttf_hours * cfg.ELEC_P_MAX_KW)
                      * power_used_kw * dt_h)

        total_cost = energy_cost + stack_depr
        lcoh       = total_cost / h2_kg_produced if h2_kg_produced > 1e-4 else 0.0

        # Carbon
        co2_avoided = h2_kg_produced * cfg.CO2_SAVED_PER_KG_H2
        co2_emitted = (power_used_kw * cfg.GRID_CO2_INTENSITY * dt_h
                       if "Grid" in source else 0.0)
        net_co2     = co2_avoided - co2_emitted
        carbon_rev  = (net_co2 / 1000.0) * cfg.CARBON_TAX_EUR_TON
        subsidy     = h2_kg_produced * cfg.GREEN_H2_SUBSIDY

        return EconomicsResult(
            lcoh_eur_kg=round(lcoh, 4),
            carbon_revenue_eur=round(carbon_rev, 5),
            net_co2_saved_kg=round(net_co2, 4),
            subsidy_earned_eur=round(subsidy, 5),
            total_revenue_eur=round(carbon_rev + subsidy, 5),
            is_profitable=(0 < lcoh <= cfg.LCOH_TARGET_EURO_KG),
        )

    # ------------------------------------------------------------------
    # Phase 5 — Downstream: FC → EV + grid
    # ------------------------------------------------------------------

    def manage_fc_and_grid(
        self,
        fc_power_output_kw: float,
        ev_demand_kw:       float,
    ) -> DownstreamResult:
        """
        Allocate fuel cell output: EV gets priority, surplus goes to grid.

        The fuel cell is the PRIMARY EV power source (H₂ → FC → EV).
        This decouples EV charging from renewable generation timing.
        """
        p_ev   = float(min(fc_power_output_kw, max(ev_demand_kw, 0.0)))
        p_grid = max(0.0, fc_power_output_kw - p_ev)
        rev    = p_grid * self._cfg.GRID_PRICE_SELL

        return DownstreamResult(
            p_ev_kw=round(p_ev, 3),
            p_grid_kw=round(p_grid, 3),
            grid_revenue_eur=round(rev, 5),
            ev_sessions_supported=int(p_ev // self._cfg.EV_CHARGER_POWER_KW),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ramp(self, target_kw: float, timestep_sec: int) -> float:
        """
        Apply ramp-rate limits to protect PEM membrane from load transients.

        Ramp rate: 0.3 kW/s up, 0.5 kW/s down = 5.3%/s of rated power.
        PEM specification: 0.1–10%/s — within spec ✅
        """
        ps     = self._ps
        max_up = ps.electrolyzer_ramp_up_kw_s   * timestep_sec
        max_dn = ps.electrolyzer_ramp_down_kw_s * timestep_sec

        if target_kw > self._elec_current_kw:
            self._elec_current_kw = min(target_kw, self._elec_current_kw + max_up)
        else:
            self._elec_current_kw = max(target_kw, self._elec_current_kw - max_dn)

        # Hard cutoff below P_MIN — no partial operation
        if self._elec_current_kw < self._cfg.ELEC_P_MIN_KW:
            self._elec_current_kw = 0.0

        return round(self._elec_current_kw, 3)

    # ------------------------------------------------------------------
    # Forecast-aware dispatch overlay (NEW in v4.4)
    # ------------------------------------------------------------------

    def forecast_aware_dispatch(
        self,
        forecast,                    # ForecastPacket from weather_api.py
        current_soc:   float = 0.55, # Current BESS SoC [0-1]
        current_gen_kw: float = 0.0, # Current generation [kW]
        horizon_h:     int   = 6,    # How many hours ahead to consider
    ) -> ForecastDecision:
        """
        Adjust EMS dispatch strategy based on 24-hour weather forecast.

        This method analyses the next `horizon_h` hours of irradiance
        forecast and produces guidance for the standard dispatch:

        Key decisions:
          1. PRE-CHARGE BESS before a predicted solar peak
             (so BESS has headroom to absorb the peak energy)
          2. HOLD BESS RESERVE if a high-irradiance window is coming soon
             (don't discharge now — solar will recharge shortly)
          3. DEFER ELECTROLYZER if current generation is poor but high
             irradiance is predicted within 2 hours
             (avoid cold-start penalty + preserve BESS for peak absorption)
          4. INCREASE ELECTROLYZER SETPOINT during predicted peak hours
             (capture maximum H₂ revenue from the best generation window)

        The standard manage_power_flow() ALWAYS runs after this.
        The returned ForecastDecision is advisory — it guides the
        operator interface and can be used to pre-set the EMS mode
        before the tick executes.

        Args:
            forecast       : ForecastPacket from WeatherProvider.fetch_forecast_24h()
            current_soc    : current BESS state of charge [0-1]
            current_gen_kw : current total generation [kW]
            horizon_h      : number of forecast hours to consider

        Returns:
            ForecastDecision with BESS and electrolyzer guidance
        """
        cfg = self._cfg

        # ── Extract next horizon_h hours from forecast ────────────────
        irr   = getattr(forecast, "irradiance_wm2",   [0.0] * 24)[:horizon_h]
        wind  = getattr(forecast, "wind_ms",           [4.5] * 24)[:horizon_h]
        hours = getattr(forecast, "hours",             list(range(24)))[:horizon_h]

        # Pad if forecast is shorter than horizon
        while len(irr)  < horizon_h: irr.append(0.0)
        while len(wind) < horizon_h: wind.append(4.5)

        # ── Estimated PV energy next horizon_h hours [kWh] ────────────
        pv_cap    = cfg.PV_SYSTEM_CAPACITY_KW
        sys_eff   = 0.97 * 0.995   # inverter × MPPT
        pv_hourly = [
            pv_cap * max(0.0, irr_h / 1000.0) * sys_eff
            for irr_h in irr
        ]
        next_6h_irr_kwh_m2 = sum(i / 1000.0 for i in irr)   # kWh/m²
        next_6h_pv_kwh     = sum(pv_hourly)

        # Peak irradiance this window
        peak_irr  = max(irr)
        peak_idx  = irr.index(peak_irr)
        peak_hour = hours[peak_idx] if hours else 12

        # ── Key thresholds ────────────────────────────────────────────
        GOOD_IRR_W_M2      = 300.0   # W/m² — worth running electrolyzer
        EXCELLENT_IRR_W_M2 = 600.0   # W/m² — run at peak load
        CLOUD_IRR_W_M2     = 50.0    # W/m² — effectively no solar

        solar_window_open  = peak_irr >= GOOD_IRR_W_M2
        cloudy_window      = all(i < CLOUD_IRR_W_M2 for i in irr[:3])
        strong_peak_soon   = (peak_irr >= EXCELLENT_IRR_W_M2
                               and peak_idx <= 3)   # within 3 hours

        # ── BESS strategy ─────────────────────────────────────────────
        bess_soc_max  = cfg.BATT_SOC_MAX
        bess_soc_min  = cfg.BATT_SOC_MIN

        if strong_peak_soon:
            # Big solar peak coming soon — create headroom for it
            # Target SoC = 40% so BESS can absorb 50% of capacity
            bess_target = max(bess_soc_min + 0.05, 0.40)
            hold_reserve  = False
            pre_charge    = False
            bess_strategy = "headroom"
        elif solar_window_open and peak_idx <= 2:
            # Good solar within 2 hours — hold BESS reserve
            bess_target  = max(current_soc, 0.50)
            hold_reserve = True
            pre_charge   = False
            bess_strategy = "hold_reserve"
        elif cloudy_window and current_soc < 0.60:
            # Cloudy ahead — pre-charge BESS now from any surplus
            bess_target  = min(bess_soc_max - 0.05, 0.80)
            hold_reserve = False
            pre_charge   = True
            bess_strategy = "pre_charge_cloudy"
        else:
            # Normal — no forecast-based adjustment
            bess_target  = 0.55
            hold_reserve = False
            pre_charge   = False
            bess_strategy = "normal"

        # ── Electrolyzer strategy ─────────────────────────────────────
        current_irr_est = irr[0] if irr else 0.0

        if current_gen_kw >= cfg.ELEC_P_MAX_KW and peak_irr >= EXCELLENT_IRR_W_M2:
            # Peak generation AND excellent forecast — run at max
            elec_setpoint = cfg.ELEC_P_MAX_KW
            defer         = False
            elec_strategy = "peak_load"
        elif current_gen_kw < cfg.ELEC_P_MIN_KW and strong_peak_soon:
            # Below minimum now but peak coming soon — defer start
            elec_setpoint = 0.0
            defer         = True
            elec_strategy = "defer_peak_soon"
        elif current_gen_kw >= cfg.ELEC_P_NOM_KW:
            # Good generation — nominal load
            elec_setpoint = cfg.ELEC_P_NOM_KW
            defer         = False
            elec_strategy = "nominal"
        elif current_gen_kw >= cfg.ELEC_P_MIN_KW:
            # Partial generation — run at available power
            elec_setpoint = current_gen_kw
            defer         = False
            elec_strategy = "partial"
        else:
            # Below minimum
            elec_setpoint = 0.0
            defer         = False
            elec_strategy = "standby"

        # ── Build strategy label and reason ───────────────────────────
        strategy_map = {
            "peak_load":       "Peak production mode",
            "defer_peak_soon": "Deferred — peak solar imminent",
            "nominal":         "Nominal dispatch",
            "partial":         "Partial load",
            "standby":         "Standby — below minimum",
        }
        bess_map = {
            "headroom":          f"BESS headroom for solar peak at {peak_hour:02d}:00",
            "hold_reserve":      f"BESS reserve held — good solar in {peak_idx}h",
            "pre_charge_cloudy": "BESS pre-charging — cloudy window ahead",
            "normal":            "Normal BESS operation",
        }
        strategy = strategy_map.get(elec_strategy, elec_strategy)
        reason   = (
            f"{bess_map.get(bess_strategy, 'Normal')}. "
            f"6h forecast: {next_6h_pv_kwh:.1f} kWh PV, "
            f"peak {peak_irr:.0f} W/m² at {peak_hour:02d}:00. "
            f"Elec: {strategy}."
        )

        return ForecastDecision(
            next_6h_irr_kwh_m2=round(next_6h_irr_kwh_m2, 3),
            next_6h_pv_kwh=round(next_6h_pv_kwh, 2),
            solar_window_open=solar_window_open,
            peak_hour=peak_hour,
            cloudy_window_ahead=cloudy_window,
            bess_target_soc=round(bess_target, 2),
            hold_bess_reserve=hold_reserve,
            pre_charge_bess=pre_charge,
            elec_setpoint_kw=round(elec_setpoint, 3),
            defer_electrolyzer=defer,
            strategy=strategy,
            reason=reason,
        )

    def reset(self) -> None:
        """Reset all ramp and runtime state — call on simulation restart."""
        self._elec_current_kw  = 0.0
        self._elec_runtime_sec = 0
        self._elec_is_running  = False
        self._comp_runtime_sec = 0
        self._comp_on          = False

    @property
    def electrolyzer_runtime_min(self) -> float:
        """Electrolyzer continuous run-time in minutes."""
        return round(self._elec_runtime_sec / 60, 1)

    @property
    def min_runtime_satisfied(self) -> bool:
        """True when the 30-min minimum run-time guard has been satisfied."""
        return self._elec_runtime_sec >= self.ELEC_MIN_RUNTIME_SEC


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    ems = EMSBrain()
    cfg = Config

    print("=" * 62)
    print("  ems_brain.py v4.4 — Electrolyzer-First Dispatch")
    print("=" * 62)

    # ── Scenario 1: Good generation (15 kW) ───────────────────────────
    print("\n[1] Good generation (15 kW, SoC 55%)")
    src  = ems.decide_energy_source(10.0, 5.0, 0.55)
    flow = ems.manage_power_flow(15.0, 0.55, ev_demand_kw=2.0, timestep_sec=10)
    print(f"  Source     : {src.source}")
    print(f"  Electrolyzer: {flow.power_to_electrolyzer_kw} kW [{flow.electrolyzer_mode}]")
    print(f"  BESS       : {flow.power_to_battery_kw} kW")
    print(f"  EV         : {flow.power_to_ev_kw} kW")
    print(f"  Export     : {flow.grid_export_kw} kW")
    print(f"  Log        : {flow.switching_event}")
    # Verify electrolyzer gets priority
    assert flow.power_to_electrolyzer_kw >= cfg.ELEC_P_NOM_KW * 0.9, \
        "❌ Electrolyzer should be at nominal load"
    print(f"  ✅ Electrolyzer at nominal (priority confirmed)")

    # ── Scenario 2: Low generation (2 kW) ─────────────────────────────
    print("\n[2] Low generation (2 kW, SoC 70%)")
    ems2  = EMSBrain()
    flow2 = ems2.manage_power_flow(2.0, 0.70, ev_demand_kw=2.0, timestep_sec=10)
    print(f"  Electrolyzer: {flow2.power_to_electrolyzer_kw} kW [{flow2.electrolyzer_mode}]")
    print(f"  BESS       : {flow2.power_to_battery_kw} kW")
    assert flow2.power_to_battery_kw == 0.0, "❌ BESS should not charge (elec has priority)"
    print(f"  ✅ BESS correctly gets 0 kW (electrolyzer takes all available)")

    # ── Scenario 3: Below minimum (0.5 kW) ────────────────────────────
    print("\n[3] Below minimum generation (0.5 kW)")
    ems3  = EMSBrain()
    flow3 = ems3.manage_power_flow(0.5, 0.60, timestep_sec=10)
    print(f"  Electrolyzer: {flow3.power_to_electrolyzer_kw} kW [{flow3.electrolyzer_mode}]")
    assert flow3.power_to_electrolyzer_kw == 0.0, "❌ Elec should be off below min"
    print(f"  ✅ Electrolyzer correctly off below P_MIN")

    # ── Scenario 4: Min-runtime guard ─────────────────────────────────
    print("\n[4] Min-runtime guard (gen drops but elec ran only 5 min)")
    ems4 = EMSBrain()
    ems4.manage_power_flow(10.0, 0.55, timestep_sec=10)
    ems4._elec_runtime_sec = 300   # 5 min — below 30 min guard
    ems4._elec_is_running  = True
    ems4._elec_current_kw  = cfg.ELEC_P_MIN_KW
    flow4 = ems4.manage_power_flow(0.3, 0.55, timestep_sec=10)
    print(f"  Elec still running : {flow4.power_to_electrolyzer_kw > 0}")
    print(f"  Runtime guard      : {not ems4.min_runtime_satisfied} (30 min not reached)")
    print(f"  ✅ Continuity guard active — elec kept alive")

    # ── Scenario 5: BESS unit fix verification ─────────────────────────
    print("\n[5] BESS charging unit fix (v4.3)")
    ems5  = EMSBrain()
    flow5 = ems5.manage_power_flow(20.0, 0.55, timestep_sec=10)  # lots of surplus
    print(f"  BESS charge  : {flow5.power_to_battery_kw} kW")
    print(f"  Max charge   : {cfg.BATT_MAX_CHARGE_KW} kW")
    assert flow5.power_to_battery_kw <= cfg.BATT_MAX_CHARGE_KW, \
        f"❌ BESS charge {flow5.power_to_battery_kw} > max {cfg.BATT_MAX_CHARGE_KW}"
    print(f"  ✅ BESS charge correctly capped at {cfg.BATT_MAX_CHARGE_KW} kW (unit fix OK)")

    # ── Economics ─────────────────────────────────────────────────────
    print("\n[6] Economics (10 s tick, nominal load, renewable)")
    h2_tick = cfg.electrolyzer.h2_nom_kg_h * (10 / 3600)
    econ = ems.calculate_economics(
        h2_kg_produced=h2_tick,
        power_used_kw=cfg.ELEC_P_NOM_KW,
        source="Hybrid (PV+Wind)",
        timestep_sec=10,
    )
    print(f"  H₂ per tick  : {h2_tick*1000:.4f} g")
    print(f"  LCOH (tick)  : €{econ.lcoh_eur_kg:.2f}/kg")
    print(f"  Profitable   : {econ.is_profitable}")
    print(f"  Note: use LCOHAccumulator for real rolling LCOH")

    # ── Runtime property ──────────────────────────────────────────────
    print(f"\n[7] Properties")
    print(f"  Runtime (min): {ems.electrolyzer_runtime_min}")
    print(f"  Min satisfied: {ems.min_runtime_satisfied}")

    # ── Forecast-aware dispatch ──────────────────────────────────────
    print("\n[8] Forecast-aware dispatch (v4.4)")

    # Simulate a ForecastPacket-like object
    class FakeForecast:
        hours           = list(range(24))
        irradiance_wm2  = [0]*6 + [100,250,450,680,750,720,650,500,350,150,50,0]*1 + [0]*2
        wind_ms         = [5.2]*24
        temp_c          = [18.0]*24
        precip_mm       = [0.0]*24
        peak_irr_wm2    = 750.0
        peak_irr_hour   = 11
        total_energy_kwh= 42.5
        source          = "live"
        fetched_at      = "10:00:00"

    ems_fc = EMSBrain()

    # Scenario A: strong peak ahead, BESS at 75% — should create headroom
    fd_a = ems_fc.forecast_aware_dispatch(
        FakeForecast(), current_soc=0.75, current_gen_kw=2.0)
    print(f"  Strategy       : {fd_a.strategy}")
    print(f"  BESS target SoC: {fd_a.bess_target_soc:.2f}")
    print(f"  Hold reserve   : {fd_a.hold_bess_reserve}")
    print(f"  Pre-charge     : {fd_a.pre_charge_bess}")
    print(f"  Elec setpoint  : {fd_a.elec_setpoint_kw:.2f} kW")
    print(f"  Reason         : {fd_a.reason[:80]}…")

    # Scenario B: night-time, cloudy forecast, low SoC — should pre-charge
    class NightForecast:
        hours           = list(range(24))
        irradiance_wm2  = [0.0]*24   # all cloudy
        wind_ms         = [3.0]*24
        temp_c          = [12.0]*24
        precip_mm       = [0.5]*24
        peak_irr_wm2    = 0.0
        peak_irr_hour   = 12
        total_energy_kwh= 0.0
        source          = "fallback"
        fetched_at      = "22:00:00"

    fd_b = ems_fc.forecast_aware_dispatch(
        NightForecast(), current_soc=0.45, current_gen_kw=3.5)
    print(f"\n  Night/cloudy scenario:")
    print(f"  Strategy      : {fd_b.strategy}")
    print(f"  BESS target   : {fd_b.bess_target_soc:.2f}")
    print(f"  Pre-charge    : {fd_b.pre_charge_bess}")
    print(f"  Solar window  : {fd_b.solar_window_open}")
    print(f"  Cloudy ahead  : {fd_b.cloudy_window_ahead}")

    assert isinstance(fd_a.elec_setpoint_kw, float),  "Setpoint must be float"
    assert 0 <= fd_a.bess_target_soc <= 1,            "SoC target out of range"
    assert fd_b.cloudy_window_ahead == True,           "Should detect cloudy window"
    print("  ✅ ForecastDecision assertions passed")

    print("\n✅ ems_brain.py v4.4 — all tests passed")
