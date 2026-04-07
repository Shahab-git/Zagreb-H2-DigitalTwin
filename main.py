# main.py - PROJECT LUMINIH2: Holistic Digital Twin
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- 1. CORE MODULES ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 2. THEME & STYLING ---
st.set_page_config(page_title="LUMINIH2 | Integrated Command", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; color: #1e293b; }
    .main-container { background: white; padding: 25px; border-radius: 20px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; }
    .status-card { background: #ffffff; border-radius: 12px; padding: 15px; border: 1px solid #e2e8f0; text-align: center; }
    .highlight-blue { color: #0284c7; font-weight: 800; font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIC & TELEMETRY ENGINE ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 0.0, 'main_tank': 0.0, 'h2_station': 0.0, 'bess_soc': 0.1,
        'history': pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'Grid', 'EV_Charging', 'Revenue']),
        'weather_engine': WeatherProvider(),
        'solar_engine': SolarSystem(),
        'wind_engine': WindSystem(),
        'ems_brain': EMSBrain(),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- STEP 1: WEATHER & DATA ACQUISITION ---
w = st.session_state.weather_engine.fetch_current_data() 
p_solar = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

# --- STEP 2: POWER SWITCHING & SOURCE SELECTION ---
source, p_re = st.session_state.ems_brain.decide_energy_source(p_solar, p_wind, 0.6)
p_grid_in = 15.0 if p_re < 8.0 else 0.0 # Grid logic
p_total = p_re + p_grid_in

# --- STEP 3: BESS & PRODUCTION CHAIN ---
# Battery First
p_to_batt = 0.0
if st.session_state.bess_soc < 0.95:
    p_to_batt = min(p_total, 10.0)
    st.session_state.bess_soc += 0.007
    p_total -= p_to_batt

# Electrolyzer -> Buffer -> Compressor
h2_gen = p_total * 0.025
st.session_state.buffer += h2_gen

comp_active = False
if st.session_state.buffer > 2.0:
    comp_active = True
    st.session_state.buffer -= 1.2
    st.session_state.main_tank += 1.1

# --- STEP 4: H2 STATION & FUEL CELL (EV HUB) ---
fc_pwr, ev_load, grid_sale = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0: # Priority 1: H2 Station (5kg)
        fill = 0.35
        st.session_state.h2_station = min(5.0, st.session_state.h2_station + fill)
        st.session_state.main_tank -= fill
    else: # Priority 2: Fuel Cell -> EV Hub
        fc_pwr = 20.0
        st.session_state.main_tank -= 0.2
        ev_load = 12.0 # Fixed Station Demand
        grid_sale = max(0.0, fc_pwr - ev_load) # Priority 3: Sale

# Data Logging
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Solar': p_solar, 'Wind': p_wind, 'Grid': p_grid_in, 'EV_Charging': ev_load, 'Revenue': grid_sale * 0.25}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-20:]

# --- 5. UNIFIED DASHBOARD LAYOUT ---

# TOP BAR: GLOBAL STATUS
t1, t2, t3 = st.columns([2, 1, 1])
with t1:
    st.title("🌐 LUMINIH2 Global Command")
    st.caption(f"Location: Zagreb Hub | Time: {now_zagreb.strftime('%H:%M:%S')} | Status: OPERATIONAL")
with t2:
    st.metric("Primary Energy Source", source)
with t3:
    st.metric("Grid Interaction", f"{p_grid_in if p_grid_in > 0 else -grid_sale:.1f} kW", "Import" if p_grid_in > 0 else "Export")

st.divider()

# ROW 1: ENERGY INPUTS & STORAGE
r1_c1, r1_c2, r1_c3 = st.columns(3)
with r1_c1:
    st.markdown("### ⚡ Power Input Mix")
    fig_pie = go.Figure(data=[go.Pie(labels=['Solar', 'Wind', 'Grid'], values=[p_solar, p_wind, p_grid_in], hole=.6, marker_colors=['#fbbf24', '#38bdf8', '#94a3b8'])])
    fig_pie.update_layout(height=250, margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
    st.plotly_chart(fig_pie, use_container_width=True)

with r1_c2:
    st.markdown("### 🔋 BESS Utilization")
    st.write(f"SoC: {st.session_state.bess_soc*100:.1f}%")
    st.progress(st.session_state.bess_soc)
    st.metric("Battery Inflow", f"{p_to_batt:.2f} kW")

with r1_c3:
    st.markdown("### 💨 H2 Storage Chain")
    st.metric("Buffer Level", f"{st.session_state.buffer:.2f} kg")
    st.metric("Main Tank", f"{st.session_state.main_tank:.2f} kg")
    st.write(f"Compressor: {'🟢 RUNNING' if comp_active else '⚪ STANDBY'}")

# ROW 2: MOBILITY HUB & DISTRIBUTION
st.divider()
r2_c1, r2_c2, r2_c3 = st.columns(3)
with r2_c1:
    st.markdown("### ⛽ H2 Refueling Station")
    fig_h2 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.h2_station, title={'text': "Refueling Tank (5kg Max)"}, gauge={'axis': {'range': [0, 5]}, 'bar': {'color': "#22c55e"}}))
    fig_h2.update_layout(height=230, margin=dict(t=50, b=0))
    st.plotly_chart(fig_h2, use_container_width=True)

with r2_c2:
    st.markdown("### 🔌 EV Charging Station")
    fig_ev = go.Figure(go.Indicator(mode="gauge+number", value=ev_load, title={'text': "Hub Load (kW)"}, gauge={'axis': {'range': [0, 25]}, 'bar': {'color': "#0ea5e9"}}))
    fig_ev.update_layout(height=230, margin=dict(t=50, b=0))
    st.plotly_chart(fig_ev, use_container_width=True)

with r2_c3:
    st.markdown("### 💰 Grid Revenue")
    st.metric("Total Sale Power", f"{grid_sale:.1f} kW")
    st.metric("Hourly Revenue", f"${grid_sale * 0.25:.2f}/hr", delta="Market High")

# ROW 3: ADVANCED ANALYTICS (SANKEY & HISTORY)
st.divider()
st.markdown("### 📈 Full System Exergy & Flow Analytics")
l4_c1, l4_c2 = st.columns([2, 1])
with l4_c1:
    # Full Process Sankey
    fig_s = go.Figure(go.Sankey(
        node=dict(label=["Atmosphere", "BESS", "Electrolyzer", "Buffer", "Main Tank", "H2 Station", "Fuel Cell", "EV Hub", "Grid Sale"], color="#0284c7"),
        link=dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[p_to_batt+2, p_total+2, 25, 20, 12, 10, ev_load+2, grid_sale+2])
    ))
    fig_s.update_layout(height=350, margin=dict(t=20, b=20))
    st.plotly_chart(fig_s, use_container_width=True)
with l4_c2:
    st.write("**Operational KPI**")
    st.metric("Exergy Efficiency", "84.2%", "Optimized")
    st.metric("CO2 Saved", "3.1 kg/hr")
    st.metric("Thermal Recovery", "5.4 kWt")
    st.info("Strategy: H2 Station Priority Fill")

# AUTO-REFRESH
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
