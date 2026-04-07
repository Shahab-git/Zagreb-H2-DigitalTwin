# main.py - THE ULTIMATE 20-CHART DIGITAL TWIN
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
    st.warning("Modules not found. Using simulation mode.")

# --- 2. LAYOUT & THEME ---
st.set_page_config(page_title="LUMINIH2 ULTIMATE", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0b0f19; color: #e2e8f0; }
    .nav-header { background: #161b22; padding: 20px; border-radius: 15px; border-bottom: 3px solid #0ea5e9; margin-bottom: 25px; }
    .card { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SESSION STATE ---
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Solar', 'Wind', 'H2_Fill', 'Revenue', 'Efficiency', 'CO2'])
    st.session_state.bess_soc = 0.45
    st.session_state.h2_tank = 2.5
    st.session_state.h2_station = 1.0

# Logic Update (Simplified for loop)
t_now = datetime.now().strftime('%H:%M:%S')
s_val, w_val = 450 + np.random.uniform(-20, 20), 5.5 + np.random.uniform(-0.5, 0.5)
rev = 5.2 + np.random.uniform(-1, 1)
eff = 82 + np.random.uniform(-2, 2)
co2 = 3.5 + np.random.uniform(0, 0.5)

new_row = pd.DataFrame([[t_now, s_val, w_val, st.session_state.h2_tank, rev, eff, co2]], 
                        columns=['Time', 'Solar', 'Wind', 'H2_Fill', 'Revenue', 'Efficiency', 'CO2'])
st.session_state.history = pd.concat([st.session_state.history, new_row], ignore_index=True).iloc[-30:]

# --- 4. TOP BAR ---
st.markdown(f"""
<div class="nav-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2 style="margin:0; color:#0ea5e9;">🌐 LUMINIH2: 20-STREAM COMMAND</h2>
        <div style="text-align:right;"><b>Zagreb Hub</b> | {t_now} | <span style="color:#238636;">SYSTEM ONLINE</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 5. THE 5-ZONE DASHBOARD (Tabs for 20 Charts) ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🌍 1. Acquisition", "🧪 2. Production", "🔋 3. Storage", "🔌 4. Distribution", "📊 5. Analytics"
])

# --- TAB 1: ACQUISITION (Charts 1-4) ---
with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.write("1. Wind Rose (Directional Intensity)")
        fig1 = go.Figure(go.Barpolar(r=[10, 15, 20, 7], theta=[0, 90, 180, 270], marker_color="#0ea5e9"))
        st.plotly_chart(fig1, use_container_width=True)
        st.write("2. Solar Irradiance Heatmap (24h)")
        fig2 = px.density_heatmap(st.session_state.history, x="Time", y="Solar", color_continuous_scale="Viridis")
        st.plotly_chart(fig2, use_container_width=True)
    with c2:
        st.write("3. Hybrid Resource Mix")
        fig3 = px.pie(values=[s_val, w_val, 50], names=['Solar', 'Wind', 'Grid'], hole=0.6)
        st.plotly_chart(fig3, use_container_width=True)
        st.write("4. Forecast vs Actual (Power)")
        fig4 = px.line(st.session_state.history, x="Time", y="Solar")
        st.plotly_chart(fig4, use_container_width=True)

# --- TAB 2: PRODUCTION (Charts 5-8) ---
with tab2:
    c1, c2 = st.columns(2)
    with c1:
        st.write("5. Electrolyzer Efficiency Curve")
        st.line_chart(st.session_state.history.set_index('Time')['Efficiency'])
        st.write("6. Stack Temperature Trend")
        fig6 = go.Figure(go.Indicator(mode="number+delta", value=65, delta={'reference': 60}, title={'text': "Stack Temp °C"}))
        st.plotly_chart(fig6, use_container_width=True)
    with c2:
        st.write("7. Specific Energy (kWh/kg)")
        st.metric("Avg Consumption", "52.4 kWh/kg", "-0.2")
        st.write("8. I-V Polar Characteristic")
        fig8 = go.Figure(go.Scatter(x=[1,2,3], y=[10,20,30], mode='lines+markers'))
        st.plotly_chart(fig8, use_container_width=True)

# --- TAB 3: STORAGE (Charts 9-12) ---
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.write("9. BESS SoC Gauge")
        fig9 = go.Figure(go.Indicator(mode="gauge+number", value=st.session_state.bess_soc*100, gauge={'bar':{'color':"#238636"}}))
        st.plotly_chart(fig9, use_container_width=True)
        st.write("10. Charge/Discharge Cycles")
        st.bar_chart(np.random.randn(20))
    with c2:
        st.write("11. H2 Buffer Pressure")
        st.metric("Pressure", "30.5 bar", "Stable")
        st.write("12. Main Tank Inventory")
        fig12 = px.area(st.session_state.history, x="Time", y="H2_Fill", color_discrete_sequence=['#0ea5e9'])
        st.plotly_chart(fig12, use_container_width=True)

# --- TAB 4: DISTRIBUTION (Charts 13-16) ---
with tab4:
    c1, c2 = st.columns(2)
    with c1:
        st.write("13. H2 Station Capacity (5kg)")
        st.progress(st.session_state.h2_station / 5.0)
        st.write("14. Fuel Cell Power Hub")
        st.metric("FC Output", "22.5 kW", "Active")
    with c2:
        st.write("15. EV Charging Load Profile")
        st.line_chart(st.session_state.history['Solar'] * 0.1) # Simulated load
        st.write("16. Gas Purity Monitor")
        st.success("Purity: 99.999% (ISO 14687)")

# --- TAB 5: ANALYTICS (Charts 17-20) ---
with tab5:
    st.write("17. Integrated Energy Flow (Sankey Diagram)")
    fig17 = go.Figure(go.Sankey(
        node=dict(label=["Sun/Wind", "BESS", "Electrolyzer", "H2 Storage", "EV Station", "Grid"], color="#0ea5e9"),
        link=dict(source=[0, 0, 2, 3, 3], target=[1, 2, 3, 4, 5], value=[10, 20, 15, 8, 7])
    ))
    st.plotly_chart(fig17, use_container_width=True)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write("18. LCOH ($/kg)")
        st.metric("Current Cost", "$4.12 /kg", "-$0.05")
    with c2:
        st.write("19. Carbon Abatement")
        st.metric("Total CO2 Saved", f"{st.session_state.history['CO2'].sum():.1f} kg")
    with c3:
        st.write("20. Grid Profit/Loss")
        st.metric("Net Profit", f"${st.session_state.history['Revenue'].iloc[-1]:.2f}", "+12%")

# REFRESH ENGINE
time.sleep(2)
st.rerun()
