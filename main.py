# =============================================================================
# main.py — LUMINIH2 Digital Twin · Multi-Page (5 Pages)
# =============================================================================

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone, timedelta

from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider
from core_engine import TickEngine, LCOHAccumulator, AlertSystem, HistoryBuffer
from subsystems import SubsystemManager
from optimizer import EconomicOptimizer
from scenario_engine import ScenarioEngine

# =============================================================================
# CONFIG
# =============================================================================
st.set_page_config(page_title="LUMINIH2 Digital Twin", layout="wide")

# =============================================================================
# INIT
# =============================================================================
def init():
    if "init" in st.session_state:
        return

    st.session_state.init = True
    st.session_state.solar = SolarSystem()
    st.session_state.wind = WindSystem()
    st.session_state.bess = BatteryBESS(0.55)
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.h2_chain = HydrogenStorageChain()
    st.session_state.fuel_cell = FuelCellAircell()
    st.session_state.ems = EMSBrain()
    st.session_state.forecaster = AIPredictor()
    st.session_state.weather = WeatherProvider()
    st.session_state.lcoh = LCOHAccumulator()
    st.session_state.alerts = AlertSystem()
    st.session_state.history = HistoryBuffer(maxlen=120)
    st.session_state.subsystems = SubsystemManager()
    st.session_state.optimizer = EconomicOptimizer(Config)
    st.session_state.scenario = ScenarioEngine(Config)

    st.session_state.engine = TickEngine(
        Config,
        st.session_state.solar,
        st.session_state.wind,
        st.session_state.bess,
        st.session_state.electrolyzer,
        st.session_state.h2_chain,
        st.session_state.fuel_cell,
        st.session_state.ems,
        st.session_state.forecaster,
        st.session_state.weather,
        st.session_state.lcoh,
        st.session_state.alerts,
    )

    st.session_state.last = None

init()

# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================
st.sidebar.title("⚡ Navigation")

page = st.sidebar.radio("Go to", [
    "Overview",
    "Energy Flow",
    "Hydrogen System",
    "AI Forecast",
    "Analytics"
])

# =============================================================================
# TICK
# =============================================================================
s, _ = st.session_state.engine.run()
st.session_state.history.append(s)
st.session_state.last = s
hist = st.session_state.history.df

# =============================================================================
# PAGE 1 — OVERVIEW
# =============================================================================
if page == "Overview":

    st.title("⚡ Overview Dashboard")

    c = st.columns(4)
    c[0].metric("Generation", f"{s.total_gen_kw:.1f} kW")
    c[1].metric("BESS SoC", f"{s.bess_soc_pct:.1f}%")
    c[2].metric("H₂ Rate", f"{s.h2_kg_h*1000:.2f} g/h")
    c[3].metric("Revenue", f"€{s.cum_revenue_eur:.2f}")

    st.divider()

    if len(hist) > 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist["time"], y=hist["solar_kw"], name="Solar"))
        fig.add_trace(go.Scatter(x=hist["time"], y=hist["wind_kw"], name="Wind"))
        st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# PAGE 2 — ENERGY FLOW
# =============================================================================
elif page == "Energy Flow":

    st.title("🔄 Energy Flow")

    fig = go.Figure(go.Sankey(
        node=dict(label=["Solar", "Wind", "BESS", "Electrolyzer"]),
        link=dict(
            source=[0,1,2],
            target=[2,2,3],
            value=[s.solar_kw, s.wind_kw, s.bess_charge_kw]
        )
    ))

    st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# PAGE 3 — HYDROGEN SYSTEM
# =============================================================================
elif page == "Hydrogen System":

    st.title("🧪 Hydrogen System")

    col1, col2 = st.columns(2)

    col1.metric("H₂ Production", f"{s.h2_kg_h*1000:.2f} g/h")
    col1.metric("Tank Level", f"{s.main_tank_pct:.1f}%")

    col2.metric("Pressure", f"{s.pressure_bar:.0f} bar")
    col2.metric("Purity", f"{s.elec_purity:.3f}%")

# =============================================================================
# PAGE 4 — AI FORECAST
# =============================================================================
elif page == "AI Forecast":

    st.title("🤖 AI Forecast")

    fc = st.session_state.forecaster.predict()

    if fc and hasattr(fc, "points"):
        df = pd.DataFrame({
            "t": [p.hour_offset for p in fc.points],
            "v": [p.value for p in fc.points]
        })

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["t"], y=df["v"], mode="lines+markers"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No forecast yet")

# =============================================================================
# PAGE 5 — ANALYTICS
# =============================================================================
elif page == "Analytics":

    st.title("📊 Analytics")

    if len(hist) > 5:
        st.line_chart(hist[["solar_kw", "wind_kw"]])

    st.metric("Total H₂", f"{s.cum_h2_kg:.3f} kg")
    st.metric("CO₂ Saved", f"{s.cum_co2_kg:.2f} kg")
