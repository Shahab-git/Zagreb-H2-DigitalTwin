import streamlit as st
import time
import pandas as pd
import plotly.graph_objects as go
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from forecaster_ai import AIPredictor

# --- ۱. تنظیمات اولیه و کش کردن آبجکت‌ها ---
st.set_page_config(page_title="H2 Digital Twin Zagreb", layout="wide", initial_sidebar_state="expanded")

if 'init' not in st.session_state:
    st.session_state.solar = SolarSystem()
    st.session_state.wind = WindSystem()
    st.session_state.battery = BatteryBESS()
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.fc = FuelCellAircell()
    st.session_state.brain = EMSBrain()
    st.session_state.weather = WeatherProvider()
    st.session_state.ai = AIPredictor()
    st.session_state.init = True
    st.session_state.history = []

# --- ۲. دریافت دیتای زنده و اجرای منطق ---
w = st.session_state.weather.fetch_current_data()
p_pv = st.session_state.solar.get_power_output(w['irradiance'], w['temp'])
p_wind = st.session_state.wind.get_power_output(w['wind_speed'])

# تصمیم‌گیری منبع انرژی
source, p_total = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)

# مدیریت باتری و توان ورودی به الکترولایزر
p_to_batt, p_to_elec = st.session_state.brain.manage_battery_and_electrolyzer(p_total, st.session_state.battery.soc)
new_soc = st.session_state.battery.update_soc(p_to_batt)

# تولید هیدروژن و مدیریت زنجیره فشرده‌سازی
h2_kg, eff, heat = st.session_state.electrolyzer.calculate_production(p_to_elec)
comp_flow = st.session_state.h2_chain.manage_chain(h2_kg, Config.COMPRESSOR_POWER_KW if st.session_state.h2_chain.compressor_active else 0)

# --- ۳. طراحی داشبورد خفن ---
st.title("🔋 Zagreb Hydrogen Hub: Integrated Digital Twin")
st.markdown(f"**Location:** {Config.LOCATION['city']} | **Status:** 🟢 Online | **Power Source:** `{source}`")

# ردیف ۱: شاخص‌های کلیدی انرژی
col1, col2, col3, col4 = st.columns(4)
col1.metric("Solar Irradiance", f"{w['irradiance']:.1f} W/m²")
col2.metric("PV Power", f"{p_pv:.2f} kW")
col3.metric("Wind Power", f"{p_wind:.2f} kW")
col4.metric("Battery SOC", f"{new_soc*100:.1f}%", delta=f"{p_to_batt:.2f} kW")

# ردیف ۲: زنجیره هیدروژن
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Electrolyzer Load", f"{p_to_elec:.2f} kW")
c2.metric("H2 Production", f"{h2_kg:.4f} kg/h")
c3.metric("Buffer Tank", f"{(st.session_state.h2_chain.buffer_kg/Config.BUFFER_TANK_CAPACITY_KG)*100:.1f}%")
c4.metric("Compressor", "ON" if st.session_state.h2_chain.compressor_active else "OFF")

# ردیف ۳: توزیع و مخزن اصلی
st.divider()
d1, d2, d3, d4 = st.columns(4)
d1.metric("Main Tank (10.8kg)", f"{st.session_state.h2_chain.main_tank_kg:.2f} kg")
d2.metric("HRS Station", f"{st.session_state.h2_chain.h2_station_kg:.1f} / 5.0 kg")
d3.metric("System Efficiency", f"{eff*100:.1f}%")
d4.metric("CO2 Saved", f"{st.session_state.brain.calculate_environmental_impact(h2_kg):.2f} kg/h")

# نمودار جریان انرژی (Sankey)
st.subheader("📊 Energy Flow Mapping")
fig = go.Figure(data=[go.Sankey(
    node = dict(pad = 15, thickness = 20, line = dict(color = "black", width = 0.5),
      label = ["Source", "Battery", "Electrolyzer", "Buffer", "Main Tank"],
      color = ["#00d4ff", "#00fbff", "#94f7d3", "#42f59e", "#10b981"]),
    link = dict(source = [0, 0, 2, 3], target = [1, 2, 3, 4],
      value = [abs(p_to_batt), p_to_elec, h2_kg*100, comp_flow*100]))])
st.plotly_chart(fig, use_container_width=True)

# دکمه‌های کنترلی در سایدبار
st.sidebar.header("🕹️ System Control")
if st.sidebar.button("Manual START"):
    st.sidebar.success("Signal Sent to MQTT: START")
if st.sidebar.button("Manual STOP"):
    st.sidebar.error("Signal Sent to MQTT: STOP")

# رفرش خودکار صفحه برای حالت Real-time
time.sleep(Config.TIMESTEP_SEC)
st.rerun()