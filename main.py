# main.py (Industrial Operator Edition)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain
from ems_brain import EMSBrain
import pytz  # این را در ابتدای فایل اضافه کنید

# --- در بخش محاسبات یا بدنه اصلی کد ---
# تنظیم منطقه زمانی زاگرب
zagreb_tz = pytz.timezone('Europe/Zagreb')
now_zagreb = datetime.now(zagreb_tz)

# --- در بخش Header (جایی که ساعت چاپ می‌شود) ---
with header_l:
    st.markdown(f"""
        <div class="status-card">
            <span style="color: #8b949e; font-size: 14px;">📍 HUB LOCATION: ZAGREB, CROATIA</span><br>
            <span style="font-size: 26px; font-weight: bold; color: #ffffff;">{now_zagreb.strftime('%H:%M:%S')}</span>
            <span style="color: #58a6ff; margin-left: 10px;">{now_zagreb.strftime('%A, %d %B %Y')}</span>
            <hr style="margin: 10px 0; border-color: #30363d;">
            <span style="color: #8b949e;">WEATHER:</span> 
            <b>{w['temp']}°C</b> | 💧 {w['humidity']}% | ☀️ {w['irradiance_raw']:.1f} W/m² | 🌬️ {w['wind_speed']} m/s
        </div>
    """, unsafe_allow_html=True)

# --- ۱. تنظیمات ظاهری صنعتی (Dark Steel Theme) ---
st.set_page_config(page_title="H2 Hub Zagreb | Control Room", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; }
    .stMetric { background-color: #1c2128; border-left: 5px solid #00ffcc; border-radius: 4px; padding: 10px; }
    div[data-testid="stExpander"] { background-color: #1c2128; border: none; }
    .source-tag { padding: 5px 15px; border-radius: 20px; font-weight: bold; font-family: 'Courier New'; }
    </style>
    """, unsafe_allow_html=True)

# --- ۲. مقداردهی اولیه سیستم ---
if 'init' not in st.session_state:
    st.session_state.battery = BatteryBESS()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.weather = WeatherProvider()
    st.session_state.brain = EMSBrain()
    st.session_state.history = pd.DataFrame()
    st.session_state.init = True

# --- ۳. دریافت داده‌های زنده و محاسبات ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], w['soiling_factor'])
p_wind = WindSystem().get_power_output(w['wind_speed'], w['turbulence'])

# منطق سوئیچینگ منبع (Logic-Driven Switching)
source_name, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_available, st.session_state.battery.soc)

# بروزرسانی دارایی‌ها
batt_data = st.session_state.battery.update_state(p_to_batt)
elec_out = st.session_state.electrolyzer.calculate_production(p_to_elec, w['temp'])
logistics = st.session_state.h2_chain.manage_chain(elec_out['h2_kg_h'])

# --- ۴. بخش بالایی: اطلاعات آب و هوا و زمان (مورد ۱) ---
top_l, top_r = st.columns([1, 2])

with top_l:
    st.markdown(f"""
        <div style="background-color: #1c2128; padding: 15px; border-radius: 8px; border: 1px solid #30363d;">
            <h4 style="margin:0; color: #8b949e;">📍 ZAGREB HUB TELEMETRY</h4>
            <h2 style="margin:0; color: #ffffff;">{datetime.now().strftime('%H:%M:%S')}</h2>
            <p style="margin:0; color: #58a6ff;">{datetime.now().strftime('%A, %d %B %Y')}</p>
            <hr style="margin:10px 0; border-color: #30363d;">
            <p style="margin:0;">🌡️ Temp: <b>{w['temp']}°C</b> | 💧 Hum: <b>{w['humidity']}%</b></p>
            <p style="margin:0;">☀️ Irrad: <b>{w['irradiance_raw']:.1f} W/m²</b> | 🌬️ Wind: <b>{w['wind_speed']} m/s</b></p>
        </div>
    """, unsafe_allow_html=True)

with top_r:
    # نمایش منبع انرژی فعال با رنگ اختصاصی (مورد ۲)
    colors = {"Solar (PV)": "#ffcc00", "Wind Turbine": "#00d4ff", "National Grid": "#ff4b4b"}
    src_color = colors.get(source_name, "#ffffff")
    st.markdown(f"""
        <div style="text-align: right;">
            <span style="color: #8b949e;">ACTIVE ENERGY SOURCE:</span><br>
            <span class="source-tag" style="background-color: {src_color}22; color: {src_color}; border: 1px solid {src_color}; font-size: 24px;">
                ● {source_name.upper()}
            </span>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- ۵. ردیف میانی: شاخص‌های کلیدی و نمودارهای متنوع (مورد ۳) ---
col1, col2, col3 = st.columns([1, 1, 1.5])

with col1:
    st.subheader("⚡ Power Balance")
    # نمودار میله‌ای برای توزیع توان
    fig_power = go.Figure(go.Bar(
        x=['From Source', 'To Battery', 'To Electrolyzer'],
        y=[p_available, abs(p_to_batt), p_to_elec],
        marker_color=[src_color, '#00ffcc', '#3399ff']
    ))
    fig_power.update_layout(height=300, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_power, use_container_width=True)

with col2:
    st.subheader("🔋 Storage Status")
    # نمودار دایره‌ای برای SOC باتری
    fig_soc = go.Figure(go.Pie(
        labels=['Used', 'Available'], 
        values=[1-batt_data['soc'], batt_data['soc']],
        hole=.7,
        marker_colors=['#161b22', '#00ffcc'],
        showlegend=False
    ))
    fig_soc.add_annotation(text=f"{batt_status['soc']*100:.1f}%", x=0.5, y=0.5, showarrow=False, font_size=20)
    fig_soc.update_layout(height=300, margin=dict(t=0, b=0), paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_soc, use_container_width=True)

with col3:
    st.subheader("🧪 H2 Production & Pressure")
    # نمودار خطی فشار تانک
    new_entry = {'Time': datetime.now().strftime('%H:%M:%S'), 'Pressure': logistics['pressure_bar'], 'H2_Rate': elec_out['h2_kg_h']}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_entry])], ignore_index=True).iloc[-20:]
    
    fig_h2 = go.Figure()
    fig_h2.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Pressure'], name="Pressure (bar)", line=dict(color='#3399ff', width=3)))
    fig_h2.update_layout(height=300, template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_h2, use_container_width=True)

# --- ۶. ردیف پایینی: جزئیات لجستیک و سلامت (مورد ۴) ---
st.subheader("⚙️ Industrial Asset Diagnostics")
bot1, bot2, bot3, bot4 = st.columns(4)

bot1.metric("Electrolyzer SOH", f"{elec_out['soh']:.2%}", delta="-0.01% daily")
bot2.metric("Gas Purity", f"{elec_out['purity']:.4f}%", "Optimal")
bot3.metric("Water Demand", f"{elec_out['water_l_h']:.2f} L/h")
bot4.metric("Tank Temp", f"{logistics['temp_c']:.1f} °C")

# تکرار حلقه
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
