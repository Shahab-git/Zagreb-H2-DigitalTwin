# main.py - PROJECT LUMINIH2: Integrated Green Energy Hub
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import pytz

# --- CRITICAL: YOUR CORE MODULES ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- 1. SETTINGS & EXECUTIVE LIGHT THEME ---
st.set_page_config(page_title="LUMINIH2 | Global Hub", layout="wide")

st.markdown("""
    <style>
    /* Global Background & Text */
    .stApp { background-color: #f8fafc; color: #1e293b; }
    
    /* Metric Cards Customization */
    div[data-testid="stMetricValue"] { color: #0284c7 !important; font-size: 32px; font-weight: 800; }
    div[data-testid="stMetricLabel"] { color: #64748b !important; font-weight: 600; }
    
    .stMetric { 
        background-color: #ffffff; 
        border-radius: 16px; 
        padding: 20px; 
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        border: 1px solid #e2e8f0;
    }
    
    /* Layer Headers */
    .layer-card { 
        background: #ffffff; 
        border-left: 6px solid #0ea5e9; 
        padding: 15px 20px; 
        border-radius: 12px; 
        margin: 30px 0 15px 0;
        box-shadow: 0 2px 4px rgb(0 0 0 / 0.05);
        color: #0f172a;
        font-size: 1.1rem;
        display: flex;
        align-items: center;
    }
    
    /* Progress Bars */
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #0ea5e9, #22c55e); }
    
    .safety-ok { 
        background-color: #dcfce7; 
        color: #166534; 
        padding: 4px 12px; 
        border-radius: 20px; 
        font-size: 14px;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE MANAGEMENT ---
if 'init' not in st.session_state:
    st.session_state.buffer = 2.1
    st.session_state.main_tank = 1.5
    st.session_state.h2_station = 3.0
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'EV'])
    
    st.session_state.weather_engine = WeatherProvider()
    st.session_state.solar_engine = SolarSystem()
    st.session_state.wind_engine = WindSystem()
    st.session_state.ems_brain = EMSBrain()
    st.session_state.init = True

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- 3. DATA ACQUISITION & LOGIC ---
w = st.session_state.weather_engine.fetch_current_data()
p_pv = st.session_state.solar_engine.get_power_output(w['irradiance_raw'], w['temp'], 0.95)
p_wind = st.session_state.wind_engine.get_power_output(w['wind_speed'], 0.02)

fc_out, ev_load, grid_export = 0.0, 0.0, 0.0
source, p_total = st.session_state.ems_brain.decide_energy_source(p_pv, p_wind, 0.6)

# Energy Flow Logic
p_to_batt = min(p_total, 5.0) 
p_to_elec = max(0, p_total - p_to_batt)
h2_gen = p_to_elec * 0.022
st.session_state.buffer += h2_gen

# Compressor
comp_active = False
if st.session_state.buffer > 5.0:
    comp_active = True
    st.session_state.buffer -= 2.0
    st.session_state.main_tank += 1.8

# Logistics
if st.session_state.main_tank > 0.5:
    if st.session_state.h2_station < 5.0:
        st.session_state.h2_station += 0.2
        st.session_state.main_tank -= 0.2
    else:
        fc_out = 15.0 
        st.session_state.main_tank -= 0.05
        ev_load = min(fc_out, 10.0)
        grid_export = max(0, fc_out - ev_load)

thermal_recovery = (p_to_elec * 0.15) + (fc_out * 0.20)

new_row = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Solar': p_pv, 'Wind': p_wind, 'EV': ev_load}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_row])], ignore_index=True).iloc[-20:]

# --- 4. DASHBOARD RENDER ---

# --- TOP NAVIGATION BAR ---
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.title("🌐 LUMINIH2 Global Command")
    st.markdown(f"**Zagreb Hub** | System Time: `{now_zagreb.strftime('%H:%M:%S')}`")
with col_t2:
    st.markdown("<br><span class='safety-ok'>● SYSTEM ONLINE</span>", unsafe_allow_html=True)

# --- LAYER 1: THE SOURCE ---
st.markdown('<div class="layer-card">⚡ LAYER 1: ENERGY ACQUISITION & MIX</div>', unsafe_allow_html=True)
l1_c1, l1_c2, l1_c3 = st.columns([1, 1.2, 1.8])

with l1_c1:
    st.metric("Solar Radiation", f"{w['irradiance_raw']:.1f} W/m²")
    st.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s")

with l1_c2:
    # Donut Chart for Energy Mix
    mix_fig = go.Figure(data=[go.Pie(labels=['Solar', 'Wind'], values=[p_pv, p_wind], hole=.7, 
                                   marker_colors=['#fca311', '#0ea5e9'])])
    mix_fig.update_layout(showlegend=False, height=200, margin=dict(t=0, b=0, l=0, r=0))
    mix_fig.add_annotation(text=f"{p_total:.1f}<br>kW", x=0.5, y=0.5, font_size=20, showarrow=False)
    st.plotly_chart(mix_fig, use_container_width=True)

with l1_c3:
    # Pro History Area Chart
    hist_fig = px.area(st.session_state.history, x='Time', y=['Solar', 'Wind'], 
                       color_discrete_map={'Solar': '#fca311', 'Wind': '#0ea5e9'}, template='plotly_white')
    hist_fig.update_layout(height=220, margin=dict(t=10, b=0, l=0, r=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(hist_fig, use_container_width=True)

# --- LAYER 2 & 3: PROCESSING & DISTRIBUTION ---
st.markdown('<div class="layer-card">🛡️ LAYER 2 & 3: PRODUCTION & LOGISTICS</div>', unsafe_allow_html=True)
col_l2, col_l3 = st.columns(2)

with col_l2:
    st.subheader("Hydrogen Production")
    m1, m2 = st.columns(2)
    m1.metric("Storage Tank", f"{st.session_state.main_tank:.2f} kg")
    m2.metric("Compressor", "Active" if comp_active else "Standby")
    st.write("Battery Charge (BESS)")
    st.progress(0.85)

with col_l3:
    st.subheader("Mobility & Grid")
    # Bullet chart for Station
    fig_b = go.Figure(go.Indicator(mode = "gauge+number", value = st.session_state.h2_station,
        title = {'text': "H2 Station (kg)"}, gauge = {'axis': {'range': [0, 5]}, 'bar': {'color': "#22c55e"}}))
    fig_b.update_layout(height=180, margin=dict(t=40, b=0))
    st.plotly_chart(fig_b, use_container_width=True)

# --- LAYER 4: ANALYTICS ---
st.markdown('<div class="layer-card">📈 LAYER 4: SYSTEM EXERGY & FLOW ANALYTICS</div>', unsafe_allow_html=True)
l4_c1, l4_c2 = st.columns([2, 1])

with l4_c1:
    # Sankey with Professional Colors
    fig_s = go.Figure(go.Sankey(
        node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5), 
                 label=["Renewables", "BESS", "Electrolyzer", "H2 Tank", "Fuel Cell", "EV Hub", "Grid"], 
                 color="#0284c7"),
        link=dict(source=[0, 0, 2, 3, 4, 4], target=[1, 2, 3, 4, 5, 6], 
                 value=[p_to_batt, p_to_elec, 25, 15, ev_load, grid_export], color="rgba(14, 165, 233, 0.2)")
    ))
    fig_s.update_layout(height=350, font_size=12, margin=dict(t=20, b=20))
    st.plotly_chart(fig_s, use_container_width=True)

with l4_c2:
    st.metric("Thermal Recovery", f"{thermal_recovery:.2f} kWt")
    st.metric("Revenue Stream", f"${grid_export * 0.18:.2f}/hr")
    st.info(f"**Efficiency Profile:** Combined Cycle 82.1%")
    st.success(f"**CO2 Saved:** 2.4 kg/hr")

# --- AUTO REFRESH ---
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
