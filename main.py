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
st.set_page_config(page_title="LUMINIH2 | Global Hub", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    div[data-testid="stMetricValue"] { color: #0284c7 !important; font-size: 32px; font-weight: 800; }
    .stMetric { background-color: #ffffff; border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px rgb(0 0 0 / 0.05); border: 1px solid #e2e8f0; }
    .layer-card { 
        background: #ffffff; border-left: 6px solid #0ea5e9; padding: 15px 20px; border-radius: 12px; 
        margin: 25px 0 10px 0; box-shadow: 0 2px 4px rgb(0 0 0 / 0.05); color: #0f172a; font-weight: 700;
    }
    .status-tag { background-color: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: 700; }
    .header-box { background: white; padding: 20px; border-radius: 16px; box-shadow: 0 4px 6px rgb(0 0 0 / 0.05); margin-bottom: 20px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.2,
        'history': pd.DataFrame(columns=['Time', 'RE_Power', 'Grid_In', 'EV_Load', 'Grid_Sale']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 4. THE FOUR-LAYER LOGIC ENGINE ---

# LAYER 1: Acquisition & Switching
w = st.session_state.weather_engine.fetch_current_data() 
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

source, p_re = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)
p_grid_in = 10.0 if p_re < 5.0 else 0.0 
p_total_pool = p_re + p_grid_in

# LAYER 2: Battery & Hydrogen Chain
p_to_batt = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_batt = min(p_total_pool, 6.0)
    st.session_state.bess_soc += 0.008
    p_total_pool -= p_to_batt

h2_gen = p_total_pool * 0.022
st.session_state.buffer += h2_gen

comp_active = False
if st.session_state.buffer > 2.5:
    comp_active = True
    st.session_state.buffer -= 1.5
    st.session_state.main_tank += 1.4

# LAYER 3: Distribution (H2 Station & EV Hub)
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0:
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + 0.3)
        st.session_state.main_tank -= 0.3
    else:
        fc_pwr = 18.0
        st.session_state.main_tank -= 0.2
        ev_load = 12.0 # EV Hub Supply
        grid_sale = max(0.0, fc_pwr - ev_load)

# Update History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Renewable': p_re, 'Grid_In': p_grid_in, 'EV_Load': ev_load, 'Grid_Sale': grid_sale}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-15:]

# --- 5. DASHBOARD RENDER ---

# HEADER
st.markdown(f"""
<div class="header-box">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin:0; color:#0f172a;">🌐 LUMINIH2 Global Command</h1>
            <p style="margin:0; color:#64748b;">Zagreb Hub | System Time: {now_zagreb.strftime('%H:%M:%S')}</p>
        </div>
        <div class="status-tag">● SYSTEM ONLINE</div>
    </div>
</div>
""", unsafe_allow_html=True)

# LAYER 1
st.markdown('<div class="layer-card">⚡ LAYER 1: ENERGY ACQUISITION & MIX</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1, 2])
with l1_c1:
    st.metric("Solar Radiation", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s")
with l1_c2:
    fig_src = go.Figure(data=[go.Pie(labels=['RE Power', 'Grid In'], values=[p_re, p_grid_in], hole=.7, marker_colors=['#0ea5e9', '#cbd5e1'])])
    fig_src.update_layout(showlegend=False, height=180, margin=dict(t=0, b=0))
    st.plotly_chart(fig_src, use_container_width=True)
with l1_c3:
    fig_h1 = px.area(st.session_state.history, x='Time', y=['Renewable', 'Grid_In'], color_discrete_map={'Renewable': '#0ea5e9', 'Grid_In': '#cbd5e1'}, template='plotly_white')
    fig_h1.update_layout(height=200, margin=dict(t=0, b=0))
    st.plotly_chart(fig_h1, use_container_width=True)

# LAYER 2 & 3
st.markdown('<div class="layer-card">🛡️ LAYER 2 & 3: PRODUCTION & LOGISTICS</div>', unsafe_allow_html=True)
col_prod, col_dist = st.columns(2)
with col_prod:
    st.subheader("Hydrogen Production")
    st.write("Battery Charge (BESS)")
    st.progress(st.session_state.bess_soc)
    m1, m2 = st.columns(2)
    m1.metric("Storage Tank", f"{st.session_state.main_tank:.2f} kg")
    m2.metric("Compressor", "Active" if comp_active else "Standby")

with col_dist:
    st.subheader("Mobility & Grid (EV Hub)")
    d1, d2 = st.columns(2)
    # H2 Station Indicator
    with d1:
        fig_h2 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.h2_station, title={'text': "H2 Station (kg)"}, gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#22c55e"}}))
        fig_h2.update_layout(height=180, margin=dict(t=40, b=0))
        st.plotly_chart(fig_h2, use_container_width=True)
    # EV Charging Hub Indicator (FIXED)
    with d2:
        fig_ev = go.Figure(go.Indicator(mode="gauge+number", value=ev_load, title={'text': "EV Charging (kW)"}, gauge={'axis': {'range': [0, 20]}, 'bar': {'color': "#0284c7"}}))
        fig_ev.update_layout(height=180, margin=dict(t=40, b=0))
        st.plotly_chart(fig_ev, use_container_width=True)

# LAYER 4
st.markdown('<div class="layer-card">📈 LAYER 4: SYSTEM EXERGY & FLOW ANALYTICS</div>', unsafe_allow_html=True)
l4_c1, l4_c2 = st.columns([2, 1])
with l4_c1:
    fig_s = go.Figure(go.Sankey(
        node=dict(label=["Power", "BESS", "Electrolyzer", "Buffer", "Main Tank", "H2 Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#0284c7"),
        link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_batt+1, p_total_pool+1, 20, 18, 10, 8, ev_load+1, grid_sale+1])
    ))
    fig_s.update_layout(height=350, margin=dict(t=20, b=20))
    st.plotly_chart(fig_s, use_container_width=True)
with l4_c2:
    st.metric("Thermal Recovery", "5.2 kWt")
    st.metric("Revenue Stream", f"${grid_sale * 0.22:.2f}/hr")
    st.info("Efficiency Profile: Combined Cycle 82.1%")
    st.success("CO2 Saved: 2.4 kg/hr")

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
