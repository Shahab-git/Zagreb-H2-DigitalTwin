# =============================================================================
# core_engine.py — LUMINIH2 Core Simulation Engine
# Tick Engine · LCOH Accumulator · State Management · Alert System
# Version: 4.0 (Real Digital Twin · Streamlit Cloud Ready)
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging
import numpy as np

logger = logging.getLogger("CoreEngine")

# =============================================================================
# LCOH Accumulator — hourly rolling window (fixes per-tick explosion)
# =============================================================================

@dataclass
class LCOHAccumulator:
    """
    Accumulates energy cost and H₂ production over a rolling 1-hour window.
    LCOH = total_cost_EUR / total_h2_kg  (never divides by tiny per-tick amounts)
    """
    _cost_window:   list = field(default_factory=list)
    _h2_window:     list = field(default_factory=list)
    _window_size:   int  = 360          # 360 × 10s = 1 hour
    total_cost_eur: float = 0.0
    total_h2_kg:    float = 0.0
    lcoh:           float = 0.0
    is_profitable:  bool  = False

    def update(self, cost_eur_tick: float, h2_kg_tick: float, target: float) -> float:
        self._cost_window.append(cost_eur_tick)
        self._h2_window.append(h2_kg_tick)
        if len(self._cost_window) > self._window_size:
            self._cost_window.pop(0)
            self._h2_window.pop(0)

        self.total_cost_eur += cost_eur_tick
        self.total_h2_kg    += h2_kg_tick

        window_h2   = sum(self._h2_window)
        window_cost = sum(self._cost_window)
        if window_h2 > 0.001:
            self.lcoh = round(window_cost / window_h2, 3)
        else:
            self.lcoh = 0.0
        self.is_profitable = 0 < self.lcoh <= target
        return self.lcoh


# =============================================================================
# Alert System
# =============================================================================

@dataclass
class Alert:
    level:   str    # "error" | "warning" | "info"
    code:    str    # machine-readable code
    message: str
    value:   float  = 0.0
    ts:      str    = ""

    def __post_init__(self):
        if not self.ts:
            self.ts = datetime.now().strftime("%H:%M:%S")


class AlertSystem:
    """Collects and deduplicates alerts each tick."""

    CODES = {
        "THERMAL_RUNAWAY":  ("error",   "BESS thermal runaway risk!"),
        "BESS_OVERHEAT":    ("warning", "BESS temperature elevated"),
        "H2_LEAK":          ("error",   "H₂ leak detected — mass anomaly"),
        "STACK_DEGRADED":   ("warning", "Electrolyzer SoH low"),
        "FC_H2_SHORTAGE":   ("info",    "Fuel cell H₂ supply limited"),
        "BESS_LOW_SOC":     ("warning", "BESS SoC critically low"),
        "PRESSURE_HIGH":    ("error",   "Tank pressure near safety limit"),
        "WIND_CUTOUT":      ("info",    "Wind turbine cut-out (turbulence)"),
        "GRID_IMPORT":      ("info",    "Emergency grid import active"),
    }

    def __init__(self):
        self.active: list[Alert] = []

    def clear(self):
        self.active = []

    def check(self, code: str, condition: bool, value: float = 0.0):
        if condition and code in self.CODES:
            level, msg = self.CODES[code]
            if not any(a.code == code for a in self.active):
                self.active.append(Alert(level, code, msg, value))

    def errors(self)   -> list[Alert]: return [a for a in self.active if a.level == "error"]
    def warnings(self) -> list[Alert]: return [a for a in self.active if a.level == "warning"]
    def infos(self)    -> list[Alert]: return [a for a in self.active if a.level == "info"]


# =============================================================================
# Tick Engine — decouples simulation time from Streamlit rerun
# =============================================================================

@dataclass
class TickState:
    """Complete snapshot of the system at one tick."""
    tick:               int   = 0
    timestamp:          str   = ""
    # Generation
    solar_kw:           float = 0.0
    wind_kw:            float = 0.0
    total_gen_kw:       float = 0.0
    solar_cell_temp_c:  float = 25.0
    solar_eff_pct:      float = 0.0
    wind_regime:        str   = "below_cut_in"
    # BESS
    bess_soc_pct:       float = 55.0
    bess_soh_pct:       float = 100.0
    bess_temp_c:        float = 25.0
    bess_charge_kw:     float = 0.0
    bess_thermal_warn:  bool  = False
    bess_runaway:       bool  = False
    # EMS switching
    source:             str   = "—"
    switching_event:    str   = "Standby"
    elec_kw:            float = 0.0
    ev_kw:              float = 0.0
    grid_export_kw:     float = 0.0
    grid_import_kw:     float = 0.0
    # Electrolyzer
    h2_kg_h:            float = 0.0
    elec_eff_pct:       float = 0.0
    elec_purity:        float = 99.999
    elec_soh_pct:       float = 100.0
    water_l_h:          float = 0.0
    heat_kw:            float = 0.0
    # H₂ chain
    buffer_pct:         float = 0.0
    main_tank_pct:      float = 0.0
    hrs_pct:            float = 0.0
    pressure_bar:       float = 30.0
    tank_temp_c:        float = 20.0
    compressor_on:      bool  = False
    leak_detected:      bool  = False
    # Fuel cell
    fc_kw:              float = 0.0
    fc_eff_pct:         float = 0.0
    fc_h2_shortage:     bool  = False
    # Economics
    lcoh:               float = 0.0
    is_profitable:      bool  = False
    co2_saved_kg:       float = 0.0
    carbon_rev_eur:     float = 0.0
    subsidy_eur:        float = 0.0
    grid_rev_eur:       float = 0.0
    # Weather
    wx_temp_c:          float = 15.0
    wx_humidity:        float = 60.0
    wx_wind_ms:         float = 4.5
    wx_irradiance:      float = 0.0
    wx_soiling:         float = 0.98
    wx_precip_mm:       float = 0.0
    wx_source:          str   = "fallback"
    # Cumulative
    cum_h2_kg:          float = 0.0
    cum_co2_kg:         float = 0.0
    cum_revenue_eur:    float = 0.0
    cum_water_l:        float = 0.0


class TickEngine:
    """
    Runs one complete physics + EMS tick.
    Called once per Streamlit rerun — does NOT use time.sleep.
    All physics objects live in st.session_state and persist across reruns.
    """

    def __init__(self, config, solar, wind, bess, electrolyzer,
                 h2_chain, fuel_cell, ems, forecaster, weather,
                 lcoh_acc, alerts):
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

        # Cumulative accumulators
        self.cum_h2_kg:       float = 0.0
        self.cum_co2_kg:      float = 0.0
        self.cum_revenue_eur: float = 0.0
        self.cum_water_l:     float = 0.0
        self.tick_count:      int   = 0

    def run(self,
            override: Optional[dict] = None,
            ev_demand_kw: float = 10.0,
            force_bess_charge: bool = False,
            ) -> TickState:
        """Execute one simulation tick. Returns TickState snapshot."""
        import pytz
        from datetime import datetime as dt
        self.tick_count += 1
        now = dt.now(pytz.timezone("Europe/Zagreb"))
        dt_h = self.cfg.TIMESTEP_SEC / 3600.0

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
            wx_hist    = [wx_irr * max(0, np.sin(np.pi * (h - 6) / 14)) for h in range(24)]
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

        # ── 2. Generation ──────────────────────────────────────────────
        solar_r = self.solar.get_power_output(wx_irr, wx_temp, wx_soiling)
        wind_r  = self.wind.get_power_output(wx_wind, wx_turb)
        total_gen = solar_r.ac_power_kw + wind_r.ac_power_kw

        # ── 3. AI Forecast (train every 20 ticks) ─────────────────────
        if self.tick_count % 20 == 1 and len(wx_hist) >= 24:
            train_data = wx_hist * 3 if len(wx_hist) < 48 else wx_hist
            self.ai.train_on_historical_data(train_data)
        forecast = self.ai.predict_future(wx_hist, horizon_hours=6, current_dt=now)

        # ── 4. EMS Power Switching ─────────────────────────────────────
        src_dec = self.ems.decide_energy_source(
            solar_r.ac_power_kw, wind_r.ac_power_kw, self.bess.soc
        )
        incoming = total_gen
        if force_bess_charge:
            incoming += self.cfg.BATT_MAX_CHARGE_KW * 0.4
        flow = self.ems.manage_power_flow(
            incoming_power_kw=incoming,
            current_soc=self.bess.soc,
            ev_demand_kw=ev_demand_kw,
            timestep_sec=self.cfg.TIMESTEP_SEC,
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
        h2_tick   = elec_r.h2_kg_h * dt_h
        # Energy cost per tick
        if "Grid" in src_dec.source:
            cost_tick = flow.power_to_electrolyzer_kw * self.cfg.GRID_PRICE_BUY * dt_h
        else:
            cost_tick = flow.power_to_electrolyzer_kw * 0.02 * dt_h
        # Stack depreciation
        load_f     = flow.power_to_electrolyzer_kw / max(self.cfg.ELEC_P_MAX_KW, 0.01)
        cost_tick += load_f * (self.cfg.STACK_REPLACEMENT_COST / (self.cfg.ELEC_P_MAX_KW * 8760)) * dt_h

        lcoh = self.lcoh_acc.update(cost_tick, h2_tick, self.cfg.LCOH_TARGET_EURO_KG)

        co2_avoided = h2_tick * self.cfg.CO2_SAVED_PER_KG_H2
        co2_emitted = (flow.power_to_electrolyzer_kw * self.cfg.GRID_CO2_INTENSITY * dt_h
                       if "Grid" in src_dec.source else 0.0)
        net_co2     = co2_avoided - co2_emitted
        carbon_rev  = (net_co2 / 1000.0) * self.cfg.CARBON_TAX_EUR_TON
        subsidy     = h2_tick * self.cfg.GREEN_H2_SUBSIDY
        grid_rev    = ds.grid_revenue_eur

        # ── 10. Cumulative accumulators ────────────────────────────────
        self.cum_h2_kg       += h2_tick
        self.cum_co2_kg      += max(0.0, net_co2)
        self.cum_revenue_eur += grid_rev + subsidy + carbon_rev
        self.cum_water_l     += elec_r.water_l_h * dt_h

        # ── 11. Alerts ─────────────────────────────────────────────────
        self.alerts.clear()
        self.alerts.check("THERMAL_RUNAWAY", bess_r.thermal_runaway_risk, bess_r.temperature_c)
        self.alerts.check("BESS_OVERHEAT",   bess_r.thermal_warning, bess_r.temperature_c)
        self.alerts.check("H2_LEAK",         chain_r.leak_detected)
        self.alerts.check("STACK_DEGRADED",  elec_r.soh < 0.80, elec_r.soh)
        self.alerts.check("FC_H2_SHORTAGE",  fc_r.h2_shortage)
        self.alerts.check("BESS_LOW_SOC",    bess_r.soc < self.cfg.BATT_SOC_MIN + 0.03, bess_r.soc)
        self.alerts.check("PRESSURE_HIGH",   chain_r.pressure_bar > self.cfg.SAFETY_MAX_PRESSURE_BAR * 0.90, chain_r.pressure_bar)
        self.alerts.check("WIND_CUTOUT",     wind_r.operating_regime == "cut_out")
        self.alerts.check("GRID_IMPORT",     flow.grid_import_kw > 0)

        # ── 12. Build TickState ────────────────────────────────────────
        return TickState(
            tick=self.tick_count,
            timestamp=now.strftime("%H:%M:%S"),
            solar_kw=round(solar_r.ac_power_kw, 2),
            wind_kw=round(wind_r.ac_power_kw, 2),
            total_gen_kw=round(total_gen, 2),
            solar_cell_temp_c=solar_r.cell_temp_c,
            solar_eff_pct=round((1 - solar_r.thermal_derating_pct / 100) * 100, 1),
            wind_regime=wind_r.operating_regime,
            bess_soc_pct=round(bess_r.soc * 100, 1),
            bess_soh_pct=round(bess_r.soh * 100, 2),
            bess_temp_c=bess_r.temperature_c,
            bess_charge_kw=flow.power_to_battery_kw,
            bess_thermal_warn=bess_r.thermal_warning,
            bess_runaway=bess_r.thermal_runaway_risk,
            source=src_dec.source,
            switching_event=flow.switching_event,
            elec_kw=flow.power_to_electrolyzer_kw,
            ev_kw=flow.power_to_ev_kw,
            grid_export_kw=flow.grid_export_kw,
            grid_import_kw=flow.grid_import_kw,
            h2_kg_h=round(elec_r.h2_kg_h, 5),
            elec_eff_pct=round(elec_r.efficiency * 100, 2),
            elec_purity=round(elec_r.purity_pct, 4),
            elec_soh_pct=round(elec_r.soh * 100, 2),
            water_l_h=round(elec_r.water_l_h, 4),
            heat_kw=round(elec_r.heat_recovered_kw, 3),
            buffer_pct=chain_r.buffer_fill_pct,
            main_tank_pct=chain_r.main_fill_pct,
            hrs_pct=chain_r.hrs_fill_pct,
            pressure_bar=chain_r.pressure_bar,
            tank_temp_c=chain_r.temp_c,
            compressor_on=chain_r.compressor_active,
            leak_detected=chain_r.leak_detected,
            fc_kw=round(fc_r.p_out_kw, 3),
            fc_eff_pct=round(fc_r.efficiency * 100, 1),
            fc_h2_shortage=fc_r.h2_shortage,
            lcoh=lcoh,
            is_profitable=self.lcoh_acc.is_profitable,
            co2_saved_kg=round(max(0.0, net_co2), 4),
            carbon_rev_eur=round(carbon_rev, 4),
            subsidy_eur=round(subsidy, 4),
            grid_rev_eur=round(grid_rev, 4),
            wx_temp_c=wx_temp,
            wx_humidity=wx_hum,
            wx_wind_ms=wx_wind,
            wx_irradiance=wx_irr,
            wx_soiling=wx_soiling,
            wx_precip_mm=wx_precip,
            wx_source=wx_src,
            cum_h2_kg=round(self.cum_h2_kg, 4),
            cum_co2_kg=round(self.cum_co2_kg, 3),
            cum_revenue_eur=round(self.cum_revenue_eur, 3),
            cum_water_l=round(self.cum_water_l, 2),
        ), forecast


# =============================================================================
# History Buffer — fixed-size rolling window for charts
# =============================================================================

class HistoryBuffer:
    """Ring-buffer that keeps last N ticks as a pandas DataFrame."""
    COLUMNS = [
        "time", "solar_kw", "wind_kw", "total_gen_kw",
        "bess_soc_pct", "bess_temp_c", "bess_charge_kw",
        "elec_kw", "h2_kg_h", "elec_eff_pct",
        "buffer_pct", "main_tank_pct", "hrs_pct", "pressure_bar",
        "fc_kw", "ev_kw", "grid_export_kw", "grid_import_kw",
        "lcoh", "co2_saved_kg", "grid_rev_eur",
        "wx_temp_c", "wx_irradiance", "wx_wind_ms",
    ]

    def __init__(self, maxlen: int = 120):
        import pandas as pd
        self.maxlen = maxlen
        self.df = pd.DataFrame(columns=self.COLUMNS)

    def append(self, s: TickState):
        import pandas as pd
        row = {c: getattr(s, c, 0.0) for c in self.COLUMNS}
        self.df = pd.concat(
            [self.df, pd.DataFrame([row])], ignore_index=True
        ).iloc[-self.maxlen:]

    def last(self) -> dict:
        if len(self.df) == 0:
            return {c: 0.0 for c in self.COLUMNS}
        return self.df.iloc[-1].to_dict()


# =============================================================================
# Smoke-test
# =============================================================================
if __name__ == "__main__":
    acc = LCOHAccumulator()
    for _ in range(100):
        lcoh = acc.update(0.05, 0.012, 4.5)
    print(f"LCOH after 100 ticks: {lcoh:.3f} EUR/kg")

    alerts = AlertSystem()
    alerts.check("THERMAL_RUNAWAY", True, 68.0)
    alerts.check("BESS_OVERHEAT", True, 57.0)
    print(f"Errors: {[a.message for a in alerts.errors()]}")
    print(f"Warnings: {[a.message for a in alerts.warnings()]}")

    print("✅ core_engine.py v4.0 OK")
