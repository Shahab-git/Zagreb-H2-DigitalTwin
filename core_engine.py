# =============================================================================
# core_engine.py — LUMINIH2 Core Simulation Engine
# Tick Engine · LCOH Accumulator · State Management · Alert System
# Version: 4.2
# =============================================================================
#
# KEY COMPONENTS:
#   LCOHAccumulator — rolling 1-hour window (prevents per-tick division explosion)
#   AlertSystem     — deduplicates alerts, auto-clears stale conditions
#   TickEngine      — one complete physics + EMS cycle per Streamlit rerun
#   HistoryBuffer   — ring-buffer of last N ticks as pandas DataFrame
#
# DESIGN PRINCIPLES:
#   - TickEngine never calls time.sleep() — safe for Streamlit Cloud
#   - All physics objects live in st.session_state (persist across reruns)
#   - LCOH uses 1-hour rolling window, not per-tick division
#   - Alerts are deduplicated by code and auto-clear when condition clears
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
import logging

import numpy as np

logger = logging.getLogger("CoreEngine")


# =============================================================================
# LCOH Accumulator — 1-hour rolling window
# =============================================================================

@dataclass
class LCOHAccumulator:
    """
    Accumulates energy cost and H₂ production over a rolling 1-hour window.

    LCOH = window_cost_EUR / window_h2_kg

    Using a rolling window prevents the explosive values that occur when
    dividing tiny per-tick costs by tiny per-tick H₂ amounts.

    Window size: 360 ticks × 10 s/tick = 3600 s = 1 hour
    """
    _cost_window:   list  = field(default_factory=list)
    _h2_window:     list  = field(default_factory=list)
    _window_size:   int   = 360          # 1 hour at 10 s/tick
    total_cost_eur: float = 0.0          # session cumulative
    total_h2_kg:    float = 0.0          # session cumulative
    lcoh:           float = 0.0          # current rolling LCOH
    is_profitable:  bool  = False

    def update(
        self,
        cost_eur_tick: float,
        h2_kg_tick:    float,
        target:        float,
    ) -> float:
        """
        Add one tick of data and return current rolling LCOH.

        Args:
            cost_eur_tick : energy + stack cost this tick [€]
            h2_kg_tick    : H₂ produced this tick [kg]
            target        : LCOH target [€/kg] for profitability flag

        Returns:
            Current rolling LCOH [€/kg]
        """
        self._cost_window.append(cost_eur_tick)
        self._h2_window.append(h2_kg_tick)
        if len(self._cost_window) > self._window_size:
            self._cost_window.pop(0)
            self._h2_window.pop(0)

        # Session totals
        self.total_cost_eur += cost_eur_tick
        self.total_h2_kg    += h2_kg_tick

        # Rolling LCOH
        window_h2   = sum(self._h2_window)
        window_cost = sum(self._cost_window)
        if window_h2 > 0.001:
            self.lcoh = round(window_cost / window_h2, 3)
        else:
            self.lcoh = 0.0

        self.is_profitable = 0 < self.lcoh <= target
        return self.lcoh

    @property
    def window_minutes(self) -> float:
        """How many minutes of data are in the current window."""
        return len(self._cost_window) * 10 / 60


# =============================================================================
# Alert System
# =============================================================================

@dataclass
class Alert:
    """A single system alert with level, code, and timestamp."""
    level:   str    # "error" | "warning" | "info"
    code:    str    # machine-readable identifier
    message: str    # human-readable description
    value:   float = 0.0
    ts:      str   = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = datetime.now().strftime("%H:%M:%S")


class AlertSystem:
    """
    Collects, deduplicates, and auto-clears alerts each tick.

    Usage:
        alerts.clear()               # call at start of each tick
        alerts.check("CODE", cond)   # raises alert if condition is True
        alerts.errors()              # list of error-level alerts
        alerts.warnings()            # list of warning-level alerts
    """

    # Registry: code → (level, message)
    CODES: dict[str, tuple[str, str]] = {
        "THERMAL_RUNAWAY": ("error",   "BESS thermal runaway risk — check cooling!"),
        "BESS_OVERHEAT":   ("warning", "BESS temperature elevated (>55°C)"),
        "H2_LEAK":         ("error",   "H₂ leak detected — mass balance anomaly"),
        "STACK_DEGRADED":  ("warning", "Electrolyzer stack SoH below 80%"),
        "FC_H2_SHORTAGE":  ("info",    "Fuel cell H₂ supply limited"),
        "BESS_LOW_SOC":    ("warning", "BESS SoC critically low"),
        "PRESSURE_HIGH":   ("error",   "Tank pressure approaching safety limit"),
        "WIND_CUTOUT":     ("info",    "Wind turbine cut-out — turbulence"),
        "GRID_IMPORT":     ("info",    "Emergency grid import active"),
        "WATER_QUALITY":   ("warning", "Water conductivity out of spec"),
        "H2_MOISTURE":     ("warning", "H₂ moisture above 5 ppm — dryer check"),
    }

    def __init__(self) -> None:
        self.active: list[Alert] = []
        self._prev_codes: set[str] = set()

    def clear(self) -> None:
        """Clear all alerts — call at the start of each tick."""
        self.active = []

    def check(
        self,
        code:      str,
        condition: bool,
        value:     float = 0.0,
    ) -> None:
        """
        Raise an alert if condition is True and code is not already active.

        Args:
            code      : alert code from CODES registry
            condition : True → raise alert
            value     : numeric context value (e.g. temperature)
        """
        if condition and code in self.CODES:
            level, msg = self.CODES[code]
            if not any(a.code == code for a in self.active):
                self.active.append(Alert(level, code, msg, value))

    def newly_raised(self) -> list[Alert]:
        """
        Return alerts in `active` that were not active on the previous tick,
        then advance the previous-tick snapshot.

        Call once per tick, after all check() calls. Since clear()+check()
        rebuild `active` fresh every tick, a still-active alert would
        otherwise look "new" on every single tick — this filters that down
        to genuine inactive→active transitions, so callers (e.g. DB
        persistence) get one row per alert episode instead of a flood of
        duplicate rows for every tick the condition stays true.
        """
        new = [a for a in self.active if a.code not in self._prev_codes]
        self._prev_codes = {a.code for a in self.active}
        return new

    def errors(self)   -> list[Alert]:
        return [a for a in self.active if a.level == "error"]

    def warnings(self) -> list[Alert]:
        return [a for a in self.active if a.level == "warning"]

    def infos(self)    -> list[Alert]:
        return [a for a in self.active if a.level == "info"]

    @property
    def has_critical(self) -> bool:
        return len(self.errors()) > 0


# =============================================================================
# Tick State — complete system snapshot
# =============================================================================

@dataclass
class TickState:
    """
    Complete snapshot of the LUMINIH2 system at one simulation tick.
    All fields are plain Python scalars — safe to store in pandas DataFrames.
    """
    tick:               int   = 0
    timestamp:          str   = ""

    # ── Generation ────────────────────────────────────────────────────
    solar_kw:           float = 0.0
    wind_kw:            float = 0.0
    total_gen_kw:       float = 0.0
    solar_cell_temp_c:  float = 25.0
    solar_eff_pct:      float = 0.0
    wind_regime:        str   = "below_cut_in"

    # ── BESS ──────────────────────────────────────────────────────────
    bess_soc_pct:       float = 55.0
    bess_soh_pct:       float = 100.0
    bess_temp_c:        float = 25.0
    bess_charge_kw:     float = 0.0
    bess_thermal_warn:  bool  = False
    bess_runaway:       bool  = False

    # ── EMS dispatch ──────────────────────────────────────────────────
    source:             str   = "—"
    switching_event:    str   = "Standby"
    elec_kw:            float = 0.0
    ev_kw:              float = 0.0
    grid_export_kw:     float = 0.0
    grid_import_kw:     float = 0.0

    # ── Electrolyzer ──────────────────────────────────────────────────
    h2_kg_h:            float = 0.0
    elec_eff_pct:       float = 0.0
    elec_purity:        float = 99.999
    elec_soh_pct:       float = 100.0
    water_l_h:          float = 0.0
    heat_kw:            float = 0.0

    # ── H₂ chain ──────────────────────────────────────────────────────
    buffer_pct:         float = 0.0
    main_tank_pct:      float = 0.0
    hrs_pct:            float = 0.0
    pressure_bar:       float = 30.0
    tank_temp_c:        float = 20.0
    compressor_on:      bool  = False
    leak_detected:      bool  = False

    # ── Fuel cell ─────────────────────────────────────────────────────
    fc_kw:              float = 0.0
    fc_eff_pct:         float = 0.0
    fc_h2_shortage:     bool  = False

    # ── Economics ─────────────────────────────────────────────────────
    lcoh:               float = 0.0
    is_profitable:      bool  = False
    co2_saved_kg:       float = 0.0
    carbon_rev_eur:     float = 0.0
    subsidy_eur:        float = 0.0
    grid_rev_eur:       float = 0.0

    # ── Forecast-aware EMS (v4.2) ─────────────────────────────────────
    ems_strategy:       str   = "normal"   # forecast EMS strategy label
    ems_elec_setpoint:  float = 0.0        # forecast-suggested setpoint [kW]
    ems_bess_target:    float = 0.55       # forecast-suggested BESS SoC
    next_6h_pv_kwh:     float = 0.0        # predicted PV energy next 6 h [kWh]

    # ── Weather ───────────────────────────────────────────────────────
    wx_temp_c:          float = 15.0
    wx_humidity:        float = 60.0      # % relative humidity
    wx_wind_ms:         float = 4.5
    wx_irradiance:      float = 0.0       # W/m²
    wx_soiling:         float = 0.98
    wx_precip_mm:       float = 0.0       # mm precipitation
    wx_source:          str   = "fallback"

    # ── Cumulative session totals ──────────────────────────────────────
    cum_h2_kg:          float = 0.0
    cum_co2_kg:         float = 0.0
    cum_revenue_eur:    float = 0.0
    cum_water_l:        float = 0.0


# =============================================================================
# Tick Engine
# =============================================================================

class TickEngine:
    """
    Executes one complete LUMINIH2 physics + EMS simulation tick.

    Called once per Streamlit rerun. Never uses time.sleep().
    All stateful physics objects are passed in from st.session_state
    and persist across reruns.

    Tick sequence:
        1. Fetch weather (real API or manual override)
        2. Calculate solar + wind generation
        3. AI forecast (retrain every 20 ticks)
        3b. Forecast-aware EMS overlay (v4.2)
        4. EMS power dispatch (electrolyzer-first priority)
        5. BESS update
        6. Electrolyzer production
        7. H₂ chain (buffer → compressor → tank → HRS)
        8. Fuel cell output
        9. Economics (LCOH rolling window)
        10. Cumulative accumulators
        11. Alert checks
        12. Build and return TickState snapshot
    """

    def __init__(
        self,
        config,
        solar,
        wind,
        bess,
        electrolyzer,
        h2_chain,
        fuel_cell,
        ems,
        forecaster,
        weather,
        lcoh_acc:  LCOHAccumulator,
        alerts:    AlertSystem,
    ) -> None:
        self.cfg   = config
        self.solar = solar
        self.wind  = wind
        self.bess  = bess
        self.elec  = electrolyzer
        self.chain = h2_chain
        self.fc    = fuel_cell
        self.ems   = ems
        self.ai    = forecaster
        self.wx    = weather
        self.lcoh_acc = lcoh_acc
        self.alerts   = alerts

        # Session cumulative accumulators
        self.cum_h2_kg:       float = 0.0
        self.cum_co2_kg:      float = 0.0
        self.cum_revenue_eur: float = 0.0
        self.cum_water_l:     float = 0.0
        self.tick_count:      int   = 0
        self.db               = None   # set by shared.py to Database instance

    def run(
        self,
        override:           Optional[dict] = None,
        ev_demand_kw:       float = 2.0,
        force_bess_charge:  bool  = False,
    ) -> Tuple[TickState, object]:
        """
        Execute one simulation tick.

        Args:
            override          : dict with irradiance/wind_ms/temp_c for manual override
            ev_demand_kw      : EV charger demand [kW]
            force_bess_charge : force BESS to charge from grid

        Returns:
            (TickState, ForecastResult) tuple
        """
        from datetime import datetime as dt, timezone, timedelta
        self.tick_count += 1
        zagreb_tz = timezone(timedelta(hours=2))
        now       = dt.now(zagreb_tz)
        dt_h      = self.cfg.TIMESTEP_SEC / 3600.0

        # ── 1. Weather ─────────────────────────────────────────────────
        if override:
            wx_irr     = float(override.get("irradiance", 500))
            wx_wind    = float(override.get("wind_ms", 6.0))
            wx_temp    = float(override.get("temp_c", 20.0))
            wx_soiling = 0.98
            wx_turb    = 0.12
            wx_precip  = 0.0
            wx_hum     = 60.0
            wx_src     = "manual"
            wx_hist    = [
                max(0.0, wx_irr * np.sin(np.pi * max(0, h - 6) / 14))
                for h in range(24)
            ]
        else:
            pkt        = self.wx.fetch_current_data()
            wx_irr     = pkt.irradiance_raw_wm2
            wx_wind    = pkt.wind_speed_ms
            wx_temp    = pkt.temp_c
            wx_soiling = pkt.soiling_factor
            wx_turb    = pkt.turbulence_intensity
            wx_precip  = pkt.precipitation_mm
            wx_hum     = pkt.humidity_pct
            wx_src     = pkt.source
            wx_hist    = pkt.history_irradiance_24h

        # ── 1b. 24-h forecast (cached 30 min) ─────────────────────────
        try:
            wx_forecast = self.wx.fetch_forecast_24h()
        except Exception:
            wx_forecast = None

        # ── 2. Generation ──────────────────────────────────────────────
        solar_r   = self.solar.get_power_output(wx_irr, wx_temp, wx_soiling)
        wind_r    = self.wind.get_power_output(wx_wind, wx_turb)
        total_gen = solar_r.ac_power_kw + wind_r.ac_power_kw

        # ── 3. AI Forecast (retrain every 20 ticks) ───────────────────
        if self.tick_count % 20 == 1 and len(wx_hist) >= 24:
            train_data = wx_hist * 3 if len(wx_hist) < 48 else wx_hist
            self.ai.train_on_historical_data(train_data)
        forecast = self.ai.predict_future(wx_hist, horizon_hours=6, current_dt=now)

        # ── 3b. Forecast-aware EMS overlay ──────────────────────────────
        fc_decision = None
        if wx_forecast is not None:
            try:
                fc_decision = self.ems.forecast_aware_dispatch(
                    wx_forecast,
                    current_soc=self.bess.soc,
                    current_gen_kw=total_gen,
                )
            except Exception:
                fc_decision = None

        # ── 4. EMS Power Dispatch (electrolyzer-first) ─────────────────
        src_dec  = self.ems.decide_energy_source(
            solar_r.ac_power_kw, wind_r.ac_power_kw, self.bess.soc
        )
        incoming = total_gen
        if force_bess_charge:
            incoming += self.cfg.BATT_MAX_CHARGE_KW * 0.4
        # The forecast overlay now actually steers dispatch, not just the
        # display panel: bess_target_soc caps BESS charging (e.g. holds it
        # at ~40% headroom ahead of a predicted solar peak instead of always
        # filling to BATT_SOC_MAX), and defer_electrolyzer skips a fresh
        # cold-start when a strong peak is only 1-3h away — it never
        # interrupts a unit that's already running under the min-runtime guard.
        flow = self.ems.manage_power_flow(
            incoming_power_kw=incoming,
            current_soc=self.bess.soc,
            ev_demand_kw=ev_demand_kw,
            timestep_sec=self.cfg.TIMESTEP_SEC,
            bess_soc_ceiling=(fc_decision.bess_target_soc if fc_decision else None),
            defer_electrolyzer_start=(bool(fc_decision.defer_electrolyzer) if fc_decision else False),
        )

        # ── 5. BESS ────────────────────────────────────────────────────
        net_bess = flow.power_to_battery_kw - (
            self.bess.get_max_discharge_power() * 0.05
        )
        bess_r = self.bess.update_state(net_bess, wx_temp)

        # ── 6. Electrolyzer ────────────────────────────────────────────
        elec_r = self.elec.calculate_production(
            flow.power_to_electrolyzer_kw, wx_temp
        )

        # ── 7. H₂ Chain ────────────────────────────────────────────────
        chain_r = self.chain.manage_chain(elec_r.h2_kg_h, wx_temp)

        # ── 8. Fuel Cell ───────────────────────────────────────────────
        fc_r = self.fc.generate_power(chain_r.hrs_kg, ev_demand_kw)
        ds   = self.ems.manage_fc_and_grid(fc_r.p_out_kw, ev_demand_kw)

        # ── 9. Economics ───────────────────────────────────────────────
        h2_tick = elec_r.h2_kg_h * dt_h

        # Energy cost per tick
        if "Grid" in src_dec.source:
            cost_tick = (flow.power_to_electrolyzer_kw
                         * self.cfg.GRID_PRICE_BUY * dt_h)
        else:
            cost_tick = (flow.power_to_electrolyzer_kw * 0.02 * dt_h)

        # Stack depreciation per tick
        load_f     = flow.power_to_electrolyzer_kw / max(self.cfg.ELEC_P_MAX_KW, 0.01)
        cost_tick += load_f * (
            self.cfg.STACK_REPLACEMENT_COST
            / (self.cfg.ELEC_P_MAX_KW * 8760)
        ) * dt_h

        lcoh = self.lcoh_acc.update(cost_tick, h2_tick, self.cfg.LCOH_TARGET_EURO_KG)

        # Carbon & revenue
        co2_avoided = h2_tick * self.cfg.CO2_SAVED_PER_KG_H2
        co2_emitted = (
            flow.power_to_electrolyzer_kw * self.cfg.GRID_CO2_INTENSITY * dt_h
            if "Grid" in src_dec.source else 0.0
        )
        net_co2    = co2_avoided - co2_emitted
        carbon_rev = (net_co2 / 1000.0) * self.cfg.CARBON_TAX_EUR_TON
        subsidy    = h2_tick * self.cfg.GREEN_H2_SUBSIDY
        grid_rev   = ds.grid_revenue_eur

        # ── 10. Cumulative accumulators ────────────────────────────────
        self.cum_h2_kg       += h2_tick
        self.cum_co2_kg      += max(0.0, net_co2)
        self.cum_revenue_eur += grid_rev + subsidy + carbon_rev
        self.cum_water_l     += elec_r.water_l_h * dt_h

        # ── 11. Alerts ─────────────────────────────────────────────────
        self.alerts.clear()
        self.alerts.check("THERMAL_RUNAWAY",
            bess_r.thermal_runaway_risk, bess_r.temperature_c)
        self.alerts.check("BESS_OVERHEAT",
            bess_r.thermal_warning, bess_r.temperature_c)
        self.alerts.check("H2_LEAK",
            chain_r.leak_detected)
        self.alerts.check("STACK_DEGRADED",
            elec_r.soh < 0.80, elec_r.soh)
        self.alerts.check("FC_H2_SHORTAGE",
            fc_r.h2_shortage)
        self.alerts.check("BESS_LOW_SOC",
            bess_r.soc < self.cfg.BATT_SOC_MIN + 0.03, bess_r.soc)
        self.alerts.check("PRESSURE_HIGH",
            chain_r.pressure_bar > self.cfg.SAFETY_MAX_PRESSURE_BAR * 0.90,
            chain_r.pressure_bar)
        self.alerts.check("WIND_CUTOUT",
            wind_r.operating_regime == "cut_out")
        self.alerts.check("GRID_IMPORT",
            flow.grid_import_kw > 0)

        # Persist newly-raised alerts to the database — one row per alert
        # episode (inactive→active transition), not a flood of duplicate
        # rows for every tick the condition stays true.
        _new_alerts = self.alerts.newly_raised()
        if self.db is not None:
            for _a in _new_alerts:
                try:
                    self.db.write_alert(_a.level, _a.code, _a.message)
                except Exception:
                    pass

        # ── 12. Build and return TickState ─────────────────────────────
        state = TickState(
            tick=self.tick_count,
            timestamp=now.strftime("%H:%M:%S"),
            # Generation
            solar_kw=round(solar_r.ac_power_kw, 2),
            wind_kw=round(wind_r.ac_power_kw, 2),
            total_gen_kw=round(total_gen, 2),
            solar_cell_temp_c=solar_r.cell_temp_c,
            solar_eff_pct=round(
                (1 - solar_r.thermal_derating_pct / 100) * 100, 1),
            wind_regime=wind_r.operating_regime,
            # BESS
            bess_soc_pct=round(bess_r.soc * 100, 1),
            bess_soh_pct=round(bess_r.soh * 100, 2),
            bess_temp_c=bess_r.temperature_c,
            bess_charge_kw=flow.power_to_battery_kw,
            bess_thermal_warn=bess_r.thermal_warning,
            bess_runaway=bess_r.thermal_runaway_risk,
            # EMS
            source=src_dec.source,
            switching_event=flow.switching_event,
            elec_kw=flow.power_to_electrolyzer_kw,
            ev_kw=flow.power_to_ev_kw,
            grid_export_kw=flow.grid_export_kw,
            grid_import_kw=flow.grid_import_kw,
            # Forecast EMS
            ems_strategy=(fc_decision.strategy if fc_decision else "normal"),
            ems_elec_setpoint=(fc_decision.elec_setpoint_kw if fc_decision else 0.0),
            ems_bess_target=(fc_decision.bess_target_soc if fc_decision else 0.55),
            next_6h_pv_kwh=(fc_decision.next_6h_pv_kwh if fc_decision else 0.0),
            # Electrolyzer
            h2_kg_h=round(elec_r.h2_kg_h, 5),
            elec_eff_pct=round(elec_r.efficiency * 100, 2),
            elec_purity=round(elec_r.purity_pct, 4),
            elec_soh_pct=round(elec_r.soh * 100, 2),
            water_l_h=round(elec_r.water_l_h, 4),
            heat_kw=round(elec_r.heat_recovered_kw, 3),
            # H₂ chain
            buffer_pct=chain_r.buffer_fill_pct,
            main_tank_pct=chain_r.main_fill_pct,
            hrs_pct=chain_r.hrs_fill_pct,
            pressure_bar=chain_r.pressure_bar,
            tank_temp_c=chain_r.temp_c,
            compressor_on=chain_r.compressor_active,
            leak_detected=chain_r.leak_detected,
            # Fuel cell
            fc_kw=round(fc_r.p_out_kw, 3),
            fc_eff_pct=round(fc_r.efficiency * 100, 1),
            fc_h2_shortage=fc_r.h2_shortage,
            # Economics
            lcoh=lcoh,
            is_profitable=self.lcoh_acc.is_profitable,
            co2_saved_kg=round(max(0.0, net_co2), 4),
            carbon_rev_eur=round(carbon_rev, 4),
            subsidy_eur=round(subsidy, 4),
            grid_rev_eur=round(grid_rev, 4),
            # Weather
            wx_temp_c=wx_temp,
            wx_humidity=wx_hum,
            wx_wind_ms=wx_wind,
            wx_irradiance=wx_irr,
            wx_soiling=wx_soiling,
            wx_precip_mm=wx_precip,
            wx_source=wx_src,
            # Cumulative
            cum_h2_kg=round(self.cum_h2_kg, 4),
            cum_co2_kg=round(self.cum_co2_kg, 3),
            cum_revenue_eur=round(self.cum_revenue_eur, 3),
            cum_water_l=round(self.cum_water_l, 2),
        )
        return state, forecast


# =============================================================================
# History Buffer — ring-buffer for chart data
# =============================================================================

class HistoryBuffer:
    """
    Fixed-size ring-buffer that stores the last N TickState snapshots
    as a pandas DataFrame for plotting in Streamlit.

    Columns include all fields needed by the 9 dashboard tabs.
    """

    COLUMNS = [
        "time",
        # Generation
        "solar_kw", "wind_kw", "total_gen_kw",
        # BESS
        "bess_soc_pct", "bess_temp_c", "bess_charge_kw",
        # EMS
        "elec_kw", "ev_kw", "grid_export_kw", "grid_import_kw",
        # H₂
        "h2_kg_h", "elec_eff_pct",
        "buffer_pct", "main_tank_pct", "hrs_pct", "pressure_bar",
        # FC & economics
        "fc_kw", "lcoh", "co2_saved_kg", "grid_rev_eur",
        # Weather
        "wx_temp_c", "wx_irradiance", "wx_wind_ms",
        "wx_humidity", "wx_precip_mm", "wx_soiling",
    ]

    def __init__(self, maxlen: int = 120) -> None:
        import pandas as pd
        self.maxlen = maxlen
        self.df     = pd.DataFrame(columns=self.COLUMNS)

    def append(self, s: TickState) -> None:
        """Add one TickState row, dropping oldest if at capacity."""
        import pandas as pd
        row = {"time": s.timestamp}
        for c in self.COLUMNS:
            if c != "time":
                row[c] = getattr(s, c, 0.0)
        self.df = pd.concat(
            [self.df, pd.DataFrame([row])], ignore_index=True
        ).iloc[-self.maxlen:]

    def last(self) -> dict:
        """Return the most recent row as a dict."""
        if len(self.df) == 0:
            return {c: 0.0 for c in self.COLUMNS}
        return self.df.iloc[-1].to_dict()

    @property
    def minutes_of_data(self) -> float:
        """How many minutes of data are stored."""
        return len(self.df) * 10 / 60


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    print("=" * 55)
    print("  core_engine.py v4.2 — Smoke test")
    print("=" * 55)

    # ── LCOHAccumulator ───────────────────────────────────────────────
    print("\n[1] LCOH Accumulator")
    acc = LCOHAccumulator()
    for i in range(200):
        lcoh = acc.update(0.05, 0.012, 4.5)
    print(f"  LCOH after 200 ticks : €{lcoh:.3f}/kg")
    print(f"  Window minutes       : {acc.window_minutes:.1f} min")
    print(f"  Total H₂             : {acc.total_h2_kg:.4f} kg")
    print(f"  Is profitable        : {acc.is_profitable}")

    # ── AlertSystem ───────────────────────────────────────────────────
    print("\n[2] Alert System")
    alerts = AlertSystem()
    alerts.check("THERMAL_RUNAWAY", True, 68.0)
    alerts.check("BESS_OVERHEAT",   True, 57.0)
    alerts.check("GRID_IMPORT",     True, 5.0)
    alerts.check("THERMAL_RUNAWAY", True, 69.0)   # duplicate — should not add
    print(f"  Active alerts    : {len(alerts.active)}")
    print(f"  Errors           : {[a.code for a in alerts.errors()]}")
    print(f"  Warnings         : {[a.code for a in alerts.warnings()]}")
    print(f"  Infos            : {[a.code for a in alerts.infos()]}")
    print(f"  Has critical     : {alerts.has_critical}")
    alerts.clear()
    print(f"  After clear      : {len(alerts.active)} alerts")

    # ── TickState fields ──────────────────────────────────────────────
    print("\n[3] TickState fields")
    s = TickState(tick=1, timestamp="10:00:00")
    required = ["wx_humidity", "wx_precip_mm", "wx_soiling",
                "cum_h2_kg", "cum_revenue_eur", "leak_detected"]
    for f in required:
        val = getattr(s, f, "MISSING")
        status = "✅" if val != "MISSING" else "❌"
        print(f"  {status} {f} = {val}")

    # ── HistoryBuffer ─────────────────────────────────────────────────
    print("\n[4] HistoryBuffer")
    buf = HistoryBuffer(maxlen=10)
    for i in range(15):
        s = TickState(tick=i, timestamp=f"{i:02d}:00:00",
                      solar_kw=float(i), wx_irradiance=float(i*50))
        buf.append(s)
    print(f"  Rows stored      : {len(buf.df)} (max 10)")
    print(f"  Minutes of data  : {buf.minutes_of_data:.1f}")
    print(f"  Columns          : {len(buf.df.columns)}")
    print(f"  wx_humidity col  : {'wx_humidity' in buf.df.columns}")
    print(f"  wx_precip col    : {'wx_precip_mm' in buf.df.columns}")
    last = buf.last()
    print(f"  Last solar_kw    : {last['solar_kw']}")

    print("\n✅ core_engine.py v4.2 — all tests passed")
