# main.py - PROJECT LUMINIH2: Integrated Green Energy Hub
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- 1. CRITICAL: IMPORTING YOUR CORE MODULES ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 2. SETTINGS & WORLD-CLASS LIGHT THEME ---
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
    .status-tag { background-color: #dcfce7; color: #166534; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE MANAGEMENT ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.1,
        'history': pd.DataFrame(columns=['Time', 'RE_Power', 'Grid_In', 'Electric_Hub_Load', 'Grid_Sale']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 4. DATA ACQUISITION & MULTI-LAYER LOGIC ---

# Layer 1: Atmospheric Inputs & Switching
w = st.session_state.weather_engine.fetch_current_data()
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

# EMS Decision: RE source choice
source, p_re = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)

# Grid Backup Switching
p_grid_in = 0.0
if p_re < 5.0: # If RE is insufficient
    p_grid_in = 12.0
p_total_input = p_re + p_grid_in

# Layer 2: Battery -> Electrolyzer -> Buffer -> Compressor
# 1. BESS Priority (Charge battery first)
p_to_batt = 0.0
if st.session_state.bess_soc < 0.98:
    p_to_batt = min(p_total_input, 7.0)
    st.session_state.bess_soc += 0.008
    p_total_input -= p_to_batt

# 2. Production Stage
h2_gen = p_total_input * 0.022
st.session_state.buffer += h2_gen

# 3. Buffer -> Compressor Logic
comp_active = False
if st.session_state.buffer > 2.0:
    comp_active = True
    st.session_state.buffer -= 1.2
    st.session_state.main_tank += 1.1

# Layer 3: H2 Station -> Fuel Cell -> Electric Hub -> Grid Sale
fc_pwr, hub_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0: # Priority 1: 5kg Station
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + 0.2)
        st.session_state.main_tank -= 0.2
    else: # Priority 2: Fuel Cell Start
        fc_pwr = 15.0
        st.session_state.main_tank -= 0.15
        # Priority 3: Electric Hub (Tools/Battery Devices)
        hub_load = 9.0 
        # Priority 4: Selling Excess
        grid_sale = max(0.0, fc_pwr - hub_load)

# Record History
new_row = {
    'Time': now_zagreb.strftime('%H:%M:%S'), 'RE_Power': p_re, 
    'Grid_In': p_grid_in, 'Electric_Hub_Load': hub_load, 'Grid_Sale': grid_sale
}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-15:]

# --- 5. DASHBOARD RENDER ---

st.title("🌐 LUMINIH2 | Global Strategic Energy Hub")
st.markdown(f"**Location:** Zagreb, HR | **Live Telemetry:** {now_zagreb.strftime('%H:%M:%S')} | <span class='status-tag'>SYSTEM NOMINAL</span>", unsafe_allow_html=True)

# LAYER 1: SOURCE
st.markdown('<div class="layer-card">LAYER 1: ATMOSPHERIC INPUTS & DYNAMIC SOURCE SWITCHING</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1, 2])
with l1_c1:
    st.metric("Solar Radiation", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Grid Intake", f"{p_grid_in:.1f} kW", "Stabilization Active" if p_grid_in > 0 else None)
with l1_c2:
    fig_src = go.Figure(data=[go.Pie(labels=['RE Power', 'Grid In'], values=[p_re, p_grid_in], hole=.7, marker_colors=['#0ea5e9', '#cbd5e1'])])
    fig_src.update_layout(showlegend=False, height=180, margin=dict(t=0, b=0))
    st.plotly_chart(fig_src, use_container_width=True)
with l1_c3:
    fig_h1 = px.area(st.session_state.history, x='Time', y=['RE_Power', 'Grid_In'], color_discrete_map={'RE_Power': '#0ea5e9', 'Grid_In': '#cbd5e1'}, template='plotly_white')
    fig_h1.update_layout(height=200, margin=dict(t=0, b=0))
    st.plotly_chart(fig_h1, use_container_width=True)

# LAYER 2: PRODUCTION
st.markdown('<div class="layer-card">LAYER 2: BESS CHARGING & HYDROGEN PRODUCTION STAGE</div>', unsafe_allow_html=True)
l2_c1, l2_c2, l2_c3 = st.columns(3)
with l2_c1:
    st.write("**BESS Status (Primary Goal)**")
    st.progress(st.session_state.bess_soc)
    st.metric("Battery Charge", f"{st.session_state.bess_soc*100:.1f}%", f"{p_to_batt:.1f} kW Input")
with l2_c2:
    st.write("**H2 Buffer & Compression**")
    st.progress(min(st.session_state.buffer/5, 1.0))
    st.write(f"Compressor: {'🟢 ON' if comp_active else '⚪ READY'}")
with l2_c3:
    st.metric("Main Storage Tank", f"{st.session_state.main_tank:.2f} kg", "High Pressure")

# LAYER 3: DISTRIBUTION
st.markdown('<div class="layer-card">LAYER 3: REFUELING LOGISTICS, ELECTRIC HUB & GRID SALES</div>', unsafe_allow_html=True)
l3_c1, l3_c2, l3_c3 = st.columns(3)
with l3_c1:
    fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.h2_station, title={'text': "H2 Station (5kg Cap)"}, gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#22c55e"}}))
    fig_gauge.update_layout(height=180, margin=dict(t=30, b=0))
    st.plotly_chart(fig_gauge, use_container_width=True)
with l3_c2:
    st.metric("Fuel Cell Power", f"{fc_pwr:.1f} kW")
    st.metric("Electric Hub Load", f"{hub_load:.1f} kW", "Priority 1")
with l3_c3:
    st.metric("Grid Revenue", f"${grid_sale * 0.20:.2f}/hr", f"{grid_sale:.1f} kW Export")
    st.info(f"System Mode: {source}")

# LAYER 4: ANALYTICS
st.markdown('<div class="layer-card">LAYER 4: FULL SYSTEM EXERGY & THERMAL ANALYTICS</div>', unsafe_allow_html=True)
l4_c1, l4_c2, l4_c3 = st.columns([2, 1, 1])
with l4_c1:
    fig_s = go.Figure(go.Sankey(
        node=dict(label=["Power", "BESS", "Electrolyzer", "H2 Tank", "H2 Station", "Fuel Cell", "Electric Hub", "National Grid"], color="#0284c7"),
        link=dict(source=[0, 0, 2, 3, 3, 5, 5], target=[1, 2, 3, 4, 5, 6, 7], value=[p_to_batt+1, p_total_input+1, 20, 8, 12, hub_load+1, grid_sale+1])
    ))
    fig_s.update_layout(height=350, margin=dict(t=20, b=20))
    st.plotly_chart(fig_s, use_container_width=True)
with l4_c2:
    st.write("**Operational Exergy**")
    st.metric("Heat Recovery", "5.1 kWt", delta="Active")
    st.write("**Carbon Strategy**")
    st.metric("Avoided CO2", "3.4 kg/hr")
with l4_c3:
    st.metric("Efficiency Index", "83.5%")
    st.success("ROI Trend: Optimizing")

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
