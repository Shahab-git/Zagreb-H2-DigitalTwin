# main.py - THE ULTIMATE 20-CHART DIGITAL TWIN (Light & Live Zagreb Time)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time
import numpy as np
import pytz

# --- 1. CORE MODULES ---
try:
    from config import Config
    from weather_api import WeatherProvider
    from energy_assets import SolarSystem, WindSystem
    from ems_brain import EMSBrain
except:
    pass 

# --- 2. LIGHT THEME STYLING ---
st.set_page_config(page_title="LUMINIH2 ULTIMATE", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #1e293b; }
    .nav-header { 
        background: #f8fafc; padding: 15px 30px; border-radius: 15px; 
        border-bottom: 3px solid #0ea5e9; margin-bottom: 25px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    .card { 
        background: #ffffff; padding: 15px; border-radius: 10px; 
        border: 1px solid #e2e8f0; margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    h1, h2, h3, p, span { color: #1e293b !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9; border-radius: 5px 5px 0 0; padding: 10px 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE & LIVE DATA ---
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'H2_Fill', 'Revenue', 'Efficiency', 'CO2'])
    st.session_state.bess_soc = 0.45
    st.session_state.h2_tank = 2.5
    st.session_state.h2_station = 1.0

# دریافت زمان زنده زاگرب
zagreb_tz = pytz.timezone('Europe/Zagreb')
now_zagreb = datetime.now(zagreb_tz)
t_display = now_zagreb.strftime('%H:%M:%S')

# بروزرسانی دیتا برای نمودارها
s_val, w_val = 450 + np.random.uniform(-20, 20), 5.5 + np.random.uniform(-0.5, 0.5)
rev = 5.2 + np.random.uniform(-1, 1)
eff = 82 + np.random.uniform(-2, 2)
co2 = 3.5 + np.random.uniform(0, 0.5)

new_row = pd.DataFrame([[t_display, s_val, w_val, st.session_state.h2_tank, rev, eff, co2]], 
                        columns=['Time', 'Solar', 'Wind', 'H2_Fill', 'Revenue', 'Efficiency', 'CO2'])
st.session_state.history = pd.concat([st.session_state.history, new_row], ignore_index=True).iloc[-30:]

# --- 4. TOP BAR (ZAGREB LIVE UPDATE) ---
st.markdown(f"""
<div class="nav-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2 style="margin:0; color:#0ea5e9; font-weight:bold;">🌐 LUMINIH2: 20-STREAM COMMAND</h2>
        <div style="text-align:right; font-size: 18px;">
            <span style="color:#64748b;">Zagreb Hub</span> | 
            <span style="font-weight:bold; color:#1e293b;">{t_display}</span> | 
            <span style="color:#10b981; font-weight:bold;">● SYSTEM ONLINE</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 5. THE 5-ZONE DASHBOARD (Tabs for 20 Charts) ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🌍 1. Acquisition", "🧪 2. Production", "🔋 3. Storage", "🔌 4. Distribution", "📊 5. Analytics"
])

chart_theme = "plotly_white"

# --- TAB 1: ACQUISITION ---
with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1. Wind Rose (Zagreb)")
        fig1 = go.Figure(go.Barpolar(r=[10, 15, 20, 7], theta=[0, 90, 180, 270], marker_color="#0ea5e9"))
        fig1.update_layout(template=chart_theme)
        st.plotly_chart(fig1, use_container_width=True)
        st.subheader("2. Solar Irradiance Heatmap")
        fig2 = px.density_heatmap(st.session_state.history, x="Time", y="Solar", template=chart_theme)
        st.plotly_chart(fig2, use_container_width=True)
    with c2:
        st.subheader("3. Power Source Mix")
        fig3 = px.pie(values=[s_val, w_val, 50], names=['Solar', 'Wind', 'Grid'], hole=0.6, template=chart_theme)
        st.plotly_chart(fig3, use_container_width=True)
        st.subheader("4. Resource Trend (Live)")
        fig4 = px.line(st.session_state.history, x="Time", y="Solar", template=chart_theme)
        st.plotly_chart(fig4, use_container_width=True)

# --- TAB 2: PRODUCTION ---
with tab2:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("5. Electrolyzer Efficiency")
        fig5 = px.line(st.session_state.history, x="Time", y="Efficiency", template=chart_theme)
        st.plotly_chart(fig5, use_container_width=True)
        st.subheader("6. Stack Temp Gauge")
        fig6 = go.Figure(go.Indicator(mode="gauge+number", value=65, title={'text': "°C"}, gauge={'bar':{'color':"#ef4444"}}))
        fig6.update_layout(template=chart_theme, height=250)
        st.plotly_chart(fig6, use_container_width=True)
    with c2:
        st.subheader("7. Energy Intensity")
        st.metric("Avg Consumption", "52.4 kWh/kg", "-0.2")
        st.subheader("8. Production Characteristics")
        fig8 = px.scatter(st.session_state.history, x="Solar", y="Efficiency", template=chart_theme)
        st.plotly_chart(fig8, use_container_width=True)

# --- TAB 3: STORAGE ---
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("9. BESS SoC (%)")
        fig9 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.bess_soc*100, gauge={'bar':{'color':"#10b981"}}))
        fig9.update_layout(template=chart_theme, height=250)
        st.plotly_chart(fig9, use_container_width=True)
        st.subheader("10. Battery Cycle Trend")
        st.bar_chart(np.random.randn(20))
    with c2:
        st.subheader("11. Buffer Pressure (bar)")
        st.metric("Pressure Status", "30.5 bar", "Stable")
        st.subheader("12. H2 Inventory Level")
        fig12 = px.area(st.session_state.history, x="Time", y="H2_Fill", template=chart_theme)
        st.plotly_chart(fig12, use_container_width=True)

# --- TAB 4: DISTRIBUTION ---
with tab4:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("13. H2 Station Fill (5kg)")
        st.progress(st.session_state.h2_station / 5.0)
        st.subheader("14. Fuel Cell Hub")
        st.metric("FC Active Power", "22.5 kW")
    with c2:
        st.subheader("15. EV Load Simulation")
        st.line_chart(st.session_state.history['Solar'] * 0.1)
        st.subheader("16. Gas Quality Status")
        st.success("ISO 14687 Certified: 99.999%")

# --- TAB 5: ANALYTICS ---
with tab5:
    st.subheader("17. Full System Energy Flow (Sankey Diagram)")
    fig17 = go.Figure(go.Sankey(
        node=dict(label=["Sun/Wind", "BESS", "Electrolyzer", "H2 Storage", "EV Station", "Grid"], color="#0ea5e9"),
        link=dict(source=[0, 0, 2, 3, 3], target=[1, 2, 3, 4, 5], value=[10, 20, 15, 8, 7])
    ))
    fig17.update_layout(template=chart_theme, height=400)
    st.plotly_chart(fig17, use_container_width=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("18. Cost Analytics (LCOH)")
        st.metric("Current $/kg", "$4.12")
    with c2:
        st.subheader("19. Total CO2 Saved")
        st.metric("Abatement", f"{st.session_state.history['CO2'].sum():.1f} kg")
    with c3:
        st.subheader("20. Financial Status")
        st.metric("Grid Revenue", f"${st.session_state.history['Revenue'].iloc[-1]:.2f}")

# AUTO-REFRESH (LUMIN-SYNC)
time.sleep(2)
st.rerun()
