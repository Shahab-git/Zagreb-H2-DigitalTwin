# main.py (Zagreb H2 Hub - Full Infrastructure Edition)
# Version: 6.0 | Theme: Light Industrial | Comprehensive Monitoring

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import pytz 

# ایمپورت ماژول‌های پروژه
from config import Config
from weather_api import WeatherProvider
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain
from ems_brain import EMSBrain

# --- ۱. تنظیمات ظاهری (Clean Light Theme) ---
st.set_page_config(page_title="H2 Hub Zagreb | Full Control Room", layout="wide")

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

# تنظیمات عمومی پلاتلی
plotly_layout = dict(
    height=280, template="plotly_white", paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=30, l=0, r=0),
    font=dict(color='#1e293b')
)

# --- ۳. دریافت داده‌ها و محاسبات عملیاتی ---
w = st.session_state.weather.fetch_current_data()
p_pv = SolarSystem().get_power_output(w['irradiance_raw'], w['temp'], w['soiling_factor'])
p_wind = WindSystem().get_power_output(w['wind_speed'], w['turbulence'])

# مدیریت انرژی توسط مغز سیستم (EMS)
source_name, p_available = st.session_state.brain.decide_energy_source(p_pv, p_wind, st.session_state.battery.soc)
p_to_batt, p_to_elec = st.session_state.brain.manage_power_flow(p_available, st.session_state.battery.soc)

# بروزرسانی دارایی‌های فیزیکی
batt_data = st.session_state.battery.update_state(p_to_batt)
elec_out = st.session_state.electrolyzer.calculate_production(p_to_elec, w['temp'])
logistics = st.session_state.h2_chain.manage_chain(elec_out['h2_kg_h'])

# ذخیره تاریخچه برای نمودارها
new_data = {
    'Time': now_zagreb.strftime('%H:%M:%S'),
    'Pressure': logistics['pressure_bar'],
    'Production': elec_out['h2_kg_h'],
    'Solar': p_pv,
    'Wind': p_wind
}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_data])], ignore_index=True).iloc[-30:]

# --- ۴. بخش هدر و وضعیت ایستگاه برقی ---
top_l, top_r = st.columns([1, 2])
with top_l:
    st.markdown(f"""
        <div class="status-card">
            <h4 style="margin:0; color: #64748b; font-size: 13px;">📍 ZAGREB ENERGY STATION</h4>
            <h2 style="margin:0; font-weight: 800;">{now_zagreb.strftime('%H:%M:%S')}</h2>
            <p style="margin:0; color: #0ea5e9;">{now_zagreb.strftime('%A, %d %B %Y')}</p>
            <hr style="margin:10px 0; border-color: #e2e8f0;">
            <p style="margin:0; font-size: 14px;">☀️ Solar: <b>{p_pv:.1f} kW</b> | 🌬️ Wind: <b>{p_wind:.1f} kW</b></p>
        </div>
    """, unsafe_allow_html=True)

with top_r:
    colors = {"Solar (PV)": "#f59e0b", "Wind Turbine": "#0ea5e9", "National Grid": "#ef4444"}
    src_color = colors.get(source_name, "#1e293b")
    st.markdown(f"""
        <div style="text-align: right; margin-top: 10px;">
            <span style="color: #64748b; font-size: 13px; font-weight: 600;">ACTIVE POWER SOURCE</span><br>
            <span class="source-tag" style="background-color: {src_color}15; color: {src_color}; border: 2px solid {src_color}; font-size: 22px;">
                ● {source_name.upper()}
            </span>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# --- ۵. مانیتورینگ تولید و فشار (ایستگاه تولید هیدروژن) ---
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("🧪 Hydrogen Production Rate (kg/h)")
    fig_prod = go.Figure(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Production'],
                                   fill='tozeroy', line=dict(color='#0ea5e9', width=3)))
    fig_prod.update_layout(**plotly_layout)
    st.plotly_chart(fig_prod, use_container_width=True)

with col2:
    st.subheader("🎚️ Main Tank Pressure")
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = logistics['pressure_bar'],
        gauge = {'axis': {'range': [0, 500]}, 'bar': {'color': "#0ea5e9"}},
        title = {'text': "Pressure (Bar)", 'font': {'size': 14}}
    ))
    fig_gauge.update_layout(height=280, margin=dict(t=50, b=0))
    st.plotly_chart(fig_gauge, use_container_width=True)

# --- ۶. مانیتورینگ بافر و ایستگاه سوخت‌رسانی ---
st.subheader("⛽ Hydrogen Logistics & Buffer Status")
log_col1, log_col2, log_col3 = st.columns(3)

with log_col1:
    buffer_val = 45 + (elec_out['h2_kg_h'] * 2) # شبیه‌سازی سطح بافر
    st.write("**Buffer Tank (Low Pressure)**")
    st.progress(min(buffer_val/100, 1.0))
    st.caption(f"Intermediate Buffer: {buffer_val:.1f}% Full")

with log_col2:
    st.metric("Total Hub Storage", f"{logistics['pressure_bar'] * 0.8:.2f} kg", delta="Filling Rate +0.2kg/s")

with log_col3:
    station_ready = "READY" if logistics['pressure_bar'] > 150 else "PRESSURIZING"
    st.markdown(f"**Filling Station Status:** <br> <span style='font-size:24px; color:{'#10b981' if station_ready=='READY' else '#f59e0b'}'>● {station_ready}</span>", unsafe_allow_html=True)

st.divider()

# --- ۷. تحلیل‌های مهندسی (Sankey, Forecast, Efficiency) ---
st.header("🔍 Advanced Engineering Analytics")
an_col1, an_col2, an_col3 = st.columns(3)

with an_col1:
    st.subheader("🔄 Energy Flow (Sankey)")
    fig_s = go.Figure(go.Sankey(
        node=dict(label=[source_name, "BESS", "Electrolyzer", "Losses"], color="#0ea5e9"),
        link=dict(source=[0, 0, 0], target=[1, 2, 3], value=[abs(p_to_batt), p_to_elec, 0.5])
    ))
    fig_s.update_layout(height=280)
    st.plotly_chart(fig_s, use_container_width=True)

with an_col2:
    st.subheader("🌡️ Thermodynamic (P-T)")
    fig_pt = make_subplots(specs=[[{"secondary_y": True}]])
    fig_pt.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['Pressure'], name="P (bar)"), secondary_y=False)
    fig_pt.add_trace(go.Scatter(x=st.session_state.history['Time'], y=[logistics['temp_c']]*len(st.session_state.history), name="T (°C)", line=dict(dash='dot')), secondary_y=True)
    fig_pt.update_layout(**plotly_layout)
    st.plotly_chart(fig_pt, use_container_width=True)

with an_col3:
    st.subheader("🔋 Battery SOC %")
    fig_b = go.Figure(go.Pie(labels=['Full', 'Empty'], values=[batt_data['soc'], 1-batt_data['soc']], hole=.7, marker_colors=['#10b981', '#f1f5f9']))
    fig_b.update_layout(**plotly_layout, showlegend=False)
    st.plotly_chart(fig_b, use_container_width=True)

# --- ۸. ردیف نهایی: استهلاک و هزینه ---
st.subheader("⚙️ Asset Health & Economics")
end_col1, end_col2 = st.columns([2, 1])

with end_col1:
    days = list(range(30))
    fig_soh = go.Figure()
    fig_soh.add_trace(go.Scatter(x=days, y=[100-(i*0.01) for i in days], name="Electrolyzer SOH"))
    fig_soh.add_trace(go.Scatter(x=days, y=[100-(i*0.005) for i in days], name="Battery SOH"))
    fig_soh.update_layout(**plotly_layout, title="Long-term Health Degradation")
    st.plotly_chart(fig_soh, use_container_width=True)

with end_col2:
    st.subheader("💰 LCOH Breakdown")
    fig_cost = go.Figure(go.Pie(labels=['Power', 'O&M', 'Stack Fund'], values=[65, 15, 20], hole=.5))
    fig_cost.update_layout(**plotly_layout)
    st.plotly_chart(fig_cost, use_container_width=True)

# تکرار شبیه‌سازی
time.sleep(Config.TIMESTEP_SEC)
st.rerun()
