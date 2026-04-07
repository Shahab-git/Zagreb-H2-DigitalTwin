# main.py - Zagreb H2 Hub (Corrected EV Flow Edition)
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
    .layer-header { background-color: #0ea5e9; color: white; padding: 10px; border-radius: 5px; margin-top: 20px; margin-bottom: 15px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- ۲. مدیریت وضعیت سیستم (Session State) ---
if 'init' not in st.session_state:
    st.session_state.battery = BatteryBESS() 
    st.session_state.history = pd.DataFrame()
    st.session_state.buffer_level = 0.0
    st.session_state.main_tank_kg = 0.0
    st.session_state.h2_station_kg = 0.0
    st.session_state.init = True

now_zagreb = datetime.now(pytz.timezone('Europe/Zagreb'))

# --- ۳. منطق محاسباتی لایه‌بندی شده ---
w = WeatherProvider().fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], 0.9)
p_wind = WindSystem().get_power_output(w['wind_speed'], 0.05)

# لایه ۱: سوئیچینگ منبع (خورشید > باد > شبکه)
source_name, p_total = EMSBrain().decide_energy_source(p_pv, p_wind, 0.5)

# لایه ۲: اولویت با شارژ باتری، سپس الکترولایزر
p_to_battery = min(p_total, 10.0) 
p_to_electrolyzer = max(0, p_total - p_to_battery)

# تولید H2 و مدیریت بافر و کمپرسور
h2_gen = p_to_electrolyzer * 0.02 
st.session_state.buffer_level += h2_gen
compressor_active = False
if st.session_state.buffer_level > 5.0:
    compressor_active = True
    st.session_state.buffer_level -= 2.0
    st.session_state.main_tank_kg += 1.8

# لایه ۳: اولویت ایستگاه سوخت H2، سپس پیل سوختی برای ایستگاه EV
fc_power_out = 0.0
ev_charging_load = 0.0
grid_export = 0.0

if st.session_state.main_tank_kg > 0.5:
    if st.session_state.h2_station_kg < 5.0:
        # اولویت ۱: پر کردن مخزن ۵ کیلویی ایستگاه سوخت
        st.session_state.h2_station_kg += 0.5
        st.session_state.main_tank_kg -= 0.5
    else:
        # اولویت ۲: فعال‌سازی پیل سوختی با هیدروژن مازاد
        fc_power_out = 15.0 # توان تولیدی پیل سوختی (kW)
        st.session_state.main_tank_kg -= 0.4
        
        # تغذیه ایستگاه EV از طریق پیل سوختی
        ev_capacity_need = 10.0 # نیاز لحظه‌ای ایستگاه EV
        ev_charging_load = min(fc_power_out, ev_capacity_need)
        
        # فروش مازاد برق پیل سوختی به شبکه
        grid_export = max(0, fc_power_out - ev_charging_load)

# --- ۴. نمایش خروجی ---

# لایه ۱
st.markdown('<div class="layer-header">🌐 لایه ۱: تأمین توان و سوئیچینگ هوشمند</div>', unsafe_allow_html=True)
c1_1, c1_2, c1_3 = st.columns(3)
c1_1.metric("Solar Irradiance", f"{w['irradiance_raw']:.1f} W/m²")
c1_2.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s")
c1_3.info(f"منبع اصلی فعال: {source_name}")

# لایه ۲
st.markdown('<div class="layer-header">🔋 لایه ۲: ذخیره‌ساز باتری و زنجیره تولید هیدروژن</div>', unsafe_allow_html=True)
c2_1, c2_2, c2_3 = st.columns(3)
with c2_1:
    st.write("وضعیت شارژ باتری (BESS)")
    st.progress(0.75)
    st.caption(f"Power to BESS: {p_to_battery:.1f} kW")
with c2_2:
    st.write("سطح مخزن بافر")
    st.progress(min(st.session_state.buffer_level/10, 1.0))
    st.write(f"وضعیت کمپرسور: {'🟢 فعال' if compressor_active else '⚪ غیرفعال'}")
with c2_3:
    st.metric("ذخیره مخزن اصلی", f"{st.session_state.main_tank_kg:.2f} kg", delta="H2 High Pressure")

# لایه ۳
st.markdown('<div class="layer-header">🚗 لایه ۳: لجستیک H2 و تأمین برق ایستگاه EV</div>', unsafe_allow_html=True)
c3_1, c3_2, c3_3 = st.columns(3)
c3_1.metric("ایستگاه سوخت (۵kg)", f"{st.session_state.h2_station_kg:.2f} kg", "Priority 1")
with c3_2:
    st.metric("خروجی پیل سوختی", f"{fc_power_out:.1f} kW")
    st.caption("برق تولیدی جهت ایستگاه EV")
with c3_3:
    st.metric("توان تحویلی به EV Station", f"{ev_charging_load:.1f} kW")
    if grid_export > 0:
        st.write(f"⚡ صادرات مازاد به شبکه: **{grid_export:.1f} kW**")

# لایه ۴
st.markdown('<div class="layer-header">📊 لایه ۴: نقشه جریان انرژی و شاخص‌های پایداری</div>', unsafe_allow_html=True)
c4_1, c4_2 = st.columns([2, 1])
with c4_1:
    # اصلاح نمودار Sankey: Renewables -> BESS/Elec -> Tank -> FC -> EV/Grid
    fig_sankey = go.Figure(go.Sankey(
        node=dict(label=["تجدیدپذیر", "باتری", "الکترولایزر", "مخزن H2", "پیل سوختی", "ایستگاه EV", "شبکه"], color="#0ea5e9"),
        link=dict(
            source=[0, 0, 2, 3, 4, 4], # مسیرها
            target=[1, 2, 3, 4, 5, 6], # مقصدها
            value=[p_to_battery, p_to_electrolyzer, 25, 15, ev_charging_load, grid_export]
        )
    ))
    fig_sankey.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=20))
    st.plotly_chart(fig_sankey, use_container_width=True)

with c4_2:
    st.metric("حرارت بازیافت شده", "5.4 kWt", "از الکترولایزر و FC")
    st.metric("کاهش انتشار CO2", "1.45 kg/hr")
    st.info("System Status: Carbon Neutral")

time.sleep(Config.TIMESTEP_SEC)
st.rerun()
