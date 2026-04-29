# =============================================================================
# main.py — LUMINIH2 Digital Twin Dashboard v4.1
# Clean White Theme · Zagreb, Croatia · Full English
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone, timedelta
import numpy as np
import pytz

# وارد کردن ماژول‌های پروژه (مطمئن شوید این فایل‌ها در مسیر پروژه هستند)
from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider
from core_engine import TickEngine, LCOHAccumulator, AlertSystem, HistoryBuffer
from scenario_engine import ScenarioEngine, ScenarioParams
from subsystems import SubsystemManager
from optimizer import EconomicOptimizer

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
# CLEAN WHITE THEME CSS (Updated as per your request)
# =============================================================================
st.markdown("""
<style>
.stApp {background: #ffffff; color: #1f2328}
.block-container {padding: 1rem 2rem}
.lumi-header {background: #f6f8fa; border: 1px solid #d0d7de; border-left: 5px solid #00d4ff; border-radius: 10px; padding: 15px 25px; margin-bottom: 20px}
.kpi {background: #ffffff; border: 1px solid #d0d7de; border-radius: 10px; padding: 15px; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.05)}
.kpi-lbl {font-size: 12px; color: #656d76; text-transform: uppercase; font-weight: 600}
.kpi-val {font-size: 24px; font-weight: 700; margin: 5px 0}
.kpi-sub {font-size: 11px; color: #6e7781}
.kpi-green {color: #1a7f37} .kpi-amber {color: #9a6700} .kpi-red {color: #d1242f} .kpi-blue {color: #0969da} .kpi-cyan {color: #0599de}
.badge {display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600}
.badge-green {background: #dafbe1; color: #1a7f37; border: 1px solid #1a7f37}
.badge-cyan {background: #ddf4ff; color: #0969da; border: 1px solid #0969da}
.switch-log {background: #f6f8fa; border-left: 3px solid #00d4ff; padding: 10px; font-family: monospace; font-size: 13px; margin: 10px 0}
.sec-hdr {font-size: 14px; font-weight: 700; color: #1f2328; margin: 15px 0 10px; border-bottom: 2px solid #eaeef2; padding-bottom: 5px}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# VISUAL CONFIG
# =============================================================================
LIGHT_THEME = dict(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                  font_color="#1f2328", margin=dict(t=30, b=30, l=50, r=20))

C = dict(solar="#FFB347", wind="#0969da", bess="#1a7f37", elec="#8250df",
         h2="#0599de", fc="#cf222e", grid="#6e7781", ev="#2da44e")

def mk(**kw): return {**LIGHT_THEME, **kw}

# =============================================================================
# STARTUP & SESSION STATE
# =============================================================================
try:
    validate_config()
except AssertionError as e:
    st.error(f"Configuration error: {e}"); st.stop()

def _init():
    if "lumi_init" in st.session_state: return
    st.session_state.lumi_init = True
    
    # Assets Initialization
    st.session_state.solar = SolarSystem()
    st.session_state.wind = WindSystem()
    st.session_state.bess = BatteryBESS(initial_soc=0.55)
    
    # Engine & Analytics
    st.session_state.forecaster = AIPredictor()
    st.session_state.lcoh_acc = LCOHAccumulator()
    st.session_state.alerts = AlertSystem()
    st.session_state.history = HistoryBuffer(maxlen=120)
    st.session_state.subsystems = SubsystemManager()
    st.session_state.engine = TickEngine(
        Config, st.session_state.solar, st.session_state.wind,
        st.session_state.bess, st.session_state.forecaster
    )
    
    st.session_state.sim_running = True
    st.session_state.last_state = None

_init()

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.markdown("### ⚡ LUMINIH2 Control")
    st.session_state.sim_running = st.toggle("Live simulation", value=st.session_state.sim_running)
    refresh_rate = st.slider("Refresh (sec)", 2, 10, 4)
    
    st.divider()
    st.markdown("### 🌦 Weather Override")
    use_ov = st.checkbox("Manual override")
    ov = None
    if use_ov:
        ov = {
            "irradiance": st.slider("Irradiance W/m²", 0, 1000, 500),
            "wind_ms": st.slider("Wind speed m/s", 0.0, 25.0, 6.0),
            "temp_c": st.slider("Temperature °C", -10, 45, 22)
        }

    st.divider()
    ev_demand = st.slider("EV demand (kW)", 0.0, float(Config.EV_CHARGER_POWER_KW), 5.0)
    force_bess = st.checkbox("Force BESS charge from grid")

    if st.button("🔄 Reset System"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# =============================================================================
# PHYSICS TICK & DATA PREP
# =============================================================================
zagreb_tz = pytz.timezone("Europe/Zagreb")
now_dt = datetime.now(zagreb_tz)

if st.session_state.sim_running:
    # Run the simulation engine
    s = st.session_state.engine.run(
        override=ov, 
        ev_demand_kw=ev_demand, 
        force_bess_charge=force_bess
    )
    st.session_state.history.append(s)
    st.session_state.last_state = s

s = st.session_state.last_state
if s is None:
    st.info("Initializing simulation engine..."); st.stop()

hist = st.session_state.history.df

# =============================================================================
# MAIN DASHBOARD UI
# =============================================================================

# Header
st.markdown(f"""
<div class="lumi-header">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div>
        <span style="font-size:24px; font-weight:800; color:#0599de;">⚡ LUMINIH2</span>
        <span style="margin-left:15px; color:#656d76;">Digital Twin v4.1 • Zagreb Hub</span>
    </div>
    <div style="text-align:right;">
        <span style="font-size:20px; font-weight:700; font-family:monospace;">{now_dt.strftime('%H:%M:%S')}</span>
        <div style="margin-top:5px;">
            <span class="badge badge-cyan">● LIVE</span>
            <span class="badge badge-green">TICK #{s.tick}</span>
        </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# KPI Row
def render_kpi(col, lbl, val, sub, cls="kpi-cyan"):
    col.markdown(f'<div class="kpi"><p class="kpi-lbl">{lbl}</p><p class="kpi-val {cls}">{val}</p><p class="kpi-sub">{sub}</p></div>', unsafe_allow_html=True)

k = st.columns(5)
render_kpi(k[0], "Generation", f"{s.total_gen_kw:.1f} kW", f"Solar: {s.solar_kw:.1f} | Wind: {s.wind_kw:.1f}", "kpi-amber")
render_kpi(k[1], "BESS SoC", f"{s.bess_soc_pct:.1f}%", f"Temp: {s.bess_temp_c:.1f}°C", "kpi-green" if s.bess_soc_pct > 20 else "kpi-red")
render_kpi(k[2], "H₂ Production", f"{s.h2_kg_h*1000:.1f} g/h", f"Efficiency: {s.elec_eff_pct:.1f}%", "kpi-cyan")
render_kpi(k[3], "LCOH", f"€{s.lcoh:.2f}/kg", "Profitable" if s.is_profitable else "Optimizing", "kpi-blue")
render_kpi(k[4], "Revenue", f"€{s.cum_revenue_eur:.2f}", f"Daily CO₂: {s.cum_co2_kg:.1f}kg", "kpi-green")

st.markdown(f'<div class="switch-log"><b>System Status:</b> {s.switching_event}</div>', unsafe_allow_html=True)

# Tabs for detailed analysis
tabs = st.tabs(["🌍 Generation", "⚗️ Hydrogen", "🔋 Storage & Grid", "📊 History"])

with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">Current Power Mix</p>', unsafe_allow_html=True)
        fig_pie = go.Figure(go.Pie(
            values=[max(0.1, s.solar_kw), max(0.1, s.wind_kw), max(0.1, s.grid_import_kw)],
            labels=["Solar", "Wind", "Grid"],
            hole=0.7,
            marker=dict(colors=[C["solar"], C["wind"], C["grid"]])
        ))
        fig_pie.update_layout(**mk(height=300, showlegend=True))
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with c2:
        st.markdown('<p class="sec-hdr">Weather Conditions</p>', unsafe_allow_html=True)
        w1, w2 = st.columns(2)
        w1.metric("Irradiance", f"{s.wx_irradiance:.0f} W/m²")
        w2.metric("Wind Speed", f"{s.wx_wind_ms:.1f} m/s")
        if not hist.empty:
            fig_irr = px.line(hist, x="time", y="wx_irradiance", title="Irradiance Trend")
            fig_irr.update_layout(**mk(height=200))
            st.plotly_chart(fig_irr, use_container_width=True)

with tabs[3]:
    st.markdown('<p class="sec-hdr">System Parameter History</p>', unsafe_allow_html=True)
    if not hist.empty:
        st.line_chart(hist.set_index("time")[["solar_kw", "wind_kw", "elec_kw"]])

# Auto-refresh logic
if st.session_state.sim_running:
    import time
    time.sleep(refresh_rate)
    st.rerun()
