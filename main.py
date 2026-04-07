# main.py - THE ULTIMATE INTEGRATED DIGITAL TWIN (Full Engineering Suite)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz
import numpy as np

# --- 1. CORE ENGINEERING IMPORTS (Your Custom Modules) ---
try:
    from config import Config
    from weather_api import WeatherProvider
    from energy_assets import SolarSystem, WindSystem
    from ems_brain import EMSBrain
except ImportError:
    st.error("Error: Custom modules (config, weather_api, etc.) not found. Ensure they are in the same directory.")

# --- 2. ELITE COMMAND CENTER STYLING ---
st.set_page_config(page_title="LUMINIH2 | INTEGRATED COMMAND", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@300;500;700&display=swap');
    .stApp { background-color: #0d1117; color: #c9d1d9; font-family: 'Inter', sans-serif; }
    
    /* Global Card Architecture */
    .op-card { 
        background: #161b22; border: 1px solid #30363d; border-radius: 16px; 
        padding: 20px; transition: 0.4s ease; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .op-card:hover { border-color: #58a6ff; box-shadow: 0 0 15px rgba(88, 166, 255, 0.2); }
    
    /* Professional Headers */
    .main-header { 
        background: linear-gradient(90deg, #0d1117 0%, #161b22 100%); 
        padding: 25px; border-radius: 15px; border-left: 6px solid #58a6ff; 
        margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center;
    }
    .tech-label { font-family: 'Orbitron', sans-serif; color: #58a6ff; font-size: 0.85rem; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. TELEMETRY & LOGIC ENGINE ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.25,
        'history': pd.DataFrame(columns=['Time', 'Power_RE', 'H2_Level', 'EV_Demand', 'Profit']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

# Time Control (Zagreb)
now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# LAYER 1 & 2: Acquisition & Production Logic
w = st.session_state.weather_engine.fetch_current_data() 
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)
p_re_total = p_pv + p_wind

# EMS Brain Strategy
source_mode, _ = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)
p_grid_in = 12.0 if p_re_total < 8.0 else 0.0
p_available = p_re_total + p_grid_in

# Battery Priority (Charging first for stability)
p_to_bess = 0.0
if st.session_state.bess_soc < 0.98:
    p_to_bess = min(p_available, 10.0)
    st.session_state.bess_soc += 0.008
    p_available -= p_to_bess

# Hydrogen Production Logic
h2_gen = p_available * 0.024
st.session_state.buffer += h2_gen
if st.session_state.buffer > 1.8:
    st.session_state.buffer -= 1.0
    st.session_state.main_tank += 0.95

# LAYER 3: Distribution (H2 Station -> EV Hub -> Grid)
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0: # Priority 1: H2 Station (5kg)
        refill = 0.35
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + refill)
        st.session_state.main_tank -= refill
    else: # Priority 2: EV Charging via Fuel Cell
        fc_pwr = 22.0
        st.session_state.main_tank -= 0.2
        ev_load = 14.5 
        grid_sale = fc_pwr - ev_load # Priority 3: Selling surplus

# Log History
new_log = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Power_RE': p_re_total, 
           'H2_Level': st.session_state.main_tank, 'EV_Demand': ev_load, 'Profit': grid_sale * 0.32}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_log])], ignore_index=True).iloc[-20:]

# --- 4. ULTIMATE UI RENDER ---

# TOP HEADER
st.markdown(f"""
<div class="main-header">
    <div>
        <h1 style="margin:0; font-family:'Orbitron'; color:#58a6ff;">LUMINIH2 COMMAND CENTER</h1>
        <p style="margin:0; opacity:0.7; font-weight:300;">Strategic Hydrogen Integration | Zagreb Hub</p>
    </div>
    <div style="text-align: right;">
        <div style="font-size:22px; font-weight:800;">{now_zagreb.strftime('%H:%M:%S')}</div>
        <div style="color:#3fb950; font-size:0.9rem;">● TELEMETRY: ACTIVE</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ROW 1: ACQUISITION & STORAGE (Layer 1 & 2)
st.markdown('<p class="tech-label">Section 01: Resource Acquisition & Energy Storage</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.caption("Zagreb Atmosphere")
    st.metric("Solar Radiation", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s")
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.caption("Energy Mix")
    fig_mix = go.Figure(data=[go.Pie(labels=['Solar', 'Wind', 'Grid'], values=[p_pv, p_wind, p_grid_in], hole=.7, 
                                     marker_colors=['#f97316', '#0ea5e9', '#4b5563'])])
    fig_mix.update_layout(height=180, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_mix, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.caption("BESS Capacity")
    st.title(f"{st.session_state.bess_soc*100:.1f}%")
    st.progress(st.session_state.bess_soc)
    st.write(f"Inflow: {p_to_bess:.1f} kW")
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.caption("H2 Production Chain")
    st.metric("Buffer Tank", f"{st.session_state.buffer:.2f} kg")
    st.metric("Main Storage", f"{st.session_state.main_tank:.2f} kg")
    st.markdown('</div>', unsafe_allow_html=True)

# ROW 2: DISTRIBUTION & ANALYTICS (Layer 3 & 4)
st.markdown('<br><p class="tech-label">Section 02: Distribution Hub & Exergy Analytics</p>', unsafe_allow_html=True)
left_panel, right_panel = st.columns([2, 1])

with left_panel:
    st.markdown('<div class="op-card">', unsafe_allow_html=True)
    st.write("**Integrated Energy Flow (Sankey)**")
    fig_s = go.Figure(go.Sankey(
        node=dict(label=["Zagreb RE", "BESS", "Electrolyzer", "H2 Main Tank", "H2 Station", "Fuel Cell Hub", "EV Charging", "Grid Sale"], 
                  color="#58a6ff", pad=15, thickness=20),
        link=dict(source=[0, 0, 2, 3, 3, 5, 5], target=[1, 2, 3, 4, 5, 6, 7], 
                  value=[12, 20, 18, 10, 8, ev_load, grid_sale], color="rgba(88, 166, 255, 0.2)")
    ))
    fig_s.update_layout(height=400, paper_bgcolor='rgba(0,0,0,0)', font_color="#c9d1d9", margin=dict(t=20, b=20, l=10, r=10))
    st.plotly_chart(fig_s, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right_panel:
    st.markdown('<div class="op-card" style="height:445px;">', unsafe_allow_html=True)
    st.write("**Operational KPIs**")
    st.metric("H2 Station Fill", f"{st.session_state.h2_station:.1f} / 5 kg", delta="Priority 1")
    st.metric("EV Hub Supply", f"{ev_load:.1f} kW", delta="Priority 2")
    st.metric("Hourly Profit", f"${grid_sale * 0.32:.2f}", delta=f"{grid_sale:.1f} kW Sold")
    st.write("---")
    st.info(f"Strategy: {source_mode} Optimized")
    st.success(f"CO2 Avoided: {p_re_total * 0.4:.1f} kg/hr")
    st.markdown('</div>', unsafe_allow_html=True)

# AUTO-REFRESH (LUMIN-SYNC)
time.sleep(Config.TIMESTEP_SEC if 'Config' in locals() else 2)
st.rerun()
