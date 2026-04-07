# main.py — LUMINIH2 | Integrated Hydrogen Digital Twin (FINAL VERSION)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import pytz
import time

# --- CORE MODULES ---
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- UI CONFIG ---
st.set_page_config(page_title="LUMINIH2 Digital Twin", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #f1f5f9; }
.layer { background:white; padding:15px; border-radius:12px; margin-top:20px; border-left:6px solid #0284c7;}
</style>
""", unsafe_allow_html=True)

# --- SESSION INIT ---
if "init" not in st.session_state:
    st.session_state.update({
        "bess": 0.1,
        "buffer": 0.0,
        "tank": 0.0,
        "h2_station": 0.0,
        "history": pd.DataFrame(columns=[
            "time","renewable","grid_in","h2_prod","ev_load","grid_out"
        ]),
        "weather": WeatherProvider(),
        "solar": SolarSystem(),
        "wind": WindSystem(),
        "ems": EMSBrain(),
        "init": True
    })

# --- TIME ---
now = datetime.now(pytz.timezone("Europe/Zagreb"))

# =========================================================
# 🔷 LAYER 1: DATA + ENERGY SWITCHING
# =========================================================
w = st.session_state.weather.fetch_current_data()

p_pv = st.session_state.solar.get_power_output(w["irradiance_raw"], w["temp"], 0.95)
p_wind = st.session_state.wind.get_power_output(w["wind_speed"], 0.02)

source, p_re = st.session_state.ems.decide_energy_source(p_pv, p_wind, 0.6)

p_grid = 0.0
if p_re < 5:
    p_grid = 10.0

p_total = p_re + p_grid

# =========================================================
# 🔷 LAYER 2: BESS + H2 PRODUCTION CHAIN
# =========================================================

# 1. Battery Priority
p_bess = 0
if st.session_state.bess < 0.95:
    p_bess = min(p_total, 6)
    st.session_state.bess += 0.008
    p_total -= p_bess

# 2. Electrolyzer
h2_prod = p_total * 0.022
st.session_state.buffer += h2_prod

# 3. Buffer → Compressor → Tank
compressor = False
if st.session_state.buffer > 2.5:
    compressor = True
    st.session_state.buffer -= 1.5
    st.session_state.tank += 1.4

# =========================================================
# 🔷 LAYER 3: DISTRIBUTION
# =========================================================
fc_power = 0
ev_load = 0
grid_out = 0

if st.session_state.tank > 0.5:

    # H2 Station Priority (5kg)
    if st.session_state.h2_station < 5:
        flow = min(0.3, st.session_state.tank)
        st.session_state.h2_station += flow
        st.session_state.tank -= flow

    # Fuel Cell → EV
    else:
        fc_power = 15
        st.session_state.tank -= 0.2

        ev_load = 10
        grid_out = max(0, fc_power - ev_load)

# --- SAVE HISTORY ---
new = pd.DataFrame([{
    "time": now.strftime("%H:%M:%S"),
    "renewable": p_re,
    "grid_in": p_grid,
    "h2_prod": h2_prod,
    "ev_load": ev_load,
    "grid_out": grid_out
}])

st.session_state.history = pd.concat(
    [st.session_state.history, new]
).iloc[-20:]

# =========================================================
# 🔷 UI DASHBOARD
# =========================================================
st.title("⚡ LUMINIH2 Hydrogen Digital Twin")
st.caption(f"Zagreb | {now.strftime('%H:%M:%S')}")

# ---------------- LAYER 1 ----------------
st.markdown('<div class="layer">LAYER 1: Energy Sources</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)

with c1:
    st.metric("Solar", f"{p_pv:.1f} kW")
    st.metric("Wind", f"{p_wind:.1f} kW")
    st.metric("Grid Input", f"{p_grid:.1f} kW")

with c2:
    fig = go.Figure(data=[go.Pie(
        labels=["Solar","Wind","Grid"],
        values=[p_pv,p_wind,p_grid],
        hole=0.6
    )])
    st.plotly_chart(fig, use_container_width=True)

# ---------------- LAYER 2 ----------------
st.markdown('<div class="layer">LAYER 2: Storage & Hydrogen</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("Battery SOC", f"{st.session_state.bess*100:.1f}%")
    st.progress(st.session_state.bess)

with c2:
    st.metric("Buffer", f"{st.session_state.buffer:.2f} kg")
    st.write("Compressor:", "ON" if compressor else "OFF")

with c3:
    st.metric("Main Tank", f"{st.session_state.tank:.2f} kg")

# ---------------- LAYER 3 ----------------
st.markdown('<div class="layer">LAYER 3: Distribution</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric("H2 Station", f"{st.session_state.h2_station:.2f} / 5 kg")

with c2:
    st.metric("Fuel Cell", f"{fc_power:.1f} kW")
    st.metric("EV Load", f"{ev_load:.1f} kW")

with c3:
    st.metric("Grid Export", f"{grid_out:.1f} kW")

# ---------------- LAYER 4 ----------------
st.markdown('<div class="layer">LAYER 4: Analytics</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)

# Time Series
with c1:
    fig = px.line(st.session_state.history,
                  x="time",
                  y=["renewable","grid_in","grid_out"])
    st.plotly_chart(fig, use_container_width=True)

# Sankey
with c2:
    fig = go.Figure(go.Sankey(
        node=dict(label=[
            "Input","BESS","Electrolyzer",
            "Buffer","Tank","H2 Station",
            "Fuel Cell","EV","Grid"
        ]),
        link=dict(
            source=[0,0,2,3,4,4,6,6],
            target=[1,2,3,4,5,6,7,8],
            value=[
                p_bess+1,
                p_total+1,
                15,12,10,8,
                ev_load+1,
                grid_out+1
            ]
        )
    ))
    st.plotly_chart(fig, use_container_width=True)

# KPIs
st.markdown("### System KPIs")
k1, k2, k3 = st.columns(3)
k1.metric("Efficiency", "83%")
k2.metric("Carbon Saving", "3.1 kg/h")
k3.metric("Main Source", source)

# --- AUTO REFRESH ---
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
