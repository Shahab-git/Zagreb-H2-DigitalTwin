# main.py (Zagreb Integrated Multi-Energy Hub - Strategic Edition)
# Version: 7.0 | Full Roadmap Integration (EV, Fuel Cell, Heat Recovery)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time
import pytz 

# --- ۱. تنظیمات ظاهری (Clean Light Theme) ---
st.set_page_config(page_title="H2 Hub Zagreb | Integrated Control Room", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; color: #1e293b; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #0ea5e9; border-radius: 8px; padding: 10px; }
    .status-card { background-color: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .source-tag { padding: 5px 15px; border-radius: 20px; font-weight: bold; font-family: 'Segoe UI', sans-serif; }
    h1, h2, h3, h4, p, span { color: #1e293b !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ۲. مقداردهی اولیه و شبیه‌سازی منطق نقشه راه ---
if 'init' not in st.session_state:
    st.session_state.history = pd.DataFrame()
    st.session_state.init = True

zagreb_tz = pytz.timezone('Europe/Zagreb')
now_zagreb = datetime.now(zagreb_tz)

# پارامترهای فرضی (برای نمایش در داشبورد - در نسخه نهایی از کلاس‌های شما خوانده می‌شود)
p_solar, p_wind = 45.5, 12.8  # kW
soc_battery = 0.65            # 65%
h2_prod_rate = 1.2            # kg/h
tank_pressure = 185           # bar
fuel_cell_power = 5.5         # kW (تولید از هیدروژن مازاد)
ev_load = 4.2                 # kW (بار ایستگاه شارژ خودرو برقی)
heat_recovered = 3.4          # kWt (گرما بازیافتی)

# ذخیره تاریخچه برای نمودارها
new_entry = {'Time': now_zagreb.strftime('%H:%M:%S'), 'P': tank_pressure, 'EV': ev_load, 'FC': fuel_cell_power}
st.session_state.history = pd.concat([st.session_state.history, pd.DataFrame([new_entry])], ignore_index=True).iloc[-20:]

# --- ۳. هدر سیستم و منبع انرژی فعال ---
t_l, t_r = st.columns([1, 2])
with t_l:
    st.markdown(f"""<div class="status-card">
        <h4 style="margin:0; color: #64748b;">📍 ZAGREB INTEGRATED HUB</h4>
        <h2 style="margin:0;">{now_zagreb.strftime('%H:%M:%S')}</h2>
        <p style="margin:0; color: #0ea5e9;">Priority: <b>Electrolyzer (Optimized)</b></p>
    </div>""", unsafe_allow_html=True)

with t_r:
    st.markdown(f"""<div style="text-align: right; margin-top: 10px;">
        <span style="color: #64748b; font-size: 13px;">AI PREDICTED STATUS:</span><br>
        <span class="source-tag" style="background-color: #10b98115; color: #10b981; border: 2px solid #10b981; font-size: 20px;">
            ● STABLE PRODUCTION & EV CHARGING ACTIVE
        </span>
    </div>""", unsafe_allow_html=True)

st.divider()

# --- ۴. ردیف اول: زنجیره تولید و ذخیره‌سازی هیدروژن (مطابق نقشه راه) ---
st.subheader("🛠️ Hydrogen Production & Storage Chain")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.write("**1. Electrolyzer S30**")
    st.metric("H2 Production", f"{h2_prod_rate} kg/h", "SOH: 98.5%")
with c2:
    st.write("**2. Buffer & Compressor**")
    st.progress(0.45) # سطح بافر
    st.caption("Buffer Level: 45%")
with c3:
    st.write("**3. High-Pressure Storage**")
    st.metric("Tank Pressure", f"{tank_pressure} bar", f"{tank_pressure-180} delta")
with c4:
    st.write("**4. H2 Refueling Station**")
    st.metric("Dispenser Status", "READY", "5kg Tank Sync")

# --- ۵. ردیف دوم: نمودارهای یکپارچه (EV Station & Fuel Cell) ---
st.divider()
col_ev, col_fc = st.columns(2)

with col_ev:
    st.subheader("🚗 EV Charging Station (Powered by FC/Grid)")
    fig_ev = go.Figure()
    fig_ev.add_trace(go.Scatter(x=st.session_state.history['Time'], y=st.session_state.history['EV'], 
                                fill='tozeroy', line=dict(color='#8b5cf6', width=3), name="EV Load (kW)"))
    fig_ev.update_layout(height=250, template="plotly_white", margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig_ev, use_container_width=True)
    st.caption("برق خروجی از پیل سوختی ابتدا به این ایستگاه هدایت می‌شود.")

with col_fc:
    st.subheader("🔋 Fuel Cell & Grid Interaction")
    # نمودار تعامل پیل سوختی و تزریق به شبکه
    fig_fc = go.Figure(go.Bar(
        x=['Fuel Cell Out', 'EV Demand', 'Grid Export'],
        y=[fuel_cell_power, ev_load, max(0, fuel_cell_power - ev_load)],
        marker_color=['#10b981', '#8b5cf6', '#3b82f6']
    ))
    fig_fc.update_layout(height=250, template="plotly_white", margin=dict(t=20, b=20, l=0, r=0))
    st.plotly_chart(fig_fc, use_container_width=True)

# --- ۶. ردیف سوم: بازیافت حرارت و راندمان کل (Heat Recovery) ---
st.divider()
st.subheader("♻️ Waste Heat Recovery & Efficiency")
h1, h2, h3 = st.columns(3)

with h1:
    st.metric("Recovered Thermal Power", f"{heat_recovered} kWt", "from Electrolyzer/FC")
    st.caption("سیستم بازیابی حرارت باعث بهبود راندمان کل شده است.")
with h2:
    st.write("**Total System Efficiency**")
    st.info(f"Combined P+T Efficiency: 74.2%") # برق + حرارت
with h3:
    st.metric("CO2 Avoided", "12.4 kg/day", "Green H2 Tracking")

# --- ۷. ردیف پایینی: نقشه جریان انرژی (Sankey نهایی) ---
with st.expander("📊 Full System Energy & H2 Mapping"):
    fig_sankey = go.Figure(go.Sankey(
        node=dict(pad=15, thickness=20, 
                  label=["PV/Wind", "BESS", "Electrolyzer", "H2 Station", "Fuel Cell", "EV Station", "Grid Export"],
                  color="#0ea5e9"),
        link=dict(
            source=[0, 0, 2, 2, 4, 4], # From
            target=[1, 2, 3, 4, 5, 6], # To
            value=[15, 45, 30, 15, 10, 5]  # Values
        )
    ))
    st.plotly_chart(fig_sankey, use_container_width=True)

# تکرار شبیه‌سازی
time.sleep(5)
st.rerun()
