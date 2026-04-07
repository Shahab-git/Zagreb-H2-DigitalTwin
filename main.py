# main.py - PROJECT LUMINIH2: Integrated Green Energy Hub
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz

# --- CRITICAL: YOUR CORE MODULES ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 1. SETTINGS & NEON THEME ---
st.set_page_config(page_title="LUMINIH2 | Command Center", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0f172a; color: #f8fafc; }
    div[data-testid="stMetricValue"] { color: #0ea5e9 !important; font-size: 28px; font-weight: 700; }
    .stMetric { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 15px; }
    .layer-card { 
        background: linear-gradient(90deg, #1e293b, #0f172a); 
        border-left: 5px solid #0ea5e9; 
        padding: 12px; 
        border-radius: 8px; 
        margin-top: 25px;
        margin-bottom: 15px;
        font-weight: bold;
    }
    h1, h2, h3 { color: #f1f5f9 !important; font-family: 'Inter', sans-serif; }
    .safety-ok { color: #10b981; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE MANAGEMENT ---
if 'init' not in st.session_state:
    st.session_state.buffer = 2.1
    st.session_state.main_tank = 1.5
    st.session_state.h2_station = 3.0
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'EV'])
    
    # Initialize your custom objects into session state for efficiency
    st.session_state.weather_engine = WeatherProvider()
    st.session_state.solar_engine = SolarSystem()
    st.session_state.wind_engine = WindSystem()
    st.session_state.ems_brain = EMSBrain()
    
    st.session_state.init = True

# Global Time Setup
zagreb_tz = pytz.timezone('Europe/Zagreb')
now_zagreb = datetime.now(zagreb_tz)

# --- 3. DATA ACQUISITION & LOGIC (USING YOUR MODULES) ---

# Fetch real data using your WeatherProvider
w = st.session_state.weather_engine.fetch_current_data()

# Calculate Power using Solar & Wind Systems
# Assuming standard efficiency (0.95) and losses (0.02)
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

# Pre-initialize logic variables to prevent NameError
fc_out = 0.0
ev_load = 0.0
grid_export = 0.0
thermal_recovery = 0.0

# Layer 1: Decision making using your EMSBrain
source, p_total = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)

# Layer 2: Battery & H2 Chain
p_to_batt = min(p_total, 5.0) 
p_to_elec = max(0, p_total - p_to_batt)
h2_gen = p_to_elec * 0.022
st.session_state.buffer += h2_gen

# Compressor Simulation
comp_active = False
if st.session_state.buffer > 5.0:
    comp_active = True
    st.session_state.buffer -= 2.0
    st.session_state.main_tank += 1.8

# Layer 3: H2 Logistics -> Fuel Cell -> EV -> Grid
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0:
        st.session_state.h2_station += 0.2
        st.session_state.main_tank -= 0.2
    else:
        fc_out = 15.0 # KW production
        st.session_state.main_tank -= 0.05
        ev_load = min(fc_out, 10.0)
        grid_export = max(0, fc_out - ev_load)

# Layer 4: Performance Analytics
thermal_recovery = (p_to_elec * 0.15) + (fc_out * 0.20)

# Update History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Solar': p_pv, 'Wind': p_wind, 'EV': ev_load}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-20:]

# --- 4. DASHBOARD RENDER ---

st.title("⚡ LUMINIH2 | Command Center")
st.markdown(f"**Location:** Zagreb, HR | **Live Telemetry:** {now_zagreb.strftime('%H:%M:%S')} | <span class='safety-ok'>SYSTEM STATUS: NOMINAL</span>", unsafe_allow_html=True)
st.divider()

# LAYER 1
st.markdown('<div class="layer-card">LAYER 1: ATMOSPHERIC INPUTS & SMART SOURCE ALLOCATION</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1, 2])
with l1_c1:
    st.metric("Solar Irradiance", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Wind Velocity", f"{w['wind_speed']:.1f} m/s")
with l1_c2:
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = p_total,
        title = {'text': "Total Input (kW)", 'font': {'color': 'white'}},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0ea5e9"}}
    ))
    fig_gauge.update_layout(height=220, margin=dict(t=40, b=0, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    st.plotly_chart(fig_gauge, use_container_width=True)
with l1_c3:
    fig_area = go.Figure()
    fig_area.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Solar'], fill='tozeroy', name='Solar (kW)', line_color='#f59e0b'))
    fig_area.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Wind'], fill='tozeroy', name='Wind (kW)', line_color='#10b981'))
    fig_area.update_layout(height=220, margin=dict(t=20, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    st.plotly_chart(fig_area, use_container_width=True)

# LAYER 2
st.markdown('<div class="layer-card">LAYER 2: BESS MANAGEMENT & GREEN H2 PRODUCTION</div>', unsafe_allow_html=True)
l2_c1, l2_c2, l2_c3 = st.columns(3)
with l2_c1:
    st.write("Battery SOC (BESS)")
    st.progress(0.85)
    st.caption(f"Charging: {p_to_batt:.1f} kW")
with l2_c2:
    st.write("H2 Buffer Level")
    st.progress(min(st.session_state.buffer/10, 1.0))
    st.write(f"Compressor: {'🟢 ACTIVE' if comp_active else '⚪ STANDBY'}")
with l2_c3:
    st.metric("Main Storage Tank", f"{st.session_state.main_tank:.2f} kg", "Chain Priority 1")

# LAYER 3
st.markdown('<div class="layer-card">LAYER 3: LOGISTICS, FUEL CELL & MOBILITY HUB</div>', unsafe_allow_html=True)
l3_c1, l3_c2, l3_c3 = st.columns(3)
with l3_c1:
    fig_bullet = go.Figure(go.Indicator(
        mode = "number+gauge", value = st.session_state.h2_station,
        title = {'text' : "H2 Refueling (5kg)", 'font': {'color': 'white'}},
        gauge = {'shape': "bullet", 'axis': {'range': [0, 5]}, 'bar': {'color': "#10b981"}}
    ))
    fig_bullet.update_layout(height=120, paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    st.plotly_chart(fig_bullet, use_container_width=True)
with l3_c2:
    st.metric("Fuel Cell Power", f"{fc_out:.1f} kW", "Source: Surplus H2")
    st.metric("EV Charger Demand", f"{ev_load:.1f} kW")
with l3_c3:
    st.metric("Grid Revenue", f"${grid_export * 0.15:.2f}/hr", f"{grid_export:.1f} kW Export")
    st.info(f"Primary Feed: {source}")

# LAYER 4
st.markdown('<div class="layer-card">LAYER 4: ENERGY FLOW (SANKEY) & THERMAL RECOVERY</div>', unsafe_allow_html=True)
l4_c1, l4_c2 = st.columns([2, 1])
with l4_c1:
    fig_sankey = go.Figure(go.Sankey(
        node=dict(label=["Renewables", "BESS", "Electrolyzer", "H2 Tank", "Fuel Cell", "EV Hub", "Grid"], color="#0ea5e9"),
        link=dict(source=[0, 0, 2, 3, 4, 4], target=[1, 2, 3, 4, 5, 6], value=[p_to_batt, p_to_elec, 25, 15, ev_load, grid_export])
    ))
    fig_sankey.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)', font={'color': "white", 'size': 12})
    st.plotly_chart(fig_sankey, use_container_width=True)
with l4_c2:
    st.metric("Heat Recovered", f"{thermal_recovery:.2f} kWt")
    st.metric("Carbon Avoidance", "2.4 kg/hr")
    st.write("**Integrated Efficiency**")
    st.info("System Exergy: 82.1%")

# Refresh Loop
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
