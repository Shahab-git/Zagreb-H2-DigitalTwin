import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import numpy as np
import pytz

# --- 1. تنظیمات صفحه و استایل ---
st.set_page_config(page_title="LUMINIH2 ULTIMATE DIGITAL TWIN", layout="wide", initial_sidebar_state="collapsed")

# استایل CSS سفارشی برای تم سفید و حرفه‌ای
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #1e293b; }
    .nav-header { 
        background: #f8fafc; padding: 20px; border-radius: 15px; 
        border-left: 5px solid #0ea5e9; margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-card {
        background: #f1f5f9; padding: 15px; border-radius: 10px;
        text-align: center; border: 1px solid #e2e8f0;
    }
    h1, h2, h3 { color: #0f172a !important; font-family: 'Segoe UI', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. مدیریت داده‌ها (Session State) ---
# ایجاد دیتابیس مجازی برای ۳۰ نقطه زمانی آخر
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'H2_Tank', 'Revenue', 'Efficiency', 'CO2'])
    st.session_state.bess_soc = 0.65
    st.session_state.h2_station = 1.2

# دریافت زمان زنده زاگرب
zagreb_tz = pytz.timezone('Europe/Zagreb')
t_display = datetime.now(zagreb_tz).strftime('%H:%M:%S')

# شبیه‌سازی تلمتری زنده (جایگزین با داده‌های واقعی در مرحله بعد)
s_val = max(0, 500 + 300 * np.sin(time.time()/100) + np.random.normal(0, 10))
w_val = max(0, 8 + 4 * np.cos(time.time()/150) + np.random.normal(0, 0.5))
eff_val = 82 + np.random.uniform(-1, 1)
rev_val = 12.5 + np.random.uniform(0, 2)
co2_val = 0.45 + np.random.uniform(0, 0.05)

# بروزرسانی تاریخچه
new_data = pd.DataFrame([[t_display, s_val, w_val, st.session_state.h2_station, rev_val, eff_val, co2_val]], 
                        columns=st.session_state.history.columns)
st.session_state.history = pd.concat([st.session_state.history, new_data], ignore_index=True).iloc[-30:]

# --- 3. هدر ناوبری ---
st.markdown(f"""
<div class="nav-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin:0; font-size:24px;">🌐 LUMINIH2: Digital Twin Hub</h1>
            <p style="margin:0; color:#64748b;">North Adriatic Green Hydrogen Corridor | Zagreb Node</p>
        </div>
        <div style="text-align:right;">
            <span style="font-size:20px; font-weight:bold;">{t_display}</span><br>
            <span style="color:#10b981;">● LIVE TELEMETRY</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 4. چیدمان ۵ ناحیه‌ای (ZONEs) ---
tabs = st.tabs(["🌍 Acquisition", "🧪 Production", "🔋 Storage", "🔌 Distribution", "📊 Analytics"])
chart_theme = "plotly_white"
color_scale = ["#0ea5e9", "#0284c7", "#0369a1", "#075985"]

# --- ZONE 1: ACQUISITION ---
with tabs[0]:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Wind Turbulence Intensity")
        fig1 = go.Figure(go.Scatterpolar(r=[w_val, w_val*1.2, w_val*0.8, w_val], 
                                         theta=[0, 90, 180, 270], fill='toself', line_color='#0ea5e9'))
        fig1.update_layout(template=chart_theme, height=300, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig1, use_container_width=True)
        
        st.subheader("2. Solar Irradiance Heatmap")
        fig2 = px.density_heatmap(st.session_state.history, x="Time", y="Solar", color_continuous_scale="Blues")
        fig2.update_layout(template=chart_theme, height=300)
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("3. Resource Mix Portfolio")
        fig3 = px.pie(values=[s_val, w_val*10, 100], names=['Solar', 'Wind', 'Grid'], hole=0.7, color_discrete_sequence=color_scale)
        fig3.update_layout(template=chart_theme, height=300, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)
        
        st.subheader("4. Real-time Absorption (W/m²)")
        fig4 = px.area(st.session_state.history, x="Time", y="Solar", line_shape="spline")
        fig4.update_traces(fillcolor="rgba(14, 165, 233, 0.2)", line_color="#0ea5e9")
        fig4.update_layout(template=chart_theme, height=300)
        st.plotly_chart(fig4, use_container_width=True)

# --- ZONE 2: PRODUCTION ---
with tabs[1]:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("5. Electrolyzer Efficiency (PEM)")
        fig5 = px.line(st.session_state.history, x="Time", y="Efficiency")
        fig5.update_traces(line_color="#10b981")
        st.plotly_chart(fig5, use_container_width=True)
        
        st.subheader("6. Thermal Stack Health")
        fig6 = go.Figure(go.Indicator(mode="gauge+number", value=58, gauge={'bar':{'color':"#0ea5e9"}, 'axis':{'range':[0, 100]}}))
        fig6.update_layout(height=250, margin=dict(t=50, b=0))
        st.plotly_chart(fig6, use_container_width=True)
    with col2:
        st.subheader("7. Water Consumption (L/h)")
        st.metric("Deionized Water Flow", "14.2 L/h", "Stable")
        st.subheader("8. Load vs Efficiency Curve")
        fig8 = px.scatter(st.session_state.history, x="Solar", y="Efficiency", trendline="lowess")
        st.plotly_chart(fig8, use_container_width=True)

# --- ZONE 3: STORAGE ---
with tabs[2]:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("9. BESS State of Charge")
        fig9 = go.Figure(go.Indicator(mode="number+delta", value=st.session_state.bess_soc*100, delta={'reference': 50}))
        st.plotly_chart(fig9, use_container_width=True)
        st.subheader("10. Battery Temperature Sync")
        st.bar_chart(np.random.normal(25, 1, 15))
    with col2:
        st.subheader("11. Tank Pressure Dynamics")
        st.info(f"Main Tank: {30 + np.random.uniform(0, 2):.1f} bar | Safety: OK")
        st.subheader("12. H2 Mass Balance (kg)")
        fig12 = px.line(st.session_state.history, x="Time", y="H2_Tank")
        st.plotly_chart(fig12, use_container_width=True)

# --- ZONE 4: DISTRIBUTION ---
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("13. HRS Station (5kg Hub)")
        fill = st.session_state.h2_station / 5.0
        st.progress(fill)
        st.caption(f"Current Fill: {st.session_state.h2_station:.2f} kg / 5.00 kg")
        st.subheader("14. Fuel Cell Power Output")
        st.metric("Regeneration Active", "18.4 kW")
    with c2:
        st.subheader("15. EV Charging Load")
        st.line_chart(np.random.randint(10, 50, 20))
        st.subheader("16. Output Purity")
        st.success("H2 Purity: 99.999% (ISO Certified)")

# --- ZONE 5: ANALYTICS ---
with tabs[4]:
    st.subheader("17. System-Wide Energy Flow (Sankey)")
    fig17 = go.Figure(go.Sankey(
        node=dict(label=["Renewables", "BESS", "Electrolyzer", "Storage", "EV/HRS", "Grid"], color="#0ea5e9", pad=15),
        link=dict(source=[0, 0, 1, 2, 3, 3], target=[1, 2, 0, 3, 4, 5], value=[40, 60, 10, 55, 30, 25])
    ))
    fig17.update_layout(height=400, template=chart_theme)
    st.plotly_chart(fig17, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("18. LCOH Insight")
        st.metric("Green H2 Cost", "$4.12 /kg", "-0.05")
    with c2:
        st.subheader("19. CO2 Abatement")
        total_co2 = st.session_state.history['CO2'].sum()
        st.metric("Carbon Saved", f"{total_co2:.2f} kg")
    with c3:
        st.subheader("20. Financial Zone")
        st.metric("Daily Revenue", f"${st.session_state.history['Revenue'].sum():.2f}")

# --- 5. منطق تکرار (Live Refresh) ---
time.sleep(2)
st.rerun()
