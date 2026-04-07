# main.py
# High-Fidelity Digital Twin Dashboard: Zagreb Green H2 Hub
# Version: 4.0 (Industrial Control Room Edition)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime

from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain

# --- 1. UI CONFIGURATION (Industrial Theme) ---
st.set_page_config(page_title="Zagreb H2 Hub - Control Room", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #c9d1d9; }
    .stMetric { background-color: #161b22; border-left: 5px solid #58a6ff; border-radius: 4px; padding: 12px; }
    .status-card { background-color: #1c2128; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
    .source-label { font-size: 20px; font-weight: bold; padding: 8px 20px; border-radius: 20px; border: 1px solid; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE INITIALIZATION ---
if 'init' not in st.session_state:
    st.session_state.history = pd.DataFrame()
    st.session_state.battery = BatteryBESS()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.fuel_cell = FuelCellAircell()
    st.session_state.weather = WeatherProvider()
    st.session_state.brain = EMSBrain()
    st.session_state.init = True

# --- 3. DATA ACQUISITION & CALCULATIONS ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], w['soiling_factor'])
p_wind = WindSystem().get_power_output(w['wind_speed'], w['turbulence'])

# EMS Strategy Execution
source, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_available, st.session_state.battery.soc)

# Physical Updates
batt_status = st.session_state.battery.update_state(p_to_batt)
elec_metrics = st.session_state.electrolyzer.calculate_production(p_to_elec, w['temp'])
h2_kg_h = elec_metrics['h2_kg_h']
logistics = st.session_state.h2_chain.manage_chain(h2_kg_h)
eco = st.session_state.brain.calculate_economics(h2_kg_h * (Config.TIMESTEP_SEC / 3600), p_to_elec, source)

# --- 4. TOP BAR: TELEMETRY & SOURCE (Requirement 1 & 2) ---
header_l, header_r = st.columns([1, 1])

with header_l:
    st.markdown(f"""
        <div class="status-card">
            <span style="color: #8b949e; font-size: 14px;">📍 HUB LOCATION: ZAGREB, CROATIA</span><br>
            <span style="font-size: 26px; font-weight: bold; color: #ffffff;">{datetime.now().strftime('%H:%M:%S')}</span>
            <span style="color: #58a6ff; margin-left: 10px;">{datetime.now().strftime('%A, %d %B %Y')}</span>
            <hr style="margin: 10px 0; border-color: #30363d;">
            <span style="color: #8b949e;">WEATHER:</span> 
            <b>{w['temp']}°C</b> | 💧 {w['humidity']}% | ☀️ {w['irradiance_raw']:.1f} W/m² | 🌬️ {w['wind_speed']} m/s
        </div>
    """, unsafe_allow_html=True)

with header_r:
    # Source Switching Logic Visualization
    src_colors = {"Solar (PV)": "#ffcc00", "Wind Turbine": "#00d4ff", "National Grid": "#ff4b4b"}
    current_color = src_colors.get(source, "#ffffff")
    st.markdown(f"""
        <div style="text-align: right; margin-top: 15px;">
            <span style="color: #8b949e; font-size: 14px;">PRIMARY ENERGY INPUT</span><br><br>
            <span class="source-label" style="color: {current_color}; border-color: {current_color}; background-color: {current_color}11;">
                ● {source.upper()}
            </span>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- 5. MAIN DASHBOARD: DIVERSE CHARTS (Requirement 3 & 4) ---
col_p, col_b, col_h = st.columns([1.2, 1, 1.2])

with col_p:
    st.subheader("⚡ Power Distribution (kW)")
    # Bar Chart for Power Balance
    fig_power = go.Figure(go.Bar(
        x=['Inbound', 'To Battery', 'To Electrolyzer'],
        y=[p_available, abs(p_to_batt), p_to_elec],
        marker_color=[current_color, '#00ffcc', '#3399ff'],
        text=[f"{v:.2f}" for v in [p_available, abs(p_to_batt), p_to_elec]],
        textposition='auto'
    ))
    fig_power.update_layout(height=300, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig_power, use_container_width=True)

with col_b:
    st.subheader("🔋 Battery SOC")
    # Donut Chart for Battery
    fig_soc = go.Figure(go.Pie(
        labels=['Charged', 'Remaining'],
        values=[batt_status['soc'], 1 - batt_status['soc']],
        hole=.7,
        marker_colors=['#00ffcc', '#161b22'],
        showlegend=False
    ))
    fig_soc.add_annotation(text=f"{batt_status['soc']*100:.1f}%", x=0.5, y=0.5, showarrow=False, font_size=24, font_color="white")
    fig_soc.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_soc, use_container_width=True)

with col_h:
    st.subheader("🧪 Production & Pressure")
    # Line Chart for Pressure History
    new_entry = {
        'Time': datetime.now().strftime('%H:%M:%S'),
        'Pressure': logistics['pressure_bar'],
        'H2_Rate': h2_kg_h * 100
    }
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_entry])], ignore_index=True).iloc[-30:]
    
    fig_h2 = go.Figure()
    fig_h2.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Pressure'], 
                                name="Tank Pressure", line=dict(color='#3399ff', width=3), fill='tozeroy'))
    fig_h2.update_layout(height=300, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig_h2, use_container_width=True)

# --- 6. INDUSTRIAL KPI GRID ---
st.subheader("🛠️ Asset Diagnostics & Economics")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("Stack Health (SOH)", f"{elec_metrics['soh']:.2%}", delta="-0.01% Cycle")
kpi2.metric("Hydrogen Purity", f"{elec_metrics['purity']:.4f}%", "Optimal")
kpi3.metric("Live LCOH", f"€ {eco['lcoh']:.2f}", f"{eco['lcoh']-4.5:.2f} delta")
kpi4.metric("CO2 Abated", f"{eco['net_co2_kg']:.2f} kg")

# Simulation Timing
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
