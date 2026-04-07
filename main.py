# main.py - Zagreb H2 Hub Full Roadmap Integration
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz

# فرض بر برقرار بودن ماژول‌های زیر
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain
from ems_brain import EMSBrain

# --- ۱. تنظیمات ظاهری ---
st.set_page_config(page_title="Zagreb Integrated H2 Hub", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
    .layer-header { background-color: #0ea5e9; color: white; padding: 10px; border-radius: 5px; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- ۲. مدیریت وضعیت سیستم (Session State) ---
if 'init' not in st.session_state:
    st.session_state.battery = BatteryBESS() # فرض بر وجود کلاس
    st.session_state.history = pd.DataFrame()
    st.session_state.buffer_level = 0.0
    st.session_state.main_tank_kg = 0.0
    st.session_state.h2_station_kg = 0.0
    st.session_state.init = True

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- ۳. دریافت داده‌ها و منطق لایه‌بندی شده (Simulation Logic) ---
w = WeatherProvider().fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], 0.9)
p_wind = WindSystem().get_power_output(w['wind_speed'], 0.05)

# لایه ۱: سوئیچینگ قدرت
source_name, p_total = EMSBrain().decide_energy_source(p_pv, p_wind, 0.5)

# لایه ۲: اولویت باتری و سپس الکترولایزر
p_to_battery = min(p_total, 10.0) # فرض: حداکثر ۱۰ کیلووات برای شارژ باتری
p_to_electrolyzer = max(0, p_total - p_to_battery)

# شبیه‌سازی تولید هیدروژن و بافر
h2_gen = p_to_electrolyzer * 0.02 # ضریب فرضی تولید
st.session_state.buffer_level += h2_gen
compressor_active = False
if st.session_state.buffer_level > 5.0: # حد آستانه بافر
    compressor_active = True
    st.session_state.buffer_level -= 2.0
    st.session_state.main_tank_kg += 1.8

# لایه ۳: توزیع هیدروژن (ابتدا ایستگاه سوخت، سپس پیل سوختی)
fc_power = 0.0
grid_export = 0.0
if st.session_state.main_tank_kg > 0.5:
    if st.session_state.h2_station_kg < 5.0:
        st.session_state.h2_station_kg += 0.5
        st.session_state.main_tank_kg -= 0.5
    else:
        # هیدروژن مازاد برای پیل سوختی
        fc_power = 8.0 # تولید ۸ کیلووات
        st.session_state.main_tank_kg -= 0.3
        ev_station_load = 5.0
        grid_export = max(0, fc_power - ev_station_load)

# --- ۴. رندر کردن داشبورد لایه به لایه ---

# --- لایه ۱ ---
st.markdown('<div class="layer-header">🌐 لایه ۱: ورودی‌های محیطی و سوئیچینگ منبع</div>', unsafe_allow_html=True)
c1_1, c1_2, c1_3 = st.columns(3)
c1_1.metric("Solar (Zagreb)", f"{w['irradiance_raw']:.1f} W/m²")
c1_2.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s")
c1_3.info(f"منبع فعال: {source_name}")

# --- لایه ۲ ---
st.markdown('<div class="layer-header">🔋 لایه ۲: مدیریت باتری و زنجیره تولید H2</div>', unsafe_allow_html=True)
c2_1, c2_2, c2_3 = st.columns(3)
with c2_1:
    st.write("وضعیت باتری (BESS)")
    st.progress(0.7) # فرضی
    st.caption(f"توان ورودی به باتری: {p_to_battery:.1f} kW")
with c2_2:
    st.write("سطح مخزن بافر")
    st.progress(min(st.session_state.buffer_level/10, 1.0))
    st.write(f"کمپرسور: {'🟢 روشن' if compressor_active else '🔴 خاموش'}")
with c2_3:
    st.metric("مخزن اصلی هیدروژن", f"{st.session_state.main_tank_kg:.2f} kg")

# --- لایه ۳ ---
st.markdown('<div class="layer-header">🚗 لایه ۳: لجستیک سوخت و ایستگاه EV</div>', unsafe_allow_html=True)
c3_1, c3_2, c3_3 = st.columns(3)
c3_1.metric("مخزن ایستگاه سوخت (۵kg)", f"{st.session_state.h2_station_kg:.2f} kg")
c3_2.metric("خروجی پیل سوختی", f"{fc_power} kW")
c3_3.metric("صادرات به شبکه (Grid)", f"{grid_export} kW", delta="درآمدزایی فعال")

# --- لایه ۴ ---
st.markdown('<div class="layer-header">📊 لایه ۴: تحلیل‌های پیشرفته و بازیافت حرارت</div>', unsafe_allow_html=True)
c4_1, c4_2 = st.columns([2, 1])
with c4_1:
    # نمودار Sankey برای نمایش جریان انرژی
    fig_sankey = go.Figure(go.Sankey(
        node=dict(label=["Renewables", "Battery", "Electrolyzer", "H2 Tank", "Fuel Cell", "EV Station", "Grid"]),
        link=dict(source=[0, 0, 2, 3, 4, 4], target=[1, 2, 3, 4, 5, 6], value=[p_to_battery, p_to_electrolyzer, 20, 10, 5, 2])
    ))
    fig_sankey.update_layout(title_text="نقشه جریان انرژی (Sankey)", font_size=10, height=300)
    st.plotly_chart(fig_sankey, use_container_width=True)

with c4_2:
    st.metric("حرارت بازیافتی (Heat Recovery)", "4.2 kWt")
    st.metric("کاهش لحظه‌ای CO2", "1.2 kg/hr")

# تکرار شبیه‌سازی
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
