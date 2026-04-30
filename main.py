# =============================================================================
# main.py — LUMINIH2 Digital Twin · Multi-Page Integrated Dashboard
# White Industrial Theme · Voice Welcome · Zagreb, Croatia · v4.1
# =============================================================================

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone, timedelta

from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider
from core_engine import TickEngine, LCOHAccumulator, AlertSystem, HistoryBuffer
from subsystems import SubsystemManager
from optimizer import EconomicOptimizer
from scenario_engine import ScenarioEngine, ScenarioParams

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="LUMINIH2 Digital Twin",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# WHITE THEME CSS
# =============================================================================
st.markdown("""
<style>
html, body { background-color: #ffffff !important; }
.stApp { background-color: #ffffff !important; color: #0f172a !important; }
[data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
[data-testid="stHeader"] { background-color: #ffffff !important; }
section[data-testid="stSidebar"] { background-color: #f8fafc !important; border-right: 1px solid #e2e8f0 !important; }
h1, h2, h3, h4, p, span, div, label { color: #0f172a; }
[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700; }
.kpi {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 13px 15px; box-shadow: 0 1px 4px rgba(0,0,0,.05); height: 100%;
}
.kpi-lbl { font-size: 10px; color: #64748b; text-transform: uppercase; font-weight: 600; margin: 0; }
.kpi-val { font-size: 22px; font-weight: 700; margin: 4px 0 2px; }
.kpi-cyan { color: #0284c7; } .kpi-amber { color: #d97706; } .kpi-green { color: #16a34a; } .kpi-red { color: #dc2626; }
.page-header {
    background: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #0ea5e9;
    border-radius: 10px; padding: 14px 20px; margin-bottom: 16px;
}
.device-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 9px;
}
.device-title { font-size: 14px; font-weight: 600; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.badge-green { background: #dcfce7; color: #15803d; }
.badge-amber { background: #fef9c3; color: #a16207; }
.badge-cyan { background: #e0f2fe; color: #0369a1; }
.sec-hdr { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 14px 0 8px; }
.ems-log { background: #f0f9ff; border-left: 3px solid #0ea5e9; padding: 8px 14px; font-family: monospace; font-size: 12px; color: #0369a1; margin: 8px 0; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE & CORE LOGIC (Background)
# =============================================================================
def _init():
    if "lumi_v41" in st.session_state: return
    st.session_state.lumi_v41 = True
    st.session_state.solar = SolarSystem()
    st.session_state.wind = WindSystem()
    st.session_state.bess = BatteryBESS(0.55)
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.fuel_cell = FuelCellAircell()
    st.session_state.ems = EMSBrain()
    st.session_state.forecaster = AIPredictor()
    st.session_state.weather = WeatherProvider()
    st.session_state.lcoh_acc = LCOHAccumulator()
    st.session_state.alerts = AlertSystem()
    st.session_state.history = HistoryBuffer(maxlen=120)
    st.session_state.subsystems = SubsystemManager()
    st.session_state.optimizer = EconomicOptimizer(Config)
    st.session_state.scenario_eng = ScenarioEngine(Config)
    st.session_state.engine = TickEngine(
        Config, st.session_state.solar, st.session_state.wind,
        st.session_state.bess, st.session_state.electrolyzer,
        st.session_state.h2_chain, st.session_state.fuel_cell,
        st.session_state.ems, st.session_state.forecaster,
        st.session_state.weather, st.session_state.lcoh_acc, st.session_state.alerts
    )
    st.session_state.sim_running = True
    st.session_state.last_state = None
    st.session_state.sub_result = None
_init()

# Physics Calculation (Must run every refresh)
if st.session_state.sim_running:
    s, fc_res = st.session_state.engine.run(ev_demand_kw=2.0)
    st.session_state.history.append(s)
    st.session_state.last_state = s
    st.session_state.last_fc = fc_res
    st.session_state.sub_result = st.session_state.subsystems.tick(
        h2_kg_h=s.h2_kg_h, elec_power_kw=s.elec_kw, ambient_temp_c=s.wx_temp_c, timestep_sec=Config.TIMESTEP_SEC)

s = st.session_state.last_state
hist = st.session_state.history.df
sub = st.session_state.sub_result
if s is None: st.stop()

# Helper for UI
C = dict(solar="#f59e0b", wind="#3b82f6", bess="#22c55e", elec="#8b5cf6", h2="#0ea5e9", fc="#ef4444", grid="#94a3b8", ev="#60a5fa")
def kpi(col, lbl, val, sub="", cls="kpi-cyan"):
    col.markdown(f'<div class="kpi"><p class="kpi-lbl">{lbl}</p><p class="kpi-val {cls}">{val}</p><p class="kpi-sub">{sub}</p></div>', unsafe_allow_html=True)

# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================
with st.sidebar:
    st.markdown('<div style="font-size:18px;font-weight:700;color:#0ea5e9;">⚡ LUMINIH2 MENU</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", ["Overview", "Energy Assets", "Hydrogen Chain", "Economics & AI", "System Health"])
    st.divider()
    st.session_state.sim_running = st.toggle("Live simulation", value=st.session_state.sim_running)
    refresh = st.slider("Refresh (sec)", 2, 15, 4)
    if st.button("🔄 Reset System"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# =============================================================================
# PAGE ROUTING
# =============================================================================

# Common Header (Always Visible)
st.markdown(f"""
<div class="page-header">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <div style="font-size:20px;font-weight:700;color:#0ea5e9;">LUMINIH2 Digital Twin — {page.upper()}</div>
      <div style="font-size:12px;color:#64748b;">Zagreb Hub · Status: ACTIVE · Tick #{s.tick}</div>
    </div>
    <div style="font-size:22px;font-weight:700;">{datetime.now().strftime('%H:%M:%S')}</div>
  </div>
</div>""", unsafe_allow_html=True)

if page == "Overview":
    # Top KPI Row
    k = st.columns(4)
    kpi(k[0], "Total Generation", f"{s.total_gen_kw:.1f} kW", "Solar + Wind", "kpi-amber")
    kpi(k[1], "BESS SoC", f"{s.bess_soc_pct:.1f}%", f"{s.bess_temp_c:.1f}°C", "kpi-green")
    kpi(k[2], "H₂ Rate", f"{s.h2_kg_h*1000:.1f} g/h", "Current Production", "kpi-cyan")
    kpi(k[3], "Current LCOH", f"€{s.lcoh:.2f}/kg", "Economic Index", "kpi-cyan")

    col_main, col_side = st.columns([3, 1])
    with col_main:
        st.markdown('<p class="sec-hdr">Live Energy Flow (Sankey)</p>', unsafe_allow_html=True)
        # Sankey Logic here (from your main code)
        fig_sk = go.Figure(go.Sankey(
            node=dict(label=["Solar", "Wind", "BESS", "Electrolyzer", "Storage", "HRS", "EV", "Grid"],
                      color=[C["solar"], C["wind"], C["bess"], C["elec"], C["h2"], "#f97316", C["ev"], C["grid"]]),
            link=dict(source=[0, 1, 0, 1, 2, 3, 4, 4], target=[2, 2, 3, 3, 3, 4, 5, 6],
                      value=[max(0.1, s.solar_kw)*0.4, max(0.1, s.wind_kw)*0.4, max(0.1, s.solar_kw)*0.6, max(0.1, s.wind_kw)*0.6, 2, 5, 2, 1])
        ))
        fig_sk.update_layout(height=400, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_sk, use_container_width=True)

    with col_side:
        st.markdown('<p class="sec-hdr">Quick Actions</p>', unsafe_allow_html=True)
        st.info(f"EMS: {s.switching_event}")
        st.metric("CO2 Saved", f"{s.cum_co2_kg:.2f} kg")

elif page == "Energy Assets":
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">Generation Trend (kW)</p>', unsafe_allow_html=True)
        fg = go.Figure()
        fg.add_trace(go.Scatter(x=hist["time"], y=hist["solar_kw"], name="Solar", line=dict(color=C["solar"])))
        fg.add_trace(go.Scatter(x=hist["time"], y=hist["wind_kw"], name="Wind", line=dict(color=C["wind"])))
        fg.update_layout(height=300, template="plotly_white")
        st.plotly_chart(fg, use_container_width=True)
    with c2:
        st.markdown('<p class="sec-hdr">Battery Storage Performance</p>', unsafe_allow_html=True)
        fb = go.Figure()
        fb.add_trace(go.Scatter(x=hist["time"], y=hist["bess_soc_pct"], name="SoC %", fill="tozeroy", line=dict(color=C["bess"])))
        fb.update_layout(height=300, template="plotly_white")
        st.plotly_chart(fb, use_container_width=True)

elif page == "Hydrogen Chain":
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown('<p class="sec-hdr">Electrolyzer Output (g/h)</p>', unsafe_allow_html=True)
        fh = go.Figure(go.Bar(x=hist["time"], y=hist["h2_kg_h"]*1000, marker_color=C["h2"]))
        fh.update_layout(height=350, template="plotly_white")
        st.plotly_chart(fh, use_container_width=True)
    with c2:
        st.markdown('<p class="sec-hdr">Storage & Purity</p>', unsafe_allow_html=True)
        st.metric("Tank Pressure", f"{s.pressure_bar:.1f} bar")
        st.metric("H2 Purity", f"{s.elec_purity:.3f} %")
        st.metric("Water Consumption", f"{s.cum_water_l:.1f} L")

elif page == "Economics & AI":
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">AI Solar Forecast (6h)</p>', unsafe_allow_html=True)
        fc = st.session_state.last_fc
        if fc and hasattr(fc, "points"):
            f3 = go.Figure(go.Scatter(x=[p.hour_offset for p in fc.points], y=[p.value for p in fc.points], mode="lines+markers", line=dict(color=C["h2"])))
            f3.update_layout(height=300, template="plotly_white", yaxis_title="W/m²")
            st.plotly_chart(f3, use_container_width=True)
    with c2:
        st.markdown('<p class="sec-hdr">Revenue & Credits</p>', unsafe_allow_html=True)
        st.metric("Session Revenue", f"€{s.cum_revenue_eur:.3f}")
        st.metric("Carbon Credits", f"€{(s.cum_co2_kg/1000)*Config.CARBON_TAX_EUR_TON:.2f}")

elif page == "System Health":
    st.markdown('<p class="sec-hdr">Active System Alerts</p>', unsafe_allow_html=True)
    for a in st.session_state.alerts.errors():
        st.error(f"🚨 [{a.code}] {a.message}")
    for a in st.session_state.alerts.warnings():
        st.warning(f"⚠️ [{a.code}] {a.message}")
    
    st.markdown('<p class="sec-hdr">EMS Operations Log</p>', unsafe_allow_html=True)
    st.code(f"Timestamp: {datetime.now()}\nEvent: {s.switching_event}\nGrid Interaction: {s.grid_export_kw:.2f} kW Export")

# =============================================================================
# AUTO-REFRESH
# =============================================================================
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=refresh * 1000, key="main_refresh")
