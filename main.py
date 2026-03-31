import streamlit as st
import pandas as pd  # اضافه شد
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

# --- ۲. اینیشیالایز کردن سیستم (فقط یکبار اجرا می‌شود) ---
if 'init' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'H2_Prod', 'Battery', 'Solar', 'Wind'])
    st.session_state.battery = BatteryBESS()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.weather = WeatherProvider()
    st.session_state.brain = EMSBrain()
    st.session_state.init = True

# --- ۳. دریافت دیتا و اجرای منطق لحظه‌ای ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance'], w['temp'])
p_wind = WindSystem().get_power_output(w['wind_speed'])
grid_price = 0.25 # قیمت لحظه‌ای

# فراخوانی مغز سیستم (هماهنگ با آخرین نسخه EMSBrain)
# توجه: متغیر p_export در اینجا برای مدیریت شبکه اضافه شده است
source, p_batt, p_elec = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)
# در نسخه جدید شما p_batt و p_elec از متد مدیریت جریان می‌آیند:
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_pv + p_wind, st.session_state.battery.soc)

# آپدیت فیزیکی دستگاه‌ها
soc = st.session_state.battery.update_soc(p_to_batt)
h2_kg, eff, recovered_heat = st.session_state.electrolyzer.calculate_production(p_to_elec)
comp_flow = st.session_state.h2_chain.manage_chain(h2_kg, Config.COMPRESSOR_POWER_KW if st.session_state.h2_chain.compressor_active else 0)

# --- ۴. نمایش در داشبورد ---
st.title("🔋 Integrated H2 Hub & E-Mobility - Zagreb")
st.markdown(f"**Live Source:** `{source}` | **Weather:** {w['temp']}°C, {w['wind_speed']}m/s")

# ردیف ۱: وضعیت لحظه‌ای (Indicators)
cols = st.columns(4)
with cols[0]:
    fig_batt = go.Figure(go.Indicator(
        mode="gauge+number",
        value=soc*100,
        title={'text': "Battery SOC %"},
        gauge={'bar': {'color': "#00ffcc"}, 'axis': {'range': [0, 100]}}))
    fig_batt.update_layout(height=250, margin=dict(t=50, b=0))
    st.plotly_chart(fig_batt, use_container_width=True)

with cols[1]:
    fig_h2 = go.Figure(go.Indicator(
        mode="gauge+number",
        value=st.session_state.h2_chain.main_tank_kg,
        title={'text': "Main Tank (kg)"},
        gauge={'axis': {'range': [0, 10.8]}, 'bar': {'color': "#3399ff"}}))
    fig_h2.update_layout(height=250, margin=dict(t=50, b=0))
    st.plotly_chart(fig_h2, use_container_width=True)

with cols[2]:
    st.metric("HRS Station", f"{st.session_state.h2_chain.h2_station_kg:.2f} / 5 kg")
    st.progress(min(st.session_state.h2_chain.h2_station_kg / 5.0, 1.0))
    st.metric("Electrolyzer Load", f"{p_to_elec:.2f} kW")

with cols[3]:
    st.metric("H2 Production", f"{h2_kg:.4f} kg/h")
    st.metric("System Efficiency", f"{eff*100:.1f}%")
    st.metric("CO2 Offset", f"{h2_kg * Config.CO2_SAVED_PER_KG_H2:.2f} kg/h")

# ردیف ۲: نمودار خطی داینامیک (Trends)
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
        source=[0, 0, 2, 3, 4, 4],
        target=[1, 2, 3, 4, 5, 6],
        value=[max(0.1, p_to_batt), max(0.1, p_to_elec), max(0.1, h2_kg*100), max(0.1, comp_flow*100), 1, 1]
    )
)])
st.plotly_chart(fig_flow, use_container_width=True)

# تکرار اجرای کد (بر اساس تایم‌استپ کانفیگ)
time.sleep(Config.TIMESTEP_SEC)
st.rerun()