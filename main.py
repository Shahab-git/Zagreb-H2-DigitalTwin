# main.py (Zagreb H2 Hub - Unified Digital Twin)
# Version: 5.0 | Theme: Light Industrial | Location: Zagreb, Croatia

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import pytz 

# ایمپورت ماژول‌های پروژه (مطمئن شوید این فایل‌ها در کنار main.py هستند)
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain
from ems_brain import EMSBrain

# --- ۱. تنظیمات ظاهری (Clean Light Theme) ---
st.set_page_config(page_title="H2 Hub Zagreb | Control Room", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; color: #1e293b; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #0ea5e9; border-radius: 8px; padding: 10px; }
    div[data-testid="stExpander"] { background-color: #f1f5f9; border: 1px solid #e2e8f0; }
    .source-tag { padding: 5px 15px; border-radius: 20px; font-weight: bold; font-family: 'Segoe UI', sans-serif; }
    .status-card { background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    h1, h2, h3, h4, p, span { color: #1e293b !important; }
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

# تنظیم منطقه زمانی زاگرب
zagreb_tz = pytz.timezone('Europe/Zagreb')
now_zagreb = datetime.now(zagreb_tz)

# تنظیمات عمومی پلاتلی برای تم روشن
plotly_layout = dict(
    height=300,
    template="plotly_white",
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(t=30, b=30, l=0, r=0),
    font=dict(color='#1e293b')
)

# --- ۳. دریافت داده‌ها و محاسبات هسته سیستم ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], w['soiling_factor'])
p_wind = WindSystem().get_power_output(w['wind_speed'], w['turbulence'])

# منطق هوشمند EMS
source_name, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_available, st.session_state.battery.soc)

# بروزرسانی وضعیت فیزیکی دارایی‌ها
batt_data = st.session_state.battery.update_state(p_to_batt)
elec_out = st.session_state.electrolyzer.calculate_production(p_to_elec, w['temp'])
logistics = st.session_state.h2_chain.manage_chain(elec_out['h2_kg_h'])

# --- ۴. بخش هدر: تلمتری و منبع انرژی فعال ---
top_l, top_r = st.columns([1, 2])

with top_l:
    st.markdown(f"""
        <div class="status-card">
            <h4 style="margin:0; color: #64748b; font-size: 13px;">📍 ZAGREB HUB TELEMETRY</h4>
            <h2 style="margin:0; color: #1e293b; font-weight: 800;">{now_zagreb.strftime('%H:%M:%S')}</h2>
            <p style="margin:0; color: #0ea5e9; font-weight: 500;">{now_zagreb.strftime('%A, %d %B %Y')}</p>
            <hr style="margin:10px 0; border-color: #e2e8f0;">
            <p style="margin:0; font-size: 14px; color: #475569;">🌡️ Temp: <b>{w['temp']}°C</b> | ☀️ Irrad: <b>{w['irradiance_raw']:.1f} W/m²</b></p>
            <p style="margin:0; font-size: 14px; color: #475569;">🌬️ Wind: <b>{w['wind_speed']} m/s</b> | 💧 Hum: <b>{w['humidity']}%</b></p>
        </div>
    """, unsafe_allow_html=True)

with top_r:
    colors = {"Solar (PV)": "#f59e0b", "Wind Turbine": "#0ea5e9", "National Grid": "#ef4444"}
    src_color = colors.get(source_name, "#1e293b")
    st.markdown(f"""
        <div style="text-align: right; margin-top: 10px;">
            <span style="color: #64748b; font-size: 13px; font-weight: 600;">ACTIVE ENERGY SOURCE</span><br>
            <span class="source-tag" style="background-color: {src_color}15; color: {src_color}; border: 2px solid {src_color}; font-size: 22px;">
                ● {source_name.upper()}
            </span>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- ۵. ردیف میانی: مانیتورینگ آنلاین (Power, Battery, Pressure) ---
col1, col2, col3 = st.columns([1, 1, 1.5])

with col1:
    st.subheader("⚡ Power Distribution (kW)")
    fig_power = go.Figure(go.Bar(
        x=['Inbound', 'To BESS', 'To Elec'],
        y=[p_available, abs(p_to_batt), p_to_elec],
        marker_color=[src_color, '#10b981', '#3b82f6'],
        text=[f"{p_available:.1f}", f"{abs(p_to_batt):.1f}", f"{p_to_elec:.1f}"],
        textposition='auto', textfont=dict(color='white')
    ))
    fig_power.update_layout(**plotly_layout)
    st.plotly_chart(fig_power, use_container_width=True)

with col2:
    st.subheader("🔋 Battery SOC")
    fig_soc = go.Figure(go.Pie(
        labels=['Charged', 'Empty'], values=[batt_data['soc'], 1 - batt_data['soc']],
        hole=.7, marker_colors=['#10b981', '#f1f5f9'], showlegend=False
    ))
    fig_soc.add_annotation(text=f"{batt_data['soc']*100:.1f}%", x=0.5, y=0.5, showarrow=False, font_size=24, font_family="Arial Black")
    fig_soc.update_layout(**plotly_layout)
    st.plotly_chart(fig_soc, use_container_width=True)

with col3:
    st.subheader("🧪 System Pressure (bar)")
    new_entry = {'Time': now_zagreb.strftime('%H:%M:%S'), 'Pressure': logistics['pressure_bar']}
    st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_entry])], ignore_index=True).iloc[-20:]
    fig_h2 = go.Figure(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Pressure'], 
                                 fill='tozeroy', line=dict(color='#3b82f6', width=3), fillcolor='rgba(59, 130, 246, 0.1)'))
    fig_h2.update_layout(**plotly_layout)
    st.plotly_chart(fig_h2, use_container_width=True)

# --- ۶. ردیف شاخص‌های سلامت دارایی‌ها ---
st.subheader("⚙️ Industrial Asset Diagnostics")
bot1, bot2, bot3, bot4 = st.columns(4)
bot1.metric("Electrolyzer SOH", f"{elec_out['soh']:.2%}", delta="-0.01%")
bot2.metric("Gas Purity", f"{elec_out['purity']:.4f}%", "Optimal")
bot3.metric("Water Demand", f"{elec_out['water_l_h']:.2f} L/h")
bot4.metric("Tank Temp", f"{logistics['temp_c']:.1f} °C")

st.divider()

# --- ۷. ردیف تحلیل‌های پیشرفته: پیش‌بینی و جریان انرژی ---
st.header("🔍 Advanced Engineering Analytics")
row7_l, row7_r = st.columns([1.5, 1])

with row7_l:
    st.subheader("🔮 24H AI Production Forecast")
    f_time = [(now_zagreb + pd.Timedelta(hours=i)).strftime('%H:00') for i in range(24)]
    f_val = [p_pv * (0.5 + 0.4 * np.sin(i/4)) if 6 < i < 19 else 0 for i in range(24)]
    fig_f = go.Figure(go.Scatter(x=f_time, y=f_val, fill='tozeroy', line=dict(color='#f59e0b')))
    fig_f.update_layout(**plotly_layout, xaxis_title="Next 24h")
    st.plotly_chart(fig_f, use_container_width=True)

with row7_r:
    st.subheader("🔄 Energy Flow (Sankey)")
    fig_s = go.Figure(go.Sankey(
        node=dict(pad=15, thickness=20, label=[source_name, "BESS", "Electrolyzer", "Loss/Export"], 
                  color=["#f59e0b", "#10b981", "#3b82f6", "#94a3b8"]),
        link=dict(source=[0, 0, 0], target=[1, 2, 3], 
                  value=[abs(p_to_batt), p_to_elec, max(0.1, p_available - p_to_elec - abs(p_to_batt))])
    ))
    fig_s.update_layout(height=300)
    st.plotly_chart(fig_s, use_container_width=True)

# --- ۸. ردیف ترمودینامیک و راندمان ---
row8_l, row8_r = st.columns(2)

with row8_l:
    st.subheader("🌡️ Thermodynamic Profile (P-T)")
    fig_pt = make_subplots(specs=[[{"secondary_y": True}]])
    fig_pt.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Pressure'], 
                                name="Pressure (bar)", line=dict(color='#3b82f6')), secondary_y=False)
    # شبیه‌سازی دمای لحظه‌ای گاز
    t_trend = [logistics['temp_c'] + (i*0.05) for i in range(len(st.session_state.history))]
    fig_pt.add_trace(go.Scatter(x=st.session_state.history['Time'], y=t_trend, 
                                name="Gas Temp (°C)", line=dict(color='#ef4444', dash='dot')), secondary_y=True)
    fig_pt.update_layout(**plotly_layout)
    st.plotly_chart(fig_pt, use_container_width=True)

with row8_r:
    st.subheader("📉 Electrolyzer Efficiency Curve")
    l_pts, e_pts = [10, 30, 50, 80, 100], [88, 84, 79, 72, 65]
    fig_e = go.Figure()
    fig_e.add_trace(go.Scatter(x=l_pts, y=e_pts, mode='lines', name='Design', line=dict(color='#94a3b8')))
    curr_l = (p_to_elec / 5.6) * 100
    fig_e.add_trace(go.Scatter(x=[curr_l], y=[elec_out.get('efficiency', 78)], mode='markers', 
                               marker=dict(color='#10b981', size=15), name="Current"))
    fig_e.update_layout(**plotly_layout, xaxis_title="Load %")
    st.plotly_chart(fig_e, use_container_width=True)

# --- ۹. ردیف اقتصاد و استهلاک نهایی ---
row9_l, row9_r = st.columns([1, 1.5])

with row9_l:
    st.subheader("💰 LCOH Breakdown")
    fig_c = go.Figure(go.Pie(labels=['Elec', 'O&M', 'Sinking Fund', 'Grid'], values=[65, 10, 20, 5], 
                             hole=.5, marker_colors=['#3b82f6', '#10b981', '#f59e0b', '#94a3b8']))
    fig_c.update_layout(**plotly_layout)
    st.plotly_chart(fig_c, use_container_width=True)

with row9_r:
    st.subheader("📉 Long-term SOH Degradation")
    days = list(range(30))
    b_trend = [100 - (i*0.01) for i in days]
    e_trend = [100 - (i*0.02) for i in days]
    fig_soh = go.Figure()
    fig_soh.add_trace(go.Scatter(x=days, y=b_trend, name="BESS SOH", line=dict(color='#10b981')))
    fig_soh.add_trace(go.Scatter(x=days, y=e_trend, name="Elec SOH", line=dict(color='#f59e0b')))
    fig_soh.update_layout(**plotly_layout, xaxis_title="Days")
    st.plotly_chart(fig_soh, use_container_width=True)

# تکرار شبیه‌سازی
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
