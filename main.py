# main.py (Zagreb H2 Hub - Phase 1: Environmental & Source Switching)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import pytz 

# ایمپورت ماژول‌های پروژه (فرضی بر اساس ساختار قبلی شما)
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem
from ems_brain import EMSBrain

# --- ۱. تنظیمات ظاهری (Clean Light Theme) ---
st.set_page_config(page_title="H2 Hub Zagreb | Source Control", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; color: #1e293b; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #0ea5e9; border-radius: 8px; padding: 10px; }
    .status-card { background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .source-tag { padding: 5px 15px; border-radius: 20px; font-weight: bold; font-family: 'Segoe UI', sans-serif; }
    h1, h2, h3, h4, p, span { color: #1e293b !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ۲. مقداردهی اولیه سیستم ---
if 'init' not in st.session_state:
    st.session_state.weather = WeatherProvider()
    st.session_state.brain = EMSBrain()
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'Source'])
    st.session_state.init = True

# تنظیم منطقه زمانی زاگرب
zagreb_tz = pytz.timezone('Europe/Zagreb')
now_zagreb = datetime.now(zagreb_tz)

# تنظیمات بصری نمودارها
plotly_layout = dict(
    height=300, template="plotly_white", paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=30, l=0, r=0),
    font=dict(color='#1e293b')
)

# --- ۳. دریافت داده‌های محیطی و محاسبات سوئیچینگ ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], w['soiling_factor'])
p_wind = WindSystem().get_power_output(w['wind_speed'], w['turbulence'])

# منطق سوئیچینگ: اولویت با خورشید، سپس باد و در نهایت شبکه
source_name, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, soc=0.5) # SOC فرضی برای فاز ۱

# ذخیره در تاریخچه برای نمودارهای خطی
new_entry = {
    'Time': now_zagreb.strftime('%H:%M:%S'),
    'Solar': p_pv,
    'Wind': p_wind,
    'Source': source_name
}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_entry])], ignore_index=True).iloc[-20:]

# --- ۴. نمایش لایه ۱: ورودی‌های محیطی زاگرب ---
st.header("🌐 Layer 1: Atmospheric Inputs & AI Source Switching")

top_col1, top_col2, top_col3 = st.columns(3)

with top_col1:
    st.metric("Solar Irradiance", f"{w['irradiance_raw']:.1f} W/m²", delta=f"{w['temp']} °C")
    st.write("**Solar Power Potential (kW)**")
    st.line_chart(st.session_state.history.set_index('Time')['Solar'], height=120, use_container_width=True)

with top_col2:
    st.metric("Wind Speed", f"{w['wind_speed']:.1f} m/s", delta="Stable" if w['turbulence'] < 0.1 else "Turbulent")
    st.write("**Wind Power Potential (kW)**")
    st.line_chart(st.session_state.history.set_index('Time')['Wind'], height=120, use_container_width=True)

with top_col3:
    reliability = 100 - (w['turbulence'] * 100)
    st.markdown(f"""
        <div class="status-card">
            <h4 style="margin:0; color: #64748b; font-size: 13px;">📍 ZAGREB TELEMETRY</h4>
            <h2 style="margin:0; font-weight: 800;">{now_zagreb.strftime('%H:%M:%S')}</h2>
            <hr style="margin:10px 0; border-color: #e2e8f0;">
            <p style="margin:0; font-size: 14px;">Source Reliability: <b>{reliability:.1f}%</b></p>
            <p style="margin:0; font-size: 14px; color: #0ea5e9;">AI Forecast: <b>Stable Production</b></p>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- ۵. نمایش منطق سوئیچینگ توان (Active Source) ---
logic_col1, logic_col2 = st.columns([2, 1])

with logic_col1:
    st.subheader("🔌 Active Power Source Allocation")
    
    # آماده‌سازی داده برای نمودار میله‌ای سوئیچینگ
    y_vals = [
        p_pv if source_name == "Solar (PV)" else 0,
        p_wind if source_name == "Wind Turbine" else 0,
        p_available if source_name == "National Grid" else 0
    ]
    
    fig_switch = go.Figure(go.Bar(
        x=['Solar PV', 'Wind Turbine', 'National Grid'],
        y=y_vals,
        marker_color=['#f59e0b', '#0ea5e9', '#ef4444'],
        text=[f"{v:.1f} kW" if v > 0 else "" for v in y_vals],
        textposition='outside'
    ))
    fig_switch.update_layout(**plotly_layout, yaxis_title="Allocated Power (kW)")
    st.plotly_chart(fig_switch, use_container_width=True)

with logic_col2:
    st.subheader("💡 System Decision")
    
    # نمایش کارت وضعیت منبع فعلی
    colors = {"Solar (PV)": "#f59e0b", "Wind Turbine": "#0ea5e9", "National Grid": "#ef4444"}
    src_color = colors.get(source_name, "#1e293b")
    
    st.markdown(f"""
        <div style="background-color: {src_color}10; border: 2px solid {src_color}; padding: 20px; border-radius: 10px; text-align: center;">
            <p style="margin:0; color: #64748b; font-size: 12px; font-weight: bold;">CURRENT FEED</p>
            <h3 style="margin:5px 0; color: {src_color};">{source_name.upper()}</h3>
            <p style="margin:0; font-size: 18px; font-weight: bold;">{p_available:.2f} kW</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    if source_name == "National Grid":
        st.error("RE Sources insufficient. Grid bypass active.")
    else:
        st.success("Operating on 100% Renewable Energy.")

# تکرار شبیه‌سازی بر اساس گام زمانی تعریف شده
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
