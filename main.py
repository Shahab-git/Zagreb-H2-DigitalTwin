import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import numpy as np
import pytz

# --- 1. تنظیمات سیستمی و ظاهری ---
st.set_page_config(page_title="LUMINIH2 ULTIMATE", layout="wide", initial_sidebar_state="collapsed")

# استایل اختصاصی برای تم سفید حرفه‌ای (Zagreb Light Theme)
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #1e293b; }
    .nav-header { 
        background: #f8fafc; padding: 20px; border-radius: 15px; 
        border-left: 5px solid #0ea5e9; margin-bottom: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9; border-radius: 5px 5px 0 0; padding: 8px 16px; color: #475569;
    }
    .stTabs [aria-selected="true"] { background-color: #0ea5e9 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. مدیریت داده‌های زنده (Session State) ---
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'H2_Fill', 'Revenue', 'Efficiency', 'CO2'])
    st.session_state.bess_soc = 0.55
    st.session_state.h2_station = 1.5

# زمان زنده زاگرب
zagreb_tz = pytz.timezone('Europe/Zagreb')
t_now = datetime.now(zagreb_tz).strftime('%H:%M:%S')

# شبیه‌سازی هوشمند تلمتری (جایگزین با ماژول‌های فیزیکی شما)
s_val = max(0, 450 + 200 * np.sin(time.time()/60) + np.random.normal(0, 5))
w_val = max(2, 6 + 3 * np.cos(time.time()/100) + np.random.normal(0, 0.2))
eff = 82 + np.random.uniform(-1, 1)
rev = 4.5 + np.random.uniform(0, 0.5)
co2 = 0.3 + np.random.uniform(0, 0.02)

# بروزرسانی دیتابیس لحظه‌ای
new_row = pd.DataFrame([[t_now, s_val, w_val, st.session_state.h2_station, rev, eff, co2]], 
                        columns=st.session_state.history.columns)
st.session_state.history = pd.concat([st.session_state.history, new_row], ignore_index=True).iloc[-30:]

# --- 3. هدر فرماندهی پروژه ---
st.markdown(f"""
<div class="nav-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin:0; font-size:26px; color:#0f172a;">🌐 LUMINIH2: Digital Twin Control</h1>
            <p style="margin:0; color:#64748b;">Zagreb Energy Hub | Real-time Power Switching</p>
        </div>
        <div style="text-align:right;">
            <span style="font-size:22px; font-weight:bold; color:#1e293b;">{t_now}</span><br>
            <span style="color:#10b981; font-weight:bold;">● ZONE ACTIVE</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 4. داشبورد ۲۰ نموداری (۵ تب اصلی) ---
tab_names = ["🌍 1. Acquisition", "🧪 2. Production", "🔋 3. Storage", "🔌 4. Distribution", "📊 5. Analytics"]
tabs = st.tabs(tab_names)
theme = "plotly_white"

# --- ZONE 1: ACQUISITION (پایش اتمسفر زاگرب) ---
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Wind Vector Dynamics")
        fig1 = go.Figure(go.Scatterpolar(r=[w_val, w_val*1.1, w_val*0.9, w_val], theta=[0, 90, 180, 270], fill='toself'))
        fig1.update_layout(template=theme, height=300)
        st.plotly_chart(fig1, use_container_width=True)
        
        st.subheader("2. Irradiance Distribution")
        fig2 = px.histogram(st.session_state.history, x="Solar", nbins=10, color_discrete_sequence=['#0ea5e9'])
        st.plotly_chart(fig2, use_container_width=True)
    with c2:
        st.subheader("3. Resource Mix Portfolio")
        fig3 = px.pie(values=[s_val, w_val*12, 150], names=['Solar', 'Wind', 'Grid Balance'], hole=0.7)
        st.plotly_chart(fig3, use_container_width=True)
        
        st.subheader("4. Telemetry Flux (Live)")
        fig4 = px.area(st.session_state.history, x="Time", y="Solar")
        fig4.update_traces(fillcolor="rgba(14, 165, 233, 0.1)", line_color="#0ea5e9")
        st.plotly_chart(fig4, use_container_width=True)

# --- ZONE 2: PRODUCTION (الکترولایزر و مدیریت انرژی) ---
with tabs[1]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("5. Stack Efficiency (%)")
        st.line_chart(st.session_state.history.set_index('Time')['Efficiency'])
        
        st.subheader("6. Electrolyzer Heat Map")
        fig6 = go.Figure(go.Indicator(mode="gauge+number", value=62, title={'text': "Stack Temp °C"}, 
                                      gauge={'bar':{'color':"#ef4444"}, 'axis':{'range':[0, 100]}}))
        st.plotly_chart(fig6, use_container_width=True)
    with c2:
        st.subheader("7. Specific Consumption")
        st.metric("Energy Intensity", "51.8 kWh/kg", "-0.4")
        
        st.subheader("8. Load-Efficiency Correlation")
        # حل مشکل statsmodels با try-except
        try:
            fig8 = px.scatter(st.session_state.history, x="Solar", y="Efficiency", trendline="ols")
        except:
            fig8 = px.scatter(st.session_state.history, x="Solar", y="Efficiency")
        st.plotly_chart(fig8, use_container_width=True)

# --- ZONE 3: STORAGE (ذخیره‌سازی هوشمند) ---
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("9. BESS State of Charge")
        fig9 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.bess_soc*100, 
                                      gauge={'bar':{'color':"#10b981"}}))
        st.plotly_chart(fig9, use_container_width=True)
        
        st.subheader("10. Battery Voltage Stability")
        st.bar_chart(np.random.normal(400, 2, 20))
    with c2:
        st.subheader("11. Tank Pressure (Bar)")
        st.info("Operating Pressure: 32.4 Bar | Threshold: 35.0")
        
        st.subheader("12. Hydrogen Inventory")
        fig12 = px.line(st.session_state.history, x="Time", y="H2_Fill", markers=True)
        st.plotly_chart(fig12, use_container_width=True)

# --- ZONE 4: DISTRIBUTION (توزیع سبز و EV) ---
with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("13. HRS 5kg Station Fill")
        st.progress(st.session_state.h2_station / 5.0)
        st.caption(f"Current Capacity: {st.session_state.h2_station:.2f} / 5.00 kg")
        
        st.subheader("14. Fuel Cell Hub Status")
        st.success("FC Status: NOMINAL | Output: 24.1 kW")
    with c2:
        st.subheader("15. EV Charging Station Load")
        st.line_chart(np.random.randint(5, 45, 15))
        
        st.subheader("16. Purity Compliance")
        st.markdown("✅ **ISO 14687:2019** - Grade D (99.999% H2)")

# --- ZONE 5: ANALYTICS (ثروت و کربن) ---
with tabs[4]:
    st.subheader("17. Global Energy Flow (Sankey)")
    fig17 = go.Figure(go.Sankey(
        node=dict(label=["Atmosphere", "BESS", "Electrolyzer", "Storage", "EV Station", "Grid"], color="#0ea5e9"),
        link=dict(source=[0, 0, 1, 2, 3, 3], target=[1, 2, 0, 3, 4, 5], value=[35, 65, 10, 50, 25, 20])
    ))
    fig17.update_layout(height=400, template=theme)
    st.plotly_chart(fig17, use_container_width=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("18. Levelized Cost (LCOH)")
        st.metric("Price Index", "$4.08 /kg", "-2%")
    with c2:
        st.subheader("19. CO2 Avoided (Zagreb)")
        st.metric("Total Abatement", f"{st.session_state.history['CO2'].sum():.2f} kg", "+0.04")
    with c3:
        st.subheader("20. Financial Portfolio")
        st.metric("Grid Revenue", f"${st.session_state.history['Revenue'].sum():.2f}")

# --- 5. رفرش خودکار ---
time.sleep(2)
st.rerun()
