# main.py - PROJECT LUMINIH2: Integrated Green Energy Hub
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz

# Simulation Mock Modules (Assuming your existing logic)
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 1. SETTINGS & NEON THEME ---
st.set_page_config(page_title="LUMINIH2 | Command Center", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0f172a; color: #f8fafc; }
    div[data-testid="stMetricValue"] { color: #0ea5e9 !important; font-size: 24px; font-weight: 700; }
    .stMetric { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 15px; }
    .layer-card { 
        background: rgba(30, 41, 59, 0.7); 
        border-left: 5px solid #0ea5e9; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 20px;
    }
    h1, h2, h3 { color: #f1f5f9 !important; font-family: 'Inter', sans-serif; }
    .safety-ok { color: #10b981; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE MANAGEMENT ---
if 'init' not in st.session_state:
    st.session_state.update({
        'buffer': 2.5, 'main_tank': 1.2, 'h2_station': 3.1, 
        'history': pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'EV']),
        'init': True
    })

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 3. DATA ACQUISITION & LOGIC ---
w = WeatherProvider().fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = WindSystem().get_power_output(w['wind_speed'], 0.02)

# Logic Layer 1: Power Switching
source, p_total = EMSBrain().decide_energy_source(p_pv, p_wind, 0.6)

# Logic Layer 2: Battery & H2 Production
p_to_batt = min(p_total, 5.0) 
p_to_elec = max(0, p_total - p_to_batt)
h2_gen = p_to_elec * 0.022
st.session_state.buffer += h2_gen

# Logic Layer 3: Distribution (H2 Station -> FC -> EV -> Grid)
fc_out, ev_load, grid_export = 0.0, 0.0, 0.0
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0:
        st.session_state.h2_station += 0.2
        st.session_state.main_tank -= 0.2
    else:
        fc_out = 14.5 
        ev_load = 8.5
        grid_export = fc_out - ev_load

# Update History
new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Solar': p_pv, 'Wind': p_wind, 'EV': ev_load}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-15:]

# --- 4. DASHBOARD RENDER ---

# HEADER
st.title("⚡ LUMINIH2 | Integrated Hydrogen Ecosystem")
st.markdown(f"**Location:** Zagreb, HR | **Timestamp:** {now_zagreb.strftime('%Y-%m-%d %H:%M:%S')} | <span class='safety-ok'>SYSTEM STATUS: NOMINAL</span>", unsafe_allow_html=True)
st.divider()

# LAYER 1: ATMOSPHERIC & SOURCE SWITCHING
st.markdown('<div class="layer-card"><b>LAYER 1:</b> ATMOSPHERIC INPUTS & SMART SOURCE ALLOCATION</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1, 2])

with l1_c1:
    st.metric("Solar Irradiance", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Wind Velocity", f"{w['wind_speed']:.1f} m/s")

with l1_c2:
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = p_total,
        title = {'text': "Total Input (kW)"},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#0ea5e9"}}
    ))
    fig_gauge.update_layout(height=200, margin=dict(t=30, b=0, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    st.plotly_chart(fig_gauge, use_container_width=True)

with l1_c3:
    fig_area = go.Figure()
    fig_area.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Solar'], fill='tozeroy', name='Solar', line_color='#f59e0b'))
    fig_area.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Wind'], fill='tozeroy', name='Wind', line_color='#10b981'))
    fig_area.update_layout(height=200, margin=dict(t=20, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    st.plotly_chart(fig_area, use_container_width=True)

# LAYER 2: STORAGE & PRODUCTION
st.markdown('<div class="layer-card"><b>LAYER 2:</b> BESS MANAGEMENT & H2 GENERATION CHAIN</div>', unsafe_allow_html=True)
l2_c1, l2_c2, l2_c3 = st.columns(3)

with l2_c1:
    st.write("Battery SOC (BESS)")
    st.progress(0.82)
    st.caption(f"Charging Priority Active: {p_to_batt:.1f} kW")

with l2_c2:
    st.write("Buffer Tank Level")
    st.progress(min(st.session_state.buffer/10, 1.0))
    st.caption("Auto-Compressor logic: Active > 5.0kg")

with l2_c3:
    st.metric("Main Storage Tank", f"{st.session_state.main_tank:.2f} kg", "High Pressure")

# LAYER 3: FUEL CELL & MOBILITY
st.markdown('<div class="layer-card"><b>LAYER 3:</b> LOGISTICS, FUEL CELL & EV CHARGING HUB</div>', unsafe_allow_html=True)
l3_c1, l3_c2, l3_c3 = st.columns(3)

with l3_c1:
    fig_bullet = go.Figure(go.Indicator(
        mode = "number+gauge", value = st.session_state.h2_station,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text' : "H2 Refueling (5kg)"},
        gauge = {'shape': "bullet", 'axis': {'range': [0, 5]}, 'bar': {'color': "#10b981"}}
    ))
    fig_bullet.update_layout(height=120, paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
    st.plotly_chart(fig_bullet, use_container_width=True)

with l3_c2:
    st.metric("Fuel Cell Power", f"{fc_out:.1f} kW", delta="From H2 Surplus")
    st.metric("EV Station Demand", f"{ev_load:.1f} kW")

with l3_c3:
    st.metric("Grid Revenue Export", f"{grid_export:.1f} kW", delta="Financial Gain", delta_color="normal")
    st.success(f"Source: {source}")

# LAYER 4: ADVANCED ANALYTICS (SANKEY & HEAT RECOVERY)
st.markdown('<div class="layer-card"><b>LAYER 4:</b> HEAT RECOVERY & SYSTEM EXERGY FLOW</div>', unsafe_allow_html=True)
l4_c1, l4_c2 = st.columns([2, 1])

with l4_c1:
    fig_sankey = go.Figure(go.Sankey(
        node=dict(label=["RE Sources", "BESS", "Electrolyzer", "H2 Tank", "Fuel Cell", "EV Hub", "Grid"], color="#0ea5e9"),
        link=dict(source=[0, 0, 2, 3, 4, 4], target=[1, 2, 3, 4, 5, 6], value=[p_to_batt, p_to_elec, 25, 18, ev_load, grid_export])
    ))
    fig_sankey.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)', font={'color': "white", 'size': 12})
    st.plotly_chart(fig_sankey, use_container_width=True)

with l4_c2:
    st.metric("Heat Recovery Rate", "5.4 kWt", "Recovered")
    st.metric("Carbon Avoidance", "1.82 kg/hr", "Green Certificate")
    st.write("**Total System Efficiency**")
    st.info("Combined (P+T): 79.2%")

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
