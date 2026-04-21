# =============================================================================
# app.py — LUMINIH2 Digital Twin · Streamlit Dashboard
# Integrated Green Hydrogen & E-Mobility Hub · Zagreb, Croatia
# Version: 3.2 (Streamlit Cloud Ready · All Modules Connected)
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import numpy as np
import pytz

from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider

# =============================================================================
# PAGE CONFIG — must be first Streamlit call
# =============================================================================
st.set_page_config(
    page_title="LUMINIH2 Digital Twin",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CUSTOM CSS — Zagreb Light Theme
# =============================================================================
st.markdown("""
<style>
.stApp { background-color: #f8fafc; color: #1e293b; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }

/* Header */
.lumi-header {
    background: #ffffff;
    border-left: 5px solid #0ea5e9;
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* KPI cards */
.kpi-card {
    background: #ffffff;
    border-radius: 10px;
    padding: 14px 18px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 10px;
}
.kpi-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin: 0; }
.kpi-value { font-size: 26px; font-weight: 600; color: #0f172a; margin: 2px 0; }
.kpi-delta { font-size: 12px; margin: 0; }
.kpi-delta.up   { color: #10b981; }
.kpi-delta.down { color: #ef4444; }
.kpi-delta.neu  { color: #64748b; }

/* Status badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
}
.badge-green  { background: #dcfce7; color: #15803d; }
.badge-yellow { background: #fef9c3; color: #a16207; }
.badge-red    { background: #fee2e2; color: #b91c1c; }
.badge-blue   { background: #dbeafe; color: #1d4ed8; }

/* Switching log */
.switch-log {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    color: #334155;
    min-height: 48px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 2px solid #e2e8f0; }
.stTabs [data-baseweb="tab"] {
    background: #f1f5f9;
    border-radius: 8px 8px 0 0;
    padding: 8px 18px;
    color: #475569;
    font-weight: 500;
    border: none;
}
.stTabs [aria-selected="true"] {
    background: #0ea5e9 !important;
    color: #ffffff !important;
}

/* Sidebar */
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# STARTUP VALIDATION
# =============================================================================
try:
    validate_config()
except AssertionError as e:
    st.error(f"❌ Config validation failed: {e}")
    st.stop()

# =============================================================================
# SESSION STATE — physics objects persist across reruns
# =============================================================================
def _init_state():
    if "initialized" in st.session_state:
        return
    st.session_state.initialized = True

    # Physics engines
    st.session_state.solar      = SolarSystem()
    st.session_state.wind       = WindSystem()
    st.session_state.bess       = BatteryBESS(initial_soc=0.55)
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.h2_chain   = HydrogenStorageChain()
    st.session_state.fuel_cell  = FuelCellAircell()
    st.session_state.ems        = EMSBrain()
    st.session_state.forecaster = AIPredictor()
    st.session_state.weather    = WeatherProvider()

    # Time-series history (last 60 ticks)
    st.session_state.history = pd.DataFrame(columns=[
        "time", "solar_kw", "wind_kw", "total_gen_kw",
        "bess_soc", "bess_temp", "bess_kw",
        "elec_kw", "h2_kg_h", "elec_eff",
        "buffer_pct", "main_tank_pct", "hrs_pct", "pressure_bar",
        "fc_kw", "ev_kw", "grid_export_kw", "grid_import_kw",
        "lcoh", "co2_saved", "revenue", "switching_event",
    ])

    # Accumulators
    st.session_state.total_h2_kg    = 0.0
    st.session_state.total_revenue  = 0.0
    st.session_state.total_co2_kg   = 0.0
    st.session_state.tick           = 0
    st.session_state.sim_running    = True
    st.session_state.last_forecast  = []
    st.session_state.forecast_trained = False

_init_state()

# =============================================================================
# SIDEBAR — simulation controls
# =============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Simulation Controls")
    st.session_state.sim_running = st.toggle("▶ Live Simulation", value=st.session_state.sim_running)
    refresh_rate = st.slider("Refresh interval (sec)", 1, 10, 3)
    st.divider()

    st.markdown("### 🌦 Manual Weather Override")
    use_override = st.checkbox("Enable manual override")
    if use_override:
        man_irr   = st.slider("Irradiance (W/m²)", 0, 1000, 500)
        man_wind  = st.slider("Wind speed (m/s)", 0.0, 25.0, 6.0, 0.1)
        man_temp  = st.slider("Temperature (°C)", -10, 45, 20)
    st.divider()

    st.markdown("### 🔋 BESS Manual")
    bess_force_charge = st.checkbox("Force BESS charge from grid")
    st.divider()

    st.markdown("### 📡 Info")
    st.caption(f"Config v3.2 | Location: {Config.location.city}")
    st.caption(f"Tick: {st.session_state.tick}")
    if st.button("🔄 Reset Simulation"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# =============================================================================
# PHYSICS TICK — runs once per rerun
# =============================================================================
zagreb_tz = pytz.timezone("Europe/Zagreb")
now_dt = datetime.now(zagreb_tz)

if st.session_state.sim_running:
    st.session_state.tick += 1

    # ── 1. Weather ────────────────────────────────────────────────────
    if use_override:
        wx_irr     = float(man_irr)
        wx_wind    = float(man_wind)
        wx_temp    = float(man_temp)
        wx_soiling = 0.98
        wx_turb    = 0.12
        wx_history = [wx_irr] * 24
    else:
        wx = st.session_state.weather.fetch_current_data()
        wx_irr     = wx.irradiance_raw_wm2
        wx_wind    = wx.wind_speed_ms
        wx_temp    = wx.temp_c
        wx_soiling = wx.soiling_factor
        wx_turb    = wx.turbulence_intensity
        wx_history = wx.history_irradiance_24h

    # ── 2. Generation ─────────────────────────────────────────────────
    solar_r = st.session_state.solar.get_power_output(wx_irr, wx_temp, wx_soiling)
    wind_r  = st.session_state.wind.get_power_output(wx_wind, wx_turb)
    solar_kw = solar_r.ac_power_kw
    wind_kw  = wind_r.ac_power_kw
    total_gen = solar_kw + wind_kw

    # ── 3. AI Forecast (train every 10 ticks, predict once per tick) ──
    if st.session_state.tick % 10 == 1 and len(wx_history) >= 48:
        st.session_state.forecaster.train_on_historical_data(wx_history * 3)
        st.session_state.forecast_trained = True

    forecast_result = st.session_state.forecaster.predict_future(
        last_24h_data=wx_history, horizon_hours=6, current_dt=now_dt
    )
    st.session_state.last_forecast = forecast_result

    # ── 4. EMS Power Switching ────────────────────────────────────────
    bess = st.session_state.bess
    ev_demand = Config.EV_CHARGER_POWER_KW * np.clip(np.random.beta(2, 3), 0, 1)
    src_dec = st.session_state.ems.decide_energy_source(solar_kw, wind_kw, bess.soc)

    incoming = total_gen + (Config.BATT_MAX_CHARGE_KW * 0.5 if bess_force_charge else 0.0)
    flow = st.session_state.ems.manage_power_flow(
        incoming_power_kw=incoming,
        current_soc=bess.soc,
        ev_demand_kw=ev_demand,
        timestep_sec=Config.TIMESTEP_SEC,
    )

    # ── 5. BESS update ────────────────────────────────────────────────
    net_bess = flow.power_to_battery_kw - (bess.get_max_discharge_power() * 0.1)
    bess_r = bess.update_state(net_bess, ambient_temp_c=wx_temp)

    # ── 6. Electrolyzer ───────────────────────────────────────────────
    elec_r = st.session_state.electrolyzer.calculate_production(
        flow.power_to_electrolyzer_kw, wx_temp
    )

    # ── 7. H₂ Storage chain ───────────────────────────────────────────
    chain_r = st.session_state.h2_chain.manage_chain(elec_r.h2_kg_h, wx_temp)

    # ── 8. Fuel Cell + Downstream ─────────────────────────────────────
    fc_r  = st.session_state.fuel_cell.generate_power(chain_r.hrs_kg, ev_demand)
    ds    = st.session_state.ems.manage_fc_and_grid(fc_r.p_out_kw, ev_demand)

    # ── 9. Economics ─────────────────────────────────────────────────
    econ = st.session_state.ems.calculate_economics(
        elec_r.h2_kg_h * (Config.TIMESTEP_SEC / 3600),
        flow.power_to_electrolyzer_kw,
        src_dec.source,
    )

    # ── 10. Accumulators ──────────────────────────────────────────────
    dt_h = Config.TIMESTEP_SEC / 3600
    st.session_state.total_h2_kg   += elec_r.h2_kg_h * dt_h
    st.session_state.total_revenue += ds.grid_revenue_eur + econ.subsidy_earned_eur
    st.session_state.total_co2_kg  += econ.net_co2_saved_kg * dt_h

    # ── 11. History append (keep last 60) ────────────────────────────
    new_row = {
        "time": now_dt.strftime("%H:%M:%S"),
        "solar_kw": solar_kw, "wind_kw": wind_kw, "total_gen_kw": total_gen,
        "bess_soc": bess_r.soc * 100, "bess_temp": bess_r.temperature_c, "bess_kw": flow.power_to_battery_kw,
        "elec_kw": flow.power_to_electrolyzer_kw, "h2_kg_h": elec_r.h2_kg_h, "elec_eff": elec_r.efficiency * 100,
        "buffer_pct": chain_r.buffer_fill_pct, "main_tank_pct": chain_r.main_fill_pct,
        "hrs_pct": chain_r.hrs_fill_pct, "pressure_bar": chain_r.pressure_bar,
        "fc_kw": fc_r.p_out_kw, "ev_kw": flow.power_to_ev_kw,
        "grid_export_kw": flow.grid_export_kw, "grid_import_kw": flow.grid_import_kw,
        "lcoh": econ.lcoh_eur_kg, "co2_saved": econ.net_co2_saved_kg,
        "revenue": ds.grid_revenue_eur, "switching_event": flow.switching_event,
    }
    hist = st.session_state.history
    st.session_state.history = pd.concat(
        [hist, pd.DataFrame([new_row])], ignore_index=True
    ).iloc[-60:]

# Convenience aliases
hist = st.session_state.history
tick = st.session_state.tick
last = hist.iloc[-1] if len(hist) > 0 else {}

# =============================================================================
# HEADER
# =============================================================================
st.markdown(f"""
<div class="lumi-header">
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
    <div>
      <div style="font-size:22px; font-weight:700; color:#0f172a;">⚡ LUMINIH2 Digital Twin</div>
      <div style="font-size:13px; color:#64748b; margin-top:2px;">
        Zagreb Energy Hub &nbsp;·&nbsp; Tick #{tick} &nbsp;·&nbsp; {now_dt.strftime('%A %d %b %Y')}
      </div>
    </div>
    <div style="display:flex; gap:16px; align-items:center; flex-wrap:wrap;">
      <div style="text-align:right;">
        <div style="font-size:24px; font-weight:700; color:#0f172a; letter-spacing:0.05em;">
          {now_dt.strftime('%H:%M:%S')}
        </div>
        <div style="font-size:11px; color:#64748b;">Europe/Zagreb</div>
      </div>
      <div>
        <span class="badge badge-green">● SYSTEM ACTIVE</span><br>
        <span class="badge badge-blue" style="margin-top:4px; display:inline-block;">
          SRC: {last.get('solar_kw', 0)+last.get('wind_kw', 0):.1f} kW
        </span>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# TOP KPI ROW
# =============================================================================
k1, k2, k3, k4, k5 = st.columns(5)

def kpi(col, label, value, delta="", delta_dir="neu"):
    col.markdown(f"""
    <div class="kpi-card">
      <p class="kpi-label">{label}</p>
      <p class="kpi-value">{value}</p>
      <p class="kpi-delta {delta_dir}">{delta}</p>
    </div>
    """, unsafe_allow_html=True)

kpi(k1, "Total Generation",
    f"{last.get('total_gen_kw', 0):.1f} kW",
    f"☀ {last.get('solar_kw',0):.1f} + 💨 {last.get('wind_kw',0):.1f}", "neu")
kpi(k2, "BESS State of Charge",
    f"{last.get('bess_soc', 0):.1f}%",
    f"🌡 {last.get('bess_temp', 25):.1f}°C",
    "up" if last.get('bess_soc', 50) > 50 else "down")
kpi(k3, "H₂ Production",
    f"{last.get('h2_kg_h', 0)*1000:.2f} g/h",
    f"η = {last.get('elec_eff', 0):.1f}%", "up")
kpi(k4, "Total H₂ Produced",
    f"{st.session_state.total_h2_kg:.3f} kg",
    f"CO₂ saved: {st.session_state.total_co2_kg:.2f} kg", "up")
kpi(k5, "Revenue (session)",
    f"€ {st.session_state.total_revenue:.3f}",
    f"LCOH: €{last.get('lcoh', 0):.2f}/kg",
    "up" if econ.is_profitable else "down")

# Power switching log
st.markdown(f"""
<div class="switch-log">
⚡ EMS Switching → {last.get("switching_event", "Standby")}
</div>
""", unsafe_allow_html=True)

# Alert banners
if bess_r.thermal_runaway_risk:
    st.error("🔥 THERMAL RUNAWAY RISK — BESS emergency shutdown initiated!")
elif bess_r.thermal_warning:
    st.warning(f"⚠️ BESS temperature elevated: {bess_r.temperature_c:.1f}°C")
if chain_r.leak_detected:
    st.error("🚨 H₂ Leak Detected — mass balance anomaly in main tank!")
if elec_r.stack_warning:
    st.warning(f"⚠️ Electrolyzer SoH low: {elec_r.soh*100:.1f}%")
if fc_r.h2_shortage:
    st.info("ℹ️ Fuel cell operating below demand — H₂ supply limited.")

# =============================================================================
# MAIN TABS
# =============================================================================
tabs = st.tabs([
    "🌍 1. Acquisition",
    "⚗️ 2. Production",
    "🔋 3. Storage",
    "🔌 4. Distribution",
    "📊 5. Analytics",
])
THEME = "plotly_white"

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — ACQUISITION
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 1. Live Generation Mix")
        fig1 = px.pie(
            values=[
                max(0.01, last.get("solar_kw", 0)),
                max(0.01, last.get("wind_kw", 0)),
                max(0.01, last.get("grid_import_kw", 0)),
            ],
            names=["Solar PV", "Wind", "Grid Import"],
            hole=0.6,
            color_discrete_sequence=["#f59e0b", "#60a5fa", "#94a3b8"],
        )
        fig1.update_layout(template=THEME, height=280, margin=dict(t=10, b=10))
        st.plotly_chart(fig1, use_container_width=True)

        st.markdown("#### 2. Solar Irradiance Timeline")
        if len(hist) > 1:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=hist["time"], y=hist["solar_kw"],
                fill="tozeroy", fillcolor="rgba(245,158,11,0.12)",
                line=dict(color="#f59e0b", width=2), name="Solar kW",
            ))
            fig2.update_layout(template=THEME, height=220, margin=dict(t=10, b=10),
                               xaxis_title="", yaxis_title="kW")
            st.plotly_chart(fig2, use_container_width=True)

    with c2:
        st.markdown("#### 3. Wind Vector (Polar)")
        wv = last.get("wind_kw", 5)
        fig3 = go.Figure(go.Scatterpolar(
            r=[wv, wv * 0.9, wv * 1.1, wv * 0.95, wv],
            theta=[0, 72, 144, 216, 288],
            fill="toself",
            fillcolor="rgba(96,165,250,0.15)",
            line=dict(color="#3b82f6"),
        ))
        fig3.update_layout(template=THEME, height=280, margin=dict(t=10, b=10))
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("#### 4. AI Forecast — Next 6 Hours")
        fc = st.session_state.last_forecast
        if fc and hasattr(fc, "points") and fc.points:
            fc_df = pd.DataFrame({
                "Hour": [f"+{p.hour_offset+1}h" for p in fc.points],
                "Forecast": [p.value for p in fc.points],
                "Upper": [p.upper_bound for p in fc.points],
                "Lower": [p.lower_bound for p in fc.points],
            })
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(
                x=fc_df["Hour"], y=fc_df["Upper"],
                line=dict(width=0), showlegend=False,
            ))
            fig4.add_trace(go.Scatter(
                x=fc_df["Hour"], y=fc_df["Lower"],
                fill="tonexty", fillcolor="rgba(14,165,233,0.12)",
                line=dict(width=0), name="Confidence band",
            ))
            fig4.add_trace(go.Scatter(
                x=fc_df["Hour"], y=fc_df["Forecast"],
                line=dict(color="#0ea5e9", width=2), name="Forecast",
                mode="lines+markers",
            ))
            fig4.update_layout(template=THEME, height=220, margin=dict(t=10, b=10),
                               yaxis_title="W/m²")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("Forecaster training — data accumulating...")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — PRODUCTION
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 5. Power Flow Allocation")
        if len(hist) > 1:
            fig5 = go.Figure()
            for col, color, name in [
                ("bess_kw", "#10b981", "BESS"),
                ("elec_kw", "#8b5cf6", "Electrolyzer"),
                ("ev_kw", "#3b82f6", "EV Charger"),
                ("grid_export_kw", "#f59e0b", "Grid Export"),
            ]:
                fig5.add_trace(go.Scatter(
                    x=hist["time"], y=hist[col],
                    stackgroup="one", name=name,
                    line=dict(color=color, width=1),
                    fillcolor=color.replace("#", "rgba(") + ",0.7)",
                ))
            fig5.update_layout(template=THEME, height=260, margin=dict(t=10, b=10),
                               yaxis_title="kW")
            st.plotly_chart(fig5, use_container_width=True)

        st.markdown("#### 6. Electrolyzer Stack Health")
        fig6 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=elec_r.soh * 100,
            delta={"reference": 100},
            title={"text": "Stack SoH (%)"},
            gauge={
                "axis": {"range": [70, 100]},
                "bar": {"color": "#8b5cf6"},
                "steps": [
                    {"range": [70, 80], "color": "#fee2e2"},
                    {"range": [80, 90], "color": "#fef9c3"},
                    {"range": [90, 100], "color": "#dcfce7"},
                ],
                "threshold": {"line": {"color": "#ef4444", "width": 2}, "value": 80},
            },
        ))
        fig6.update_layout(template=THEME, height=240, margin=dict(t=30, b=10))
        st.plotly_chart(fig6, use_container_width=True)

    with c2:
        st.markdown("#### 7. H₂ Production Rate")
        if len(hist) > 1:
            fig7 = go.Figure()
            fig7.add_trace(go.Bar(
                x=hist["time"], y=hist["h2_kg_h"] * 1000,
                marker_color="#8b5cf6", name="g/h",
            ))
            fig7.update_layout(template=THEME, height=220, margin=dict(t=10, b=10),
                               yaxis_title="g H₂/h")
            st.plotly_chart(fig7, use_container_width=True)

        st.markdown("#### 8. Electrolyzer Efficiency vs Load")
        if len(hist) > 3:
            fig8 = px.scatter(
                hist, x="elec_kw", y="elec_eff",
                color="h2_kg_h",
                color_continuous_scale="Purples",
                labels={"elec_kw": "Power (kW)", "elec_eff": "Efficiency (%)"},
            )
            fig8.update_layout(template=THEME, height=240, margin=dict(t=10, b=10))
            st.plotly_chart(fig8, use_container_width=True)

        col_a, col_b = st.columns(2)
        col_a.metric("Purity", f"{elec_r.purity_pct:.4f}%", "ISO 14687")
        col_b.metric("Water use", f"{elec_r.water_l_h:.3f} L/h", "per kg H₂")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — STORAGE
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 9. BESS State of Charge")
        fig9 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=bess_r.soc * 100,
            title={"text": "SoC (%)"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#10b981"},
                "steps": [
                    {"range": [0, Config.BATT_SOC_MIN * 100], "color": "#fee2e2"},
                    {"range": [Config.BATT_SOC_MIN * 100, Config.BATT_SOC_MAX * 100], "color": "#f0fdf4"},
                ],
                "threshold": {"line": {"color": "#ef4444", "width": 2},
                              "value": Config.BATT_SOC_MIN * 100},
            },
        ))
        fig9.update_layout(template=THEME, height=240, margin=dict(t=30, b=10))
        st.plotly_chart(fig9, use_container_width=True)

        st.markdown("#### 10. BESS Temperature")
        if len(hist) > 1:
            fig10 = go.Figure()
            fig10.add_trace(go.Scatter(
                x=hist["time"], y=hist["bess_temp"],
                line=dict(color="#ef4444", width=2), name="Temp °C",
            ))
            fig10.add_hline(y=55, line_dash="dash", line_color="#f97316",
                           annotation_text="Warning 55°C")
            fig10.add_hline(y=Config.THERMAL_RUNAWAY_TEMP, line_dash="dash",
                           line_color="#ef4444", annotation_text="Runaway limit")
            fig10.update_layout(template=THEME, height=200, margin=dict(t=10, b=10),
                               yaxis_title="°C")
            st.plotly_chart(fig10, use_container_width=True)

    with c2:
        st.markdown("#### 11. Hydrogen Tank Levels")
        tanks = {
            "Buffer": chain_r.buffer_fill_pct,
            "Main Tank": chain_r.main_fill_pct,
            "HRS Station": chain_r.hrs_fill_pct,
        }
        fig11 = go.Figure(go.Bar(
            x=list(tanks.keys()), y=list(tanks.values()),
            marker_color=["#60a5fa", "#8b5cf6", "#10b981"],
            text=[f"{v:.1f}%" for v in tanks.values()],
            textposition="outside",
        ))
        fig11.update_layout(template=THEME, height=240, yaxis_range=[0, 110],
                           margin=dict(t=10, b=10), yaxis_title="%")
        st.plotly_chart(fig11, use_container_width=True)

        st.markdown("#### 12. Main Tank Pressure")
        fig12 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=chain_r.pressure_bar,
            title={"text": "Pressure (bar)"},
            gauge={
                "axis": {"range": [0, Config.SAFETY_MAX_PRESSURE_BAR]},
                "bar": {"color": "#3b82f6"},
                "threshold": {"line": {"color": "#ef4444", "width": 2},
                              "value": Config.SAFETY_MAX_PRESSURE_BAR * 0.9},
            },
        ))
        fig12.update_layout(template=THEME, height=200, margin=dict(t=30, b=10))
        st.plotly_chart(fig12, use_container_width=True)

        comp_badge = "badge-green" if chain_r.compressor_active else "badge-yellow"
        comp_text  = "ON" if chain_r.compressor_active else "STANDBY"
        st.markdown(f'Compressor: <span class="badge {comp_badge}">● {comp_text}</span> '
                   f'({chain_r.compressor_runtime_sec}s runtime)', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — DISTRIBUTION
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### 13. HRS 5 kg Station")
        hrs_pct = chain_r.hrs_fill_pct / 100
        st.progress(min(hrs_pct, 1.0))
        st.caption(f"{chain_r.hrs_kg:.3f} / {Config.HRS_H2_TANK_CAPACITY_KG:.1f} kg "
                  f"({chain_r.hrs_fill_pct:.1f}%)")
        badge_hrs = "badge-green" if chain_r.hrs_fill_pct > 60 else "badge-yellow"
        st.markdown(f'Status: <span class="badge {badge_hrs}">'
                   f'{"● READY" if chain_r.hrs_fill_pct > 60 else "▼ FILLING"}</span>',
                   unsafe_allow_html=True)

        st.markdown("#### 14. Fuel Cell Output")
        fig14 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=fc_r.p_out_kw,
            title={"text": "FC Power (kW)"},
            gauge={
                "axis": {"range": [0, Config.FC_POWER_NOM_KW * 1.1]},
                "bar": {"color": "#10b981"},
            },
        ))
        fig14.update_layout(template=THEME, height=220, margin=dict(t=30, b=10))
        st.plotly_chart(fig14, use_container_width=True)
        st.caption(f"η = {fc_r.efficiency*100:.1f}% | H₂ used: {fc_r.h2_used_kg*1000:.4f} g/step")

    with c2:
        st.markdown("#### 15. Grid Export vs EV Load")
        if len(hist) > 1:
            fig15 = go.Figure()
            fig15.add_trace(go.Scatter(x=hist["time"], y=hist["grid_export_kw"],
                                      fill="tozeroy", name="Grid export",
                                      line=dict(color="#f59e0b")))
            fig15.add_trace(go.Scatter(x=hist["time"], y=hist["ev_kw"],
                                      fill="tozeroy", name="EV load",
                                      line=dict(color="#3b82f6")))
            fig15.update_layout(template=THEME, height=240, margin=dict(t=10, b=10),
                               yaxis_title="kW")
            st.plotly_chart(fig15, use_container_width=True)

        st.markdown("#### 16. Downstream Split")
        fig16 = px.pie(
            values=[
                max(0.01, last.get("ev_kw", 0)),
                max(0.01, last.get("grid_export_kw", 0)),
                max(0.01, fc_r.heat_recovered_kw),
            ],
            names=["EV Charging", "Grid Export", "Heat Recovery"],
            color_discrete_sequence=["#3b82f6", "#f59e0b", "#f97316"],
            hole=0.5,
        )
        fig16.update_layout(template=THEME, height=240, margin=dict(t=10, b=10))
        st.plotly_chart(fig16, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.markdown("#### 17. Energy Flow — Sankey")
    s_kw  = max(0.01, last.get("solar_kw", 0))
    w_kw  = max(0.01, last.get("wind_kw", 0))
    b_kw  = max(0.01, last.get("bess_kw", 0))
    e_kw  = max(0.01, last.get("elec_kw", 0))
    ev_kw = max(0.01, last.get("ev_kw", 0))
    g_kw  = max(0.01, last.get("grid_export_kw", 0))

    fig17 = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=["Solar PV", "Wind", "BESS", "Electrolyzer", "H₂ Storage", "EV Station", "Grid"],
            color=["#f59e0b", "#60a5fa", "#10b981", "#8b5cf6", "#a78bfa", "#3b82f6", "#94a3b8"],
            pad=15, thickness=20,
        ),
        link=dict(
            source=[0, 1, 0, 1, 2, 3, 4, 4],
            target=[2, 2, 3, 3, 3, 4, 5, 6],
            value=[s_kw * 0.4, w_kw * 0.4, s_kw * 0.6, w_kw * 0.6,
                   b_kw * 0.2, e_kw, ev_kw, g_kw],
            color=["rgba(245,158,11,0.3)"] * 4 + ["rgba(16,185,129,0.3)",
                   "rgba(139,92,246,0.3)", "rgba(59,130,246,0.3)", "rgba(148,163,184,0.3)"],
        ),
    ))
    fig17.update_layout(template=THEME, height=360, margin=dict(t=10, b=10))
    st.plotly_chart(fig17, use_container_width=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### 18. LCOH Trend")
        if len(hist) > 1 and hist["lcoh"].max() > 0:
            fig18 = px.line(hist, x="time", y="lcoh",
                           labels={"lcoh": "€/kg", "time": ""},
                           color_discrete_sequence=["#8b5cf6"])
            fig18.add_hline(y=Config.LCOH_TARGET_EURO_KG, line_dash="dash",
                           line_color="#10b981", annotation_text=f"Target {Config.LCOH_TARGET_EURO_KG} €/kg")
            fig18.update_layout(template=THEME, height=220, margin=dict(t=10, b=10))
            st.plotly_chart(fig18, use_container_width=True)
        st.metric("Current LCOH", f"€ {last.get('lcoh', 0):.3f}/kg",
                 "✅ Target met" if econ.is_profitable else "⚠ Above target")

    with c2:
        st.markdown("#### 19. CO₂ Abatement")
        if len(hist) > 1:
            fig19 = go.Figure(go.Bar(
                x=hist["time"], y=hist["co2_saved"],
                marker_color="#10b981", name="kg CO₂ saved",
            ))
            fig19.update_layout(template=THEME, height=220, margin=dict(t=10, b=10),
                               yaxis_title="kg CO₂")
            st.plotly_chart(fig19, use_container_width=True)
        st.metric("Session total", f"{st.session_state.total_co2_kg:.2f} kg saved",
                 f"≈ {st.session_state.total_co2_kg / 12:.3f} kg H₂ equivalent")

    with c3:
        st.markdown("#### 20. Financial Summary")
        rev = st.session_state.total_revenue
        h2v = st.session_state.total_h2_kg * Config.GREEN_H2_SUBSIDY
        st.metric("Grid revenue", f"€ {rev:.3f}")
        st.metric("H₂ subsidy value", f"€ {h2v:.3f}")
        st.metric("Total H₂ produced", f"{st.session_state.total_h2_kg*1000:.1f} g")

        profitable_ticks = int(((hist["lcoh"] > 0) & (hist["lcoh"] <= Config.LCOH_TARGET_EURO_KG)).sum()) if len(hist) > 0 else 0
        st.caption(f"Profitable ticks: {profitable_ticks} / {len(hist)}")

# =============================================================================
# AUTO-REFRESH
# =============================================================================
time.sleep(refresh_rate)
st.rerun()
