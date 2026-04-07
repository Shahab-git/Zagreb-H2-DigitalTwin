# main.py - PROJECT LUMINIH2: Strategic Command Center
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- 1. CORE ENGINE INTEGRATION ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 2. ELITE DASHBOARD STYLING ---
st.set_page_config(page_title="LUMINIH2 | Global Command", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@300;500;700&display=swap');
    
    .stApp { background-color: #0f172a; color: #f8fafc; }
    
    /* Global Card Style */
    .operation-card { 
        background: #1e293b; border: 1px solid #334155; border-radius: 20px; 
        padding: 24px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    
    /* Metrics Styling */
    div[data-testid="stMetricValue"] { color: #38bdf8 !important; font-family: 'Orbitron', sans-serif; font-size: 28px; }
    div[data-testid="stMetricDelta"] { color: #10b981 !important; }
    
    .status-header {
        background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
        padding: 20px 40px; border-bottom: 2px solid #38bdf8; margin-bottom: 30px;
        display: flex; justify-content: space-between; align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & TELEMETRY ENGINE ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.3,
        'history': pd.DataFrame(columns=['Time', 'Power', 'H2_Level', 'Revenue']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# Logical Execution
w = st.session_state.weather_engine.fetch_current_data() 
p_solar = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)
p_re = p_solar + p_wind

source_mode, _ = st.session_state.ems_brain.decide_energy_source(p_solar, p_wind, 0.6)
p_grid_in = 15.0 if p_re < 10.0 else 0.0
p_total = p_re + p_grid_in

# BESS Logic
p_to_bess = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_bess = min(p_total, 10.0)
    st.session_state.bess_soc += 0.009
    p_total -= p_to_bess

# H2 Production Logic
h2_gen = p_total * 0.025
st.session_state.buffer += h2_gen
if st.session_state.buffer > 2.0:
    st.session_state.buffer -= 1.2
    st.session_state.main_tank += 1.1

# Distribution Logic
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0:
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + 0.4)
        st.session_state.main_tank -= 0.4
    else:
        fc_pwr = 25.0
        st.session_state.main_tank -= 0.2
        ev_load = 18.0
        grid_sale = fc_pwr - ev_load

# Update History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Power': p_re, 'H2_Level': st.session_state.main_tank, 'Revenue': grid_sale * 0.3}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-20:]

# --- 4. COMMAND CENTER UI ---

# HEADER
st.markdown(f"""
<div class="status-header">
    <div>
        <h1 style="margin:0; font-family:'Orbitron'; color:#38bdf8;">LUMINIH2 COMMAND</h1>
        <p style="margin:0; opacity:0.7;">Zagreb Strategic Operations Hub</p>
    </div>
    <div style="text-align:right;">
        <div style="font-size:20px; font-weight:bold;">{now_zagreb.strftime('%H:%M:%S')}</div>
        <div style="color:#10b981;">● SYSTEM: STABLE</div>
    </div>
</div>
""", unsafe_allow_html=True)

# TOP ROW: THE POWER GRID & ENVIRONMENT
col_weather, col_mix, col_bess = st.columns([1, 1, 1.2])

with col_weather:
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("🌐 Atmosphere")
    st.metric("Solar Irradiance", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s")
    st.caption(f"Location: 45.8N, 15.9E")
    st.markdown('</div>', unsafe_allow_html=True)

with col_mix:
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("⚡ Energy Mix")
    fig_mix = go.Figure(data=[go.Pie(labels=['Solar', 'Wind', 'Grid'], values=[p_solar, p_wind, p_grid_in], hole=.7, marker_colors=['#fbbf24', '#38bdf8', '#64748b'])])
    fig_mix.update_layout(height=180, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_mix, use_container_width=True)
    st.caption(f"Primary Source: {source_mode}")
    st.markdown('</div>', unsafe_allow_html=True)

with col_bess:
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("🔋 BESS Storage")
    st.metric("Battery State", f"{st.session_state.bess_soc*100:.1f}%", f"{p_to_bess:.1f} kW Intake")
    st.progress(st.session_state.bess_soc)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# MIDDLE ROW: HYDROGEN & MOBILITY HUB
col_h2, col_ev = st.columns(2)

with col_h2:
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("💧 Hydrogen Logistics")
    m1, m2, m3 = st.columns(3)
    m1.metric("Buffer", f"{st.session_state.buffer:.2f} kg")
    m2.metric("Main Tank", f"{st.session_state.main_tank:.2f} kg")
    m3.metric("Station", f"{st.session_state.h2_station:.1f}/5kg")
    
    fig_h2 = px.area(st.session_state.history, x='Time', y='H2_Level', color_discrete_sequence=['#10b981'])
    fig_h2.update_layout(height=150, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_visible=False)
    st.plotly_chart(fig_h2, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_ev:
    st.markdown('<div class="operation-card">', unsafe_allow_html=True)
    st.subheader("🔌 Mobility Hub (EV)")
    st.metric("EV Charging Load", f"{ev_load:.1f} kW", "Priority Supply")
    st.metric("Grid Export Profit", f"${grid_sale * 0.3:.2f}/hr", f"{grid_sale:.1f} kW")
    
    fig_rev = px.bar(st.session_state.history, x='Time', y='Revenue', color_discrete_sequence=['#38bdf8'])
    fig_rev.update_layout(height=150, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_visible=False)
    st.plotly_chart(fig_rev, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# BOTTOM ROW: SYSTEM FLOW
st.markdown('<div class="operation-card">', unsafe_allow_html=True)
st.subheader("🔗 System Exergy Flow (Sankey)")
fig_s = go.Figure(go.Sankey(
    node=dict(label=["Atmosphere", "BESS", "Electrolyzer", "Buffer", "Main Tank", "H2 Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#38bdf8"),
    link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_bess+2, p_total+2, 25, 20, 12, 10, ev_load+2, grid_sale+2], color="rgba(56, 189, 248, 0.3)")
))
fig_s.update_layout(height=350, margin=dict(l=10, r=10, t=20, b=20), paper_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig_s, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# REFRESH
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
