import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
import numpy as np
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain

# --- ۱. تنظیمات بصری ---
st.set_page_config(page_title="H2 Hub Zagreb - Dynamic Twin", layout="wide")

# --- ۲. اینیشیالایز کردن سیستم (فقط یکبار در شروع برنامه) ---
if 'init' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'H2_Prod', 'Battery', 'Solar', 'Wind'])
    st.session_state.battery = BatteryBESS()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.weather = WeatherProvider()
    st.session_state.brain = EMSBrain()
    st.session_state.init = True

# --- ۳. دریافت دیتا و اجرای محاسبات موتور فیزیکی ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance'], w['temp'])
p_wind = WindSystem().get_power_output(w['wind_speed'])

# الف) انتخاب منبع انرژی (فقط ۲ خروجی طبق ems_brain)
source, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)

# ب) مدیریت جریان توان (باتری و الکترولایزر)
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_available, st.session_state.battery.soc)

# ج) آپدیت وضعیت فیزیکی دستگاه‌ها
soc = st.session_state.battery.update_soc(p_to_batt)
h2_kg, eff, recovered_heat = st.session_state.electrolyzer.calculate_production(p_to_elec)

# د) مدیریت لجستیک هیدروژن
comp_status, dispatch = st.session_state.brain.hydrogen_logistics_control(
    st.session_state.h2_chain.buffer_kg,
    st.session_state.h2_chain.main_tank_kg,
    st.session_state.h2_chain.h2_station_kg
)
comp_flow = st.session_state.h2_chain.manage_chain(h2_kg, Config.COMPRESSOR_POWER_KW if comp_status == "ON" else 0)

# --- ۴. طراحی داشبورد بصری ---
st.title("🔋 Integrated H2 Hub & E-Mobility - Zagreb")
st.markdown(f"**Live Source:** `{source}` | **Weather:** {w['temp']}°C | **Wind:** {w['wind_speed']} m/s")

# ردیف ۱: شاخص‌های کلیدی (Gauges & Metrics)
cols = st.columns(4)
with cols[0]:
    fig_batt = go.Figure(go.Indicator(
        mode="gauge+number", value=soc*100,
        title={'text': "Battery SOC %"},
        gauge={'bar': {'color': "#00ffcc"}, 'axis': {'range': [0, 100]}}))
    fig_batt.update_layout(height=250, margin=dict(t=50, b=0))
    st.plotly_chart(fig_batt, use_container_width=True)

with cols[1]:
    fig_h2 = go.Figure(go.Indicator(
        mode="gauge+number", value=st.session_state.h2_chain.main_tank_kg,
        title={'text': "Main Tank (kg)"},
        gauge={'axis': {'range': [0, 10.8]}, 'bar': {'color': "#3399ff"}}))
    fig_h2.update_layout(height=250, margin=dict(t=50, b=0))
    st.plotly_chart(fig_h2, use_container_width=True)

with cols[2]:
    st.metric("HRS Station Status", f"{st.session_state.h2_chain.h2_station_kg:.2f} / 5 kg")
    st.progress(min(st.session_state.h2_chain.h2_station_kg / 5.0, 1.0))
    st.metric("Compressor Status", comp_status)

with cols[3]:
    st.metric("H2 Production Rate", f"{h2_kg:.4f} kg/h")
    st.metric("System Efficiency", f"{eff*100:.1f}%")
    st.metric("Active Dispatch", dispatch)

# ردیف ۲: نمودار روندهای لحظه‌ای (Real-time Trends)
st.subheader("📈 Real-time System Trends")
new_entry = pd.DataFrame([{
    'Time': time.strftime('%H:%M:%S'),
    'H2_Prod': h2_kg,
    'Battery': soc*100,
    'Solar': p_pv,
    'Wind': p_wind
}])
st.session_state.history = pd.concat([st.session_state.history, new_entry], ignore_index=True).iloc[-30:]
st.line_chart(st.session_state.history.set_index('Time'))

# ردیف ۳: فلوچارت جریان (Sankey)
st.subheader("🔄 Energy & Mass Flow Architecture")
fig_flow = go.Figure(data=[go.Sankey(
    node = dict(pad=15, thickness=20, label=[source, "Battery", "Electrolyzer", "Buffer", "Main Tank", "HRS", "Fuel Cell", "EV Station", "Grid Export"]),
    link = dict(
        source=[0, 0, 2, 3, 4, 4], # مسیرهای جریان
        target=[1, 2, 3, 4, 5, 6], # گره‌های مقصد
        value=[max(0.1, abs(p_to_batt)), max(0.1, p_to_elec), max(0.1, h2_kg*100), max(0.1, comp_flow*100), 1, 1]
    )
)])
st.plotly_chart(fig_flow, use_container_width=True)

# تکرار حلقه شبیه‌سازی
time.sleep(Config.TIMESTEP_SEC)
st.rerun()