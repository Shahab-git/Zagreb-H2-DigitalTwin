# main.py - PROJECT LUMINIH2: Integrated Digital Twin
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- 1. CORE MODULES INTEGRATION ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 2. EXECUTIVE UI SETTINGS ---
st.set_page_config(page_title="LUMINIH2 | Digital Twin", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    div[data-testid="stMetricValue"] { color: #0284c7 !important; font-size: 32px; font-weight: 800; }
    .stMetric { background-color: #ffffff; border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px rgb(0 0 0 / 0.05); border: 1px solid #e2e8f0; }
    .layer-card { 
        background: #ffffff; border-left: 6px solid #0ea5e9; padding: 15px 20px; border-radius: 12px; 
        margin: 25px 0 10px 0; box-shadow: 0 2px 4px rgb(0 0 0 / 0.05); color: #0f172a; font-weight: 700;
    }
    .status-tag { background-color: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE FOR SYSTEM TELEMETRY ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.1,
        'history': pd.DataFrame(columns=['Time', 'Renewable', 'Grid_In', 'EV_Load', 'Grid_Sale']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 4. THE FOUR-LAYER LOGIC ENGINE ---

# --- LAYER 1: Acquisition & Switching ---
w = st.session_state.weather_engine.fetch_current_data() 
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

# Power Switching Logic (RE vs Grid)
source, p_re = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)
p_grid_in = 0.0
if p_re < 5.0: # If wind/solar are insufficient
    p_grid_in = 10.0 # Standard Grid Compensation
p_total_pool = p_re + p_grid_in

# --- LAYER 2: Battery & Hydrogen Chain ---
# 1. Priority: BESS Charging
p_to_batt = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_batt = min(p_total_pool, 6.0)
    st.session_state.bess_soc += 0.008
    p_total_pool -= p_to_batt

# 2. Priority: Electrolyzer (RE or Grid derived)
h2_gen = p_total_pool * 0.022
st.session_state.buffer += h2_gen

# 3. Buffer -> Compressor -> Main Tank
comp_active = False
if st.session_state.buffer > 2.5:
    comp_active = True
    st.session_state.buffer -= 1.5
    st.session_state.main_tank += 1.4

# --- LAYER 3: Distribution & EV Charging ---
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    # 1. Fill 5kg H2 Station first
    if st.session_state.h2_station < 5.0:
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + 0.3)
        st.session_state.main_tank -= 0.3
    # 2. Fuel Cell -> EV Charging Hub
    else:
        fc_pwr = 15.0
        st.session_state.main_tank -= 0.2
        ev_load = 10.0 # Hub Demand
        # 3. Surplus Sale to Grid
        grid_sale = max(0.0, fc_pwr - ev_load)

# Update Telemetry History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Renewable': p_re, 'Grid_In': p_grid_in, 'EV_Load': ev_load, 'Grid_Sale': grid_sale}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-15:]

# --- 5. DASHBOARD VISUALIZATION ---

st.title("⚡ LUMINIH2 | Advanced Digital Twin")
st.markdown(f"**Location:** Zagreb, HR | **Last Sync:** {now_zagreb.strftime('%H:%M:%S')} | <span class='status-tag'>SYSTEM OPERATIONAL</span>", unsafe_allow_html=True)

# LAYER 1: INPUTS
st.markdown('<div class="layer-card">LAYER 1: ATMOSPHERIC DATA & SOURCE SWITCHING</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1, 2])
with l1_c1:
    st.metric("Solar Radiation", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Grid Intake", f"{p_grid_in:.1f} kW", delta="Stabilizing" if p_grid_in > 0 else None)
with l1_c2:
    fig_mix = go.Figure(data=[go.Pie(labels=['Solar', 'Wind', 'Grid'], values=[p_pv, p_wind, p_grid_in], hole=.7, marker_colors=['#fca311', '#0ea5e9', '#94a3b8'])])
    fig_mix.update_layout(showlegend=False, height=180, margin=dict(t=0, b=0))
    st.plotly_chart(fig_mix, use_container_width=True)
with l1_c3:
    fig_h1 = px.area(st.session_state.history, x='Time', y=['Renewable', 'Grid_In'], color_discrete_map={'Renewable': '#0ea5e9', 'Grid_In': '#cbd5e1'}, template='plotly_white')
    fig_h1.update_layout(height=200, margin=dict(t=0, b=0))
    st.plotly_chart(fig_h1, use_container_width=True)

# LAYER 2: PRODUCTION
st.markdown('<div class="layer-card">LAYER 2: BESS BUFFERING & H2 PRODUCTION CHAIN</div>', unsafe_allow_html=True)
l2_c1, l2_c2, l2_c3 = st.columns(3)
with l2_c1:
    st.write("**BESS Status (Priority 1)**")
    st.progress(st.session_state.bess_soc)
    st.metric("Battery Level", f"{st.session_state.bess_soc*100:.1f}%")
with l2_c2:
    st.write("**Buffer & Compression**")
    st.progress(min(st.session_state.buffer/5, 1.0))
    st.caption(f"Compressor: {'🟢 ACTIVE' if comp_active else '⚪ STANDBY'}")
with l2_c3:
    st.metric("Main Storage Tank", f"{st.session_state.main_tank:.2f} kg", "High Pressure")

# LAYER 3: DISTRIBUTION
st.markdown('<div class="layer-card">LAYER 3: H2 REFUELING & EV CHARGING HUB</div>', unsafe_allow_html=True)
l3_c1, l3_c2, l3_c3 = st.columns(3)
with l3_c1:
    fig_g = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.h2_station, title={'text': "H2 Station (5kg Cap)"}, gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#22c55e"}}))
    fig_g.update_layout(height=180, margin=dict(t=30, b=0))
    st.plotly_chart(fig_g, use_container_width=True)
with l3_c2:
    st.metric("Fuel Cell Power", f"{fc_pwr:.1f} kW")
    st.metric("EV Charging Load", f"{ev_load:.1f} kW", "Priority Flow")
with l3_c3:
    st.metric("Grid Sale Revenue", f"${grid_sale * 0.22:.2f}/hr", f"{grid_sale:.1f} kW Export")
    st.info(f"Main Feed: {source}")

# LAYER 4: ANALYTICS
st.markdown('<div class="layer-card">LAYER 4: FULL SYSTEM EXERGY & FLOW ANALYSIS</div>', unsafe_allow_html=True)
l4_c1, l4_c2 = st.columns([2, 1])
with l4_c1:
    # Full Process Sankey
    fig_s = go.Figure(go.Sankey(
        node=dict(label=["Input", "BESS", "Electrolyzer", "Buffer", "Main Tank", "H2 Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#0284c7"),
        link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_batt+1, p_total_pool+1, 20, 18, 10, 8, ev_load+1, grid_sale+1])
    ))
    fig_s.update_layout(height=350, margin=dict(t=20, b=20))
    st.plotly_chart(fig_s, use_container_width=True)
with l4_c2:
    st.metric("Exergy Efficiency", "83.1%")
    st.metric("Carbon Offset", "3.2 kg/hr")
    st.write("**Operational Intelligence**")
    st.info("System is optimizing for H2 Station priority.")

# AUTO-REFRESH
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
