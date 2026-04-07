# =========================================
# 🚀 LUMINIH2 — LEVEL ULTRA (FINAL REAL)
# =========================================

# =============================
# 🔹 CORE MODULES (YOUR SYSTEM)
# =============================
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# ULTRA MODULES (اگر داری — اگر نه پایین fallback داریم)
try:
    from hydrogen_models import ElectrolyzerModel, CompressorModel, StorageModel
    from market_api import MarketProvider
    from ai_forecast import ForecastModel
    ULTRA_AVAILABLE = True
except:
    ULTRA_AVAILABLE = False

# =============================
# 🔹 LIBRARIES
# =============================
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import pytz
import time

# =============================
# 🔹 UI SETTINGS
# =============================
st.set_page_config(layout="wide", page_title="LUMINIH2 ULTRA")

# =============================
# 🔹 SESSION INIT
# =============================
if "init" not in st.session_state:
    st.session_state.update({
        "bess": 0.25,
        "buffer": 0.0,
        "tank": 0.0,
        "h2_station": 0.0,
        "history": pd.DataFrame(columns=[
            "time","pv","wind","grid_in","ev","sale","price","revenue"
        ]),
        "weather": WeatherProvider(),
        "solar": SolarSystem(),
        "wind_sys": WindSystem(),
        "ems": EMSBrain(),
        "init": True
    })

# ULTRA OBJECTS
if ULTRA_AVAILABLE:
    electrolyzer = ElectrolyzerModel()
    compressor = CompressorModel()
    storage = StorageModel()
    market = MarketProvider()
    forecast_model = ForecastModel()

# =============================
# 🔹 TIME
# =============================
now = datetime.now(pytz.timezone("Europe/Zagreb"))

# =========================================
# 🧠 LAYER 1 — WEATHER + ENERGY
# =========================================
w = st.session_state.weather.fetch_current_data()

irr = w.get("irradiance_raw", 0)
temp = w.get("temp", 15)
wind_speed = w.get("wind_speed", 3)

# FALLBACK (خیلی مهم)
if irr < 10:
    irr = 200

pv = st.session_state.solar.get_power_output(irr, temp, Config.PV_EFFICIENCY)
wind = st.session_state.wind_sys.get_power_output(wind_speed, Config.WIND_EFFICIENCY)

# EMS DECISION
source, p_re = st.session_state.ems.decide_energy_source(pv, wind, Config.RE_THRESHOLD)

# MARKET
if ULTRA_AVAILABLE:
    price = market.get_price()
    forecast = forecast_model.predict(pv, wind)
else:
    price = 0.15
    forecast = p_re

# GRID SUPPORT
if p_re < Config.MIN_POWER:
    grid_in = Config.GRID_SUPPORT
else:
    grid_in = 0

power_pool = p_re + grid_in

# =========================================
# ⚙️ LAYER 2 — BESS + HYDROGEN
# =========================================
# BATTERY FIRST
p_to_bess = 0
if st.session_state.bess < 0.9:
    p_to_bess = min(power_pool, Config.BESS_MAX_CHARGE)
    st.session_state.bess += 0.01
    power_pool -= p_to_bess

# ELECTROLYZER
if ULTRA_AVAILABLE:
    h2_prod = electrolyzer.produce(power_pool)
else:
    h2_prod = power_pool * 0.02

st.session_state.buffer += h2_prod

# COMPRESSOR
compressor_active = False
if st.session_state.buffer > Config.BUFFER_THRESHOLD:
    compressor_active = True

    if ULTRA_AVAILABLE:
        compressed = compressor.compress(st.session_state.buffer)
    else:
        compressed = st.session_state.buffer * 0.9

    st.session_state.buffer = 0
    st.session_state.tank += compressed

# =========================================
# 🚗 LAYER 3 — DISTRIBUTION
# =========================================
fc_power = 0
ev_load = 0
grid_sale = 0

# EV DEMAND REALISTIC
hour = now.hour
if 7 <= hour <= 10:
    ev_demand = 15
elif 17 <= hour <= 22:
    ev_demand = 18
else:
    ev_demand = 6

if st.session_state.tank > 0.5:

    # PRIORITY 1: H2 STATION
    if st.session_state.h2_station < 5:
        fill = min(0.4, st.session_state.tank)
        st.session_state.h2_station += fill
        st.session_state.tank -= fill

    else:
        # PRIORITY 2: FUEL CELL
        fc_power = Config.FC_POWER
        st.session_state.tank -= 0.2

        ev_load = min(fc_power, ev_demand)

        # MARKET SELL
        if price > Config.SELL_THRESHOLD:
            grid_sale = max(0, fc_power - ev_load)
        else:
            grid_sale = 0

# =========================================
# 📊 KPI
# =========================================
revenue = grid_sale * price

eff = (ev_load + grid_sale) / (pv + wind + grid_in + 0.001)

# =========================================
# 🧾 LOG
# =========================================
row = {
    "time": now.strftime("%H:%M:%S"),
    "pv": pv,
    "wind": wind,
    "grid_in": grid_in,
    "ev": ev_load,
    "sale": grid_sale,
    "price": price,
    "revenue": revenue
}

st.session_state.history = pd.concat(
    [st.session_state.history, pd.DataFrame([row])]
).tail(30)

# =========================================
# 🎨 UI
# =========================================
st.title("🚀 LUMINIH2 ULTRA — DIGITAL TWIN")

# --- ENERGY ---
st.subheader("⚡ Energy Layer")
c1,c2,c3 = st.columns(3)
c1.metric("PV", f"{pv:.2f} kW")
c2.metric("Wind", f"{wind:.2f} kW")
c3.metric("Grid In", f"{grid_in:.2f} kW")

# --- STORAGE ---
st.subheader("🛢 Hydrogen System")
st.progress(st.session_state.bess)
c1,c2,c3 = st.columns(3)
c1.metric("Buffer", f"{st.session_state.buffer:.2f} kg")
c2.metric("Tank", f"{st.session_state.tank:.2f} kg")
c3.metric("H2 Station", f"{st.session_state.h2_station:.2f}/5 kg")

# --- DISTRIBUTION ---
st.subheader("🚗 Demand & Grid")
c1,c2,c3 = st.columns(3)
c1.metric("EV Load", f"{ev_load:.2f} kW")
c2.metric("Grid Sale", f"{grid_sale:.2f} kW")
c3.metric("Price", f"{price:.2f} €/kWh")

# --- KPI ---
st.subheader("📊 KPI")
c1,c2 = st.columns(2)
c1.metric("Revenue", f"{revenue:.2f} €/h")
c2.metric("Efficiency", f"{eff*100:.1f}%")

# --- CHARTS ---
fig1 = px.line(st.session_state.history, x="time", y=["pv","wind","grid_in"])
st.plotly_chart(fig1, use_container_width=True)

fig2 = px.line(st.session_state.history, x="time", y=["ev","sale"])
st.plotly_chart(fig2, use_container_width=True)

fig3 = px.line(st.session_state.history, x="time", y=["price","revenue"])
st.plotly_chart(fig3, use_container_width=True)

# SANKEY (Flow)
fig4 = go.Figure(go.Sankey(
    node=dict(label=["Energy","BESS","H2","Tank","Station","FC","EV","Grid"]),
    link=dict(
        source=[0,0,2,3,3,5,5],
        target=[1,2,3,4,5,6,7],
        value=[p_to_bess+1, power_pool+1, 8,6,5,ev_load+1,grid_sale+1]
)))
st.plotly_chart(fig4, use_container_width=True)

# LOOP
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
