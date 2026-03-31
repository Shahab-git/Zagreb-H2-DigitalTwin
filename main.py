# main.py
# High-Fidelity Digital Twin Dashboard: Zagreb Green H2 Hub
# Version: 3.0 (Industrial Cyberpunk Theme)

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

# --- 1. UI CONFIGURATION ---
st.set_page_config(page_title="Zagreb H2 Hub - Digital Twin", layout="wide", initial_sidebar_state="expanded")

# Custom Cyberpunk CSS
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #00ffcc; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; }
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

# --- 3. DATA ACQUISITION & ENGINE EXECUTION ---
# A. Fetch Environment
w = st.session_state.weather.fetch_current_data()
pv_engine = SolarSystem()
wind_engine = WindSystem()

# B. Power Generation (with Soiling & Turbulence)
p_pv = pv_engine.get_power_output(w['irradiance_raw'], w['temp'], w['soiling_factor'])
p_wind = wind_engine.get_power_output(w['wind_speed'], w['turbulence'])

# C. EMS Strategy
source, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_available, st.session_state.battery.soc)

# D. Update Physical Assets
batt_status = st.session_state.battery.update_state(p_to_batt)
elec_metrics = st.session_state.electrolyzer.calculate_production(p_to_elec, w['temp'])
h2_kg_h = elec_metrics['h2_kg_h']

# E. Logistics & Economics
logistics = st.session_state.h2_chain.manage_chain(h2_kg_h)
eco = st.session_state.brain.calculate_economics(h2_kg_h * (Config.TIMESTEP_SEC / 3600), p_to_elec, source)

# --- 4. DASHBORD LAYOUT ---
st.title("🎛️ Zagreb Integrated H2 Hub | Industrial Digital Twin")
st.markdown(
    f"**Environmental Context:** {w['temp']}°C | Irradiance: {w['irradiance_effective']:.1f} W/m² (Soiling: {w['soiling_factor']:.2%}) | Wind: {w['wind_speed']} m/s")

# --- ROW 1: PRIMARY TELEMETRY (GAUGES) ---
cols = st.columns([1, 1, 1, 1])

with cols[0]:
    # Battery Status Gauge
    fig_batt = go.Figure(go.Indicator(
        mode="gauge+number", value=batt_status['soc'] * 100,
        title={'text': "Battery SOC %"},
        gauge={'bar': {'color': "#00ffcc"}, 'axis': {'range': [0, 100]},
               'steps': [{'range': [0, 20], 'color': "red"}]}))
    fig_batt.update_layout(height=220, margin=dict(t=40, b=0, l=20, r=20), paper_bgcolor='rgba(0,0,0,0)',
                           font={'color': "white"})
    st.plotly_chart(fig_batt, use_container_width=True)
    st.caption(f"Health (SoH): {batt_status['soh']:.2%}")

with cols[1]:
    # H2 Storage Pressure
    fig_press = go.Figure(go.Indicator(
        mode="gauge+number", value=logistics['pressure_bar'],
        title={'text': "Main Tank Pressure (bar)"},
        gauge={'axis': {'range': [0, 700]}, 'bar': {'color': "#3399ff"}}))
    fig_press.update_layout(height=220, margin=dict(t=40, b=0, l=20, r=20), paper_bgcolor='rgba(0,0,0,0)',
                            font={'color': "white"})
    st.plotly_chart(fig_press, use_container_width=True)
    st.caption(f"Tank Temperature: {logistics['temp_c']:.1f} °C")

with cols[2]:
    # Economic KPI: LCOH
    st.metric("Live LCOH (€/kg)", f"€ {eco['lcoh']:.2f}", delta=f"{eco['lcoh'] - 4.5:.2f} vs Target")
    st.metric("Carbon Revenue", f"€ {eco['carbon_revenue']:.4f}", delta=f"{eco['net_co2_kg']:.2f} kg CO2 saved")

with cols[3]:
    # Purity & Efficiency
    st.metric("H2 Purity", f"{elec_metrics['purity']:.4f}%")
    st.metric("Water Consumption", f"{elec_metrics['water_l_h']:.2f} L/h")
    st.metric("HRS Inventory", f"{logistics['hrs_kg']:.2f} / 5.0 kg")

# --- ROW 2: SYSTEM TRENDS ---
st.subheader("📈 Real-time Asset Performance & Analytics")
new_data = {
    'Timestamp': datetime.now().strftime('%H:%M:%S'),
    'PV_Output': p_pv,
    'Wind_Output': p_wind,
    'H2_Production': h2_kg_h * 100,  # scaled for visibility
    'Battery_SOC': batt_status['soc'] * 100,
    'LCOH': eco['lcoh']
}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_data])], ignore_index=True).iloc[-50:]

# Multi-axis Chart
fig_trends = make_subplots(specs=[[{"secondary_y": True}]])
fig_trends.add_trace(
    go.Scatter(x=st.session_state.history['Timestamp'], y=st.session_state.history['PV_Output'], name="Solar (kW)",
               line=dict(color="#ffcc00")), secondary_y=False)
fig_trends.add_trace(
    go.Scatter(x=st.session_state.history['Timestamp'], y=st.session_state.history['Battery_SOC'], name="Battery (%)",
               line=dict(color="#00ffcc", dash='dash')), secondary_y=True)
fig_trends.update_layout(height=400, template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig_trends, use_container_width=True)

# --- ROW 3: DIGITAL TWIN SCHEMATIC (SANKEY) ---
st.subheader("🔄 System Mass & Energy Architecture")
source_idx = 0 if source == "Solar (PV)" else (1 if source == "Wind Turbine" else 2)
labels = [source, "Battery BESS", "PEM Electrolyzer", "H2 Buffer", "Main Storage", "HRS Station", "Fuel Cell"]

fig_sankey = go.Figure(data=[go.Sankey(
    node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5), label=labels, color="cyan"),
    link=dict(
        source=[0, 0, 1, 2, 3, 4],  # Power Flow
        target=[1, 2, 2, 3, 4, 5],  # Mass Flow
        value=[max(0.1, p_to_batt), max(0.1, p_to_elec), 2.0, max(0.1, h2_kg_h * 10), 1.0, 1.0],
        color='rgba(0, 255, 204, 0.4)'
    )
)])
fig_sankey.update_layout(height=450, font_size=12, template="plotly_dark")
st.plotly_chart(fig_sankey, use_container_width=True)

# --- SIDEBAR: PREDICTIVE MAINTENANCE & ALERTS ---
with st.sidebar:
    st.header("🛠️ Predictive Diagnostics")
    st.write(f"**Electrolyzer SOH:** {elec_metrics['soh']:.2%}")
    if elec_metrics['soh'] < 0.95:
        st.warning("Maintenance Required: Stack degradation detected.")

    st.write(f"**BESS Health:** {batt_status['soh']:.2%}")
    st.info(f"Total Throughput: {batt_status['throughput']:.2f} kWh")

    st.divider()
    st.write("**Operational Strategy:**")
    st.success(f"Current Priority: {source}")
    st.write(
        f"Dispatching to: {st.session_state.brain.hydrogen_logistics_control(logistics['buffer_kg'], logistics['main_tank_kg'], logistics['hrs_kg'])[1]}")

# Simulation Loop
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
