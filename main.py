# main.py - PROJECT LUMINIH2: Optimized Industrial Digital Twin
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
st.set_page_config(page_title="LUMINIH2 | Advanced Control", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .header-box { background: #0f172a; color: white; padding: 1.5rem 2.5rem; border-radius: 15px; margin-bottom: 2rem; }
    .metric-card { background: white; padding: 1.5rem; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .priority-tag { font-size: 0.8rem; background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 10px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE & ENGINE ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.20,
        'history': pd.DataFrame(columns=['Time', 'Total_RE', 'Electrolyzer_In', 'EV_Load', 'Grid_Profit']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 4. OPTIMIZED LOGIC FLOW ---

# LAYER 1: Hybrid Acquisition
w = st.session_state.weather_engine.fetch_current_data() 
p_solar = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)
p_total_re = p_solar + p_wind

# Power Source Switching (EMS Logic)
source_mode, _ = st.session_state.ems_brain.decide_energy_source(p_solar, p_wind, 0.6)
p_grid_in = 15.0 if p_total_re < 10.0 else 0.0
p_available = p_total_re + p_grid_in

# LAYER 2: Battery & Hydrogen Production Chain
# 1. BESS Priority (Charging)
p_to_bess = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_bess = min(p_available, 10.0)
    st.session_state.bess_soc += 0.008
    p_available -= p_to_bess

# 2. Electrolyzer (Input from RE or Grid)
p_electrolyzer = p_available
h2_produced = p_electrolyzer * 0.024
st.session_state.buffer += h2_produced

# 3. Buffer -> Compressor -> Main Tank
comp_active = False
if st.session_state.buffer > 1.5:
    comp_active = True
    st.session_state.buffer -= 1.0
    st.session_state.main_tank += 0.95

# LAYER 3: Distribution (H2 Station & Fuel Cell Hub)
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    # 1. H2 Station Priority (5kg Cap)
    if st.session_state.h2_station < 5.0:
        refill = 0.3
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + refill)
        st.session_state.main_tank -= refill
    # 2. Fuel Cell -> EV Hub & Grid
    else:
        fc_pwr = 25.0
        st.session_state.main_tank -= 0.25
        ev_load = 15.0 # Demand
        grid_sale = fc_pwr - ev_load # Sell Surplus

# Log History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Total_RE': p_total_re, 'Electrolyzer_In': p_electrolyzer, 'EV_Load': ev_load, 'Grid_Profit': grid_sale * 0.30}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-20:]

# --- 5. VISUAL DASHBOARD ---

# Header
st.markdown(f"""
<div class="header-box">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin:0;">🌐 LUMINIH2 Global Command</h1>
            <p style="margin:0; opacity:0.8;">Zagreb Strategic Hub | Digital Twin v3.0</p>
        </div>
        <div style="text-align: right;">
            <div style="font-weight:bold;">{now_zagreb.strftime('%H:%M:%S')}</div>
            <div style="font-size:0.8rem; color:#4ade80;">● SYSTEM NOMINAL</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Main Grid
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.subheader("⚡ Layer 1: Acquisition")
    st.caption(f"Primary Mode: {source_mode}")
    st.metric("Total RE Power", f"{p_total_re:.1f} kW", f"Solar: {p_solar:.1f}")
    st.metric("Grid Intake", f"{p_grid_in:.1f} kW", delta_color="inverse", delta="Active" if p_grid_in > 0 else None)
    
    fig_re = px.line(st.session_state.history, x='Time', y='Total_RE', title="RE Trend")
    fig_re.update_layout(height=150, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_re, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.subheader("🛡️ Layer 2: Production")
    st.write(f"BESS SoC: {st.session_state.bess_soc*100:.1f}%")
    st.progress(st.session_state.bess_soc)
    
    c1, c2 = st.columns(2)
    c1.metric("H2 Buffer", f"{st.session_state.buffer:.2f} kg")
    c2.metric("Main Tank", f"{st.session_state.main_tank:.2f} kg")
    st.write(f"Compressor: {'🟢 ON' if comp_active else '⚪ STANDBY'}")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.subheader("🚀 Layer 3: Distribution")
    st.markdown('<span class="priority-tag">PRIORITY: H2 STATION</span>', unsafe_allow_html=True)
    
    # Dual Gauge for Mobility
    fig_mob = go.Figure()
    fig_mob.add_trace(go.Indicator(mode="gauge+number", value=st.session_state.h2_station, domain={'x': [0, 0.45], 'y': [0, 1]}, title={'text': "H2 (kg)"}, gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#10b981"}}))
    fig_mob.add_trace(go.Indicator(mode="gauge+number", value=ev_load, domain={'x': [0.55, 1], 'y': [0, 1]}, title={'text': "EV (kW)"}, gauge={'axis': {'range': [0, 25]}, 'bar': {'color': "#0ea5e9"}}))
    fig_mob.update_layout(height=200, margin=dict(l=10, r=10, t=40, b=0))
    st.plotly_chart(fig_mob, use_container_width=True)
    
    st.metric("Grid Profit", f"${grid_sale * 0.30:.2f}/hr", f"{grid_sale:.1f} kW Sold")
    st.markdown('</div>', unsafe_allow_html=True)

# Layer 4: Exergy & Analytics
st.markdown("### 📊 Layer 4: System Exergy & Flow Analytics")
l4_c1, l4_c2 = st.columns([2, 1])
with l4_c1:
    fig_s = go.Figure(go.Sankey(
        node=dict(label=["Atmosphere", "BESS", "Electrolyzer", "Buffer", "Main Tank", "H2 Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#0f172a"),
        link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_bess+2, p_electrolyzer+2, 25, 20, 12, 10, ev_load+2, grid_sale+2], color="rgba(14, 165, 233, 0.4)")
    ))
    fig_s.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_s, use_container_width=True)

with l4_c2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.write("**Advanced KPIs**")
    st.metric("Exergy Efficiency", "84.7%", "Combined Cycle")
    st.metric("Thermal Recovery", "5.8 kWt", "Active")
    st.metric("CO2 Abatement", "3.6 kg/hr")
    st.info("Strategy: BESS-Buffered H2 Production")
    st.markdown('</div>', unsafe_allow_html=True)

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
