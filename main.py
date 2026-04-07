# main.py - PROJECT LUMINIH2: Integrated Green Energy Hub
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- CRITICAL: YOUR CORE MODULES ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 1. SETTINGS & WORLD-CLASS LIGHT THEME ---
st.set_page_config(page_title="LUMINIH2 | Command Center", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    div[data-testid="stMetricValue"] { color: #0284c7 !important; font-size: 32px; font-weight: 800; }
    .stMetric { background-color: #ffffff; border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px rgb(0 0 0 / 0.05); border: 1px solid #e2e8f0; }
    .layer-card { 
        background: #ffffff; border-left: 6px solid #0ea5e9; padding: 15px 20px; border-radius: 12px; 
        margin: 25px 0 10px 0; box-shadow: 0 2px 4px rgb(0 0 0 / 0.05); color: #0f172a; font-weight: 700;
    }
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #0ea5e9, #22c55e); }
    .status-tag { background-color: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE MANAGEMENT ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.2,
        'history': pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'Grid', 'EV_Load']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 3. DATA ACQUISITION & MULTI-LAYER LOGIC ---
w = st.session_state.weather_engine.fetch_current_data()
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

# LAYER 1: Power Switching (RE or Grid)
source, p_total = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)
p_grid_in = 0.0
if p_total < 5.0: # If RE is insufficient, draw from Grid
    p_grid_in = 10.0
    p_total += p_grid_in
    source = "Hybrid (RE + Grid)"

# LAYER 2: Battery -> Electrolyzer -> Buffer -> Compressor
# 1. Charge Battery First
p_to_batt = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_batt = min(p_total, 5.0)
    st.session_state.bess_soc += 0.01
    p_total -= p_to_batt

# 2. Production (Electrolyzer)
h2_gen = p_total * 0.022
st.session_state.buffer += h2_gen

# 3. Compression logic
comp_active = False
if st.session_state.buffer > 3.0:
    comp_active = True
    st.session_state.buffer -= 2.0
    st.session_state.main_tank += 1.8

# LAYER 3: H2 Station -> Fuel Cell -> EV Station -> Grid Sale
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0: # Priority 1: H2 Station (5kg)
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + 0.3)
        st.session_state.main_tank -= 0.3
    else: # Priority 2: Fuel Cell -> EV Charging
        fc_pwr = 12.0
        st.session_state.main_tank -= 0.2
        ev_load = 8.0 # Standard EV Load
        grid_sale = fc_pwr - ev_load # Priority 3: Sale surplus

# Update History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Solar': p_pv, 'Wind': p_wind, 'Grid': p_grid_in, 'EV_Load': ev_load}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-15:]

# --- 4. DASHBOARD RENDER ---

st.title("🌐 LUMINIH2 | Integrated Energy Control")
st.markdown(f"**Zagreb Hub** | {now_zagreb.strftime('%Y-%m-%d %H:%M:%S')} | <span class='status-tag'>ONLINE</span>", unsafe_allow_html=True)

# LAYER 1: THE SOURCE
st.markdown('<div class="layer-card">LAYER 1: SMART SOURCE ALLOCATION (RE & GRID SWITCHING)</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1, 2])
with l1_c1:
    st.metric("Solar/Wind Input", f"{p_pv+p_wind:.1f} kW")
    st.metric("Grid Intake", f"{p_grid_in:.1f} kW")
with l1_c2:
    fig_src = go.Figure(go.Pie(labels=['Solar', 'Wind', 'Grid'], values=[p_pv, p_wind, p_grid_in], hole=.6, marker_colors=['#fca311', '#0ea5e9', '#64748b']))
    fig_src.update_layout(height=200, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
    st.plotly_chart(fig_src, use_container_width=True)
with l1_c3:
    fig_hist = px.line(st.session_state.history, x='Time', y=['Solar', 'Wind', 'Grid'], color_discrete_sequence=['#fca311', '#0ea5e9', '#64748b'], template='plotly_white')
    fig_hist.update_layout(height=200, margin=dict(t=10, b=0))
    st.plotly_chart(fig_hist, use_container_width=True)

# LAYER 2: PRODUCTION
st.markdown('<div class="layer-card">LAYER 2: BESS STABILIZATION & H2 PRODUCTION CHAIN</div>', unsafe_allow_html=True)
l2_c1, l2_c2, l2_c3 = st.columns(3)
with l2_c1:
    st.write("Battery SOC (BESS Priority)")
    st.progress(st.session_state.bess_soc)
    st.caption(f"Buffer Charging: {p_to_batt:.1f} kW")
with l2_c2:
    st.write("H2 Buffer Tank")
    st.progress(min(st.session_state.buffer/10, 1.0))
    st.write(f"Compressor: {'🟢 RUNNING' if comp_active else '⚪ IDLE'}")
with l2_c3:
    st.metric("Main Storage Tank", f"{st.session_state.main_tank:.2f} kg", "To Distribution")

# LAYER 3: DISTRIBUTION
st.markdown('<div class="layer-card">LAYER 3: H2 REFUELING & EV MOBILITY HUB</div>', unsafe_allow_html=True)
l3_c1, l3_c2, l3_c3 = st.columns(3)
with l3_c1:
    st.write("H2 Station Tank (Cap: 5kg)")
    st.progress(st.session_state.h2_station / 5.0)
    st.metric("Refueling Level", f"{st.session_state.h2_station:.2f} kg")
with l3_c2:
    st.metric("Fuel Cell Generation", f"{fc_pwr:.1f} kW")
    st.metric("EV Charging Load", f"{ev_load:.1f} kW")
with l3_c3:
    st.metric("Grid Revenue (Sale)", f"${grid_sale * 0.18:.2f}/hr", f"{grid_sale:.1f} kW Export")
    st.info(f"System Mode: {source}")

# LAYER 4: ADVANCED ANALYTICS
st.markdown('<div class="layer-card">LAYER 4: SYSTEM EXERGY & EFFICIENCY ANALYTICS</div>', unsafe_allow_html=True)
l4_c1, l4_c2, l4_c3 = st.columns([2, 1, 1])
with l4_c1:
    # Sankey for Logic verification
    fig_s = go.Figure(go.Sankey(node=dict(label=["Input", "BESS", "Electrolyzer", "Buffer", "Main Tank", "Refuel Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#0284c7"),
        link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_batt+1, p_to_elec+1, 20, 18, 10, 8, ev_load+1, grid_sale+1])))
    fig_s.update_layout(height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig_s, use_container_width=True)
with l4_c2:
    # Heat Recovery Gauge
    fig_heat = go.Figure(go.Indicator(mode="gauge+number", value=thermal_recovery, title={'text': "Heat Recovery (kWt)"}, gauge={'bar':{'color':"#ef4444"}}))
    fig_heat.update_layout(height=250)
    st.plotly_chart(fig_heat, use_container_width=True)
with l4_c3:
    st.metric("Exergy Efficiency", "82.4%")
    st.metric("CO2 Avoidance", "2.8 kg/hr")
    st.success("ROI Trend: Positive")

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
