# =============================================================================
# LUMINIH2 Digital Twin v4.1 — نسخه جامع و نهایی (ساختار ۵ صفحه‌ای)
# سیستم مدیریت هیدروژن سبز و تحرک الکتریکی - زاگرب، کرواسی
# =============================================================================

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone, timedelta

# فراخوانی ماژول‌های اصلی (مطمئن شوید این فایل‌ها در پوشه پروژه موجود هستند)
from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider
from core_engine import TickEngine, LCOHAccumulator, AlertSystem, HistoryBuffer
from subsystems import SubsystemManager

# =============================================================================
# ۱. تنظیمات صفحه و استایل صنعتی سفید (CSS)
# =============================================================================
st.set_page_config(page_title="LUMINIH2 Digital Twin", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    /* تم سفید صنعتی */
    html, body, [data-testid="stAppViewContainer"] { background-color: #ffffff !important; color: #0f172a !important; }
    [data-testid="stHeader"] { background-color: #ffffff !important; }
    
    /* کارت‌های KPI */
    .kpi { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 15px; box-shadow: 0 1px 4px rgba(0,0,0,.05); height: 100%; }
    .kpi-lbl { font-size: 10px; color: #64748b; text-transform: uppercase; font-weight: 600; margin: 0; }
    .kpi-val { font-size: 24px; font-weight: 700; margin: 4px 0; color: #0ea5e9; }
    
    /* بخش‌های لاگ EMS */
    .ems-log { background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 10px; font-family: monospace; color: #0369a1; margin: 10px 0; font-size: 12px; }
    
    /* استایل Tabها */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f8fafc; border-radius: 5px 5px 0 0; padding: 10px 20px; color: #64748b; }
    .stTabs [aria-selected="true"] { background-color: #0ea5e9 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# ۲. مدیریت نشست (Session State) و موتور شبیه‌ساز
# =============================================================================
def _init_state():
    if "lumi_v41" not in st.session_state:
        st.session_state.lumi_v41 = True
        # مقداردهی اولیه دارایی‌های فیزیکی
        st.session_state.solar = SolarSystem()
        st.session_state.wind = WindSystem()
        st.session_state.bess = BatteryBESS(0.55)
        st.session_state.electrolyzer = ElectrolyzerS30()
        st.session_state.h2_chain = HydrogenStorageChain()
        st.session_state.fuel_cell = FuelCellAircell()
        st.session_state.ems = EMSBrain()
        st.session_state.forecaster = AIPredictor()
        st.session_state.weather = WeatherProvider()
        st.session_state.lcoh_acc = LCOHAccumulator()
        st.session_state.alerts = AlertSystem()
        st.session_state.history = HistoryBuffer(maxlen=120)
        st.session_state.subsystems = SubsystemManager()
        st.session_state.engine = TickEngine(
            Config, st.session_state.solar, st.session_state.wind, st.session_state.bess,
            st.session_state.electrolyzer, st.session_state.h2_chain, st.session_state.fuel_cell,
            st.session_state.ems, st.session_state.forecaster, st.session_state.weather,
            st.session_state.lcoh_acc, st.session_state.alerts
        )
        st.session_state.sim_running = True
        st.session_state.last_state = None
_init_state()

# =============================================================================
# ۳. نوار کناری (Sidebar) - کنترل‌های مدیریتی
# =============================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#0ea5e9;'>⚡ LUMINIH2 Control</h2>", unsafe_allow_html=True)
    st.session_state.sim_running = st.toggle("Live Simulation", value=st.session_state.sim_running)
    refresh_rate = st.slider("Refresh Interval (sec)", 2, 10, 4)
    st.divider()
    st.subheader("🛠️ Weather & Load")
    use_ov = st.checkbox("Manual Weather Override")
    ov = None
    if use_ov:
        ov = {
            "irradiance": st.slider("Solar Irradiance (W/m²)", 0, 1000, 500),
            "wind_ms": st.slider("Wind Speed (m/s)", 0.0, 20.0, 6.0)
        }
    ev_load = st.slider("EV Charging Demand (kW)", 0.0, 22.0, 2.0)
    if st.button("🔄 Reset Twin"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

# =============================================================================
# ۴. اجرای منطق فیزیکی (The Tick)
# =============================================================================
if st.session_state.sim_running:
    s, fc_res = st.session_state.engine.run(override=ov, ev_demand_kw=ev_load)
    st.session_state.history.append(s)
    st.session_state.last_state = s
    st.session_state.last_fc = fc_res
    st.session_state.sub_result = st.session_state.subsystems.tick(s.h2_kg_h, s.elec_kw, s.wx_temp_c, Config.TIMESTEP_SEC)

s = st.session_state.last_state
hist = st.session_state.history.df
C = dict(solar="#f59e0b", wind="#3b82f6", bess="#22c55e", elec="#8b5cf6", h2="#0ea5e9", grid="#94a3b8")
mk = dict(template="plotly_white", paper_bgcolor="white", plot_bgcolor="#f8fafc", margin=dict(t=30, b=30, l=40, r=20))

if s is None:
    st.warning("در حال اتصال به سنسورها...")
    st.stop()

# =============================================================================
# ۵. رابط کاربری ۵ صفحه‌ای (Tabs)
# =============================================================================
st.title("LUMINIH2 Digital Twin — Dashboard v4.1")

tabs = st.tabs(["🚀 نمای کلی (Overview)", "⚗️ تولید و ذخیره (Production)", "🔋 انرژی و باتری (Energy)", "🧠 پیش‌بینی هوشمند (AI)", "💰 تحلیل اقتصادی (Economics)"])

# --- صفحه ۱: نمای کلی ---
with tabs[0]:
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Generation", f"{s.total_gen_kw:.1f} kW")
    with col2: st.metric("H2 Production", f"{s.h2_kg_h*1000:.1f} g/h")
    with col3: st.metric("BESS SoC", f"{s.bess_soc_pct:.1f}%")
    with col4: st.metric("LCOH Current", f"€{s.lcoh:.2f}/kg")
    
    st.markdown(f'<div class="ems-log">⚡ EMS DISPATCH: {s.switching_event}</div>', unsafe_allow_html=True)
    
    # نمودار Sankey برای جریان انرژی
    fig_sk = go.Figure(go.Sankey(
        node=dict(label=["Solar", "Wind", "BESS", "Electrolyzer", "EV Load", "Grid"], color=["orange", "blue", "green", "purple", "cyan", "gray"]),
        link=dict(source=[0, 1, 2, 3, 3], target=[2, 2, 3, 4, 5], value=[s.solar_kw, s.wind_kw, s.bess_charge_kw, s.ev_kw, s.grid_export_kw])
    ))
    fig_sk.update_layout(title="Energy Flow Mapping", height=400, **mk)
    st.plotly_chart(fig_sk, use_container_width=True)

# --- صفحه ۲: تولید هیدروژن ---
with tabs[1]:
    st.subheader("Hydrogen Electrolysis & Storage Analysis")
    c1, c2 = st.columns([2, 1])
    with c1:
        fig_h2 = go.Figure(go.Bar(x=hist["time"], y=hist["h2_kg_h"]*1000, marker_color=C["h2"]))
        fig_h2.update_layout(title="Production Rate (g/h)", yaxis_title="g/h", **mk)
        st.plotly_chart(fig_h2, use_container_width=True)
    with c2:
        st.markdown(f"""
        <div class="kpi">
            <p class="kpi-lbl">Storage Status</p>
            <p class="kpi-val">{s.pressure_bar:.0f} BAR</p>
            <p style="font-size:12px;">Capacity: {s.main_tank_pct:.1f}% Full</p>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Total Session H2", f"{s.cum_h2_kg:.4f} kg")
        st.metric("Electrolyzer Efficiency", f"{s.elec_eff_pct:.1f}%")

# --- صفحه ۳: مدیریت انرژی و باتری ---
with tabs[2]:
    st.subheader("BESS Performance & Power Mix")
    fig_mix = go.Figure()
    fig_mix.add_trace(go.Scatter(x=hist["time"], y=hist["bess_soc_pct"], name="Battery SoC %", fill='tozeroy', line=dict(color=C["bess"])))
    fig_mix.update_layout(title="State of Charge (SoC) Trend", yaxis_title="%", **mk)
    st.plotly_chart(fig_mix, use_container_width=True)
    
    st.info(f"Battery Temperature: {s.bess_temp_c:.1f} °C | State of Health: {s.bess_soh_pct:.1f}%")

# --- صفحه ۴: هوش مصنوعی و پیش‌بینی ---
with tabs[3]:
    st.subheader("AI-Powered Solar & Wind Forecasting (6h)")
    fc = st.session_state.last_fc
    if fc and hasattr(fc, "points"):
        f_df = pd.DataFrame({
            "Time Offset": [f"+{p.hour_offset+1}h" for p in fc.points],
            "Irradiance": [p.value for p in fc.points]
        })
        fig_fc = go.Figure(go.Scatter(x=f_df["Time Offset"], y=f_df["Irradiance"], mode='lines+markers', name="Predicted"))
        fig_fc.update_layout(title="Solar Irradiance Forecast (W/m²)", **mk)
        st.plotly_chart(fig_fc, use_container_width=True)
    else:
        st.info("در حال جمع‌آوری داده‌ها برای آموزش مدل هوش مصنوعی...")

# --- صفحه ۵: تحلیل اقتصادی ---
with tabs[4]:
    st.subheader("Levelized Cost of Hydrogen & Sustainability")
    e1, e2, e3 = st.columns(3)
    e1.metric("Current LCOH", f"€{s.lcoh:.2f}/kg", delta=f"{s.lcoh - Config.LCOH_TARGET_EURO_KG:.2f}")
    e2.metric("CO2 Offset", f"{s.cum_co2_kg:.3f} kg", "Green Credits")
    e3.metric("Grid Revenue", f"€{s.grid_rev_eur:.4f}")
    
    # گزارش پایداری
    st.success(f"تا این لحظه {s.cum_h2_kg:.4f} کیلوگرم هیدروژن پاک تولید شده که معادل {s.cum_co2_kg:.2f} کیلوگرم جلوگیری از انتشار CO2 است.")

# =============================================================================
# ۶. سیستم رفرش خودکار (Auto-Refresh)
# =============================================================================
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=refresh_rate * 1000, key="main_sim_loop")
