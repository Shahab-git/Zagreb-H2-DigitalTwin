# main.py - PROJECT LUMINIH2: Elite Digital Twin Dashboard
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- 1. CORE ENGINE IMPORTS ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 2. ELITE UI STYLING ---
st.set_page_config(page_title="LUMINIH2 | Elite Control", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f8fafc; }
    
    /* Global Container */
    .main-frame { background: white; border-radius: 24px; padding: 30px; border: 1px solid #e2e8f0; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.05); }
    
    /* Header Styling */
    .top-nav { background: #0f172a; color: white; padding: 20px 40px; border-radius: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
    .status-pulse { height: 12px; width: 12px; background-color: #22c55e; border-radius: 50%; display: inline-block; margin-right: 8px; box-shadow: 0 0 8px #22c55e; }
    
    /* Metric Cards */
    .custom-card { background: #ffffff; border: 1px solid #f1f5f9; border-radius: 20px; padding: 20px; transition: all 0.3s ease; }
    .custom-card:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & TELEMETRY ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.25,
        'history': pd.DataFrame(columns=['Time', 'Renewable', 'Grid_In', 'EV_Load', 'Profit']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# Logical Execution (Layer 1 -> 2 -> 3)
w = st.session_state.weather_engine.fetch_current_data() 
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)
source, p_re = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)

p_grid_in = 12.0 if p_re < 6.0 else 0.0
p_total = p_re + p_grid_in

# Battery Priority
p_to_batt = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_batt = min(p_total, 8.0)
    st.session_state.bess_soc += 0.009
    p_total -= p_to_batt

# H2 Chain
h2_gen = p_total * 0.024
st.session_state.buffer += h2_gen
comp_active = False
if st.session_state.buffer > 2.0:
    comp_active = True
    st.session_state.buffer -= 1.2
    st.session_state.main_tank += 1.1

# Distribution Hub
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0: # Priority 1: H2 Filling
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + 0.3)
        st.session_state.main_tank -= 0.3
    else: # Priority 2: EV Charging Hub
        fc_pwr = 22.0
        st.session_state.main_tank -= 0.2
        ev_load = 14.0 
        grid_sale = fc_pwr - ev_load # Priority 3: Sale

# Data Logging
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Renewable': p_re, 'Grid_In': p_grid_in, 'EV_Load': ev_load, 'Profit': grid_sale * 0.28}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-20:]

# --- 4. ADVANCED DASHBOARD LAYOUT ---

# TOP NAVIGATION BAR
st.markdown(f"""
<div class="top-nav">
    <div>
        <span style="font-size: 24px; font-weight: 800; letter-spacing: -1px;">LUMINIH2 COMMAND</span>
        <div style="font-size: 14px; opacity: 0.7;">Zagreb Strategic Hub | Operational Twin</div>
    </div>
    <div style="text-align: right;">
        <span class="status-pulse"></span> <span style="font-weight: 700;">LIVE TELEMETRY</span>
        <div style="font-size: 14px; opacity: 0.7;">{now_zagreb.strftime('%Y-%m-%d | %H:%M:%S')}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# TOP ROW: THE SOURCE & STORAGE
c1, c2, c3 = st.columns(3)
with c1:
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.subheader("⚡ Energy Acquisition")
        m1, m2 = st.columns(2)
        m1.metric("RE Power", f"{p_re:.1f} kW", f"{source}")
        m2.metric("Grid Intake", f"{p_grid_in:.1f} kW", "Backup")
        fig_p = go.Figure(data=[go.Pie(labels=['Solar', 'Wind', 'Grid'], values=[p_pv, p_wind, p_grid_in], hole=.7, marker_colors=['#fbbf24', '#0ea5e9', '#94a3b8'])])
        fig_p.update_layout(height=180, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        st.plotly_chart(fig_p, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.subheader("🔋 BESS Optimization")
    st.write(f"Battery SoC: {st.session_state.bess_soc*100:.1f}%")
    st.progress(st.session_state.bess_soc)
    st.metric("Charging Priority", "Active", f"{p_to_batt:.1f} kW")
    st.write("---")
    st.subheader("💨 H2 Production")
    st.metric("Main Tank Level", f"{st.session_state.main_tank:.2f} kg")
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.subheader("📈 Performance & Exergy")
    st.metric("Hourly Profit", f"${grid_sale * 0.28:.2f}", f"{grid_sale:.1f} kW Sold")
    st.metric("CO2 Avoided", "3.4 kg/hr")
    st.metric("Efficiency Index", "84.2%", "Combined")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# MIDDLE ROW: MOBILITY HUB (H2 STATION vs EV HUB)
st.markdown("### 🗺️ Integrated Mobility & Distribution Hub")
mid1, mid2 = st.columns(2)
with mid1:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.write("**Hydrogen Refueling Station (Priority 1)**")
    fig_h2 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.h2_station, title={'text': "Refuel Capacity (5kg Max)"}, gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#10b981"}}))
    fig_h2.update_layout(height=250, margin=dict(t=50, b=20))
    st.plotly_chart(fig_h2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with mid2:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    st.write("**EV Charging Infrastructure (Priority 2)**")
    fig_ev = go.Figure(go.Indicator(mode="gauge+number", value=ev_load, title={'text': "Hub Supply (kW)"}, gauge={'axis': {'range': [0, 25]}, 'bar': {'color': "#0284c7"}}))
    fig_ev.update_layout(height=250, margin=dict(t=50, b=20))
    st.plotly_chart(fig_ev, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# BOTTOM ROW: ANALYTICS
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="custom-card">', unsafe_allow_html=True)
st.subheader("🔗 Multi-Layer System Flow (Sankey)")
fig_s = go.Figure(go.Sankey(
    node=dict(label=["Atmosphere", "BESS", "Electrolyzer", "Buffer", "Main Tank", "H2 Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#0f172a"),
    link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_batt+2, p_total+2, 25, 20, 12, 10, ev_load+2, grid_sale+2], color="rgba(2, 132, 199, 0.4)")
))
fig_s.update_layout(height=400, margin=dict(t=20, b=20, l=10, r=10))
st.plotly_chart(fig_s, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# LOOP
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
