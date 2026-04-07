# main.py — LUMINIH2 FINAL (Optimized Digital Twin)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import pytz
import time

from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem

# --- UI ---
st.set_page_config(layout="wide", page_title="LUMINIH2 PRO MAX")

# --- SESSION ---
if "init" not in st.session_state:
    st.session_state.update({
        "bess": 0.2,
        "buffer": 0.0,
        "tank": 0.0,
        "h2_station": 0.0,
        "history": pd.DataFrame(columns=["time","pv","wind","grid_in","ev","sale"]),
        "weather": WeatherProvider(),
        "solar": SolarSystem(),
        "wind_sys": WindSystem(),
        "init": True
    })

now = datetime.now(pytz.timezone("Europe/Zagreb"))

# =========================
# 🔹 LAYER 1 — ENERGY INPUT
# =========================
w = st.session_state.weather.fetch_current_data()

pv = st.session_state.solar.get_power_output(w["irradiance_raw"], w["temp"], 0.95)
wind = st.session_state.wind_sys.get_power_output(w["wind_speed"], 0.02)

# SMART SWITCH
if pv > wind:
    source = "Solar"
    p_re = pv
else:
    source = "Wind"
    p_re = wind

# GRID SUPPORT
grid_in = 0
if p_re < 5:
    grid_in = 8

power_pool = p_re + grid_in

# =========================
# 🔹 LAYER 2 — BESS + H2
# =========================
# BATTERY PRIORITY
p_to_bess = 0
if st.session_state.bess < 0.9:
    p_to_bess = min(power_pool, 5)
    st.session_state.bess += 0.01
    power_pool -= p_to_bess

# ELECTROLYZER
h2_prod = power_pool * 0.025
st.session_state.buffer += h2_prod

# COMPRESSOR LOGIC
compressor = False
if st.session_state.buffer > 2:
    compressor = True
    st.session_state.buffer -= 1.5
    st.session_state.tank += 1.4

# =========================
# 🔹 LAYER 3 — DISTRIBUTION
# =========================
fc_power = 0
ev_load = 0
grid_sale = 0

if st.session_state.tank > 0.5:
    # PRIORITY 1: H2 STATION
    if st.session_state.h2_station < 5:
        fill = min(0.4, st.session_state.tank)
        st.session_state.h2_station += fill
        st.session_state.tank -= fill

    else:
        # PRIORITY 2: FUEL CELL
        fc_power = 15
        st.session_state.tank -= 0.2

        # PRIORITY 3: EV
        ev_load = min(fc_power, 10)

        # SELL EXTRA
        grid_sale = max(0, fc_power - ev_load)

# =========================
# 🔹 DATA LOG
# =========================
row = {
    "time": now.strftime("%H:%M:%S"),
    "pv": pv,
    "wind": wind,
    "grid_in": grid_in,
    "ev": ev_load,
    "sale": grid_sale
}
st.session_state.history = pd.concat(
    [st.session_state.history, pd.DataFrame([row])]
).tail(20)

# =========================
# 🔹 DASHBOARD
# =========================

st.title("🌐 LUMINIH2 DIGITAL TWIN")

# ---- LAYER 1 CHARTS ----
st.subheader("⚡ Energy Mix")

c1,c2,c3 = st.columns(3)

c1.metric("Solar", f"{pv:.2f} kW")
c2.metric("Wind", f"{wind:.2f} kW")
c3.metric("Grid", f"{grid_in:.2f} kW")

fig_mix = go.Figure(data=[
    go.Pie(labels=["PV","Wind","Grid"],
           values=[pv, wind, grid_in],
           hole=0.6)
])
st.plotly_chart(fig_mix, use_container_width=True)

# ---- LAYER 2 ----
st.subheader("🛢 Hydrogen Production")

st.progress(st.session_state.bess)

col1,col2 = st.columns(2)
col1.metric("Buffer", f"{st.session_state.buffer:.2f} kg")
col2.metric("Tank", f"{st.session_state.tank:.2f} kg")

# ---- LAYER 3 ----
st.subheader("🚗 Distribution")

col1,col2,col3 = st.columns(3)
col1.metric("H2 Station", f"{st.session_state.h2_station:.2f}/5 kg")
col2.metric("EV Load", f"{ev_load:.2f} kW")
col3.metric("Grid Sale", f"{grid_sale:.2f} kW")

# ---- LAYER 4 ----
st.subheader("📊 System Analytics")

fig_line = px.line(
    st.session_state.history,
    x="time",
    y=["pv","wind","grid_in","ev","sale"]
)
st.plotly_chart(fig_line, use_container_width=True)

fig_sankey = go.Figure(go.Sankey(
    node=dict(label=["Energy","BESS","Electrolyzer","Tank","H2 Station","Fuel Cell","EV","Grid"]),
    link=dict(
        source=[0,0,2,3,3,5,5],
        target=[1,2,3,4,5,6,7],
        value=[p_to_bess+1, power_pool+1, 15, 10, 8, ev_load+1, grid_sale+1]
)))
st.plotly_chart(fig_sankey, use_container_width=True)

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
