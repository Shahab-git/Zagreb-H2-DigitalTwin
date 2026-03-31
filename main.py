import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import numpy as np
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell

# --- تنظیمات بصری ---
st.set_page_config(page_title="H2 Hub Zagreb - Dynamic Twin", layout="wide")
st.markdown("<style> .main {background-color: #000000;} </style>", unsafe_allow_html=True)

# --- اینیشیالایز کردن سیستم ---
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'H2_Prod', 'Battery', 'Solar', 'Wind'])
    st.session_state.battery = BatteryBESS()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.weather = WeatherProvider()

# --- لایه دریافت دیتا و محاسبات ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance'], w['temp'])
p_wind = WindSystem().get_power_output(w['wind_speed'])
grid_price = 0.25 # قیمت لحظه‌ای فرضی

# اجرای مغز سیستم
from ems_brain import EMSBrain
brain = EMSBrain()
source, p_batt, p_elec, p_export = brain.decide_and_route(p_pv, p_wind, st.session_state.battery.soc, st.session_state.h2_chain.main_tank_kg, grid_price)

# آپدیت فیزیکی دستگاه‌ها
soc = st.session_state.battery.update_soc(p_batt)
h2_kg, eff, _ = ElectrolyzerS30().calculate_production(p_to_elec)
comp_flow = st.session_state.h2_chain.manage_chain(h2_kg, Config.COMPRESSOR_POWER_KW if st.session_state.h2_chain.compressor_active else 0)

# --- نمایش در داشبورد ---
st.title("🔋 Integrated H2 Hub & E-Mobility - Zagreb")

# ردیف ۱: وضعیت لحظه‌ای (Gauges)
cols = st.columns(4)
with cols[0]:
    fig_batt = go.Figure(go.Indicator(mode="gauge+number", value=soc*100, title={'text': "Battery SOC %"}, gauge={'bar': {'color': "#00ffcc"}}))
    fig_batt.update_layout(height=250, margin=dict(t=30, b=0))
    st.plotly_chart(fig_batt, use_container_width=True)

with cols[1]:
    fig_h2 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.h2_chain.main_tank_kg, title={'text': "Main Tank (kg)"}, gauge={'axis': {'range': [0, 10.8]}, 'bar': {'color': "#3399ff"}}))
    fig_h2.update_layout(height=250, margin=dict(t=30, b=0))
    st.plotly_chart(fig_h2, use_container_width=True)

with cols[2]:
    st.metric("HRS Station", f"{st.session_state.h2_chain.h2_station_kg:.2f} / 5 kg")
    st.progress(st.session_state.h2_chain.h2_station_kg / 5.0)
    st.metric("Grid Price", f"€{grid_price}/kWh")

with cols[3]:
    st.metric("Total CO2 Saved", f"{h2_kg * 22:.2f} kg")
    st.metric("System Efficiency", f"{eff*100:.1f}%")

# ردیف ۲: نمودار خطی داینامیک (Trends)
st.subheader("📈 Real-time System Trends")
# (اضافه کردن دیتا به تاریخچه و نمایش نمودار)
new_entry = {'Time': time.strftime('%H:%M:%S'), 'H2_Prod': h2_kg, 'Battery': soc*100, 'Solar': p_pv}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_entry])]).iloc[-20:]
st.line_chart(st.session_state.history.set_index('Time'))

# ردیف ۳: فلوچارت جریان انرژی (Sankey Diagram)
st.subheader("🔄 Energy & Mass Flow Architecture")

fig_flow = go.Figure(data=[go.Sankey(
    node = dict(pad=15, thickness=20, label=[source, "Battery", "Electrolyzer", "Buffer", "Main Tank", "HRS", "Fuel Cell", "EV Station", "Grid Export"]),
    link = dict(source=[0, 0, 2, 3, 4, 4, 6, 6], target=[1, 2, 3, 4, 5, 6, 7, 8], value=[abs(p_batt), p_elec, h2_kg*100, comp_flow*100, 5, 2, 3, 1])
)])
st.plotly_chart(fig_flow, use_container_width=True)

time.sleep(2)
st.rerun()