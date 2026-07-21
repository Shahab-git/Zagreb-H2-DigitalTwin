# =============================================================================
# main.py — LUMINIH2 Digital Twin Dashboard v4.2
# White Industrial Theme · AI Forecast Panel · Zagreb, Croatia
# =============================================================================

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone, timedelta
import numpy as np

from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider
from core_engine import TickEngine, LCOHAccumulator, AlertSystem, HistoryBuffer
from scenario_engine import ScenarioEngine, ScenarioParams
from subsystems import SubsystemManager
from optimizer import EconomicOptimizer
from uncertainty_engine import UncertaintyEngine
from database import Database

# =============================================================================
# PAGE CONFIG — must be first Streamlit call
# =============================================================================
st.set_page_config(
    page_title="LUMINIH2 Digital Twin",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# WHITE THEME CSS
# =============================================================================
st.markdown("""
<style>
html,body{background:#ffffff !important}
.stApp{background:#ffffff !important;color:#0f172a !important}
.stApp>div{background:#ffffff !important}
[data-testid="stAppViewContainer"]{background:#ffffff !important}
[data-testid="stHeader"]{background:#ffffff !important;box-shadow:0 1px 4px rgba(0,0,0,.06) !important}
[data-testid="stToolbar"]{background:#ffffff !important}
.main{background:#ffffff !important}
.main .block-container{background:#ffffff !important;padding:.75rem 1.5rem 1rem}
section[data-testid="stSidebar"]{background:#f1f5f9 !important;border-right:1px solid #cbd5e1 !important}
[data-testid="stSidebarContent"]{background:#f1f5f9 !important}

/* All text elements in sidebar — black */
section[data-testid="stSidebar"] *{color:#111827 !important}
section[data-testid="stSidebar"] label{color:#111827 !important;font-size:13px !important;font-weight:600 !important}
section[data-testid="stSidebar"] label p{color:#111827 !important;font-size:13px !important;font-weight:600 !important}
section[data-testid="stSidebar"] p{color:#111827 !important;font-size:13px !important}
section[data-testid="stSidebar"] span{color:#111827 !important}
section[data-testid="stSidebar"] div{color:#111827 !important}
section[data-testid="stSidebar"] small{color:#374151 !important;font-size:12px !important}
section[data-testid="stSidebar"] h3{color:#0f172a !important;font-size:14px !important;font-weight:700 !important}

/* Slider values and ticks in sidebar */
section[data-testid="stSidebar"] [data-testid="stTickBarMin"],
section[data-testid="stSidebar"] [data-testid="stTickBarMax"]{color:#374151 !important;font-size:12px !important;font-weight:600 !important}
section[data-testid="stSidebar"] [data-testid="stThumbValue"]{color:#0ea5e9 !important;font-size:13px !important;font-weight:700 !important}

/* Number inputs in sidebar */
section[data-testid="stSidebar"] input{color:#111827 !important;font-size:13px !important;font-weight:600 !important;background:#ffffff !important}

/* Select boxes in sidebar */
section[data-testid="stSidebar"] select{color:#111827 !important;font-size:13px !important;background:#ffffff !important}
section[data-testid="stSidebar"] [data-baseweb="select"] *{color:#111827 !important;font-size:13px !important}

/* Radio buttons in sidebar */
section[data-testid="stSidebar"] [data-testid="stRadio"] label p{color:#111827 !important;font-size:13px !important;font-weight:600 !important}

/* Toggle / checkbox */
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label p{color:#111827 !important;font-size:13px !important;font-weight:600 !important}

/* Caption text */
[data-testid="stCaptionContainer"]{color:#374151 !important;font-size:12px !important}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#374151 !important}

/* Markdown in sidebar */
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#111827 !important;font-size:13px !important}

/* Divider */
section[data-testid="stSidebar"] hr{border-color:#cbd5e1 !important}

.lumi-header{background:#ffffff;border:1px solid #e2e8f0;border-left:4px solid #0ea5e9;
  border-radius:10px;padding:14px 20px;margin-bottom:16px;box-shadow:0 1px 6px rgba(0,0,0,.05)}

.kpi{background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;
  height:100%;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.kpi-lbl{font-size:11px;color:#374151;text-transform:uppercase;letter-spacing:.06em;margin:0;font-weight:600}
.kpi-val{font-size:22px;font-weight:700;margin:3px 0 2px;color:#111827}
.kpi-sub{font-size:11px;color:#6b7280;margin:0}
.kpi-green{color:#15803d !important}.kpi-amber{color:#b45309 !important}
.kpi-red{color:#b91c1c !important}.kpi-blue{color:#1d4ed8 !important}
.kpi-cyan{color:#0369a1 !important}.kpi-purple{color:#6d28d9 !important}

.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:#dcfce7;color:#14532d;border:1px solid #86efac}
.badge-amber{background:#fef3c7;color:#78350f;border:1px solid #fcd34d}
.badge-red{background:#fee2e2;color:#7f1d1d;border:1px solid #fca5a5}
.badge-cyan{background:#e0f2fe;color:#0c4a6e;border:1px solid #7dd3fc}
.badge-purple{background:#ede9fe;color:#4c1d95;border:1px solid #c4b5fd}
.badge-gray{background:#f1f5f9;color:#1e293b;border:1px solid #cbd5e1}

.switch-log{background:#eff6ff;border:1px solid #bfdbfe;border-left:3px solid #3b82f6;
  border-radius:6px;padding:8px 14px;font-family:'Courier New',monospace;
  font-size:12px;color:#1e3a5f;min-height:36px;margin:8px 0;font-weight:500}

.sec-hdr{font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;
  letter-spacing:.08em;margin:14px 0 8px;border-bottom:2px solid #e2e8f0;padding-bottom:5px}

.stTabs [data-baseweb="tab-list"]{background:#f8fafc;border-bottom:2px solid #e2e8f0;gap:4px}
.stTabs [data-baseweb="tab"]{background:#ffffff;color:#374151;border-radius:8px 8px 0 0;
  padding:8px 16px;border:1px solid #e2e8f0;border-bottom:none;font-size:13px;font-weight:600}
.stTabs [aria-selected="true"]{background:#0ea5e9 !important;color:#ffffff !important;border-color:#0ea5e9 !important}

.alert-error{background:#fef2f2;border:1px solid #fca5a5;border-left:4px solid #ef4444;
  border-radius:8px;padding:10px 14px;color:#7f1d1d;font-size:13px;margin:4px 0;font-weight:500}
.alert-warning{background:#fffbeb;border:1px solid #fcd34d;border-left:4px solid #f59e0b;
  border-radius:8px;padding:10px 14px;color:#78350f;font-size:13px;margin:4px 0;font-weight:500}
.alert-info{background:#eff6ff;border:1px solid #93c5fd;border-left:4px solid #3b82f6;
  border-radius:8px;padding:10px 14px;color:#1e3a5f;font-size:13px;margin:4px 0;font-weight:500}

.health-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9}
[data-testid="stMetricValue"]{color:#111827 !important;font-weight:700 !important}
[data-testid="stMetricLabel"]{color:#374151 !important;font-weight:600 !important}
.stProgress>div>div>div{background:#0ea5e9 !important}
.stButton>button{background:#0ea5e9 !important;color:#ffffff !important;
  border:none !important;border-radius:8px !important;font-weight:600 !important}
.stButton>button:hover{background:#0284c7 !important}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# PLOTLY WHITE TEMPLATE
# =============================================================================
PLOT = dict(
    template="plotly_white",
    paper_bgcolor="#ffffff",
    plot_bgcolor="#f8fafc",
    font_color="#111827",
    font=dict(color="#111827", size=12,
              family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif"),
    margin=dict(t=32, b=56, l=52, r=20),
    legend=dict(
        orientation="h",
        y=-0.22,
        x=0.5,
        xanchor="center",
        yanchor="top",
        font=dict(size=13, color="#111827"),
        bgcolor="rgba(255,255,255,0.95)",
        bordercolor="#e2e8f0",
        borderwidth=1,
        itemsizing="constant",
        itemwidth=40,
        traceorder="normal",
    ),
)

_AX = dict(
    tickfont=dict(color="#111827", size=12),
    title_font=dict(color="#111827", size=12),
    tickcolor="#374151",
    linecolor="#e2e8f0",
    gridcolor="rgba(0,0,0,0.05)",
    zerolinecolor="rgba(0,0,0,0.08)",
)
C = dict(
    solar="#f59e0b", wind="#3b82f6", bess="#22c55e", elec="#8b5cf6",
    h2="#0ea5e9", fc="#ef4444", grid="#94a3b8", ev="#60a5fa",
    co2="#22c55e", water="#3b82f6", o2="#f59e0b",
)
def mk(**kw):
    """Build Plotly layout — enforces black axis labels and titles on every chart."""
    _FONT = dict(color="#111827", size=12)
    base  = {**PLOT}

    # Convert shortcut title strings → proper title dicts with black font
    for short_key, ax_key in [
        ("xaxis_title", "xaxis"), ("yaxis_title", "yaxis"),
        ("xaxis2_title","xaxis2"),("yaxis2_title","yaxis2"),
    ]:
        if short_key in kw:
            title_text = kw.pop(short_key)
            existing   = kw.get(ax_key, {})
            kw[ax_key] = {**existing,
                          "title": {"text": title_text, "font": _FONT}}

    # Inject black axis style; caller overrides take precedence
    for ax_key in ("xaxis", "yaxis", "xaxis2", "yaxis2"):
        if ax_key in kw:
            caller = kw.pop(ax_key)
            # Ensure title has black font even if caller passed a plain string
            if "title" in caller and isinstance(caller["title"], str):
                caller["title"] = {"text": caller["title"], "font": _FONT}
            elif "title" in caller and isinstance(caller["title"], dict):
                caller["title"].setdefault("font", _FONT)
            base[ax_key] = {**_AX, **caller,
                "tickfont":   caller.get("tickfont",   _FONT),
                "title_font": caller.get("title_font", _FONT)}
        else:
            base[ax_key] = {**_AX}
    return {**base, **kw}

# =============================================================================
# STARTUP
# =============================================================================
try:
    validate_config()
except AssertionError as e:
    st.error(f"Config error: {e}"); st.stop()

# =============================================================================
# SESSION STATE
# =============================================================================
def _init():
    if "lumi_v42" in st.session_state:
        return
    st.session_state.lumi_v42     = True
    st.session_state.solar        = SolarSystem()
    st.session_state.wind         = WindSystem()
    st.session_state.bess         = BatteryBESS(0.55)
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.h2_chain     = HydrogenStorageChain()
    st.session_state.fuel_cell    = FuelCellAircell()
    st.session_state.ems          = EMSBrain()
    st.session_state.forecaster   = AIPredictor()
    st.session_state.weather      = WeatherProvider()
    st.session_state.lcoh_acc     = LCOHAccumulator()
    st.session_state.alerts       = AlertSystem()
    st.session_state.history      = HistoryBuffer(maxlen=120)
    st.session_state.subsystems   = SubsystemManager()
    st.session_state.optimizer    = EconomicOptimizer(Config)
    st.session_state.scenario_eng = ScenarioEngine(Config)
    st.session_state.uncertainty  = UncertaintyEngine(Config)
    st.session_state.engine       = TickEngine(
        Config,
        st.session_state.solar, st.session_state.wind,
        st.session_state.bess, st.session_state.electrolyzer,
        st.session_state.h2_chain, st.session_state.fuel_cell,
        st.session_state.ems, st.session_state.forecaster,
        st.session_state.weather, st.session_state.lcoh_acc,
        st.session_state.alerts,
    )
    st.session_state.sim_running   = True
    st.session_state.last_state    = None
    st.session_state.last_fc       = None
    st.session_state.annual_report = None
    st.session_state.opt_result    = None
    st.session_state.sub_result    = None
    st.session_state.unc_report    = None
    st.session_state.voice_enabled     = True
    st.session_state.voice_alert_spoken = set()
    try:
        _db = Database()
        st.session_state.db = _db
        st.session_state.engine.db = _db
    except Exception as _dbe:
        import logging as _lg; _lg.getLogger("main").warning("DB: %s",_dbe)
        st.session_state.db = None
        st.session_state.engine.db = None
_init()

# =============================================================================
# KPI helper
# =============================================================================
def kpi(col, lbl, val, sub_="", cls="kpi-cyan"):
    col.markdown(
        f'<div class="kpi"><p class="kpi-lbl">{lbl}</p>'
        f'<p class="kpi-val {cls}">{val}</p>'
        f'<p class="kpi-sub">{sub_}</p></div>',
        unsafe_allow_html=True)

def hd(col=None):
    if len(hist) < 2: return False
    if col: return col in hist.columns and hist[col].notna().any()
    return True

def hrow(lbl, val, unit, ok, warn, fmt=".1f"):
    """Safety tab health matrix row — green/amber/red indicator."""
    v = float(val)
    if ok[0] <= v <= ok[1]:       cls, ic = "kpi-green", "●"
    elif warn[0] <= v <= warn[1]: cls, ic = "kpi-amber", "▲"
    else:                         cls, ic = "kpi-red",   "✖"
    st.markdown(
        f'<div class="health-row">'
        f'<span style="color:#1e293b;font-size:13px;font-weight:500">{lbl}</span>'
        f'<span class="kpi-val {cls}" style="font-size:14px">'
        f'{ic} {v:{fmt}} {unit}</span></div>',
        unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:

    # ── Brand header ───────────────────────────────────────────────────────
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0ea5e9,#6366f1);
  border-radius:12px;padding:14px 16px;margin-bottom:12px;text-align:center">
  <div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:.04em">
    ⚡ LUMINIH2
  </div>
  <div style="font-size:11px;color:rgba(255,255,255,.85);margin-top:3px;font-weight:500">
    Digital Twin v4.2 · {Config.location.city}, {Config.location.country}
  </div>
</div>""", unsafe_allow_html=True)

    # ── Live status mini-card ──────────────────────────────────────────────
    _s = st.session_state.last_state
    if _s:
        _soc_w  = min(100, _s.bess_soc_pct)
        _gen_w  = min(100, _s.total_gen_kw /
                      (Config.PV_SYSTEM_CAPACITY_KW + Config.WIND_SYSTEM_CAPACITY_KW) * 100)
        _h2_w   = min(100, _s.h2_kg_h * 1000 /
                      (Config.electrolyzer.h2_peak_kg_h * 1000) * 100)
        _soc_c  = "#22c55e" if _s.bess_soc_pct > 30 else "#f59e0b" if _s.bess_soc_pct > 15 else "#ef4444"
        _gen_c  = "#f59e0b"
        _h2_c   = "#0ea5e9"
        st.markdown(f"""
<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;
  padding:12px 14px;margin-bottom:12px">
  <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
    letter-spacing:.06em;margin-bottom:10px">Live system status</div>

  <div style="margin-bottom:7px">
    <div style="display:flex;justify-content:space-between;font-size:12px;
      font-weight:600;color:#111827;margin-bottom:3px">
      <span>☀ Generation</span><span>{_s.total_gen_kw:.1f} kW</span>
    </div>
    <div style="background:#e2e8f0;border-radius:999px;height:7px;overflow:hidden">
      <div style="background:{_gen_c};width:{_gen_w:.0f}%;height:100%;border-radius:999px"></div>
    </div>
  </div>

  <div style="margin-bottom:7px">
    <div style="display:flex;justify-content:space-between;font-size:12px;
      font-weight:600;color:#111827;margin-bottom:3px">
      <span>🔋 Battery SoC</span><span>{_s.bess_soc_pct:.0f}%</span>
    </div>
    <div style="background:#e2e8f0;border-radius:999px;height:7px;overflow:hidden">
      <div style="background:{_soc_c};width:{_soc_w:.0f}%;height:100%;border-radius:999px"></div>
    </div>
  </div>

  <div style="margin-bottom:7px">
    <div style="display:flex;justify-content:space-between;font-size:12px;
      font-weight:600;color:#111827;margin-bottom:3px">
      <span>⚗ H₂ rate</span><span>{_s.h2_kg_h*1000:.1f} g/h</span>
    </div>
    <div style="background:#e2e8f0;border-radius:999px;height:7px;overflow:hidden">
      <div style="background:{_h2_c};width:{_h2_w:.0f}%;height:100%;border-radius:999px"></div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:7px;
      padding:6px 8px;text-align:center">
      <div style="font-size:10px;color:#15803d;font-weight:600">LCOH</div>
      <div style="font-size:14px;font-weight:700;color:#111827">€{_s.lcoh:.2f}</div>
      <div style="font-size:9px;color:#64748b">/kg</div>
    </div>
    <div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:7px;
      padding:6px 8px;text-align:center">
      <div style="font-size:10px;color:#1d4ed8;font-weight:600">Revenue</div>
      <div style="font-size:14px;font-weight:700;color:#111827">€{_s.cum_revenue_eur:.2f}</div>
      <div style="font-size:9px;color:#64748b">session</div>
    </div>
  </div>

  <div style="margin-top:8px;padding-top:8px;border-top:1px solid #f1f5f9;
    font-size:11px;color:#64748b;text-align:center">
    Tick #{_s.tick} · {now_dt.strftime("%H:%M:%S") if "now_dt" in dir() else "--:--:--"}
  </div>
</div>""", unsafe_allow_html=True)

    # ── Simulation control ─────────────────────────────────────────────────
    st.markdown("""<div style="font-size:12px;font-weight:700;color:#0f172a;
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">
      ⚙ Simulation</div>""", unsafe_allow_html=True)
    st.session_state.sim_running = st.toggle(
        "Live simulation", value=st.session_state.sim_running)
    refresh = st.slider(
        "Refresh interval (sec)", 5, 30, 10,
        help="Each refresh rebuilds the voice widget and stops any speech "
             "in progress. Raise this if voice briefings cut off mid-sentence.")
    st.markdown("<div style='margin:10px 0 4px'></div>", unsafe_allow_html=True)

    # ── Weather override ───────────────────────────────────────────────────
    st.markdown("""<div style="font-size:12px;font-weight:700;color:#0f172a;
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">
      🌦 Weather Override</div>""", unsafe_allow_html=True)
    use_ov = st.checkbox("Enable manual override")
    ov = None
    if use_ov:
        st.markdown(
            '<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;'
            'padding:6px 10px;font-size:11px;color:#92400e;font-weight:600;margin-bottom:8px">'
            '⚠ Overriding live weather data</div>', unsafe_allow_html=True)
        ov = {
            "irradiance": st.slider("☀ Irradiance (W/m²)", 0, 1000, 500, 10),
            "wind_ms":    st.slider("💨 Wind speed (m/s)", 0.0, 25.0, 6.0, 0.1),
            "temp_c":     st.slider("🌡 Temperature (°C)", -10, 45, 20),
        }
    else:
        _wx_src = getattr(st.session_state.last_state, "wx_source", "—")                   if st.session_state.last_state else "—"
        st.markdown(
            f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
            f'padding:6px 10px;font-size:11px;color:#15803d;font-weight:600">'
            f'● Live Open-Meteo · Source: {_wx_src.upper()}</div>',
            unsafe_allow_html=True)
    st.markdown("<div style='margin:10px 0 4px'></div>", unsafe_allow_html=True)

    # ── EV & Grid control ──────────────────────────────────────────────────
    st.markdown("""<div style="font-size:12px;font-weight:700;color:#0f172a;
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">
      🔌 EV & Grid</div>""", unsafe_allow_html=True)
    ev_demand  = st.slider(
        "EV charger demand (kW)", 0.0, Config.EV_CHARGER_POWER_KW, 2.0, 0.5)
    st.markdown(
        f'<div style="font-size:11px;color:#374151;margin-top:-6px;margin-bottom:8px">'
        f'{ev_demand:.1f} / {Config.EV_CHARGER_POWER_KW} kW · '
        f'{"● Active" if ev_demand > 0 else "○ Off"}</div>',
        unsafe_allow_html=True)
    force_bess = st.checkbox("Force BESS charge from grid")
    if force_bess:
        st.markdown(
            '<div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:6px;'
            'padding:5px 9px;font-size:11px;color:#1d4ed8;font-weight:600">'
            '🔋 BESS forcing grid import</div>', unsafe_allow_html=True)
    st.markdown("<div style='margin:10px 0 4px'></div>", unsafe_allow_html=True)

    # ── Scenario settings ──────────────────────────────────────────────────
    st.markdown("""<div style="font-size:12px;font-weight:700;color:#0f172a;
      text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">
      📈 Scenario Settings</div>""", unsafe_allow_html=True)
    sc_h2_price = st.slider("H₂ sell price (€/kg)", 3.0, 12.0, 6.0, 0.5)
    st.markdown(
        f'<div style="font-size:11px;color:#374151;margin-top:-6px;margin-bottom:8px">'
        f'Market: €{sc_h2_price:.1f}/kg · '
        f'{"Above break-even ✅" if sc_h2_price >= 5.0 else "Below break-even ⚠"}</div>',
        unsafe_allow_html=True)
    sc_capex     = st.number_input("CAPEX (€)", value=250_000, step=10_000,
                                    min_value=0, max_value=10_000_000)
    sc_opex      = st.number_input("Annual OPEX (€)", value=8_000, step=500,
                                    min_value=0, max_value=500_000)
    sc_elec_mode = st.selectbox(
        "EMS priority mode",
        ["h2_max", "lcoh_opt", "grid_first"],
        format_func=lambda x: {
            "h2_max":     "⚗ H₂ max — peak production",
            "lcoh_opt":   "💰 LCOH optimised",
            "grid_first": "🌐 Grid-first export",
        }.get(x, x))
    st.markdown("<div style='margin:10px 0 4px'></div>", unsafe_allow_html=True)

    # ── Device quick-reference ─────────────────────────────────────────────
    with st.expander("📋 Device specifications", expanded=False):
        st.markdown(f"""
<div style="font-size:11px;color:#111827;line-height:1.8">
  <b>☀ PV array</b> — {Config.PV_SYSTEM_CAPACITY_KW} kW · 42 × 360W mono<br>
  <b>💨 Wind HAWT</b> — {Config.WIND_SYSTEM_CAPACITY_KW} kW · cut-in 2.5 m/s<br>
  <b>🔋 BESS LFP</b> — {Config.BATT_CAPACITY_KWH} kWh · SoC {Config.BATT_SOC_MIN*100:.0f}–{Config.BATT_SOC_MAX*100:.0f}%<br>
  <b>⚗ S30/30 PEM</b> — {Config.ELEC_P_MIN_KW}–{Config.ELEC_P_MAX_KW} kW · {Config.electrolyzer.mttf_hours:,}h MTTF<br>
  <b>🪣 TH540-50</b> — {Config.MAIN_TANK_CAPACITY_KG} kg · {Config.SAFETY_MAX_PRESSURE_BAR:.0f} bar MWP<br>
  <b>⚡ AIRCELL 3000</b> — {Config.FC_POWER_NOM_KW} kW · 99.95% H₂ req.<br>
  <b>🔩 HCS-100</b> — 2 kg/day · {Config.compressor.outlet_nom_bar:.0f} bar outlet<br>
  <b>🌐 Grid Croatia</b> — buy €{Config.GRID_PRICE_BUY}/kWh · sell €{Config.GRID_PRICE_SELL}/kWh
</div>""", unsafe_allow_html=True)

    # ── Reset + version ────────────────────────────────────────────────────
    st.markdown("<div style='margin:8px 0 6px'></div>", unsafe_allow_html=True)
    if st.button("🔄 Reset simulation", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.markdown(f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
  padding:8px 10px;margin-top:8px;text-align:center">
  <div style="font-size:11px;color:#374151;font-weight:600">LUMINIH2 Digital Twin</div>
  <div style="font-size:10px;color:#94a3b8;margin-top:2px">
    v4.2 · Zagreb, Croatia · IEC 62541
  </div>
  <div style="font-size:10px;color:#94a3b8">
    PV {Config.PV_SYSTEM_CAPACITY_KW} kW · Wind {Config.WIND_SYSTEM_CAPACITY_KW} kW · BESS {Config.BATT_CAPACITY_KWH} kWh
  </div>
</div>""", unsafe_allow_html=True)

# =============================================================================
# PHYSICS TICK
# =============================================================================
zagreb_tz = timezone(timedelta(hours=2))
now_dt    = datetime.now(zagreb_tz)

if st.session_state.sim_running:
    s, fc_res = st.session_state.engine.run(
        override=ov, ev_demand_kw=ev_demand, force_bess_charge=force_bess)
    st.session_state.history.append(s)
    st.session_state.last_state = s
    st.session_state.last_fc    = fc_res
    _dbw = st.session_state.get("db")
    if _dbw:
        try: _dbw.write_tick(s)
        except Exception: pass
    sub = st.session_state.subsystems.tick(
        h2_kg_h=s.h2_kg_h, elec_power_kw=s.elec_kw,
        ambient_temp_c=s.wx_temp_c, timestep_sec=Config.TIMESTEP_SEC)
    st.session_state.sub_result = sub
    # Store chain result for HRS dispensing display
    st.session_state.last_chain_result = \
        st.session_state.engine.chain._last_result \
        if hasattr(st.session_state.engine.chain, '_last_result') else None


s    = st.session_state.last_state
hist = st.session_state.history.df
alrt = st.session_state.alerts
sub  = st.session_state.sub_result

# Retrain AI every 20 ticks
if "wx_irradiance" in hist.columns:
    irr_history = list(hist["wx_irradiance"].dropna())
    if len(irr_history) >= 48:
        st.session_state.forecaster.maybe_retrain(irr_history)

if s is None:
    st.info("Starting simulation…"); st.stop()

# =============================================================================
# HEADER
# =============================================================================
st.markdown(f"""
<div class="lumi-header">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
    <div>
      <span style="font-size:21px;font-weight:700;color:#0ea5e9">⚡ LUMINIH2</span>
      <span style="font-size:13px;color:#374151;margin-left:10px;font-weight:500">
        Digital Twin v4.2 · Zagreb, Croatia
      </span>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <span style="font-size:22px;font-weight:700;color:#111827;letter-spacing:.06em">
        {now_dt.strftime('%H:%M:%S')}
      </span>
      <span class="badge badge-cyan">● LIVE</span>
      <span class="badge badge-gray">Tick #{s.tick}</span>
      <span class="badge {'badge-green' if s.wx_source=='live' else 'badge-amber'}">
        WX: {s.wx_source.upper()}
      </span>
      <span class="badge badge-purple">
        EMS: {s.source.split('(')[0].strip()[:12]}
      </span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Voice system ──────────────────────────────────────────────────────────
_new_alerts = []
if st.session_state.get("voice_enabled", True):
    for _a in list(alrt.errors()) + list(alrt.warnings()):
        _key = getattr(_a, "code","") + "_" + getattr(_a, "ts","")
        if _key not in st.session_state.get("voice_alert_spoken", set()):
            st.session_state.voice_alert_spoken.add(_key)
            _new_alerts.append(
                ("Critical alert: " if _a.level == "error" else "Warning: ")
                + _a.message)

_n_total   = len(list(alrt.active)) if alrt.active else 0
_n_err     = len(list(alrt.errors()))
_alert_js  = str(_new_alerts).replace("'", '"')
_von       = "true" if st.session_state.get("voice_enabled", True) else "false"
_btn_cls   = "on" if st.session_state.get("voice_enabled", True) else ""
_btn_lbl   = "🔔 Alerts ON" if st.session_state.get("voice_enabled", True) else "🔕 Alerts OFF"

_st = (f"Status. Generation {s.total_gen_kw:.1f} kilowatts. "
       f"Battery {s.bess_soc_pct:.0f} percent. "
       f"Hydrogen {s.h2_kg_h*1000:.1f} grams per hour. "
       f"LCOH {s.lcoh:.2f}. "
       + ("No alerts." if not alrt.active else
          f"{_n_err} critical, {_n_total} total alerts."))

_hv = (f"Handover, {now_dt.strftime('%H:%M')}. "
       f"Hydrogen {s.cum_h2_kg:.2f} kilograms. "
       f"Revenue {s.cum_revenue_eur:.0f} euros. "
       f"Battery {s.bess_soc_pct:.0f} percent, health {s.bess_soh_pct:.0f} percent. "
       f"Tank {s.main_tank_pct:.0f} percent. "
       + ("No alerts." if not alrt.active
          else f"{_n_total} alert{'s' if _n_total!=1 else ''}.")
       + " End handover.")

_prod  = f"Hydrogen {s.h2_kg_h*1000:.1f} grams per hour. Cumulative {s.cum_h2_kg:.3f} kilograms. Efficiency {s.elec_eff_pct:.0f} percent."
_batt  = f"Battery {s.bess_soc_pct:.0f} percent charge. {s.bess_temp_c:.0f} degrees. Health {s.bess_soh_pct:.1f} percent."
_alrm  = "No active alerts." if not alrt.active else f"{_n_total} active alerts."
_lcoh_ = f"LCOH {s.lcoh:.2f} euros per kilogram. Target {Config.LCOH_TARGET_EURO_KG}."
_rev_  = f"Session revenue {s.cum_revenue_eur:.2f} euros."

components.html(
    f"""<!DOCTYPE html><html><head><style>
body{{margin:0;padding:0;background:transparent;font-family:-apple-system,sans-serif}}
.vb_{{display:flex;align-items:center;gap:8px;padding:9px 14px;
  background:linear-gradient(135deg,#f0f9ff,#f8fafc);
  border:1px solid #bae6fd;border-radius:10px;flex-wrap:wrap}}
.btn{{border:none;border-radius:7px;cursor:pointer;font-size:12px;font-weight:600;
  padding:6px 13px;transition:all .18s}}
.btn:hover{{transform:scale(1.04)}}
.bm{{background:#0ea5e9;color:#fff}}
.bs{{background:#22c55e;color:#fff}}
.bh{{background:#8b5cf6;color:#fff}}
.bx{{background:#ef4444;color:#fff}}
.bt{{background:#f1f5f9;color:#374151;border:1px solid #e2e8f0}}
.bt.on{{background:#dcfce7;color:#15803d;border-color:#86efac}}
.ww{{display:flex;align-items:center;gap:2px;height:20px}}
.wb{{width:3px;border-radius:2px;background:#0ea5e9;height:3px}}
#vs{{font-size:11px;color:#374151;font-weight:500;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
</style></head><body>
<div class="vb_">
  <span style="font-size:13px;font-weight:700;color:#0c4a6e;white-space:nowrap">🔊 Voice</span>
  <button class="btn bm" id="bmic" onclick="sl()" title="Voice command">🎤 Command</button>
  <button class="btn bs" onclick="sp(ST)"            title="System status">📢 Status</button>
  <button class="btn bh" onclick="sp(HV)"            title="Shift handover">📋 Handover</button>
  <button class="btn bx" onclick="xa()"              title="Stop">⏹ Stop</button>
  <button class="btn bt {_btn_cls}" id="btog" onclick="tv()" title="Alert announcements">{_btn_lbl}</button>
  <div class="ww" id="ww"></div>
  <span id="vs">Ready · commands: status · handover · production · battery · alerts · lcoh · revenue</span>
</div>
<script>
var syn=window.speechSynthesis,rc=null,von={_von};
var AL={_alert_js};
var ST="{_st}";var HV="{_hv}";
var PR="{_prod}";var BA="{_batt}";var AM="{_alrm}";var LC="{_lcoh_}";var RV="{_rev_}";
var bars=[],wi=null;
function bw(){{document.getElementById('ww').innerHTML='';bars=[];
  for(var i=0;i<16;i++){{var b=document.createElement('div');b.className='wb';
  document.getElementById('ww').appendChild(b);bars.push(b);}}}}
function wave(on){{if(wi)clearInterval(wi);
  if(!on){{bars.forEach(function(b){{b.style.height='3px';}});return;}}
  wi=setInterval(function(){{bars.forEach(function(b,i){{
    var h=Math.round(3+Math.abs(Math.sin(Date.now()/150+i*.5))*14);
    b.style.height=h+'px';b.style.background=h>10?'#22c55e':'#0ea5e9';
  }});}},50);}}
function gv(){{var vs=syn.getVoices();
  return vs.find(function(v){{return v.lang==='en-GB';}})||
         vs.find(function(v){{return v.lang.startsWith('en');}})||null;}}
function sp(t,r){{if(!syn)return;syn.cancel();
  var u=new SpeechSynthesisUtterance(t);
  u.lang='en-GB';u.rate=r||0.92;u.pitch=1.0;var v=gv();if(v)u.voice=v;
  u.onstart=function(){{wave(true);document.getElementById('vs').textContent='Speaking…';}};
  u.onend=u.onerror=function(){{wave(false);document.getElementById('vs').textContent='Ready';}};
  bw();syn.speak(u);}}
function xa(){{syn.cancel();if(rc){{try{{rc.stop();}}catch(e){{}}}}
  wave(false);document.getElementById('vs').textContent='Stopped';}}
function tv(){{von=!von;var b=document.getElementById('btog');
  b.textContent=von?'🔔 Alerts ON':'🔕 Alerts OFF';b.classList.toggle('on',von);}}
if(von&&AL.length>0)setTimeout(function(){{sp(AL.join('. '),0.88);}},700);
var CM={{status:function(){{sp(ST);}},summary:function(){{sp(ST);}},
  handover:function(){{sp(HV);}},production:function(){{sp(PR);}},
  battery:function(){{sp(BA);}},alerts:function(){{sp(AM);}},
  lcoh:function(){{sp(LC);}},revenue:function(){{sp(RV);}},
  stop:function(){{xa();}}}};
function sl(){{
  var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){{sp('Voice recognition requires Chrome or Edge.');return;}}
  rc=new SR();rc.lang='en-GB';rc.interimResults=false;rc.maxAlternatives=3;
  document.getElementById('vs').textContent='🎤 Listening…';
  document.getElementById('bmic').style.background='#ef4444';wave(true);
  rc.onresult=function(e){{
    var t=e.results[0][0].transcript.toLowerCase().trim();
    document.getElementById('vs').textContent='Heard: "'+t+'"';
    wave(false);document.getElementById('bmic').style.background='#0ea5e9';
    var hit=false;for(var c in CM){{if(t.indexOf(c)!==-1){{CM[c]();hit=true;break;}}}}
    if(!hit)sp('Not recognised. Try: status, handover, production, battery, alerts, lcoh, or revenue.');
  }};
  rc.onerror=function(e){{wave(false);document.getElementById('bmic').style.background='#0ea5e9';
    document.getElementById('vs').textContent='Mic error: '+e.error;}};
  rc.onend=function(){{wave(false);document.getElementById('bmic').style.background='#0ea5e9';}};
  rc.start();}}
bw();
</script></body></html>""",
    height=72, scrolling=False)

for a in alrt.errors():
    st.markdown(f'<div class="alert-error">🚨 [{a.code}] {a.message}</div>', unsafe_allow_html=True)
for a in alrt.warnings():
    st.markdown(f'<div class="alert-warning">⚠ [{a.code}] {a.message}</div>', unsafe_allow_html=True)
if sub:
    for m in sub.get("maintenance", []):
        st.markdown(f'<div class="alert-warning">🔧 {m}</div>', unsafe_allow_html=True)

# =============================================================================
# TOP KPI ROW
# =============================================================================
k = st.columns(6)
kpi(k[0], "Generation",  f"{s.total_gen_kw:.1f} kW",
    f"☀ {s.solar_kw:.1f} + 💨 {s.wind_kw:.1f}", "kpi-amber")
kpi(k[1], "BESS SoC",    f"{s.bess_soc_pct:.1f}%",
    f"{s.bess_temp_c:.1f}°C · SoH {s.bess_soh_pct:.1f}%",
    "kpi-green" if s.bess_soc_pct > 30 else "kpi-red")
kpi(k[2], "H₂ Rate",     f"{s.h2_kg_h*1000:.2f} g/h",
    f"η {s.elec_eff_pct:.1f}% · {s.elec_purity:.3f}% pure", "kpi-cyan")
kpi(k[3], "H₂ Produced", f"{s.cum_h2_kg:.3f} kg",
    f"CO₂ saved {s.cum_co2_kg:.2f} kg", "kpi-cyan")
kpi(k[4], "LCOH",        f"€{s.lcoh:.2f}/kg",
    "✅ Target met" if s.is_profitable else f"Target €{Config.LCOH_TARGET_EURO_KG}",
    "kpi-green" if s.is_profitable else "kpi-amber")
kpi(k[5], "Revenue",     f"€{s.cum_revenue_eur:.2f}",
    f"Grid €{s.grid_rev_eur:.3f}/tick", "kpi-green")

st.markdown(
    f'<div class="switch-log">⚡ EMS → {s.switching_event}</div>',
    unsafe_allow_html=True)

# =============================================================================
# TABS
# =============================================================================
tabs = st.tabs([
    "🌍 Acquisition",
    "⚗️ Production",
    "🔋 Storage",
    "🔌 Distribution",
    "🧪 Subsystems",
    "📅 Annual Sim",
    "💡 Optimizer",
    "📊 Uncertainty",
    "🛡 Safety",
    "📐 EMS Strategy",
    "🏗 Architecture",
])

# ─── TAB 1: ACQUISITION ────────────────────────────────────────────────────
with tabs[0]:
    # ── Row 1: generation mix + weather side by side ─────────────────
    r1a, r1b = st.columns([1, 2])
    with r1a:
        st.markdown('<p class="sec-hdr">Live generation mix</p>', unsafe_allow_html=True)
        fig = go.Figure(go.Pie(
            values=[max(.01,s.solar_kw), max(.01,s.wind_kw), max(.01,s.grid_import_kw)],
            labels=["Solar PV","Wind","Grid Import"], hole=0.65,
            marker=dict(colors=[C["solar"],C["wind"],C["grid"]],
                        line=dict(color="#ffffff",width=2))))
        fig.add_annotation(text=f"<b>{s.total_gen_kw:.1f}</b><br>kW",
                           showarrow=False, font=dict(size=14,color="#111827"),
                           x=0.5, y=0.5, xref="paper", yref="paper")
        fig.update_layout(**mk(height=220, showlegend=True,
                               legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<p class="sec-hdr">Irradiance trend — live</p>', unsafe_allow_html=True)
        # Build historical data arrays from session history
        irr_vals = list(hist["wx_irradiance"].dropna()) if hd("wx_irradiance") else []
        irr_times = list(hist["time"].iloc[-len(irr_vals):]) if irr_vals else []
        irr_json  = "[" + ",".join(str(round(float(v),1)) for v in irr_vals[-72:]) + "]"
        time_json = "[" + ",".join(f'"{t}"' for t in irr_times[-72:]) + "]"
        cur_irr   = round(float(s.wx_irradiance), 1)
        cur_cloud = round(max(0, (850 - cur_irr) / 850 * 60))
        peak_irr  = round(max((float(v) for v in irr_vals), default=cur_irr))
        avg_irr   = round(sum(float(v) for v in irr_vals[-72:]) / max(len(irr_vals[-72:]),1))
        irr_html  = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:6px">
  <div>
    <span style="font-size:12px;font-weight:500;color:#374151">Solar irradiance · Zagreb</span>
    <span style="font-size:11px;color:#94a3b8;margin-left:8px">last {min(len(irr_vals),72)} readings · W/m²</span>
  </div>
  <div style="display:flex;gap:12px;font-size:11px;color:#6b7280">
    <span><span style="display:inline-block;width:14px;height:3px;background:#f59e0b;vertical-align:middle;border-radius:2px;margin-right:4px"></span>Measured</span>
    <span><span style="display:inline-block;width:14px;height:2px;border-top:2px dashed #3b82f6;vertical-align:middle;margin-right:4px"></span>Forecast</span>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px">
    <div style="font-size:10px;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:.05em">Now</div>
    <div style="font-size:19px;font-weight:500;color:#111827">{cur_irr}</div>
    <div style="font-size:10px;color:#94a3b8">W/m²</div>
  </div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px">
    <div style="font-size:10px;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:.05em">Session peak</div>
    <div style="font-size:19px;font-weight:500;color:#111827">{peak_irr}</div>
    <div style="font-size:10px;color:#94a3b8">W/m²</div>
  </div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px">
    <div style="font-size:10px;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:.05em">Average</div>
    <div style="font-size:19px;font-weight:500;color:#111827">{avg_irr}</div>
    <div style="font-size:10px;color:#94a3b8">W/m²</div>
  </div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px">
    <div style="font-size:10px;color:#64748b;font-weight:500;text-transform:uppercase;letter-spacing:.05em">Cloud est.</div>
    <div style="font-size:19px;font-weight:500;color:#111827">{cur_cloud}%</div>
    <div style="font-size:10px;color:#94a3b8">coverage</div>
  </div>
</div>
<div style="position:relative;width:100%;height:220px">
  <canvas id="irrC" role="img" aria-label="Solar irradiance trend W/m² over session"></canvas>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
(function(){{
  var hist={irr_json};
  var times={time_json};
  var isDark=matchMedia('(prefers-color-scheme: dark)').matches;
  var gc=isDark?'rgba(255,255,255,0.06)':'rgba(0,0,0,0.05)';
  var tc=isDark?'rgba(255,255,255,0.85)':'#111827';
  var fc=[];
  var lastV=hist.length?hist[hist.length-1]:0;
  for(var i=1;i<=6;i++)fc.push(Math.max(0,Math.round(lastV*(0.95+Math.random()*0.1))));
  var fcLabels=[];
  for(var j=1;j<=6;j++)fcLabels.push('+'+j+'tick');
  var allLabels=times.concat(fcLabels);
  var ctx=document.getElementById('irrC').getContext('2d');
  var g=ctx.createLinearGradient(0,0,0,220);
  g.addColorStop(0,'rgba(245,158,11,0.22)');
  g.addColorStop(1,'rgba(245,158,11,0.01)');
  new Chart(ctx,{{
    type:'line',
    data:{{
      labels:allLabels,
      datasets:[
        {{label:'W/m²',data:hist.concat(new Array(6).fill(null)),
          borderColor:'#f59e0b',borderWidth:2,backgroundColor:g,
          fill:true,tension:0.42,pointRadius:0,
          pointHoverRadius:4,pointHoverBackgroundColor:'#f59e0b',pointHoverBorderColor:'#fff',pointHoverBorderWidth:2}},
        {{label:'Forecast',data:new Array(hist.length).fill(null).concat(fc),
          borderColor:'#3b82f6',borderWidth:1.5,borderDash:[5,4],
          backgroundColor:'rgba(59,130,246,0.07)',fill:true,
          tension:0.4,pointRadius:0,pointHoverRadius:3}}
      ]
    }},
    options:{{
      responsive:true,maintainAspectRatio:false,
      animation:{{duration:0}},
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{display:false}},
        tooltip:{{
          backgroundColor:isDark?'rgba(15,23,42,0.95)':'rgba(255,255,255,0.97)',
          borderColor:isDark?'rgba(255,255,255,0.1)':'rgba(0,0,0,0.08)',
          borderWidth:1,
          titleColor:isDark?'#f1f5f9':'#111827',
          bodyColor:isDark?'rgba(255,255,255,0.6)':'rgba(0,0,0,0.55)',
          padding:8,
          callbacks:{{label:function(c){{return c.dataset.label+': '+Math.round(c.parsed.y)+' W/m²';}}}}
        }}
      }},
      scales:{{
        x:{{grid:{{color:gc,lineWidth:0.5}},ticks:{{color:tc,font:{{size:10}},maxTicksLimit:7,maxRotation:0}},border:{{display:false}}}},
        y:{{min:0,grid:{{color:gc,lineWidth:0.5}},
          ticks:{{color:tc,font:{{size:10}},callback:function(v){{return v>=1000?'1k':v;}}}},
          border:{{display:false}},
          title:{{display:true,text:'W/m²',color:tc,font:{{size:10}}}}}}
      }}
    }}
  }});
}})();
</script>
</div>"""
        components.html(irr_html, height=360, scrolling=False)

    with r1b:
        st.markdown('<p class="sec-hdr">Weather telemetry</p>', unsafe_allow_html=True)
        wc = st.columns(3)
        wc[0].metric("Temperature", f"{s.wx_temp_c:.1f}°C")
        wc[1].metric("Wind speed",  f"{s.wx_wind_ms:.1f} m/s")
        wc[2].metric("Humidity",    f"{s.wx_humidity:.0f}%")
        wc2 = st.columns(3)
        wc2[0].metric("Irradiance", f"{s.wx_irradiance:.0f} W/m²")
        wc2[1].metric("Soiling",    f"{s.wx_soiling:.3f}")
        wc2[2].metric("Precip",     f"{s.wx_precip_mm:.1f} mm")

    # ── Forecast-aware EMS status ──────────────────────────────────────
    _fc_strat = getattr(s, "ems_strategy", "")
    _fc_pv    = getattr(s, "next_6h_pv_kwh", 0.0)
    _fc_sp    = getattr(s, "ems_elec_setpoint", 0.0)
    if _fc_strat and _fc_strat not in ("normal", "standby", ""):
        st.markdown(
            f'<div class="alert-info" style="margin:4px 0 8px">🔮 '
            f'<b>Forecast EMS:</b> {_fc_strat} · '
            f'6h PV: {_fc_pv:.1f} kWh · '
            f'Recommended: {_fc_sp:.2f} kW</div>',
            unsafe_allow_html=True)

    # ── Row 2: AI forecast panel FULL WIDTH ────────────────────────────
    st.markdown('<p class="sec-hdr">AI solar forecast — Zagreb skyline panel</p>',
                unsafe_allow_html=True)
    fc_res   = st.session_state.last_fc
    last_24h = list(hist["wx_irradiance"].tail(24)) \
               if hd("wx_irradiance") else None
    # Regenerate forecast with 6-hour horizon for the panel
    if last_24h and len(last_24h) >= 6:
        fc_res = st.session_state.forecaster.predict_future(
            last_24h, horizon_hours=6, current_dt=now_dt)
    html_panel = st.session_state.forecaster.render_panel(
        result=fc_res,
        current_dt=now_dt,
        last_24h_irradiance=last_24h,
        height=850,
    )
    components.html(html_panel, height=680, scrolling=False)

# ─── TAB 2: PRODUCTION ─────────────────────────────────────────────────────
with tabs[1]:

    # ── 1. KPI row ─────────────────────────────────────────────────────────
    pk = st.columns(5)
    elec_mode = (
        "overload" if s.elec_kw > Config.ELEC_P_NOM_KW * 1.05 else
        "nominal"  if s.elec_kw >= Config.ELEC_P_NOM_KW * 0.90 else
        "partial"  if s.elec_kw >= Config.ELEC_P_MIN_KW else "off"
    )
    mode_colors = {"nominal":"kpi-green","overload":"kpi-amber","partial":"kpi-blue","off":"kpi-red"}
    mode_icons  = {"nominal":"● Nominal","overload":"▲ Overload","partial":"◎ Partial","off":"○ Off"}
    kpi(pk[0], "Electrolyzer load", f"{s.elec_kw:.2f} kW",
        f"Range {Config.ELEC_P_MIN_KW}–{Config.ELEC_P_MAX_KW} kW", "kpi-purple")
    kpi(pk[1], "H₂ rate",
        f"{s.h2_kg_h*1000:.2f} g/h",
        f"Nom: {Config.electrolyzer.h2_nom_kg_h*1000:.1f} g/h", "kpi-cyan")
    kpi(pk[2], "Efficiency",
        f"{s.elec_eff_pct:.1f}%",
        f"Purity {s.elec_purity:.3f}%",
        "kpi-green" if s.elec_eff_pct >= 75 else "kpi-amber")
    kpi(pk[3], "Stack SoH",
        f"{s.elec_soh_pct:.2f}%",
        f"MTTF {Config.electrolyzer.mttf_hours:,} h",
        "kpi-green" if s.elec_soh_pct >= 90 else "kpi-amber" if s.elec_soh_pct >= 80 else "kpi-red")
    kpi(pk[4], "Operating mode",
        mode_icons.get(elec_mode, "—"),
        f"{s.elec_kw:.2f} kW → {s.h2_kg_h*1000:.1f} g/h",
        mode_colors.get(elec_mode, "kpi-blue"))

    # ── 2. Power allocation — FULL WIDTH ───────────────────────────────────
    st.markdown('<p class="sec-hdr">Power allocation — real-time stacked</p>', unsafe_allow_html=True)
    if hd():
        f5 = go.Figure()
        for col, color, fill, name in [
            ("elec_kw",        C["elec"], "rgba(139,92,246,.55)", "Electrolyzer"),
            ("bess_charge_kw", C["bess"], "rgba(34,197,94,.45)",  "BESS charge"),
            ("ev_kw",          C["ev"],   "rgba(96,165,250,.45)", "EV charger"),
            ("grid_export_kw", C["grid"], "rgba(148,163,184,.4)", "Grid export"),
        ]:
            if col in hist.columns:
                f5.add_trace(go.Scatter(
                    x=hist["time"], y=hist[col],
                    stackgroup="one", name=name,
                    line=dict(color=color, width=1.5), fillcolor=fill,
                    hovertemplate="%{y:.2f} kW<extra>" + name + "</extra>"))
        if "total_gen_kw" in hist.columns:
            f5.add_trace(go.Scatter(
                x=hist["time"], y=hist["total_gen_kw"],
                name="Total generation",
                line=dict(color=C["solar"], width=2, dash="dot"),
                hovertemplate="%{y:.2f} kW<extra>Total gen</extra>"))
        f5.update_layout(**mk(height=260, yaxis_title="kW",
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
        st.plotly_chart(f5, use_container_width=True)

    # ── 3. H₂ trend + cumulative | Efficiency scatter + quality ───────────
    p2a, p2b = st.columns(2)
    with p2a:
        st.markdown('<p class="sec-hdr">H₂ production rate — live trend</p>', unsafe_allow_html=True)
        if hd("h2_kg_h"):
            f7 = go.Figure()
            f7.add_trace(go.Scatter(
                x=hist["time"], y=(hist["h2_kg_h"]*1000).round(2),
                fill="tozeroy", fillcolor="rgba(14,165,233,.12)",
                line=dict(color=C["h2"], width=2.5), name="g/h",
                hovertemplate="%{y:.1f} g/h<extra></extra>"))
            for ref_val, ref_lbl, ref_col in [
                (Config.electrolyzer.h2_min_kg_h*1000,  "Min",  "#94a3b8"),
                (Config.electrolyzer.h2_nom_kg_h*1000,  "Nom",  "#22c55e"),
                (Config.electrolyzer.h2_peak_kg_h*1000, "Peak", "#f59e0b"),
            ]:
                f7.add_hline(y=ref_val, line_dash="dot", line_color=ref_col,
                    line_width=1.2, annotation_text=ref_lbl,
                    annotation_font_color=ref_col, annotation_font_size=10)
            f7.update_layout(**mk(height=220, yaxis_title="g H₂/h"))
            st.plotly_chart(f7, use_container_width=True)

        st.markdown('<p class="sec-hdr">Session H₂ production</p>', unsafe_allow_html=True)
        daily_target_kg = Config.electrolyzer.h2_peak_kg_h * 18
        cum_pct = min(100.0, (s.cum_h2_kg / max(daily_target_kg, 1e-6)) * 100)
        bar_col = "#22c55e" if cum_pct >= 50 else "#f59e0b" if cum_pct >= 20 else "#0ea5e9"
        st.markdown(
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:8px">'
            f'<span style="font-size:13px;font-weight:600;color:#111827">{s.cum_h2_kg:.4f} kg produced</span>'
            f'<span style="font-size:12px;color:#6b7280">Target: {daily_target_kg:.2f} kg/day</span>'
            f'</div>'
            f'<div style="background:#e2e8f0;border-radius:999px;height:12px;overflow:hidden">'
            f'<div style="background:{bar_col};width:{cum_pct:.1f}%;height:100%;border-radius:999px"></div>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:6px">'
            f'<span style="font-size:11px;color:#6b7280">{cum_pct:.1f}% of daily target</span>'
            f'<span style="font-size:11px;color:#6b7280">CO₂ saved: {s.cum_co2_kg:.3f} kg vs SMR</span>'
            f'</div></div>',
            unsafe_allow_html=True)

    with p2b:
        st.markdown('<p class="sec-hdr">Efficiency vs load — S30/30 datasheet curve</p>', unsafe_allow_html=True)
        if hd("elec_eff_pct") and len(hist) > 3:
            import numpy as np_tab2
            f8 = go.Figure()
            ds_p  = sorted(Config.ELEC_EFF_CURVE.keys())
            ds_e  = [Config.ELEC_EFF_CURVE[p] * 100 for p in ds_p]
            p_line = np_tab2.linspace(Config.ELEC_P_MIN_KW, Config.ELEC_P_MAX_KW, 50)
            e_line = np_tab2.interp(p_line, ds_p, ds_e)
            f8.add_trace(go.Scatter(x=p_line, y=e_line, name="S30/30 datasheet",
                line=dict(color="#cbd5e1", width=3),
                hovertemplate="Datasheet η: %{y:.1f}%<extra></extra>"))
            for p_pt, e_pt, pt_lbl in zip(ds_p, ds_e, ["Min 0.74kW","Nominal 3kW","Peak 5.63kW"]):
                f8.add_trace(go.Scatter(x=[p_pt], y=[e_pt], mode="markers+text",
                    marker=dict(color=C["elec"], size=10, line=dict(color="#fff",width=2)),
                    text=[f"{e_pt:.0f}%"], textposition="top center",
                    textfont=dict(size=10, color="#374151"),
                    name=pt_lbl, showlegend=False))
            f8.add_trace(go.Scatter(x=hist["elec_kw"], y=hist["elec_eff_pct"],
                mode="markers", name="Live ticks",
                marker=dict(color=hist["h2_kg_h"]*1000,
                    colorscale=[[0,"#f0f9ff"],[0.5,C["h2"]],[1,"#0369a1"]],
                    size=6, opacity=0.75,
                    colorbar=dict(title="g/h", thickness=10, len=0.6),
                    line=dict(color="#ffffff", width=0.5)),
                hovertemplate="Load: %{x:.2f} kW  η: %{y:.1f}%<extra></extra>"))
            f8.add_trace(go.Scatter(x=[s.elec_kw], y=[s.elec_eff_pct],
                mode="markers", name="Now",
                marker=dict(color=C["fc"], size=14, symbol="star",
                    line=dict(color="#fff",width=2)),
                hovertemplate=f"Now: {s.elec_kw:.2f} kW  η={s.elec_eff_pct:.1f}%<extra></extra>"))
            f8.update_layout(**mk(height=260,
                xaxis_title="Electrolyzer power (kW)",
                yaxis_title="Efficiency η (%)",
                xaxis=dict(range=[0, Config.ELEC_P_MAX_KW + 0.3]),
                yaxis=dict(range=[50, 95]),
                legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
            st.plotly_chart(f8, use_container_width=True)

        st.markdown('<p class="sec-hdr">Process quality</p>', unsafe_allow_html=True)
        qc = st.columns(3)
        pur_ok = s.elec_purity >= 99.95
        wat_lim = Config.WATER_CONSUMPTION_L_KG * Config.electrolyzer.h2_nom_kg_h * 1.1
        kpi(qc[0], "H₂ Purity", f"{s.elec_purity:.4f}%",
            "✅ AIRCELL spec" if pur_ok else "⚠ Below 99.95%",
            "kpi-green" if pur_ok else "kpi-red")
        kpi(qc[1], "Water use", f"{s.water_l_h:.3f} L/h",
            f"Spec: {Config.WATER_CONSUMPTION_L_KG:.1f} L/kg",
            "kpi-cyan" if s.water_l_h <= wat_lim else "kpi-amber")
        kpi(qc[2], "Heat recovery", f"{s.heat_kw:.3f} kW",
            f"{Config.HEAT_RECOVERY_FACTOR*100:.0f}% recovered",
            "kpi-green" if s.heat_kw > 0 else "kpi-gray")

# ─── TAB 3: STORAGE ────────────────────────────────────────────────────────
with tabs[2]:

    # ── 1. KPI strip ───────────────────────────────────────────────────────
    sk = st.columns(5)
    bess_cls  = "kpi-green" if s.bess_soc_pct > 30 else "kpi-amber" if s.bess_soc_pct > 15 else "kpi-red"
    temp_cls  = "kpi-green" if s.bess_temp_c < 45 else "kpi-amber" if s.bess_temp_c < 55 else "kpi-red"
    tank_cls  = "kpi-cyan"  if s.main_tank_pct > 40 else "kpi-amber" if s.main_tank_pct > 10 else "kpi-red"
    pres_cls  = "kpi-blue"  if s.pressure_bar < Config.SAFETY_MAX_PRESSURE_BAR * 0.80 else "kpi-amber"
    comp_cls2 = "kpi-green" if s.compressor_on else "kpi-gray"
    kpi(sk[0], "BESS SoC",       f"{s.bess_soc_pct:.1f}%",
        f"SoH {s.bess_soh_pct:.1f}% · {s.bess_temp_c:.1f}°C", bess_cls)
    kpi(sk[1], "BESS Temperature", f"{s.bess_temp_c:.1f}°C",
        "✅ Normal" if s.bess_temp_c < 45 else "⚠ Elevated" if s.bess_temp_c < 55 else "🔥 Critical",
        temp_cls)
    kpi(sk[2], "Main Tank",      f"{s.main_tank_pct:.1f}%",
        f"{s.main_tank_pct/100*Config.MAIN_TANK_CAPACITY_KG:.2f} / {Config.MAIN_TANK_CAPACITY_KG} kg",
        tank_cls)
    kpi(sk[3], "Tank Pressure",  f"{s.pressure_bar:.0f} bar",
        f"Max {Config.SAFETY_MAX_PRESSURE_BAR:.0f} bar (MWP)", pres_cls)
    kpi(sk[4], "Compressor HCS-100",
        "● ON" if s.compressor_on else "○ STANDBY",
        f"Tank {s.tank_temp_c:.1f}°C", comp_cls2)

    # ── 2. H₂ chain flow diagram — full width ──────────────────────────────
    st.markdown('<p class="sec-hdr">H₂ storage chain — live flow</p>', unsafe_allow_html=True)

    # Calculate days-to-full and hours-to-empty
    h2_rate_kg_h = s.h2_kg_h
    main_kg      = s.main_tank_pct / 100 * Config.MAIN_TANK_CAPACITY_KG
    remaining_kg = Config.MAIN_TANK_CAPACITY_KG * 0.9 - main_kg
    days_to_full = (remaining_kg / max(h2_rate_kg_h * 24 * 0.6, 0.001)
                    if remaining_kg > 0 else 0.0)
    hrs_to_empty = (main_kg / max(h2_rate_kg_h, 0.001)
                    if main_kg > 0 else 0.0)

    def _tank_color(pct):
        if pct >= 60: return "#22c55e"
        if pct >= 20: return "#f59e0b"
        return "#ef4444"

    buf_col  = _tank_color(s.buffer_pct)
    main_col = _tank_color(s.main_tank_pct)
    hrs_col  = _tank_color(s.hrs_pct)
    comp_arrow = "→" if s.compressor_on else "⊘"
    comp_arrow_col = "#22c55e" if s.compressor_on else "#94a3b8"

    _flow_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;font-family:-apple-system,sans-serif">
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;
  padding:20px 24px;margin-bottom:4px">
  <div style="display:grid;grid-template-columns:1fr 48px 1fr 48px 1fr 48px 1fr;
    align-items:center;gap:0">
    <div style="text-align:center">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
        letter-spacing:.06em;margin-bottom:8px">Buffer Tank</div>
      <div style="background:#e2e8f0;border-radius:8px;height:90px;position:relative;
        overflow:hidden;border:2px solid {buf_col}">
        <div style="position:absolute;bottom:0;left:0;right:0;
          background:{buf_col};opacity:.25;height:{s.buffer_pct}%"></div>
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;
          align-items:center;justify-content:center">
          <span style="font-size:22px;font-weight:700;color:#111827">{s.buffer_pct:.0f}%</span>
          <span style="font-size:10px;color:#64748b">20 bar · 0.5 kg cap</span>
        </div>
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:6px">
        {s.buffer_pct/100*Config.BUFFER_TANK_CAPACITY_KG:.3f} kg
      </div>
    </div>
    <div style="text-align:center;font-size:24px;color:{comp_arrow_col};font-weight:700">
      {comp_arrow}
    </div>
    <div style="text-align:center">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
        letter-spacing:.06em;margin-bottom:8px">HCS-100</div>
      <div style="background:{"#dcfce7" if s.compressor_on else "#f1f5f9"};
        border:2px solid {"#22c55e" if s.compressor_on else "#e2e8f0"};
        border-radius:8px;height:90px;display:flex;flex-direction:column;
        align-items:center;justify-content:center">
        <span style="font-size:28px">{"⚙" if s.compressor_on else "○"}</span>
        <span style="font-size:12px;font-weight:600;
          color:{"#15803d" if s.compressor_on else "#94a3b8"}">
          {"RUNNING" if s.compressor_on else "STANDBY"}
        </span>
        <span style="font-size:10px;color:#64748b">2.7 kW · 2 kg/day</span>
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:6px">
        {Config.compressor.outlet_nom_bar:.0f} bar outlet
      </div>
    </div>
    <div style="text-align:center;font-size:24px;color:{comp_arrow_col};font-weight:700">
      {comp_arrow}
    </div>
    <div style="text-align:center">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
        letter-spacing:.06em;margin-bottom:8px">TH540-50</div>
      <div style="background:#e2e8f0;border-radius:8px;height:90px;position:relative;
        overflow:hidden;border:2px solid {main_col}">
        <div style="position:absolute;bottom:0;left:0;right:0;
          background:{main_col};opacity:.25;height:{s.main_tank_pct}%"></div>
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;
          align-items:center;justify-content:center">
          <span style="font-size:22px;font-weight:700;color:#111827">{s.main_tank_pct:.0f}%</span>
          <span style="font-size:10px;color:#64748b">{s.pressure_bar:.0f} bar</span>
        </div>
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:6px">
        {main_kg:.3f} / {Config.MAIN_TANK_CAPACITY_KG} kg usable
      </div>
    </div>
    <div style="text-align:center;font-size:24px;color:#0ea5e9;font-weight:700">→</div>
    <div style="text-align:center">
      <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
        letter-spacing:.06em;margin-bottom:8px">HRS Station</div>
      <div style="background:#e2e8f0;border-radius:8px;height:90px;position:relative;
        overflow:hidden;border:2px solid {hrs_col}">
        <div style="position:absolute;bottom:0;left:0;right:0;
          background:{hrs_col};opacity:.25;height:{s.hrs_pct}%"></div>
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;
          align-items:center;justify-content:center">
          <span style="font-size:22px;font-weight:700;color:#111827">{s.hrs_pct:.0f}%</span>
          <span style="font-size:10px;color:#64748b">⛽ 5 kg capacity</span>
        </div>
      </div>
      <div style="font-size:11px;color:#64748b;margin-top:6px">
        {s.hrs_pct/100*Config.HRS_H2_TANK_CAPACITY_KG:.3f} kg ready
      </div>
    </div>

  </div>
  <div style="display:flex;justify-content:space-between;margin-top:14px;
    padding-top:12px;border-top:1px solid #e2e8f0;flex-wrap:wrap;gap:8px">
    <span style="font-size:12px;color:#374151">
      <b>Days to full tank:</b>
      {"Tank full ✅" if days_to_full <= 0 else f"{days_to_full:.1f} days at current rate"}
    </span>
    <span style="font-size:12px;color:#374151">
      <b>H₂ flow rate:</b> {h2_rate_kg_h*1000:.2f} g/h → compressor
    </span>
    <span style="font-size:12px;color:#374151">
      <b>Leak status:</b>
      {"⚠ LEAK DETECTED" if s.leak_detected else "✅ No leak detected"}
    </span>
    <span style="font-size:12px;color:#374151">
      <b>Tank temperature:</b> {s.tank_temp_c:.1f}°C
    </span>
  </div>
</div></body></html>"""
    components.html(_flow_html, height=220, scrolling=False)

    # ── 3. BESS SoC trend + H₂ tank trends ────────────────────────────────
    s3a, s3b = st.columns(2)
    with s3a:
        st.markdown('<p class="sec-hdr">BESS — SoC history & gauge</p>', unsafe_allow_html=True)
        sc3a_inner = st.columns([1, 1])
        with sc3a_inner[0]:
            f9 = go.Figure(go.Indicator(
                mode="gauge+number",
                value=s.bess_soc_pct,
                title={"text":"SoC (%)","font":{"color":"#111827","size":13}},
                number={"font":{"color":"#111827","size":28}},
                gauge={"axis":{"range":[0,100],"tickcolor":"#374151"},
                       "bar":{"color":C["bess"]},"bgcolor":"#f8fafc",
                       "steps":[
                           {"range":[0, Config.BATT_SOC_MIN*100],          "color":"#fee2e2"},
                           {"range":[Config.BATT_SOC_MIN*100,
                                     Config.BATT_SOC_MAX*100],             "color":"#dcfce7"},
                           {"range":[Config.BATT_SOC_MAX*100, 100],        "color":"#fef9c3"},
                       ],
                       "threshold":{"line":{"color":C["fc"],"width":2},
                                    "value":Config.BATT_SOC_MIN*100}}))
            f9.update_layout(**mk(height=200, margin=dict(t=20,b=10,l=20,r=20)))
            st.plotly_chart(f9, use_container_width=True)
        with sc3a_inner[1]:
            if hd("bess_soc_pct"):
                f9b = go.Figure()
                f9b.add_trace(go.Scatter(
                    x=hist["time"], y=hist["bess_soc_pct"],
                    fill="tozeroy", fillcolor="rgba(34,197,94,.10)",
                    line=dict(color=C["bess"], width=2), name="SoC %",
                    hovertemplate="%{y:.1f}%<extra>SoC</extra>"))
                f9b.add_hline(y=Config.BATT_SOC_MIN*100, line_dash="dot",
                    line_color=C["fc"], line_width=1.2,
                    annotation_text=f"Min {Config.BATT_SOC_MIN*100:.0f}%",
                    annotation_font_size=10, annotation_font_color=C["fc"])
                f9b.add_hline(y=Config.BATT_SOC_MAX*100, line_dash="dot",
                    line_color="#94a3b8", line_width=1.2,
                    annotation_text=f"Max {Config.BATT_SOC_MAX*100:.0f}%",
                    annotation_font_size=10)
                f9b.update_layout(**mk(height=200,
                    yaxis_title="%", yaxis=dict(range=[0,105]),
                    margin=dict(t=20,b=10,l=44,r=10)))
                st.plotly_chart(f9b, use_container_width=True)

        # BESS temperature with zone shading
        if hd("bess_temp_c"):
            st.markdown('<p class="sec-hdr">BESS temperature — thermal zones</p>',
                        unsafe_allow_html=True)
            f10 = go.Figure()
            # Danger zone shading
            f10.add_hrect(y0=55, y1=Config.THERMAL_RUNAWAY_TEMP,
                fillcolor="rgba(239,68,68,.08)", line_width=0,
                annotation_text="⚠ Warning zone", annotation_font_size=10,
                annotation_font_color="#b91c1c")
            f10.add_hrect(y0=Config.THERMAL_RUNAWAY_TEMP, y1=100,
                fillcolor="rgba(239,68,68,.18)", line_width=0,
                annotation_text="🔥 Runaway zone", annotation_font_size=10,
                annotation_font_color="#7f1d1d")
            f10.add_trace(go.Scatter(
                x=hist["time"], y=hist["bess_temp_c"],
                fill="tozeroy", fillcolor="rgba(239,68,68,.06)",
                line=dict(color=C["fc"], width=2), name="°C",
                hovertemplate="%{y:.1f}°C<extra>BESS temp</extra>"))
            f10.add_hline(y=55, line_dash="dash", line_color=C["solar"],
                line_width=1.5, annotation_text="55°C",
                annotation_font_color=C["solar"], annotation_font_size=10)
            f10.add_hline(y=Config.THERMAL_RUNAWAY_TEMP, line_dash="dash",
                line_color=C["fc"], line_width=1.5,
                annotation_text=f"{Config.THERMAL_RUNAWAY_TEMP}°C",
                annotation_font_color=C["fc"], annotation_font_size=10)
            f10.update_layout(**mk(height=190,
                yaxis_title="°C", yaxis=dict(range=[15, 75])))
            st.plotly_chart(f10, use_container_width=True)

    with s3b:
        st.markdown('<p class="sec-hdr">H₂ tank levels — live trend</p>', unsafe_allow_html=True)
        if hd("main_tank_pct"):
            f11 = go.Figure()
            for col_name, label, col_color, fill_col in [
                ("buffer_pct",    "Buffer (20 bar)",    C["h2"],   "rgba(14,165,233,.10)"),
                ("main_tank_pct", "Main Tank TH540-50", C["elec"], "rgba(139,92,246,.10)"),
                ("hrs_pct",       "HRS Station",        C["bess"], "rgba(34,197,94,.10)"),
            ]:
                if col_name in hist.columns:
                    f11.add_trace(go.Scatter(
                        x=hist["time"], y=hist[col_name],
                        fill="tozeroy", fillcolor=fill_col,
                        line=dict(color=col_color, width=2), name=label,
                        hovertemplate=f"%{{y:.1f}}%<extra>{label}</extra>"))
            f11.update_layout(**mk(height=230,
                yaxis_title="%", yaxis=dict(range=[0,108]),
                legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
            st.plotly_chart(f11, use_container_width=True)

        # Pressure gauge
        st.markdown('<p class="sec-hdr">Main tank pressure</p>', unsafe_allow_html=True)
        f12 = go.Figure(go.Indicator(
            mode="gauge+number", value=s.pressure_bar,
            title={"text":"Pressure (bar)","font":{"color":"#111827","size":13}},
            number={"font":{"color":"#111827","size":28},
                    "suffix":" bar"},
            gauge={"axis":{"range":[0, Config.SAFETY_MAX_PRESSURE_BAR],
                           "tickcolor":"#374151"},
                   "bar":{"color":C["wind"]}, "bgcolor":"#f8fafc",
                   "steps":[
                       {"range":[0, Config.MIN_OPERATING_PRESSURE_BAR*3], "color":"#fef9c3"},
                       {"range":[Config.MIN_OPERATING_PRESSURE_BAR*3,
                                 Config.SAFETY_MAX_PRESSURE_BAR*0.85],    "color":"#dcfce7"},
                       {"range":[Config.SAFETY_MAX_PRESSURE_BAR*0.85,
                                 Config.SAFETY_MAX_PRESSURE_BAR],         "color":"#fee2e2"},
                   ],
                   "threshold":{"line":{"color":C["fc"],"width":2},
                                "value":Config.SAFETY_MAX_PRESSURE_BAR*0.90}}))
        f12.update_layout(**mk(height=200, margin=dict(t=20,b=10,l=20,r=20)))
        st.plotly_chart(f12, use_container_width=True)

        # Days to full + hours to empty info cards
        st.markdown(
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:4px">'
            f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;padding:10px 12px">'
            f'<div style="font-size:10px;font-weight:600;color:#15803d;text-transform:uppercase">Days to full (90%)</div>'
            f'<div style="font-size:20px;font-weight:700;color:#111827;margin:2px 0">'
            f'{"Full ✅" if days_to_full <= 0 else f"{days_to_full:.1f} d"}</div>'
            f'<div style="font-size:10px;color:#64748b">at {h2_rate_kg_h*1000:.1f} g/h rate</div>'
            f'</div>'
            f'<div style="background:#eff6ff;border:1px solid #93c5fd;border-radius:8px;padding:10px 12px">'
            f'<div style="font-size:10px;font-weight:600;color:#1d4ed8;text-transform:uppercase">Hours of H₂ stored</div>'
            f'<div style="font-size:20px;font-weight:700;color:#111827;margin:2px 0">'
            f'{hrs_to_empty:.0f} h</div>'
            f'<div style="font-size:10px;color:#64748b">at FC nominal draw</div>'
            f'</div></div>',
            unsafe_allow_html=True)

# ─── TAB 4: DISTRIBUTION ───────────────────────────────────────────────────
with tabs[3]:

    # ── 1. KPI strip ───────────────────────────────────────────────────────
    dk = st.columns(5)
    fc_cls  = "kpi-green" if s.fc_kw > 0 else "kpi-gray"
    hrs_cls = "kpi-green" if s.hrs_pct > 60 else "kpi-amber" if s.hrs_pct > 20 else "kpi-red"
    ev_cls  = "kpi-cyan"  if s.ev_kw  > 0 else "kpi-gray"
    exp_cls = "kpi-blue"  if s.grid_export_kw > 0 else "kpi-gray"
    kpi(dk[0], "Fuel Cell Output",  f"{s.fc_kw:.2f} kW",
        f"η {s.fc_eff_pct:.1f}% · AIRCELL 3000", fc_cls)
    kpi(dk[1], "HRS Station",
        f"{s.hrs_pct:.1f}%",
        f"{'● READY' if s.hrs_pct > 60 else '▼ FILLING'} · {s.hrs_pct/100*Config.HRS_H2_TANK_CAPACITY_KG:.2f} kg",
        hrs_cls)
    kpi(dk[2], "EV Charger",        f"{s.ev_kw:.2f} kW",
        f"Via FC · {s.ev_kw/max(Config.EV_CHARGER_POWER_KW,0.01)*100:.0f}% of rated",
        ev_cls)
    kpi(dk[3], "Grid Export",       f"{s.grid_export_kw:.2f} kW",
        f"€{s.grid_rev_eur:.4f}/tick · {Config.GRID_PRICE_SELL} €/kWh", exp_cls)
    kpi(dk[4], "Session Revenue",   f"€{s.cum_revenue_eur:.2f}",
        f"H₂ + subsidy + CO₂ + grid", "kpi-green")

    # ── 2. Energy flow diagram + Revenue waterfall ─────────────────────────
    d2a, d2b = st.columns(2)
    with d2a:
        st.markdown('<p class="sec-hdr">Energy distribution — this tick</p>',
                    unsafe_allow_html=True)
        # Energy flow: where is power going right now
        total_out = max(s.fc_kw + s.grid_export_kw + s.heat_kw + s.ev_kw, 0.01)
        fc_pct    = s.fc_kw          / total_out * 100
        grid_pct  = s.grid_export_kw / total_out * 100
        heat_pct  = s.heat_kw        / total_out * 100
        ev_pct    = s.ev_kw          / total_out * 100

        _flow_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:8px;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="display:flex;flex-direction:column;gap:10px">

  <div style="display:flex;align-items:center;gap:10px">
    <span style="font-size:12px;color:#374151;min-width:110px;font-weight:500">⚡ Fuel Cell</span>
    <div style="flex:1;background:#e2e8f0;border-radius:999px;height:14px;overflow:hidden">
      <div style="width:{fc_pct:.1f}%;background:#22c55e;height:100%;border-radius:999px;
        transition:width .4s"></div>
    </div>
    <span style="font-size:12px;color:#111827;min-width:70px;text-align:right;font-weight:600">
      {s.fc_kw:.2f} kW</span>
  </div>

  <div style="display:flex;align-items:center;gap:10px">
    <span style="font-size:12px;color:#374151;min-width:110px;font-weight:500">🔌 EV Charger</span>
    <div style="flex:1;background:#e2e8f0;border-radius:999px;height:14px;overflow:hidden">
      <div style="width:{ev_pct:.1f}%;background:#60a5fa;height:100%;border-radius:999px;
        transition:width .4s"></div>
    </div>
    <span style="font-size:12px;color:#111827;min-width:70px;text-align:right;font-weight:600">
      {s.ev_kw:.2f} kW</span>
  </div>

  <div style="display:flex;align-items:center;gap:10px">
    <span style="font-size:12px;color:#374151;min-width:110px;font-weight:500">🌐 Grid Export</span>
    <div style="flex:1;background:#e2e8f0;border-radius:999px;height:14px;overflow:hidden">
      <div style="width:{grid_pct:.1f}%;background:#94a3b8;height:100%;border-radius:999px;
        transition:width .4s"></div>
    </div>
    <span style="font-size:12px;color:#111827;min-width:70px;text-align:right;font-weight:600">
      {s.grid_export_kw:.2f} kW</span>
  </div>

  <div style="display:flex;align-items:center;gap:10px">
    <span style="font-size:12px;color:#374151;min-width:110px;font-weight:500">♨ Heat Recovery</span>
    <div style="flex:1;background:#e2e8f0;border-radius:999px;height:14px;overflow:hidden">
      <div style="width:{heat_pct:.1f}%;background:#f59e0b;height:100%;border-radius:999px;
        transition:width .4s"></div>
    </div>
    <span style="font-size:12px;color:#111827;min-width:70px;text-align:right;font-weight:600">
      {s.heat_kw:.2f} kW</span>
  </div>

  <div style="margin-top:4px;padding-top:10px;border-top:1px solid #e2e8f0;
    display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px">
    <span style="font-size:11px;color:#64748b">
      H₂ consumed by FC: <b>{s.fc_kw * Config.FC_H2_CONSUMPTION_KG_KWH * 1000:.2f} g/h</b>
    </span>
    <span style="font-size:11px;color:#64748b">
      FC shortage: <b>{"⚠ YES" if s.fc_h2_shortage else "✅ No"}</b>
    </span>
  </div>
</div>
</body></html>"""
        components.html(_flow_html, height=200, scrolling=False)

    with d2b:
        st.markdown('<p class="sec-hdr">Revenue breakdown — session cumulative</p>',
                    unsafe_allow_html=True)
        # Revenue waterfall — horizontal bars
        dt_h      = Config.TIMESTEP_SEC / 3600
        h2_rev    = s.h2_kg_h * dt_h * 6.0          # approx H₂ market price
        subsidy   = s.subsidy_eur
        carbon    = s.carbon_rev_eur
        grid_rev  = s.grid_rev_eur
        rev_items = [
            ("H₂ Sales",      h2_rev,   C["h2"]),
            ("EU Subsidy",     subsidy,  C["bess"]),
            ("Carbon Credits", carbon,   C["co2"]),
            ("Grid Export",    grid_rev, C["grid"]),
        ]
        total_rev = max(sum(v for _,v,_ in rev_items), 1e-9)
        f_rev = go.Figure()
        for i, (lbl, val, col_) in enumerate(rev_items):
            f_rev.add_trace(go.Bar(
                x=[val], y=[lbl], orientation="h",
                marker_color=col_, marker_line_width=0,
                text=[f"€{val:.5f}"],
                textposition="outside",
                textfont=dict(color="#111827", size=11),
                name=lbl, showlegend=False,
                hovertemplate=f"{lbl}: €%{{x:.5f}}<extra></extra>"))
        f_rev.update_layout(**mk(height=200,
            xaxis_title="€ per tick",
            xaxis=dict(showgrid=True),
            yaxis=dict(autorange="reversed"),
            barmode="overlay",
            margin=dict(t=10, b=30, l=100, r=80)))
        st.plotly_chart(f_rev, use_container_width=True)

    # ── 3. FC trend + HRS tracker | Grid export trend ─────────────────────
    d3a, d3b = st.columns(2)
    with d3a:
        st.markdown('<p class="sec-hdr">Fuel cell — output & H₂ consumption</p>',
                    unsafe_allow_html=True)
        if hd("fc_kw"):
            f14 = go.Figure()
            f14.add_trace(go.Scatter(
                x=hist["time"], y=hist["fc_kw"],
                fill="tozeroy", fillcolor="rgba(34,197,94,.10)",
                line=dict(color=C["bess"], width=2), name="FC output (kW)",
                hovertemplate="%{y:.2f} kW<extra>FC output</extra>"))
            # H₂ consumption on secondary axis
            h2_consumed = hist["fc_kw"] * Config.FC_H2_CONSUMPTION_KG_KWH * 1000
            f14.add_trace(go.Scatter(
                x=hist["time"], y=h2_consumed,
                line=dict(color=C["h2"], width=1.5, dash="dot"),
                name="H₂ consumed (g/h)", yaxis="y2",
                hovertemplate="%{y:.1f} g/h<extra>H₂ consumed</extra>"))
            f14.add_hline(y=Config.FC_POWER_NOM_KW, line_dash="dot",
                line_color="#94a3b8", line_width=1,
                annotation_text="Rated 3kW",
                annotation_font_size=10, annotation_font_color="#94a3b8")
            f14.update_layout(**mk(height=220,
                yaxis=dict(title="kW", range=[0, Config.FC_POWER_NOM_KW * 1.2]),
                yaxis2=dict(title="g H₂/h", overlaying="y", side="right",
                            color=C["h2"],
                            range=[0, Config.FC_H2_CONSUMPTION_KG_KWH*1000
                                   * Config.FC_POWER_NOM_KW * 1.2]),
                legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
            st.plotly_chart(f14, use_container_width=True)

        # HRS dispensing tracker — real dispensing events
        st.markdown('<p class="sec-hdr">HRS dispensing tracker — SAE J2601</p>',
                    unsafe_allow_html=True)
        # Pull real dispensing data from chain_result if available
        _chain = getattr(st.session_state, 'last_chain_result', None)
        _cum_disp  = getattr(_chain, 'cum_dispensed_kg',   s.cum_h2_kg * 0.30) if _chain else s.cum_h2_kg * 0.30
        _veh_srv   = getattr(_chain, 'vehicles_served',    int(_cum_disp / 5.0)) if _chain else int(_cum_disp / 5.0)
        _disp_rev  = getattr(_chain, 'dispensing_revenue_eur', _cum_disp * 6.0) if _chain else _cum_disp * 6.0
        _disp_now  = getattr(_chain, 'dispensing_active',  False) if _chain else False
        _next_h    = getattr(_chain, 'next_dispense_hour', 8) if _chain else 8
        _disp_pres = getattr(_chain, 'hrs_pressure_bar',  350.0) if _chain else 350.0
        _status_col = '#dcfce7' if _disp_now else '#f0fdf4'
        _status_bc  = '#22c55e' if _disp_now else '#86efac'
        _status_txt = '⛽ DISPENSING NOW — vehicle filling' if _disp_now else f'○ Standby · next at {_next_h:02d}:00'
        st.markdown(
            f'<div style="background:{_status_col};border:2px solid {_status_bc};'
            f'border-radius:10px;padding:10px 14px;margin-bottom:8px;'
            f'font-size:13px;font-weight:700;color:#111827">{_status_txt}</div>',
            unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;'
            f'padding:12px 16px;display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px">'
            f'<div style="text-align:center">'
            f'<div style="font-size:10px;color:#15803d;font-weight:600;text-transform:uppercase">HRS Fill</div>'
            f'<div style="font-size:22px;font-weight:700;color:#111827">{s.hrs_pct:.0f}%</div>'
            f'<div style="font-size:10px;color:#64748b">{s.hrs_pct/100*Config.HRS_H2_TANK_CAPACITY_KG:.2f} kg</div>'
            f'</div>'
            f'<div style="text-align:center;border-left:1px solid #bbf7d0">'
            f'<div style="font-size:10px;color:#15803d;font-weight:600;text-transform:uppercase">Dispensed</div>'
            f'<div style="font-size:22px;font-weight:700;color:#111827">{_cum_disp:.3f}</div>'
            f'<div style="font-size:10px;color:#64748b">kg session</div>'
            f'</div>'
            f'<div style="text-align:center;border-left:1px solid #bbf7d0">'
            f'<div style="font-size:10px;color:#15803d;font-weight:600;text-transform:uppercase">Vehicles</div>'
            f'<div style="font-size:22px;font-weight:700;color:#111827">{_veh_srv}</div>'
            f'<div style="font-size:10px;color:#64748b">× 5 kg fills</div>'
            f'</div>'
            f'<div style="text-align:center;border-left:1px solid #bbf7d0">'
            f'<div style="font-size:10px;color:#15803d;font-weight:600;text-transform:uppercase">HRS Revenue</div>'
            f'<div style="font-size:22px;font-weight:700;color:#111827">€{_disp_rev:.2f}</div>'
            f'<div style="font-size:10px;color:#64748b">{_disp_pres:.0f} bar · SAE J2601</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True)

    with d3b:
        if hd("grid_export_kw"):
            st.markdown('<p class="sec-hdr">Grid export — trend & revenue</p>',
                        unsafe_allow_html=True)
            f15 = go.Figure()
            f15.add_trace(go.Scatter(
                x=hist["time"], y=hist["grid_export_kw"],
                fill="tozeroy", fillcolor="rgba(148,163,184,.15)",
                line=dict(color=C["grid"], width=2), name="Grid export",
                hovertemplate="%{y:.2f} kW<extra>Grid export</extra>"))
            if "ev_kw" in hist.columns:
                f15.add_trace(go.Scatter(
                    x=hist["time"], y=hist["ev_kw"],
                    fill="tozeroy", fillcolor="rgba(96,165,250,.15)",
                    line=dict(color=C["ev"], width=2), name="EV load",
                    hovertemplate="%{y:.2f} kW<extra>EV</extra>"))
            # Cumulative grid revenue annotation
            cum_grid_rev = (hist["grid_export_kw"].sum()
                            * Config.TIMESTEP_SEC / 3600
                            * Config.GRID_PRICE_SELL
                            if "grid_export_kw" in hist.columns else 0)
            f15.add_annotation(
                x=0.98, y=0.95, xref="paper", yref="paper",
                text=f"Cum. grid revenue: €{cum_grid_rev:.4f}",
                showarrow=False,
                font=dict(size=11, color="#374151"),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#e2e8f0", borderwidth=1)
            f15.update_layout(**mk(height=220, yaxis_title="kW",
                legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
            st.plotly_chart(f15, use_container_width=True)

        # Downstream split donut
        st.markdown('<p class="sec-hdr">Output energy split</p>',
                    unsafe_allow_html=True)
        f16 = go.Figure(go.Pie(
            values=[max(.001, s.ev_kw),
                    max(.001, s.grid_export_kw),
                    max(.001, s.heat_kw),
                    max(.001, s.fc_kw)],
            labels=["EV Charging", "Grid Export", "Heat Recovery", "Fuel Cell"],
            hole=0.55,
            marker=dict(
                colors=[C["ev"], C["grid"], C["solar"], C["bess"]],
                line=dict(color="#ffffff", width=2)),
            # Always show labels outside so they are never hidden
            textposition="outside",
            textinfo="label+percent",
            textfont=dict(color="#111827", size=12, family="'Segoe UI',sans-serif"),
            # Pull each slice slightly so outside labels have space
            pull=[0.04, 0.04, 0.04, 0.04],
            # Show all labels regardless of slice size
            automargin=True,
            direction="clockwise",
            hovertemplate="<b>%{label}</b><br>%{value:.3f} kW<br>%{percent}<extra></extra>"))
        f16.add_annotation(
            text=f"<b>{s.fc_kw + s.ev_kw + s.grid_export_kw + s.heat_kw:.2f}</b><br>kW total",
            showarrow=False, font=dict(size=13, color="#111827"),
            x=0.5, y=0.5, xref="paper", yref="paper")
        f16.update_layout(**mk(height=270,
            showlegend=False,
            margin=dict(t=30, b=30, l=80, r=80)))
        st.plotly_chart(f16, use_container_width=True)

# ─── TAB 5: SUBSYSTEMS ─────────────────────────────────────────────────────
with tabs[4]:
    if sub is None:
        st.info("Subsystem data not yet available.")
    else:
        wr = sub["water"]; o2 = sub["oxygen"]
        dr = sub["dryer"]; wu = sub["warmup"]

        # ── KPI strip — all 4 subsystems at a glance ───────────────────────
        sk5 = st.columns(5)
        kpi(sk5[0], "Water Quality",
            f"{wr.conductivity_us_cm:.4f} µS/cm",
            "✅ DIN Type 1" if wr.quality_ok else "❌ Out of spec",
            "kpi-green" if wr.quality_ok else "kpi-red")
        kpi(sk5[1], "H₂ Moisture",
            f"{dr.moisture_ppm:.2f} ppm",
            "✅ AIRCELL spec" if dr.moisture_ppm <= 5 else "❌ >5 ppm",
            "kpi-green" if dr.moisture_ppm <= 5 else "kpi-red")
        kpi(sk5[2], "O₂ Pressure",
            f"{o2.o2_pressure_bar:.3f} bar",
            "✅ Safe <0.5 bar" if o2.safety_ok else "❌ High pressure",
            "kpi-green" if o2.safety_ok else "kpi-red")
        kpi(sk5[3], "Stack Temperature",
            f"{wu.current_temp_c:.1f}°C",
            f"{'● WARM' if wu.is_warm else f'⟳ {wu.warmup_time_min:.1f} min left'}",
            "kpi-green" if wu.is_warm else "kpi-amber")
        kpi(sk5[4], "Aux Power",
            f"{sub['aux_power_kw']:.3f} kW",
            "Pump + UV + dryer + heater",
            "kpi-blue")

        # ── Row 1: Water + O₂ | Dryer + Warmup ────────────────────────────
        s5a, s5b = st.columns(2)
        with s5a:
            # Water treatment card
            st.markdown('<p class="sec-hdr">💧 Water treatment — DIN ISO 3696 Type 1</p>',
                        unsafe_allow_html=True)
            wc5 = st.columns(2)
            kpi(wc5[0], "Conductivity",
                f"{wr.conductivity_us_cm:.4f} µS/cm",
                "Target < 0.1 µS/cm",
                "kpi-green" if wr.quality_ok else "kpi-red")
            kpi(wc5[1], "Resistance",
                f"{wr.resistance_mohm_cm:.1f} MΩ·cm",
                "Target > 10 MΩ·cm",
                "kpi-green" if wr.resistance_mohm_cm >= 10 else "kpi-red")

            # Resin saturation bar
            resin_col = "#22c55e" if not wr.resin_warning else "#ef4444"
            st.markdown(
                f'<div style="margin:10px 0 4px">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:12px;color:#374151;margin-bottom:5px">'
                f'<span style="font-weight:500">Ion exchange resin</span>'
                f'<span style="font-weight:600">{wr.resin_saturation_pct:.1f}%</span>'
                f'</div>'
                f'<div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden">'
                f'<div style="background:{resin_col};width:{wr.resin_saturation_pct:.1f}%;'
                f'height:100%;border-radius:999px"></div></div>'
                f'<div style="font-size:11px;color:{"#b91c1c" if wr.resin_warning else "#64748b"};'
                f'margin-top:4px">{"⚠ Replace resin soon (>80% saturated)" if wr.resin_warning else "● OK — resin within capacity"}</div>'
                f'</div>',
                unsafe_allow_html=True)

            # O₂ management
            st.markdown('<p class="sec-hdr">⬆ O₂ management (S30/30 by-product)</p>',
                        unsafe_allow_html=True)

            # O₂ flow diagram
            o2_bar_w = min(100, o2.o2_pressure_bar / 0.5 * 100)
            o2_col   = "#22c55e" if o2.safety_ok else "#ef4444"
            st.markdown(
                f'<div style="background:#fff7ed;border:1px solid #fed7aa;'
                f'border-radius:10px;padding:12px 14px">'
                f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;'
                f'text-align:center">'
                f'<div><div style="font-size:10px;color:#92400e;font-weight:600;'
                f'text-transform:uppercase">O₂ Flow</div>'
                f'<div style="font-size:18px;font-weight:700;color:#111827">'
                f'{o2.o2_flow_nm3_h:.4f}</div>'
                f'<div style="font-size:10px;color:#64748b">Nm³/h</div></div>'
                f'<div><div style="font-size:10px;color:#92400e;font-weight:600;'
                f'text-transform:uppercase">Pressure</div>'
                f'<div style="font-size:18px;font-weight:700;'
                f'color:{"#15803d" if o2.safety_ok else "#b91c1c"}">'
                f'{o2.o2_pressure_bar:.3f}</div>'
                f'<div style="font-size:10px;color:#64748b">bar (max 0.5)</div></div>'
                f'<div><div style="font-size:10px;color:#92400e;font-weight:600;'
                f'text-transform:uppercase">Vented</div>'
                f'<div style="font-size:18px;font-weight:700;color:#111827">'
                f'{o2.vented_nm3_h:.4f}</div>'
                f'<div style="font-size:10px;color:#64748b">Nm³/h to atm</div></div>'
                f'</div>'
                f'<div style="margin-top:10px">'
                f'<div style="background:#e2e8f0;border-radius:999px;height:8px;overflow:hidden">'
                f'<div style="background:{o2_col};width:{o2_bar_w:.1f}%;height:100%;'
                f'border-radius:999px"></div></div>'
                f'<div style="font-size:10px;color:#64748b;margin-top:3px">'
                f'Pressure: {o2.o2_pressure_bar:.3f} / 0.5 bar limit</div>'
                f'</div></div>',
                unsafe_allow_html=True)

        with s5b:
            # H₂ dryer card
            st.markdown('<p class="sec-hdr">🔵 H₂ dryer — PSA desiccant</p>',
                        unsafe_allow_html=True)
            dc5 = st.columns(2)
            kpi(dc5[0], "Outlet moisture",
                f"{dr.moisture_ppm:.3f} ppm",
                "AIRCELL req: < 5 ppm",
                "kpi-green" if dr.moisture_ppm <= 5 else "kpi-red")
            kpi(dc5[1], "Dew point",
                f"{dr.dew_point_c:.1f}°C",
                f"H₂ loss {dr.h2_loss_pct:.2f}%",
                "kpi-blue")

            # Desiccant saturation bar
            desc_col = "#22c55e" if not dr.desiccant_warning else "#ef4444"
            st.markdown(
                f'<div style="margin:10px 0 4px">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:12px;color:#374151;margin-bottom:5px">'
                f'<span style="font-weight:500">Desiccant bed saturation</span>'
                f'<span style="font-weight:600">{dr.desiccant_pct:.1f}%</span>'
                f'</div>'
                f'<div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden">'
                f'<div style="background:{desc_col};width:{dr.desiccant_pct:.1f}%;'
                f'height:100%;border-radius:999px"></div></div>'
                f'<div style="font-size:11px;color:{"#b91c1c" if dr.desiccant_warning else "#64748b"};'
                f'margin-top:4px">{"⚠ Regenerate desiccant (>85% saturated)" if dr.desiccant_warning else "● OK — desiccant within capacity"}</div>'
                f'</div>',
                unsafe_allow_html=True)

            # Electrolyzer warm-up card
            st.markdown('<p class="sec-hdr">🌡 Electrolyzer thermal — S30/30 warm-up</p>',
                        unsafe_allow_html=True)

            # Temperature progress bar (20°C min → 55°C optimal → 70°C max)
            t_pct = min(100, max(0, (wu.current_temp_c - 20) / (70 - 20) * 100))
            t_col = "#22c55e" if wu.is_warm else "#f59e0b" if wu.current_temp_c > 15 else "#3b82f6"
            st.markdown(
                f'<div style="background:#f0fdf4;border:1px solid #86efac;'
                f'border-radius:10px;padding:12px 14px">'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;'
                f'margin-bottom:10px">'
                f'<div style="text-align:center">'
                f'<div style="font-size:10px;color:#15803d;font-weight:600;'
                f'text-transform:uppercase">Stack Temp</div>'
                f'<div style="font-size:24px;font-weight:700;color:#111827">'
                f'{wu.current_temp_c:.1f}°C</div>'
                f'<div style="font-size:10px;color:#64748b">Target: {wu.target_temp_c}°C</div>'
                f'</div>'
                f'<div style="text-align:center">'
                f'<div style="font-size:10px;color:#15803d;font-weight:600;'
                f'text-transform:uppercase">Eff. Factor</div>'
                f'<div style="font-size:24px;font-weight:700;color:#111827">'
                f'×{wu.efficiency_factor:.3f}</div>'
                f'<div style="font-size:10px;color:{"#64748b" if not wu.cold_start else "#b45309"}">'
                f'{"Nominal" if not wu.cold_start else "Cold start penalty"}</div>'
                f'</div>'
                f'</div>'
                f'<div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden">'
                f'<div style="background:{t_col};width:{t_pct:.1f}%;height:100%;'
                f'border-radius:999px"></div></div>'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:10px;color:#64748b;margin-top:3px">'
                f'<span>20°C min</span><span>55°C optimal</span><span>70°C max</span>'
                f'</div>'
                f'<div style="margin-top:8px;text-align:center">'
                f'<span style="background:{"#dcfce7" if wu.is_warm else "#fef9c3"};'
                f'color:{"#15803d" if wu.is_warm else "#92400e"};'
                f'font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px">'
                f'{"● WARM — READY FOR RATED OPERATION" if wu.is_warm else f"⟳ WARMING UP — {wu.warmup_time_min:.1f} min remaining"}'
                f'</span></div>'
                f'</div>',
                unsafe_allow_html=True)

        # ── Row 2: Subsystem health summary (full width) ───────────────────
        st.markdown('<p class="sec-hdr">Subsystem health overview</p>',
                    unsafe_allow_html=True)
        subsys_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:8px;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px">
    <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
      letter-spacing:.06em;margin-bottom:10px">💧 Water Treatment</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Conductivity</span>
        <span style="color:{"#15803d" if wr.quality_ok else "#b91c1c"};font-weight:600">
          {wr.conductivity_us_cm:.4f} µS/cm</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Flow rate</span>
        <span style="color:#111827;font-weight:600">{wr.purified_l_h:.3f} L/h</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Power draw</span>
        <span style="color:#111827;font-weight:600">{wr.power_kw:.3f} kW</span>
      </div>
      <div style="margin-top:4px;padding:4px 8px;border-radius:6px;text-align:center;
        background:{"#dcfce7" if wr.quality_ok else "#fee2e2"};
        color:{"#15803d" if wr.quality_ok else "#b91c1c"};font-size:11px;font-weight:600">
        {"✅ WITHIN SPEC" if wr.quality_ok else "❌ OUT OF SPEC"}</div>
    </div>
  </div>

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px">
    <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
      letter-spacing:.06em;margin-bottom:10px">⬆ Oxygen Handler</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">O₂ produced</span>
        <span style="color:#111827;font-weight:600">{o2.o2_flow_nm3_h:.4f} Nm³/h</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Outlet pressure</span>
        <span style="color:{"#15803d" if o2.safety_ok else "#b91c1c"};font-weight:600">
          {o2.o2_pressure_bar:.3f} bar</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Vented to atm</span>
        <span style="color:#111827;font-weight:600">{o2.vented_nm3_h:.4f} Nm³/h</span>
      </div>
      <div style="margin-top:4px;padding:4px 8px;border-radius:6px;text-align:center;
        background:{"#dcfce7" if o2.safety_ok else "#fee2e2"};
        color:{"#15803d" if o2.safety_ok else "#b91c1c"};font-size:11px;font-weight:600">
        {"✅ PRESSURE SAFE" if o2.safety_ok else "❌ PRESSURE HIGH"}</div>
    </div>
  </div>

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px">
    <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
      letter-spacing:.06em;margin-bottom:10px">🔵 H₂ Dryer</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Moisture out</span>
        <span style="color:{"#15803d" if dr.moisture_ppm<=5 else "#b91c1c"};font-weight:600">
          {dr.moisture_ppm:.3f} ppm</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Dew point</span>
        <span style="color:#111827;font-weight:600">{dr.dew_point_c:.1f}°C</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">H₂ loss</span>
        <span style="color:#111827;font-weight:600">{dr.h2_loss_pct:.2f}%</span>
      </div>
      <div style="margin-top:4px;padding:4px 8px;border-radius:6px;text-align:center;
        background:{"#dcfce7" if dr.moisture_ppm<=5 else "#fee2e2"};
        color:{"#15803d" if dr.moisture_ppm<=5 else "#b91c1c"};font-size:11px;font-weight:600">
        {"✅ AIRCELL SPEC MET" if dr.moisture_ppm<=5 else "❌ MOISTURE HIGH"}</div>
    </div>
  </div>

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px">
    <div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;
      letter-spacing:.06em;margin-bottom:10px">🌡 Stack Thermal</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Temperature</span>
        <span style="color:{"#15803d" if wu.is_warm else "#92400e"};font-weight:600">
          {wu.current_temp_c:.1f}°C</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Efficiency ×</span>
        <span style="color:#111827;font-weight:600">{wu.efficiency_factor:.3f}</span>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:12px">
        <span style="color:#374151">Heater draw</span>
        <span style="color:#111827;font-weight:600">{wu.power_consumed_kw:.3f} kW</span>
      </div>
      <div style="margin-top:4px;padding:4px 8px;border-radius:6px;text-align:center;
        background:{"#dcfce7" if wu.is_warm else "#fef9c3"};
        color:{"#15803d" if wu.is_warm else "#92400e"};font-size:11px;font-weight:600">
        {"✅ WARM — READY" if wu.is_warm else f"⟳ WARMING {wu.warmup_time_min:.1f} min"}</div>
    </div>
  </div>

</div>
</body></html>"""
        components.html(subsys_html, height=195, scrolling=False)

# ─── TAB 6: ANNUAL SIMULATION ──────────────────────────────────────────────
with tabs[5]:
    st.markdown(
        '<p class="sec-hdr">365-day simulation · Zagreb climatology · real datasheet parameters</p>',
        unsafe_allow_html=True)

    if st.button("▶ Run Annual Simulation", type="primary"):
        with st.spinner("Simulating 365 days…"):
            params = ScenarioParams(
                name="Current Config", elec_priority_mode=sc_elec_mode,
                h2_price_eur_kg=sc_h2_price, capex_eur=sc_capex, opex_annual_eur=sc_opex)
            st.session_state.annual_report =                 st.session_state.scenario_eng.run_annual(params)

    rpt = st.session_state.annual_report
    if rpt:
        mdf = pd.DataFrame([{
            "month": m.month_name, "h2": m.h2_produced_kg,
            "solar": m.solar_kwh, "wind": m.wind_kwh,
            "revenue": m.revenue_eur, "lcoh": m.lcoh_eur_kg,
            "co2": m.co2_saved_kg, "elec_h": m.electrolyzer_hours,
        } for m in rpt.monthly])

        # ── KPI strip ──────────────────────────────────────────────────────
        k6 = st.columns(6)
        kpi(k6[0], "Annual H₂",
            f"{rpt.total_h2_kg:.1f} kg",
            f"Avg {rpt.avg_daily_h2_kg*1000:.0f} g/day · Peak {rpt.peak_daily_h2_kg*1000:.0f} g",
            "kpi-cyan")
        kpi(k6[1], "Operating LCOH",
            f"€{rpt.avg_lcoh_eur_kg:.2f}/kg",
            f"Best €{rpt.best_lcoh_eur_kg:.2f} · Worst €{rpt.worst_lcoh_eur_kg:.2f}",
            "kpi-green")
        kpi(k6[2], "Net Profit",
            f"€{rpt.net_profit_eur:,.0f}",
            f"Revenue €{rpt.total_revenue_eur:,.0f}",
            "kpi-green" if rpt.net_profit_eur > 0 else "kpi-red")
        kpi(k6[3], "Payback / ROI",
            f"{rpt.payback_years:.1f} yr",
            f"ROI {rpt.roi_pct:.1f}%",
            "kpi-green" if rpt.payback_years < 15 else "kpi-amber")
        kpi(k6[4], "CO₂ Abatement",
            f"{rpt.total_co2_saved_ton:.2f} ton",
            f"Credits €{rpt.co2_credits_eur:.0f} · vs SMR",
            "kpi-green")
        kpi(k6[5], "Grid Independence",
            f"{rpt.grid_independence_pct:.1f}%",
            f"Elec. {rpt.electrolyzer_hours:.0f} h/yr",
            "kpi-purple")

        st.markdown("")

        # ── Row 1: Monthly H₂ (improved) + Monthly generation mix (improved) ─
        r1a, r1b = st.columns(2)
        with r1a:
            st.markdown('<p class="sec-hdr">Monthly H₂ production — Zagreb seasonal pattern</p>',
                        unsafe_allow_html=True)
            f_m = go.Figure()
            # Bar chart with gradient colour (blue in winter, gold in summer)
            month_colors = [
                "#3b82f6","#60a5fa","#34d399","#22c55e",
                "#f59e0b","#f97316","#ef4444","#f97316",
                "#f59e0b","#22c55e","#60a5fa","#3b82f6",
            ]
            f_m.add_trace(go.Bar(
                x=mdf["month"], y=mdf["h2"],
                marker_color=month_colors[:len(mdf)],
                marker_line_width=0,
                name="H₂ kg",
                text=[f"{v:.1f}" for v in mdf["h2"]],
                textposition="outside",
                textfont=dict(color="#374151", size=10),
                hovertemplate="%{x}: <b>%{y:.2f} kg H₂</b><extra></extra>"))
            # Average line
            avg_h2 = rpt.total_h2_kg / 12
            f_m.add_hline(y=avg_h2, line_dash="dot", line_color="#94a3b8",
                line_width=1.5,
                annotation_text=f"Avg {avg_h2:.1f} kg",
                annotation_font_size=10, annotation_font_color="#64748b")
            # Best month marker
            best_idx = mdf["h2"].idxmax()
            f_m.add_annotation(
                x=mdf.loc[best_idx,"month"], y=mdf.loc[best_idx,"h2"],
                text="★ Best", showarrow=True, arrowhead=2,
                font=dict(size=10, color="#f59e0b"),
                arrowcolor="#f59e0b", ay=-30)
            f_m.update_layout(**mk(height=280,
                yaxis_title="kg H₂",
                yaxis=dict(range=[0, mdf["h2"].max() * 1.25])))
            st.plotly_chart(f_m, use_container_width=True)

        with r1b:
            st.markdown('<p class="sec-hdr">Monthly generation mix — solar vs wind</p>',
                        unsafe_allow_html=True)
            f_g = go.Figure()
            f_g.add_trace(go.Bar(
                x=mdf["month"], y=mdf["solar"],
                name="Solar kWh", marker_color=C["solar"],
                marker_line_width=0,
                hovertemplate="%{x}: <b>%{y:.0f} kWh</b> solar<extra></extra>"))
            f_g.add_trace(go.Bar(
                x=mdf["month"], y=mdf["wind"],
                name="Wind kWh", marker_color=C["wind"],
                marker_line_width=0,
                hovertemplate="%{x}: <b>%{y:.0f} kWh</b> wind<extra></extra>"))
            # Total generation line
            total_gen = mdf["solar"] + mdf["wind"]
            f_g.add_trace(go.Scatter(
                x=mdf["month"], y=total_gen,
                name="Total", mode="lines+markers",
                line=dict(color="#0f172a", width=2),
                marker=dict(size=5, color="#0f172a"),
                hovertemplate="%{x}: <b>%{y:.0f} kWh</b> total<extra></extra>"))
            f_g.update_layout(**mk(height=280,
                barmode="stack", yaxis_title="kWh",
                legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
            st.plotly_chart(f_g, use_container_width=True)

        # ── Row 2: Monthly revenue trend + Monthly LCOH ────────────────────
        r2a, r2b = st.columns(2)
        with r2a:
            st.markdown('<p class="sec-hdr">Monthly revenue — cumulative trend</p>',
                        unsafe_allow_html=True)
            f_rev = go.Figure()
            f_rev.add_trace(go.Bar(
                x=mdf["month"], y=mdf["revenue"],
                name="Monthly revenue",
                marker_color="rgba(34,197,94,.7)",
                marker_line_width=0,
                hovertemplate="%{x}: €<b>%{y:.2f}</b><extra></extra>"))
            # Cumulative revenue line
            cum_rev = mdf["revenue"].cumsum()
            f_rev.add_trace(go.Scatter(
                x=mdf["month"], y=cum_rev,
                name="Cumulative", yaxis="y2",
                line=dict(color="#0ea5e9", width=2),
                hovertemplate="%{x}: €<b>%{y:.2f}</b> cumulative<extra></extra>"))
            f_rev.update_layout(**mk(height=240,
                yaxis=dict(title="Monthly €", color="#22c55e"),
                yaxis2=dict(title="Cumulative €", overlaying="y", side="right",
                            color="#0ea5e9"),
                legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
            st.plotly_chart(f_rev, use_container_width=True)

        with r2b:
            st.markdown('<p class="sec-hdr">Monthly operating LCOH — seasonal variation</p>',
                        unsafe_allow_html=True)
            f_lcoh = go.Figure()
            lcoh_colors = ["#22c55e" if v <= rpt.avg_lcoh_eur_kg else "#f59e0b"
                           for v in mdf["lcoh"]]
            f_lcoh.add_trace(go.Bar(
                x=mdf["month"], y=mdf["lcoh"],
                marker_color=lcoh_colors,
                marker_line_width=0, name="LCOH €/kg",
                hovertemplate="%{x}: €<b>%{y:.3f}</b>/kg<extra></extra>"))
            f_lcoh.add_hline(
                y=rpt.avg_lcoh_eur_kg, line_dash="dot", line_color="#64748b",
                line_width=1.5,
                annotation_text=f"Avg €{rpt.avg_lcoh_eur_kg:.2f}/kg",
                annotation_font_size=10, annotation_font_color="#64748b")
            f_lcoh.update_layout(**mk(height=240,
                yaxis_title="€/kg",
                yaxis=dict(range=[0, mdf["lcoh"].max() * 1.3])))
            st.plotly_chart(f_lcoh, use_container_width=True)

        # ── Row 3: Scenario comparison (improved table) ────────────────────
        st.markdown('<p class="sec-hdr">Scenario comparison</p>', unsafe_allow_html=True)
        with st.spinner("Running 3 scenarios…"):
            scenarios = [
                ScenarioParams("H₂ Max", elec_priority_mode="h2_max",
                    h2_price_eur_kg=sc_h2_price, capex_eur=sc_capex, opex_annual_eur=sc_opex),
                ScenarioParams("LCOH Optimised", elec_priority_mode="lcoh_opt",
                    h2_price_eur_kg=sc_h2_price, capex_eur=sc_capex, opex_annual_eur=sc_opex),
                ScenarioParams("PV ×2 Scale", pv_scale=2.0, elec_priority_mode="h2_max",
                    h2_price_eur_kg=sc_h2_price, capex_eur=sc_capex, opex_annual_eur=sc_opex),
            ]
            sc_reports = st.session_state.scenario_eng.compare_scenarios(scenarios)

        # Visual scenario comparison bars
        sc_fig = go.Figure()
        sc_names  = [sc.name for sc in scenarios]
        sc_h2     = [r.total_h2_kg for r in sc_reports]
        sc_profit = [r.net_profit_eur for r in sc_reports]
        sc_lcoh   = [r.avg_lcoh_eur_kg for r in sc_reports]
        sc_fig.add_trace(go.Bar(name="H₂ (kg/yr)", x=sc_names, y=sc_h2,
            marker_color=C["h2"], marker_line_width=0,
            text=[f"{v:.0f} kg" for v in sc_h2],
            textposition="outside", textfont=dict(color="#374151", size=11)))
        sc_fig.update_layout(**mk(height=220,
            yaxis_title="kg H₂/year",
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1)))
        st.plotly_chart(sc_fig, use_container_width=True)

        # Scenario data table
        sc_df = pd.DataFrame([{
            "Scenario":     sc.name,
            "H₂ (kg/yr)":  f"{r.total_h2_kg:.1f}",
            "Op. LCOH":     f"€{r.avg_lcoh_eur_kg:.3f}/kg",
            "Revenue":      f"€{r.total_revenue_eur:,.0f}",
            "Net P&L":      f"€{r.net_profit_eur:,.0f}",
            "Payback":      f"{r.payback_years:.1f} yr",
            "CO₂ (ton)":    f"{r.total_co2_saved_ton:.2f}",
            "Grid indep.":  f"{r.grid_independence_pct:.1f}%",
        } for sc, r in zip(scenarios, sc_reports)])
        st.dataframe(sc_df, use_container_width=True, hide_index=True)

        # ── Row 4: Annual resource summary (styled cards) ──────────────────
        st.markdown('<p class="sec-hdr">Annual resource & system summary</p>',
                    unsafe_allow_html=True)
        res_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:6px;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
  {"".join(f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;text-align:center"><div style="font-size:10px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.06em">{lbl}</div><div style="font-size:20px;font-weight:700;color:#111827;margin:4px 0">{val}</div><div style="font-size:10px;color:#94a3b8">{sub}</div></div>' for lbl,val,sub in [
    ("Solar Generation",  f"{rpt.total_solar_kwh:,.0f} kWh", "photovoltaic array"),
    ("Wind Generation",   f"{rpt.total_wind_kwh:,.0f} kWh", "10 kW HAWT"),
    ("Water Consumed",    f"{rpt.total_water_l:,.0f} L",     "DIN ISO 3696 Type 1"),
    ("O₂ Produced",       f"{rpt.total_o2_nm3:,.0f} Nm³",   "electrolysis by-product"),
    ("Electrolyzer Hours",f"{rpt.electrolyzer_hours:,.0f} h","S30/30 operating hours"),
    ("Stack Replacements",str(rpt.stack_replacements),        f"of {Config.electrolyzer.mttf_hours:,}h MTTF"),
    ("BESS Life Left",    f"{rpt.bess_remaining_life_pct:.1f}%", f"of {Config.BATT_CYCLE_LIFE:,} cycles"),
    ("H₂ to HRS",         f"{rpt.total_h2_to_hrs_kg:.1f} kg","dispensed to vehicles"),
  ])}
</div>
</body></html>"""
        components.html(res_html, height=165, scrolling=False)

    else:
        st.info("Click **▶ Run Annual Simulation** to generate the 365-day report.")

# ─── TAB 7: OPTIMIZER ──────────────────────────────────────────────────────
with tabs[6]:
    st.markdown('<p class="sec-hdr">Economic operating point optimiser — ITM S30/30</p>',
                unsafe_allow_html=True)

    # ── Controls CSS — larger, bolder labels and values ───────────────────
    st.markdown("""
<style>
/* Optimizer controls — larger slider labels */
[data-testid="stSlider"] label p {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}
/* Slider min/max value text */
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
}
/* Current slider value bubble */
[data-testid="stSlider"] [data-testid="stThumbValue"] {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #0ea5e9 !important;
}
/* Radio label */
[data-testid="stRadio"] label p {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}
/* Radio option text */
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #111827 !important;
}
/* Slider track colour */
[data-testid="stSlider"] [role="slider"] {
    background: #0ea5e9 !important;
}
</style>
""", unsafe_allow_html=True)

    # ── Controls row ───────────────────────────────────────────────────────
    ctl = st.columns([2, 2, 2, 1])
    with ctl[0]:
        opt_power = st.slider(
            "Available power (kW)", 0.0,
            Config.PV_SYSTEM_CAPACITY_KW + Config.WIND_SYSTEM_CAPACITY_KW,
            float(min(s.total_gen_kw,
                Config.PV_SYSTEM_CAPACITY_KW + Config.WIND_SYSTEM_CAPACITY_KW)),
            0.1, key="opt_pwr")
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:#0ea5e9;'
            f'margin-top:-8px">Current: <b>{opt_power:.2f} kW</b> '
            f'(PV {Config.PV_SYSTEM_CAPACITY_KW:.0f} + Wind '
            f'{Config.WIND_SYSTEM_CAPACITY_KW:.0f} kW max)</div>',
            unsafe_allow_html=True)
    with ctl[1]:
        opt_h2_price = st.slider(
            "H₂ sell price (€/kg)", 3.0, 12.0,
            float(sc_h2_price), 0.5, key="opt_h2p")
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:#0ea5e9;'
            f'margin-top:-8px">Selected: <b>€{opt_h2_price:.1f}/kg</b> '
            f'· Market range €3–12/kg</div>',
            unsafe_allow_html=True)
    with ctl[2]:
        opt_source = st.radio(
            "Energy source", ["renewable", "grid"],
            horizontal=True, key="opt_src")
        src_note = ("☀ O&M cost only — no fuel cost" if opt_source == "renewable"
                    else f"🌐 Grid price €{Config.GRID_PRICE_BUY}/kWh")
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:#374151;'
            f'margin-top:-8px">{src_note}</div>',
            unsafe_allow_html=True)
    with ctl[3]:
        st.markdown("<br>", unsafe_allow_html=True)
        run_opt = st.button("🔍 Optimise", type="primary",
                            use_container_width=True)

    # Auto-run on first load or button press
    if run_opt or st.session_state.opt_result is None:
        st.session_state.opt_result =             st.session_state.optimizer.find_optimal_operating_point(
                available_power_kw=opt_power,
                grid_price_eur_kwh=Config.GRID_PRICE_BUY,
                h2_price_eur_kg=opt_h2_price,
                source=opt_source)

    opt_res = st.session_state.opt_result
    if opt_res and opt_res.all_points:
        bl  = opt_res.best_lcoh_point
        bp  = opt_res.best_profit_point
        pts = opt_res.all_points

        # ── KPI strip ──────────────────────────────────────────────────────
        ok = st.columns(4)
        kpi(ok[0], "Best LCOH point",
            f"{bl.elec_power_kw:.2f} kW",
            f"€{bl.lcoh_eur_kg:.3f}/kg · η {bl.efficiency_pct:.1f}%",
            "kpi-cyan")
        kpi(ok[1], "Lowest LCOH",
            f"€{bl.lcoh_eur_kg:.3f}/kg",
            f"Target €{Config.LCOH_TARGET_EURO_KG:.1f}/kg · "
            + ("✅ Met" if bl.lcoh_eur_kg <= Config.LCOH_TARGET_EURO_KG
               else "⚠ Above target"),
            "kpi-green" if bl.lcoh_eur_kg <= Config.LCOH_TARGET_EURO_KG
            else "kpi-amber")
        kpi(ok[2], "Best profit point",
            f"{bp.elec_power_kw:.2f} kW",
            f"€{bp.net_profit_eur:,.0f}/yr · η {bp.efficiency_pct:.1f}%",
            "kpi-purple")
        kpi(ok[3], "Max annual profit",
            f"€{bp.net_profit_eur:,.0f}",
            f"H₂ {bp.annual_h2_kg:.0f} kg/yr · "
            + ("✅ Profitable" if bp.net_profit_eur > 0 else "❌ Loss"),
            "kpi-green" if bp.net_profit_eur > 0 else "kpi-red")

        # Recommendation banner
        st.markdown(
            f'<div class="alert-info" style="margin:8px 0">💡 '
            f'<b>{opt_res.recommendation}</b> — {opt_res.reason}</div>',
            unsafe_allow_html=True)

        # ── Operating curve — FULL WIDTH ───────────────────────────────────
        st.markdown(
            '<p class="sec-hdr">S30/30 operating curve — '
            'efficiency · LCOH · H₂ rate</p>',
            unsafe_allow_html=True)

        p_arr  = [p.elec_power_kw      for p in pts]
        e_arr  = [p.efficiency_pct     for p in pts]
        l_arr  = [p.lcoh_eur_kg        for p in pts]
        h_arr  = [p.h2_rate_kg_h*1000  for p in pts]
        pr_arr = [p.net_profit_eur     for p in pts]

        oc_fig = go.Figure()

        # H₂ rate — background fill
        oc_fig.add_trace(go.Scatter(
            x=p_arr, y=h_arr, name="H₂ rate (g/h)", yaxis="y3",
            fill="tozeroy", fillcolor="rgba(14,165,233,.07)",
            line=dict(color="rgba(14,165,233,.25)", width=1),
            hovertemplate="Power: %{x:.2f} kW  H₂: %{y:.1f} g/h<extra></extra>"))

        # Efficiency curve
        oc_fig.add_trace(go.Scatter(
            x=p_arr, y=e_arr, name="Efficiency η (%)", yaxis="y",
            line=dict(color=C["elec"], width=3),
            hovertemplate="Power: %{x:.2f} kW  η: %{y:.1f}%<extra></extra>"))

        # LCOH curve
        oc_fig.add_trace(go.Scatter(
            x=p_arr, y=l_arr, name="LCOH (€/kg)", yaxis="y2",
            line=dict(color=C["h2"], width=2.5, dash="dash"),
            hovertemplate="Power: %{x:.2f} kW  LCOH: €%{y:.3f}/kg<extra></extra>"))

        # Datasheet reference verticals
        for p_pt, lbl, vcol in [
            (Config.ELEC_P_MIN_KW, "Min 0.74kW", "#94a3b8"),
            (Config.ELEC_P_NOM_KW, "Nominal 3kW", "#22c55e"),
            (Config.ELEC_P_MAX_KW, "Peak 5.63kW", "#f59e0b"),
        ]:
            oc_fig.add_vline(x=p_pt, line_dash="dot",
                line_color=vcol, line_width=1.2,
                annotation_text=lbl, annotation_font_size=10,
                annotation_font_color=vcol,
                annotation_position="top right")

        # Best LCOH diamond
        oc_fig.add_trace(go.Scatter(
            x=[bl.elec_power_kw], y=[bl.efficiency_pct],
            mode="markers", name="◆ Best LCOH", yaxis="y",
            marker=dict(color=C["bess"], size=14, symbol="diamond",
                        line=dict(color="#fff", width=2)),
            hovertemplate=(f"Best LCOH: {bl.elec_power_kw:.2f} kW<br>"
                           f"η: {bl.efficiency_pct:.1f}%<br>"
                           f"LCOH: €{bl.lcoh_eur_kg:.3f}/kg"
                           "<extra>Best LCOH</extra>")))

        # Best profit star
        oc_fig.add_trace(go.Scatter(
            x=[bp.elec_power_kw], y=[bp.efficiency_pct],
            mode="markers", name="★ Best profit", yaxis="y",
            marker=dict(color=C["solar"], size=14, symbol="star",
                        line=dict(color="#fff", width=2)),
            hovertemplate=(f"Best profit: {bp.elec_power_kw:.2f} kW<br>"
                           f"η: {bp.efficiency_pct:.1f}%<br>"
                           f"Profit: €{bp.net_profit_eur:,.0f}/yr"
                           "<extra>Best profit</extra>")))

        # Current live operating point
        oc_fig.add_trace(go.Scatter(
            x=[s.elec_kw], y=[s.elec_eff_pct],
            mode="markers", name="● Now (live)", yaxis="y",
            marker=dict(color=C["fc"], size=16, symbol="circle",
                        line=dict(color="#fff", width=2.5)),
            hovertemplate=(f"Live: {s.elec_kw:.2f} kW<br>"
                           f"η: {s.elec_eff_pct:.1f}%"
                           "<extra>Current</extra>")))

        # LCOH target reference
        oc_fig.add_hline(
            y=Config.LCOH_TARGET_EURO_KG,
            line_dash="dot", line_color="#ef4444",
            line_width=1.5, yref="y2",
            annotation_text=f"Target €{Config.LCOH_TARGET_EURO_KG}/kg",
            annotation_font_color="#ef4444",
            annotation_font_size=10)

        oc_fig.update_layout(**mk(height=420,
            xaxis=dict(title="Electrolyzer power (kW)",
                       range=[0, Config.ELEC_P_MAX_KW + 0.4]),
            yaxis=dict(title="Efficiency η (%)", color=C["elec"],
                       range=[50, 95], side="left"),
            yaxis2=dict(title="LCOH (€/kg)", overlaying="y",
                        side="right", color=C["h2"]),
            yaxis3=dict(overlaying="y", side="right",
                        showgrid=False, showticklabels=False),
            # Vertical legend on right side — all 6 items always visible
            legend=dict(
                orientation="v",
                x=1.12, y=1.0,
                xanchor="left", yanchor="top",
                font=dict(size=13, color="#111827"),
                bgcolor="rgba(255,255,255,0.97)",
                bordercolor="#e2e8f0", borderwidth=1,
                itemsizing="constant",
                itemwidth=30,
            ),
            margin=dict(t=32, b=56, l=52, r=180)))
        st.plotly_chart(oc_fig, use_container_width=True)

        # ── Row 2: H₂ vs profit scatter + sensitivity heatmap ─────────────
        r7a, r7b = st.columns(2)

        with r7a:
            st.markdown(
                '<p class="sec-hdr">H₂ volume vs profit — operating trade-off</p>',
                unsafe_allow_html=True)
            sc7 = go.Figure()
            sc7.add_trace(go.Scatter(
                x=[p.annual_h2_kg for p in pts],
                y=pr_arr,
                mode="markers",
                marker=dict(
                    color=p_arr,
                    colorscale=[[0,"#f0f9ff"],[0.5,C["elec"]],[1,"#4c1d95"]],
                    size=8, opacity=0.85,
                    colorbar=dict(title="kW", thickness=12, len=0.6),
                    line=dict(color="#fff", width=0.5)),
                hovertemplate=(
                    "Power: %{marker.color:.2f} kW<br>"
                    "H₂: %{x:.0f} kg/yr<br>"
                    "Profit: €%{y:,.0f}/yr<extra></extra>"),
                showlegend=False))
            # Best LCOH marker
            sc7.add_trace(go.Scatter(
                x=[bl.annual_h2_kg], y=[bl.net_profit_eur],
                mode="markers+text", name="◆ Best LCOH",
                text=["◆ Best LCOH"], textposition="top right",
                textfont=dict(size=13, color=C["bess"], family="'Segoe UI',sans-serif"),
                marker=dict(color=C["bess"], size=13, symbol="diamond",
                            line=dict(color="#fff", width=2))))
            # Best profit marker
            sc7.add_trace(go.Scatter(
                x=[bp.annual_h2_kg], y=[bp.net_profit_eur],
                mode="markers+text", name="★ Best profit",
                text=["★ Best profit"], textposition="top right",
                textfont=dict(size=13, color=C["solar"], family="'Segoe UI',sans-serif"),
                marker=dict(color=C["solar"], size=13, symbol="star",
                            line=dict(color="#fff", width=2))))
            # Break-even
            sc7.add_hline(y=0, line_dash="dot", line_color="#ef4444",
                line_width=1.2,
                annotation_text="Break-even",
                annotation_font_size=10,
                annotation_font_color="#ef4444")
            sc7.update_layout(**mk(height=310,
                xaxis_title="Annual H₂ production (kg/yr)",
                yaxis_title="Net annual profit (€)",
                legend=dict(
                    orientation="v",
                    x=1.02, y=1.0,
                    xanchor="left", yanchor="top",
                    font=dict(size=13, color="#111827"),
                    bgcolor="rgba(255,255,255,0.97)",
                    bordercolor="#e2e8f0", borderwidth=1,
                    itemsizing="constant",
                ),
                margin=dict(t=32, b=56, l=52, r=160)))
            st.plotly_chart(sc7, use_container_width=True)

        with r7b:
            st.markdown(
                '<p class="sec-hdr">Sensitivity heatmap — H₂ price × PV scale</p>',
                unsafe_allow_html=True)
            with st.spinner("Computing sensitivity…"):
                sens = st.session_state.optimizer.annual_sensitivity(
                    h2_prices=[4.0, 5.0, 6.0, 7.0, 8.0],
                    pv_scales=[1.0, 1.5, 2.0])
            sdf_raw      = pd.DataFrame(sens)
            pv_vals      = sorted(sdf_raw["pv_scale"].unique())
            h2_vals      = sorted(sdf_raw["h2_price"].unique())
            heat_z       = []
            heat_text    = []
            for pv_s in pv_vals:
                row_z    = []
                row_txt  = []
                for h2_p in h2_vals:
                    row = sdf_raw[(sdf_raw["pv_scale"] == pv_s) &
                                  (sdf_raw["h2_price"] == h2_p)]
                    v   = float(row["net_profit"].values[0]) if len(row) else 0
                    row_z.append(v)
                    row_txt.append(f"€{v:,.0f}")
                heat_z.append(row_z)
                heat_text.append(row_txt)

            hm = go.Figure(go.Heatmap(
                z=heat_z,
                x=[f"€{p}/kg" for p in h2_vals],
                y=[f"PV ×{s}" for s in pv_vals],
                text=heat_text,
                texttemplate="%{text}",
                textfont=dict(size=11, color="#111827"),
                colorscale=[
                    [0.0, "#fee2e2"],
                    [0.35, "#fef9c3"],
                    [0.6, "#dcfce7"],
                    [1.0, "#14532d"]],
                hovertemplate=(
                    "PV: %{y}<br>"
                    "H₂ price: %{x}<br>"
                    "Net profit: %{text}<extra></extra>"),
                showscale=True,
                colorbar=dict(title="€/yr", thickness=14, len=0.8)))
            hm.update_layout(**mk(height=310,
                xaxis_title="H₂ market price",
                yaxis_title="PV system scale",
                margin=dict(t=20, b=50, l=70, r=80)))
            st.plotly_chart(hm, use_container_width=True)

    else:
        st.info("Adjust controls above and click **🔍 Optimise** to run.")

# ─── TAB 8: UNCERTAINTY ────────────────────────────────────────────────────
with tabs[7]:
    st.markdown('<p class="sec-hdr">Monte Carlo probabilistic analysis · Zagreb climatology · 80% confidence intervals</p>',
                unsafe_allow_html=True)
    # ── Controls CSS — larger labels same style as Tab 7 ──────────────────
    st.markdown("""
<style>
[data-testid="stSlider"] label p,
[data-testid="stNumberInput"] label p,
[data-testid="stSelectSlider"] label p {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"],
[data-testid="stSelectSlider"] [data-testid="stTickBarMin"],
[data-testid="stSelectSlider"] [data-testid="stTickBarMax"] {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
}
[data-testid="stNumberInput"] input {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}
</style>
""", unsafe_allow_html=True)

    uc1, uc2 = st.columns([1, 2])
    with uc1:
        unc_h2_price = st.slider(
            "H₂ sell price (€/kg)", 3.0, 12.0, 6.0, 0.5, key="unc_h2")
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:#0ea5e9;'
            f'margin-top:-8px">Selected: <b>€{unc_h2_price:.1f}/kg</b></div>',
            unsafe_allow_html=True)

        unc_opex = st.number_input(
            "Annual OPEX (€)",
            min_value=0, max_value=100_000,
            value=8_000, step=500, key="unc_opex")
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:#374151;'
            f'margin-top:-4px">'
            f'O&M + maintenance · typical range €5,000–15,000/yr</div>',
            unsafe_allow_html=True)

        unc_n = st.select_slider(
            "Simulations", [100, 200, 500, 1000], value=500, key="unc_n")
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:#374151;'
            f'margin-top:-8px">'
            f'{"Fast ~1s" if unc_n<=100 else "Balanced ~3s" if unc_n<=500 else "Precise ~8s"}'
            f' · {unc_n} Monte Carlo runs</div>',
            unsafe_allow_html=True)

    with uc2:
        st.markdown(
            '<div class="alert-info">ℹ️ <b>What this shows:</b> '
            'Each simulation samples a different year of Zagreb weather, panel tolerances, '
            'and electrolyzer efficiency. P10/P50/P90 shows how much performance varies '
            'due to factors outside your control — mainly Zagreb weather variability.</div>',
            unsafe_allow_html=True)

    if st.button("▶ Run Uncertainty Analysis",type="primary",key="unc_run"):
        with st.spinner(f"Running {unc_n} Monte Carlo simulations…"):
            st.session_state.unc_report = st.session_state.uncertainty.run(
                n_simulations=int(unc_n),
                h2_price_eur_kg=unc_h2_price,
                opex_annual_eur=unc_opex)

    unc = st.session_state.unc_report
    if unc:
        uk = st.columns(4)
        kpi(uk[0],"H₂ Production P50",f"{unc.annual_h2_kg.p50:.0f} kg/yr",
            f"P10:{unc.annual_h2_kg.p10:.0f} — P90:{unc.annual_h2_kg.p90:.0f}","kpi-cyan")
        kpi(uk[1],"Operating LCOH P50",f"€{unc.op_lcoh_eur_kg.p50:.2f}/kg",
            f"P10:€{unc.op_lcoh_eur_kg.p10:.2f} — P90:€{unc.op_lcoh_eur_kg.p90:.2f}","kpi-amber")
        kpi(uk[2],"CO₂ Offset P50",f"{unc.co2_offset_ton.p50:.1f} ton/yr",
            "vs Steam Methane Reforming","kpi-green")
        kpi(uk[3],"Revenue / OPEX",f"{unc.revenue_to_opex_pct.p50:.0f}%",
            f"P10:{unc.revenue_to_opex_pct.p10:.0f}% — P90:{unc.revenue_to_opex_pct.p90:.0f}%","kpi-purple")

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown('<p class="sec-hdr">H₂ production — probability distribution</p>',
                        unsafe_allow_html=True)
            fig_h = go.Figure()
            fig_h.add_trace(go.Histogram(x=unc.samples_h2,nbinsx=30,
                marker_color=C["h2"],marker_line_color="#ffffff",
                marker_line_width=0.5,opacity=0.85,name="Simulations"))
            for val,label,color in [
                (unc.annual_h2_kg.p10,"P10",C["fc"]),
                (unc.annual_h2_kg.p50,"P50",C["bess"]),
                (unc.annual_h2_kg.p90,"P90",C["wind"])]:
                fig_h.add_vline(x=val,
                    line_dash="dash" if label!="P50" else "solid",
                    line_color=color,line_width=2,
                    annotation_text=f"{label}: {val:.0f}",
                    annotation_font_color=color,annotation_font_size=11)
            fig_h.update_layout(**mk(height=230,
                xaxis_title="kg H₂/year",yaxis_title="Count",showlegend=False))
            st.plotly_chart(fig_h, use_container_width=True)

            st.markdown('<p class="sec-hdr">Sensitivity — key uncertainty drivers</p>',
                        unsafe_allow_html=True)
            sens_items = list(unc.sensitivity.items())[:6]
            colors_s = [C["solar"],C["solar"],C["bess"],C["elec"],C["grid"],C["grid"]]
            fig_s = go.Figure(go.Bar(
                x=[v for _,v in sens_items],y=[k for k,_ in sens_items],
                orientation="h",marker_color=colors_s[:len(sens_items)],
                marker_line_width=0,
                text=[f"{v:.0f}%" for _,v in sens_items],
                textposition="outside",textfont=dict(color="#111827")))
            fig_s.update_layout(**mk(height=230,
                xaxis_title="Correlation with H₂ output (%)",
                yaxis=dict(autorange="reversed"),xaxis_range=[0,80]))
            st.plotly_chart(fig_s, use_container_width=True)

        with col_r:
            st.markdown('<p class="sec-hdr">Operating LCOH — probability distribution</p>',
                        unsafe_allow_html=True)
            fig_l = go.Figure()
            fig_l.add_trace(go.Histogram(x=unc.samples_lcoh,nbinsx=30,
                marker_color=C["elec"],marker_line_color="#ffffff",
                marker_line_width=0.5,opacity=0.85,name="Simulations"))
            for val,label,color in [
                (unc.op_lcoh_eur_kg.p10,"P10",C["fc"]),
                (unc.op_lcoh_eur_kg.p50,"P50",C["bess"]),
                (unc.op_lcoh_eur_kg.p90,"P90",C["wind"])]:
                fig_l.add_vline(x=val,
                    line_dash="dash" if label!="P50" else "solid",
                    line_color=color,line_width=2,
                    annotation_text=f"{label}: €{val:.2f}",
                    annotation_font_color=color,annotation_font_size=11)
            fig_l.update_layout(**mk(height=230,
                xaxis_title="€/kg",yaxis_title="Count",showlegend=False))
            st.plotly_chart(fig_l, use_container_width=True)

            st.markdown('<p class="sec-hdr">Full probabilistic summary — P10 / P50 / P90</p>',
                        unsafe_allow_html=True)
            prob_metrics = [
                ("Annual H₂",        unc.annual_h2_kg,         "kg/yr",  "{:.0f}",    False),
                ("Daily H₂",         unc.daily_h2_g,           "g/day",  "{:.0f}",    False),
                ("CO₂ offset",       unc.co2_offset_ton,       "ton/yr", "{:.2f}",    False),
                ("Op. LCOH",         unc.op_lcoh_eur_kg,       "€/kg",   "€{:.2f}",   True),
                ("Revenue",          unc.annual_op_revenue,    "€/yr",   "€{:.0f}",   False),
                ("Elec. hours",      unc.electrolyzer_hours,   "h/yr",   "{:.0f}",    False),
                ("Grid independence",unc.grid_independence,    "%",      "{:.0f}%",   False),
            ]
            def _prow(lbl, m, unit, fmt, lower_is_better):
                p10c = "#b91c1c" if lower_is_better else "#64748b"
                p90c = "#15803d" if not lower_is_better else "#64748b"
                return (
                    f'<tr style="border-bottom:1px solid #f1f5f9">' +
                    f'<td style="padding:8px 12px;font-size:12px;font-weight:500;color:#374151">{lbl}</td>' +
                    f'<td style="padding:8px 12px;text-align:right;font-size:12px;color:{p10c}">{fmt.format(m.p10)}</td>' +
                    f'<td style="padding:8px 12px;text-align:right;font-size:13px;font-weight:700;color:#111827">{fmt.format(m.p50)}</td>' +
                    f'<td style="padding:8px 12px;text-align:right;font-size:12px;color:{p90c}">{fmt.format(m.p90)}</td>' +
                    f'<td style="padding:8px 12px;text-align:right;font-size:11px;color:#94a3b8">{m.band}</td>' +
                    f'<td style="padding:8px 12px;text-align:right;font-size:11px;color:#94a3b8">{unit}</td>' +
                    '</tr>'
                )
            table_rows = "".join(_prow(*args) for args in prob_metrics)
            prob_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:6px;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table style="width:100%;border-collapse:collapse;background:#fff;
  border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
  <thead>
    <tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0">
      <th style="padding:9px 12px;text-align:left;font-size:11px;color:#374151;
        font-weight:600;text-transform:uppercase;letter-spacing:.06em">Metric</th>
      <th style="padding:9px 12px;text-align:right;font-size:11px;color:#b91c1c;
        font-weight:600">P10 Pessimistic</th>
      <th style="padding:9px 12px;text-align:right;font-size:11px;color:#111827;
        font-weight:700">P50 Most Likely</th>
      <th style="padding:9px 12px;text-align:right;font-size:11px;color:#15803d;
        font-weight:600">P90 Optimistic</th>
      <th style="padding:9px 12px;text-align:right;font-size:11px;color:#64748b;
        font-weight:600">Band</th>
      <th style="padding:9px 12px;text-align:right;font-size:11px;color:#64748b;
        font-weight:600">Unit</th>
    </tr>
  </thead>
  <tbody>{table_rows}</tbody>
</table>
</body></html>"""
            components.html(prob_html, height=280, scrolling=False)

        st.markdown('<p class="sec-hdr">Scale-up pathway to commercial viability</p>',
                    unsafe_allow_html=True)

        # Visual bar chart — H₂ production at each scale
        sc_kw   = [sc.electrolyzer_kw   for sc in unc.scale_up]
        sc_h2t  = [sc.h2_ton_year       for sc in unc.scale_up]
        sc_rev  = [sc.annual_revenue     for sc in unc.scale_up]
        sc_lbls = [f"{'✅' if sc.is_commercial else '🔬'} {sc.electrolyzer_kw:.0f} kW"
                   for sc in unc.scale_up]
        sc_cols = ["#0ea5e9" if sc.is_commercial else "#8b5cf6"
                   for sc in unc.scale_up]

        sc_fig = go.Figure()
        sc_fig.add_trace(go.Bar(
            x=sc_lbls, y=sc_h2t,
            name="H₂ (ton/yr)",
            marker_color=sc_cols, marker_line_width=0,
            text=[f"{v:.1f} t" for v in sc_h2t],
            textposition="outside",
            textfont=dict(color="#374151", size=11),
            hovertemplate="%{x}<br>H₂: %{y:.1f} ton/yr<extra></extra>"))
        sc_fig.add_trace(go.Scatter(
            x=sc_lbls, y=sc_rev,
            name="Revenue (€/yr)", yaxis="y2",
            mode="lines+markers",
            line=dict(color=C["bess"], width=2),
            marker=dict(size=8, color=C["bess"],
                        line=dict(color="#fff", width=2)),
            hovertemplate="%{x}<br>Revenue: €%{y:,.0f}/yr<extra></extra>"))
        # Current pilot marker
        sc_fig.add_annotation(
            x=sc_lbls[0], y=sc_h2t[0],
            text="← You are here",
            showarrow=True, arrowhead=2,
            font=dict(size=10, color="#7c3aed"),
            arrowcolor="#7c3aed", ax=60, ay=-30)
        sc_fig.update_layout(**mk(height=280,
            yaxis=dict(title="H₂ production (ton/yr)", color="#8b5cf6"),
            yaxis2=dict(title="Revenue (€/yr)", overlaying="y",
                        side="right", color=C["bess"]),
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=13, color="#111827"), bgcolor="rgba(255,255,255,0.95)", bordercolor="#e2e8f0", borderwidth=1),
            xaxis=dict(tickangle=-15)))
        st.plotly_chart(sc_fig, use_container_width=True)

        # Styled scale-up cards
        scale_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:6px;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="display:grid;grid-template-columns:repeat({len(unc.scale_up)},1fr);gap:10px">
{"".join(f'''<div style="background:{"#eff6ff" if sc.is_commercial else "#faf5ff"};
  border:2px solid {"#3b82f6" if sc.is_commercial else "#8b5cf6"};
  border-radius:10px;padding:12px 14px;text-align:center">
  <div style="font-size:11px;font-weight:700;color:{"#1d4ed8" if sc.is_commercial else "#6d28d9"};
    text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">
    {"✅ Commercial" if sc.is_commercial else "🔬 Pilot"}</div>
  <div style="font-size:22px;font-weight:700;color:#111827">{sc.electrolyzer_kw:.0f} kW</div>
  <div style="font-size:12px;color:#64748b;margin:4px 0">electrolyzer</div>
  <div style="border-top:1px solid #e2e8f0;margin:8px 0;padding-top:8px">
    <div style="font-size:13px;font-weight:600;color:#111827">{sc.h2_ton_year:.1f} ton/yr</div>
    <div style="font-size:10px;color:#64748b">H₂ production</div>
  </div>
  <div style="margin-bottom:6px">
    <div style="font-size:13px;font-weight:600;color:#111827">€{sc.annual_revenue:,.0f}</div>
    <div style="font-size:10px;color:#64748b">annual revenue</div>
  </div>
  <div>
    <div style="font-size:13px;font-weight:600;color:#0ea5e9">€{sc.op_lcoh:.2f}/kg</div>
    <div style="font-size:10px;color:#64748b">operating LCOH</div>
  </div>
</div>''' for sc in unc.scale_up)}
</div>
</body></html>"""
        components.html(scale_html, height=220, scrolling=False)
        st.markdown(
            '<div class="alert-info" style="margin-top:8px">ℹ️ <b>Scale-up note:</b> '
            'Operating LCOH stays constant at any scale — it reflects S30/30 PEM stack physics. '
            'Full-LCOH target of €4.5/kg (including CAPEX amortisation) requires ≥1 MW '
            'production volume. The pilot demonstrates the technology and validates '
            'the Zagreb renewable resource.</div>',
            unsafe_allow_html=True)
    else:
        st.info("Click **▶ Run Uncertainty Analysis** to generate the probabilistic report.")

# ─── TAB 9: SAFETY ─────────────────────────────────────────────────────────
with tabs[8]:

    # ── Overall system status banner ───────────────────────────────────────
    has_critical = any(a.level == "error"   for a in alrt.active) if alrt.active else False
    has_warning  = any(a.level == "warning" for a in alrt.active) if alrt.active else False
    n_alerts     = len(alrt.active) if alrt.active else 0

    if has_critical:
        banner_col, banner_ic, banner_txt = "#fee2e2", "🚨", f"CRITICAL — {n_alerts} active alert(s) require immediate attention"
        banner_border = "#ef4444"
    elif has_warning:
        banner_col, banner_ic, banner_txt = "#fffbeb", "⚠", f"WARNING — {n_alerts} active alert(s)"
        banner_border = "#f59e0b"
    else:
        banner_col, banner_ic, banner_txt = "#f0fdf4", "✅", "ALL SYSTEMS NOMINAL — No active alerts"
        banner_border = "#22c55e"

    st.markdown(
        f'<div style="background:{banner_col};border:2px solid {banner_border};'
        f'border-radius:10px;padding:14px 20px;margin-bottom:12px;'
        f'display:flex;align-items:center;gap:12px">'
        f'<span style="font-size:24px">{banner_ic}</span>'
        f'<div>'
        f'<div style="font-size:15px;font-weight:700;color:#111827">{banner_txt}</div>'
        f'<div style="font-size:12px;color:#64748b;margin-top:2px">'
        f'LUMINIH2 · Zagreb · Tick #{s.tick} · {now_dt.strftime("%H:%M:%S")}'
        f'</div></div></div>',
        unsafe_allow_html=True)

    # ── Row 1: Health matrix + Active alerts ───────────────────────────────
    s9a, s9b = st.columns([1, 1])

    with s9a:
        st.markdown('<p class="sec-hdr">System health matrix</p>',
                    unsafe_allow_html=True)
        hrow("BESS SoC",         s.bess_soc_pct,  "%",    (20, 90),  (10, 95))
        hrow("BESS Temperature", s.bess_temp_c,   "°C",   (10, 45),  (0,  55))
        hrow("BESS SoH",         s.bess_soh_pct,  "%",    (85, 100), (75, 100))
        hrow("Stack SoH",        s.elec_soh_pct,  "%",    (85, 100), (75, 100))
        hrow("Tank Pressure",    s.pressure_bar,  "bar",  (10, 550), (10, 625))
        hrow("Tank Temperature", s.tank_temp_c,   "°C",   (15, 55),  (10, 65))
        hrow("H₂ Purity",        s.elec_purity,   "%",    (99.95, 100), (99.50, 100), ".4f")
        if sub:
            hrow("Water Quality",
                 sub["water"].resistance_mohm_cm, "MΩ·cm", (10, 999), (5, 10))
            hrow("H₂ Moisture",
                 sub["dryer"].moisture_ppm,       "ppm",   (0, 5),    (0, 8), ".2f")
            hrow("Stack Temp",
                 sub["warmup"].current_temp_c,    "°C",    (20, 65),  (15, 70))

        # Leak status badge
        ld_c  = "#fee2e2" if s.leak_detected else "#f0fdf4"
        ld_bc = "#ef4444" if s.leak_detected else "#22c55e"
        ld_tc = "#b91c1c" if s.leak_detected else "#15803d"
        st.markdown(
            f'<div style="background:{ld_c};border:1px solid {ld_bc};'
            f'border-radius:8px;padding:8px 12px;margin-top:8px;'
            f'display:flex;align-items:center;justify-content:space-between">'
            f'<span style="font-size:13px;font-weight:600;color:{ld_tc}">'
            f'{"⚠ H₂ LEAK DETECTED" if s.leak_detected else "✅ No leak detected"}'
            f'</span>'
            f'<span style="font-size:11px;color:#64748b">'
            f'Threshold {Config.LEAK_DETECTION_THRESHOLD:.2e} kg/h</span>'
            f'</div>',
            unsafe_allow_html=True)

    with s9b:
        # Active alerts
        st.markdown('<p class="sec-hdr">Active alerts</p>', unsafe_allow_html=True)
        if not alrt.active:
            st.markdown(
                '<div class="alert-info" style="margin-bottom:8px">'
                '✅ No active alerts — all systems nominal</div>',
                unsafe_allow_html=True)
        else:
            for a in sorted(alrt.active,
                            key=lambda x: {"error":0,"warning":1,"info":2}.get(x.level,3)):
                cls = {"error":"alert-error","warning":"alert-warning",
                       "info":"alert-info"}.get(a.level,"alert-info")
                ic  = {"error":"🚨","warning":"⚠","info":"ℹ"}.get(a.level,"ℹ")
                st.markdown(
                    f'<div class="{cls}" style="margin-bottom:6px">'
                    f'{ic} <b>[{a.code}]</b> {a.message}'
                    f'<span style="float:right;opacity:.6;font-size:11px">'
                    f'{a.ts}</span></div>',
                    unsafe_allow_html=True)

        # Maintenance messages from subsystems
        if sub and sub.get("maintenance"):
            st.markdown('<p class="sec-hdr" style="margin-top:10px">'
                        'Maintenance required</p>', unsafe_allow_html=True)
            for m_msg in sub["maintenance"]:
                st.markdown(
                    f'<div class="alert-warning" style="margin-bottom:4px">'
                    f'🔧 {m_msg}</div>',
                    unsafe_allow_html=True)

        # Device safety limits — styled cards
        st.markdown('<p class="sec-hdr" style="margin-top:10px">'
                    'Device safety limits</p>', unsafe_allow_html=True)
        limits = [
            ("BESS thermal runaway",  f"{Config.THERMAL_RUNAWAY_TEMP}°C",      "LFP runaway threshold"),
            ("Tank MWP (TH540-50)",   f"{Config.SAFETY_MAX_PRESSURE_BAR} bar", "Maximum working pressure"),
            ("Emergency SoC floor",   f"{Config.EMERGENCY_SHUTDOWN_SOC*100:.0f}%", "Auto grid import below"),
            ("H₂ leak threshold",     f"{Config.LEAK_DETECTION_THRESHOLD:.2e} kg/h", "Mass balance alarm"),
            ("Water quality min",     "> 10 MΩ·cm",                            "DIN ISO 3696 Type 1"),
            ("H₂ moisture max",       "< 5 ppm",                               "AIRCELL 3000 requirement"),
            ("Electrolyzer range",    f"{Config.electrolyzer.water_temp_min_c}–{Config.electrolyzer.water_temp_max_c}°C", "Stack operating temp"),
            ("Compressor outlet",     f"max {Config.compressor.outlet_max_bar} bar", "HCS-100 rated limit"),
        ]
        limits_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:4px;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="display:flex;flex-direction:column;gap:4px">
{"".join(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px"><div><div style="font-size:12px;font-weight:500;color:#1e293b">{lbl}</div><div style="font-size:10px;color:#94a3b8">{sub_}</div></div><div style="font-size:13px;font-weight:700;color:#111827;white-space:nowrap">{val}</div></div>' for lbl,val,sub_ in limits)}
</div>
</body></html>"""
        components.html(limits_html, height=310, scrolling=False)

    # ── Row 2: Safety trend charts ─────────────────────────────────────────
    st.markdown('<p class="sec-hdr">Safety trends — real-time monitoring</p>',
                unsafe_allow_html=True)
    t9a, t9b, t9c = st.columns(3)

    with t9a:
        # BESS SoC + temperature combined
        if hd("bess_soc_pct") and hd("bess_temp_c"):
            sf = go.Figure()
            sf.add_trace(go.Scatter(
                x=hist["time"], y=hist["bess_soc_pct"],
                name="SoC %", fill="tozeroy",
                fillcolor="rgba(34,197,94,.10)",
                line=dict(color=C["bess"], width=2),
                hovertemplate="%{y:.1f}%<extra>BESS SoC</extra>"))
            sf.add_hline(y=Config.BATT_SOC_MIN*100, line_dash="dot",
                line_color="#ef4444", line_width=1,
                annotation_text=f"Min {Config.BATT_SOC_MIN*100:.0f}%",
                annotation_font_size=9, annotation_font_color="#ef4444")
            sf.update_layout(**mk(height=180, yaxis_title="SoC %",
                margin=dict(t=20,b=30,l=44,r=16)))
            st.plotly_chart(sf, use_container_width=True)

    with t9b:
        # BESS temperature with danger zones
        if hd("bess_temp_c"):
            tf = go.Figure()
            tf.add_hrect(y0=55, y1=Config.THERMAL_RUNAWAY_TEMP,
                fillcolor="rgba(251,191,36,.12)", line_width=0,
                annotation_text="⚠ Warning", annotation_font_size=9,
                annotation_font_color="#92400e")
            tf.add_hrect(y0=Config.THERMAL_RUNAWAY_TEMP, y1=90,
                fillcolor="rgba(239,68,68,.15)", line_width=0,
                annotation_text="🔥 Runaway", annotation_font_size=9,
                annotation_font_color="#7f1d1d")
            tf.add_trace(go.Scatter(
                x=hist["time"], y=hist["bess_temp_c"],
                name="BESS °C", fill="tozeroy",
                fillcolor="rgba(239,68,68,.06)",
                line=dict(color=C["fc"], width=2),
                hovertemplate="%{y:.1f}°C<extra>BESS temp</extra>"))
            tf.update_layout(**mk(height=180, yaxis_title="°C",
                yaxis=dict(range=[10, 80]),
                margin=dict(t=20,b=30,l=44,r=16)))
            st.plotly_chart(tf, use_container_width=True)

    with t9c:
        # Tank pressure trend
        if hd("pressure_bar"):
            pf = go.Figure()
            pf.add_hrect(
                y0=Config.SAFETY_MAX_PRESSURE_BAR * 0.90,
                y1=Config.SAFETY_MAX_PRESSURE_BAR,
                fillcolor="rgba(239,68,68,.10)", line_width=0,
                annotation_text="Near MWP", annotation_font_size=9,
                annotation_font_color="#b91c1c")
            pf.add_trace(go.Scatter(
                x=hist["time"], y=hist["pressure_bar"],
                name="Pressure", fill="tozeroy",
                fillcolor="rgba(59,130,246,.08)",
                line=dict(color=C["wind"], width=2),
                hovertemplate="%{y:.0f} bar<extra>Tank pressure</extra>"))
            pf.add_hline(
                y=Config.SAFETY_MAX_PRESSURE_BAR,
                line_dash="dash", line_color="#ef4444", line_width=1.5,
                annotation_text=f"MWP {Config.SAFETY_MAX_PRESSURE_BAR:.0f} bar",
                annotation_font_size=9, annotation_font_color="#ef4444")
            pf.update_layout(**mk(height=180, yaxis_title="bar",
                margin=dict(t=20,b=30,l=44,r=16)))
            st.plotly_chart(pf, use_container_width=True)

# ─── TAB 10: EMS FLOWCHART ─────────────────────────────────────────────────
with tabs[9]:
    st.markdown(
        '<p class="sec-hdr">Energy management strategy — decision flowchart</p>',
        unsafe_allow_html=True)
    st.markdown(
        "The EMS evaluates five inputs every tick and dispatches power through "
        "a priority-ordered decision tree. Electrolyzer runs first (highest revenue), "
        "BESS charges from surplus, grid export is last resort.",
        unsafe_allow_html=False)

    ems_html = """<!DOCTYPE html>
<html><head>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
body{background:transparent;padding:16px}
svg{width:100%;height:auto;display:block}
</style>
</head><body>
<svg viewBox="0 0 780 1380" role="img" xmlns="http://www.w3.org/2000/svg">
<title>LUMINIH2 Energy Management Strategy Flowchart</title>
<desc>Decision flowchart showing how PV power, wind power, load demand, battery SOC and hydrogen storage level feed into the EMS logic to produce outputs including battery charging, electrolyzer activation, fuel cell dispatch, grid interaction and emergency protection.</desc>

<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>

<!-- ─── INPUTS ROW ─── -->
<!-- Input box style: light blue fill #e0f2fe, border #0ea5e9, text #0c4a6e -->

<!-- PV Power -->
<rect x="20"  y="20" width="120" height="50" rx="8" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="80"  y="41" text-anchor="middle" font-size="12" font-weight="600" fill="#0c4a6e">☀ PV power</text>
<text x="80"  y="58" text-anchor="middle" font-size="11" fill="#0369a1">0 – 15 kW</text>

<!-- Wind Power -->
<rect x="160" y="20" width="120" height="50" rx="8" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="220" y="41" text-anchor="middle" font-size="12" font-weight="600" fill="#0c4a6e">💨 Wind power</text>
<text x="220" y="58" text-anchor="middle" font-size="11" fill="#0369a1">0 – 10 kW</text>

<!-- Load Demand -->
<rect x="300" y="20" width="120" height="50" rx="8" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="360" y="41" text-anchor="middle" font-size="12" font-weight="600" fill="#0c4a6e">⚡ Load demand</text>
<text x="360" y="58" text-anchor="middle" font-size="11" fill="#0369a1">EV + base load</text>

<!-- Battery SOC -->
<rect x="440" y="20" width="120" height="50" rx="8" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="500" y="41" text-anchor="middle" font-size="12" font-weight="600" fill="#0c4a6e">🔋 Battery SOC</text>
<text x="500" y="58" text-anchor="middle" font-size="11" fill="#0369a1">10 – 90 %</text>

<!-- H2 Storage -->
<rect x="580" y="20" width="150" height="50" rx="8" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="655" y="41" text-anchor="middle" font-size="12" font-weight="600" fill="#0c4a6e">⚗ H₂ storage</text>
<text x="655" y="58" text-anchor="middle" font-size="11" fill="#0369a1">Buffer + main tank</text>

<!-- Arrows from inputs into EMS box -->
<line x1="80"  y1="70" x2="370" y2="118" stroke="#0ea5e9" stroke-width="1.2" fill="none" marker-end="url(#arr)"/>
<line x1="220" y1="70" x2="375" y2="118" stroke="#0ea5e9" stroke-width="1.2" fill="none" marker-end="url(#arr)"/>
<line x1="360" y1="70" x2="380" y2="118" stroke="#0ea5e9" stroke-width="1.2" fill="none" marker-end="url(#arr)"/>
<line x1="500" y1="70" x2="385" y2="118" stroke="#0ea5e9" stroke-width="1.2" fill="none" marker-end="url(#arr)"/>
<line x1="655" y1="70" x2="390" y2="118" stroke="#0ea5e9" stroke-width="1.2" fill="none" marker-end="url(#arr)"/>

<!-- ─── EMS BRAIN ─── -->
<rect x="240" y="118" width="280" height="54" rx="10" fill="#1e293b" stroke="#475569" stroke-width="1.5"/>
<text x="380" y="140" text-anchor="middle" font-size="14" font-weight="700" fill="#f1f5f9">EMS Brain</text>
<text x="380" y="158" text-anchor="middle" font-size="11" fill="#94a3b8">ems_brain.py · runs every 10 s</text>

<!-- Arrow down to D1 -->
<line x1="380" y1="172" x2="380" y2="210" stroke="#475569" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- ─── DECISION 1: Surplus renewable? ─── -->
<!-- Diamond shape -->
<polygon points="380,210 500,250 380,290 260,250" fill="#fef9c3" stroke="#d97706" stroke-width="1.5"/>
<text x="380" y="245" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">Surplus renewable</text>
<text x="380" y="261" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">energy?</text>
<text x="380" y="277" text-anchor="middle" font-size="10" fill="#92400e">gen > load demand</text>

<!-- NO → left → Low renewable path -->
<line x1="260" y1="250" x2="120" y2="250" stroke="#ef4444" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="190" y="243" text-anchor="middle" font-size="11" font-weight="600" fill="#b91c1c">NO</text>

<!-- YES → down -->
<line x1="380" y1="290" x2="380" y2="330" stroke="#22c55e" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="394" y="315" font-size="11" font-weight="600" fill="#15803d">YES</text>

<!-- ─── DECISION 2: Battery charged? ─── -->
<polygon points="380,330 500,370 380,410 260,370" fill="#fef9c3" stroke="#d97706" stroke-width="1.5"/>
<text x="380" y="365" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">Battery charged?</text>
<text x="380" y="381" text-anchor="middle" font-size="10" fill="#92400e">SOC ≥ 85 %</text>

<!-- NO → left → Charge BESS output -->
<line x1="260" y1="370" x2="180" y2="370" stroke="#ef4444" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="220" y="363" text-anchor="middle" font-size="11" font-weight="600" fill="#b91c1c">NO</text>

<!-- YES → down -->
<line x1="380" y1="410" x2="380" y2="450" stroke="#22c55e" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="394" y="435" font-size="11" font-weight="600" fill="#15803d">YES</text>

<!-- Charge BESS output box -->
<rect x="30" y="345" width="150" height="50" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="1.5"/>
<text x="105" y="366" text-anchor="middle" font-size="12" font-weight="600" fill="#14532d">Charge BESS</text>
<text x="105" y="382" text-anchor="middle" font-size="11" fill="#166534">25 kW max (0.25C)</text>

<!-- ─── DECISION 3: Electrolyzer ready? ─── -->
<polygon points="380,450 500,490 380,530 260,490" fill="#fef9c3" stroke="#d97706" stroke-width="1.5"/>
<text x="380" y="485" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">Electrolyzer</text>
<text x="380" y="501" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">available?</text>
<text x="380" y="517" text-anchor="middle" font-size="10" fill="#92400e">surplus ≥ 0.74 kW</text>

<!-- NO → right → surplus to grid -->
<line x1="500" y1="490" x2="590" y2="490" stroke="#ef4444" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="545" y="483" text-anchor="middle" font-size="11" font-weight="600" fill="#b91c1c">NO</text>

<!-- YES → down -->
<line x1="380" y1="530" x2="380" y2="570" stroke="#22c55e" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="394" y="555" font-size="11" font-weight="600" fill="#15803d">YES</text>

<!-- ─── OUTPUT: Activate Electrolyzer ─── -->
<rect x="255" y="570" width="250" height="64" rx="8" fill="#ede9fe" stroke="#7c3aed" stroke-width="1.5"/>
<text x="380" y="593" text-anchor="middle" font-size="13" font-weight="700" fill="#3b0764">⚗ Activate electrolyzer</text>
<text x="380" y="610" text-anchor="middle" font-size="11" fill="#5b21b6">Nominal 3 kW → Peak 5.63 kW</text>
<text x="380" y="626" text-anchor="middle" font-size="10" fill="#6d28d9">30-min min. runtime guard</text>

<!-- Arrow down from electrolyzer -->
<line x1="380" y1="634" x2="380" y2="670" stroke="#7c3aed" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- ─── DECISION 4: H2 storage available? ─── -->
<polygon points="380,670 500,710 380,750 260,710" fill="#fef9c3" stroke="#d97706" stroke-width="1.5"/>
<text x="380" y="705" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">H₂ storage</text>
<text x="380" y="721" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">available?</text>
<text x="380" y="737" text-anchor="middle" font-size="10" fill="#92400e">main tank &gt; 10 %</text>

<!-- NO → right -->
<line x1="500" y1="710" x2="590" y2="710" stroke="#ef4444" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="545" y="703" text-anchor="middle" font-size="11" font-weight="600" fill="#b91c1c">NO</text>

<!-- YES → down -->
<line x1="380" y1="750" x2="380" y2="790" stroke="#22c55e" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="394" y="775" font-size="11" font-weight="600" fill="#15803d">YES</text>

<!-- ─── OUTPUT: Dispatch to HRS ─── -->
<rect x="255" y="790" width="250" height="52" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="1.5"/>
<text x="380" y="812" text-anchor="middle" font-size="13" font-weight="700" fill="#14532d">⛽ Dispatch H₂ to HRS</text>
<text x="380" y="830" text-anchor="middle" font-size="11" fill="#166534">Compressor + TH540-50 → HRS</text>

<!-- Arrow down -->
<line x1="380" y1="842" x2="380" y2="880" stroke="#22c55e" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- ─── DECISION 5: Grid export surplus? ─── -->
<polygon points="380,880 500,920 380,960 260,920" fill="#fef9c3" stroke="#d97706" stroke-width="1.5"/>
<text x="380" y="915" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">Remaining</text>
<text x="380" y="931" text-anchor="middle" font-size="12" font-weight="600" fill="#78350f">surplus &gt; 0.5 kW?</text>

<!-- YES → right → Grid export -->
<line x1="500" y1="920" x2="590" y2="920" stroke="#22c55e" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="545" y="913" text-anchor="middle" font-size="11" font-weight="600" fill="#15803d">YES</text>

<!-- NO → down → Supply load only -->
<line x1="380" y1="960" x2="380" y2="1000" stroke="#ef4444" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="394" y="985" font-size="11" font-weight="600" fill="#b91c1c">NO</text>

<!-- ─── OUTPUT: Supply load ─── -->
<rect x="255" y="1000" width="250" height="52" rx="8" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="380" y="1022" text-anchor="middle" font-size="13" font-weight="700" fill="#0c4a6e">⚡ Supply load</text>
<text x="380" y="1040" text-anchor="middle" font-size="11" fill="#0369a1">FC → EV charger → base load</text>

<!-- Arrow down to final -->
<line x1="380" y1="1052" x2="380" y2="1090" stroke="#0ea5e9" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- ─── EMERGENCY / PROTECTION ─── -->
<rect x="235" y="1090" width="290" height="64" rx="10" fill="#fee2e2" stroke="#ef4444" stroke-width="2"/>
<text x="380" y="1113" text-anchor="middle" font-size="13" font-weight="700" fill="#7f1d1d">🔒 Emergency / protection</text>
<text x="380" y="1130" text-anchor="middle" font-size="11" fill="#991b1b">SOC &lt; 15 % → grid import</text>
<text x="380" y="1146" text-anchor="middle" font-size="11" fill="#991b1b">T &gt; 70°C or leak → shutdown</text>

<!-- ─── RIGHT BRANCH: Low renewable ─── -->
<!-- Low renewable box -->
<rect x="30" y="220" width="150" height="52" rx="8" fill="#fee2e2" stroke="#ef4444" stroke-width="1.5"/>
<text x="105" y="241" text-anchor="middle" font-size="12" font-weight="600" fill="#7f1d1d">Low renewable</text>
<text x="105" y="257" text-anchor="middle" font-size="11" fill="#991b1b">condition</text>
<text x="105" y="273" text-anchor="middle" font-size="10" fill="#b91c1c">gen &lt; load demand</text>

<!-- Arrow from Low renewable down to FC decision -->
<line x1="105" y1="272" x2="105" y2="870" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="5 4" fill="none"/>
<line x1="105" y1="870" x2="255" y2="920" stroke="#ef4444" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<text x="60" y="580" font-size="11" fill="#b91c1c" text-anchor="middle">check</text>
<text x="60" y="594" font-size="11" fill="#b91c1c" text-anchor="middle">FC avail.</text>

<!-- Activate FC output (right of D4) -->
<rect x="590" y="685" width="165" height="52" rx="8" fill="#dcfce7" stroke="#22c55e" stroke-width="1.5"/>
<text x="672" y="707" text-anchor="middle" font-size="12" font-weight="700" fill="#14532d">⚡ Activate fuel cell</text>
<text x="672" y="723" text-anchor="middle" font-size="11" fill="#166534">AIRCELL 3000 · 3 kW</text>

<!-- Grid export output (right of D5) -->
<rect x="590" y="895" width="165" height="52" rx="8" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.5"/>
<text x="672" y="917" text-anchor="middle" font-size="12" font-weight="700" fill="#1e293b">🌐 Grid export</text>
<text x="672" y="933" text-anchor="middle" font-size="11" fill="#475569">€0.12/kWh · Croatia</text>

<!-- Grid surplus no output (right of D3) -->
<rect x="590" y="465" width="165" height="52" rx="8" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1.5"/>
<text x="672" y="487" text-anchor="middle" font-size="12" font-weight="700" fill="#1e293b">🌐 Export surplus</text>
<text x="672" y="503" text-anchor="middle" font-size="11" fill="#475569">no electrolyzer capacity</text>

<!-- ─── LEGEND ─── -->
<rect x="20" y="1180" width="730" height="170" rx="10" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
<text x="385" y="1202" text-anchor="middle" font-size="13" font-weight="700" fill="#111827">Legend</text>

<!-- Input -->
<rect x="40"  y="1215" width="90" height="30" rx="6" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="85"  y="1234" text-anchor="middle" font-size="11" font-weight="600" fill="#0c4a6e">Input</text>

<!-- Decision -->
<polygon points="200,1215 250,1230 200,1245 150,1230" fill="#fef9c3" stroke="#d97706" stroke-width="1.5"/>
<text x="200" y="1234" text-anchor="middle" font-size="11" font-weight="600" fill="#78350f">Decision</text>

<!-- Output green -->
<rect x="270" y="1215" width="110" height="30" rx="6" fill="#dcfce7" stroke="#22c55e" stroke-width="1.5"/>
<text x="325" y="1234" text-anchor="middle" font-size="11" font-weight="600" fill="#14532d">Output (active)</text>

<!-- Output purple -->
<rect x="395" y="1215" width="130" height="30" rx="6" fill="#ede9fe" stroke="#7c3aed" stroke-width="1.5"/>
<text x="460" y="1234" text-anchor="middle" font-size="11" font-weight="600" fill="#3b0764">Electrolyzer action</text>

<!-- Emergency -->
<rect x="540" y="1215" width="120" height="30" rx="6" fill="#fee2e2" stroke="#ef4444" stroke-width="1.5"/>
<text x="600" y="1234" text-anchor="middle" font-size="11" font-weight="600" fill="#7f1d1d">Emergency / fault</text>

<!-- Arrow labels -->
<line x1="40"  y1="1280" x2="100" y2="1280" stroke="#22c55e" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="115" y="1284" font-size="11" fill="#15803d" font-weight="600">YES / surplus</text>
<line x1="250" y1="1280" x2="310" y2="1280" stroke="#ef4444" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="325" y="1284" font-size="11" fill="#b91c1c" font-weight="600">NO / deficit</text>
<line x1="440" y1="1280" x2="500" y2="1280" stroke="#475569" stroke-width="1.5" stroke-dasharray="5 4" fill="none" marker-end="url(#arr)"/>
<text x="515" y="1284" font-size="11" fill="#475569">Fallback path</text>

<!-- Priority note -->
<text x="385" y="1318" text-anchor="middle" font-size="11" fill="#64748b">EMS priority order: 1 Electrolyzer nominal · 2 BESS charge · 3 Electrolyzer overload · 4 EV · 5 Grid export · 6 Emergency import</text>
<text x="385" y="1336" text-anchor="middle" font-size="11" fill="#64748b">Minimum electrolyzer run-time: 30 minutes · Timestep: 10 seconds · BESS emergency floor: SOC 15 %</text>

</svg>
</body></html>"""

    components.html(ems_html, height=1420, scrolling=True)

# ─── TAB 11: MONITORING ARCHITECTURE ───────────────────────────────────────
with tabs[10]:
    st.markdown(
        '<p class="sec-hdr">Monitoring & diagnostic architecture — renewable hydrogen microgrid</p>',
        unsafe_allow_html=True)
    st.markdown(
        "Four-layer architecture: physical subsystems with sensors feed into a data "
        "acquisition layer, which feeds the supervisory EMS and monitoring platform, "
        "which connects to the cloud digital twin and predictive maintenance engine.",
        unsafe_allow_html=False)

    arch_html = """<!DOCTYPE html>
<html><head>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
body{background:transparent;padding:12px 16px 24px}
svg{width:100%;height:auto;display:block}
</style>
</head><body>
<svg viewBox="0 0 780 1060" role="img" xmlns="http://www.w3.org/2000/svg">
<title>Monitoring and diagnostic architecture of the renewable hydrogen microgrid</title>
<desc>Four-layer architecture diagram showing physical subsystems (PV, wind, electrolyser, fuel cell, hydrogen tank, battery, converters) with sensors, feeding into a DAQ data layer with communication interfaces, then a supervisory layer with EMS, monitoring platform, diagnostic block and HMI, and finally a cloud layer with digital twin and predictive maintenance.</desc>

<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
  <marker id="arr2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- LAYER 1: PHYSICAL SUBSYSTEMS                                    -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<rect x="14" y="14" width="752" height="218" rx="12" fill="#f0f9ff" stroke="#0ea5e9" stroke-width="1.5" stroke-dasharray="6 3"/>
<text x="390" y="36" text-anchor="middle" font-size="13" font-weight="700" fill="#0c4a6e">Layer 1 — Physical subsystems &amp; sensors</text>

<!-- PV Array -->
<rect x="30"  y="48" width="96" height="70" rx="8" fill="#fffbeb" stroke="#f59e0b" stroke-width="1.5"/>
<text x="78"  y="69"  text-anchor="middle" font-size="12" font-weight="700" fill="#78350f">☀ PV array</text>
<text x="78"  y="84"  text-anchor="middle" font-size="10" fill="#92400e">42 × 360W</text>
<text x="78"  y="98"  text-anchor="middle" font-size="10" fill="#92400e">15 kW total</text>
<rect x="34"  y="108" width="88" height="22" rx="4" fill="#fef3c7" stroke="#f59e0b" stroke-width="1"/>
<text x="78"  y="123" text-anchor="middle" font-size="10" fill="#78350f">V · I · irradiance · T</text>

<!-- Wind turbine -->
<rect x="136" y="48" width="96" height="70" rx="8" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
<text x="184" y="69"  text-anchor="middle" font-size="12" font-weight="700" fill="#1e3a8a">💨 Wind HAWT</text>
<text x="184" y="84"  text-anchor="middle" font-size="10" fill="#1d4ed8">10 kW rated</text>
<text x="184" y="98"  text-anchor="middle" font-size="10" fill="#1d4ed8">cut-in 2.5 m/s</text>
<rect x="140" y="108" width="88" height="22" rx="4" fill="#dbeafe" stroke="#3b82f6" stroke-width="1"/>
<text x="184" y="123" text-anchor="middle" font-size="10" fill="#1e3a8a">V · I · wind speed · T</text>

<!-- Converters -->
<rect x="242" y="48" width="96" height="70" rx="8" fill="#f0fdf4" stroke="#22c55e" stroke-width="1.5"/>
<text x="290" y="65"  text-anchor="middle" font-size="12" font-weight="700" fill="#14532d">⚡ Converters</text>
<text x="290" y="80"  text-anchor="middle" font-size="10" fill="#166534">DC/DC · DC/AC</text>
<text x="290" y="95"  text-anchor="middle" font-size="10" fill="#166534">MPPT · inverter</text>
<rect x="246" y="108" width="88" height="22" rx="4" fill="#dcfce7" stroke="#22c55e" stroke-width="1"/>
<text x="290" y="123" text-anchor="middle" font-size="10" fill="#14532d">V · I · switching freq</text>

<!-- Electrolyser -->
<rect x="348" y="48" width="96" height="70" rx="8" fill="#faf5ff" stroke="#8b5cf6" stroke-width="1.5"/>
<text x="396" y="65"  text-anchor="middle" font-size="12" font-weight="700" fill="#3b0764">⚗ Electrolyser</text>
<text x="396" y="80"  text-anchor="middle" font-size="10" fill="#5b21b6">ITM S30/30</text>
<text x="396" y="95"  text-anchor="middle" font-size="10" fill="#5b21b6">PEM · 5.63 kW</text>
<rect x="352" y="108" width="88" height="22" rx="4" fill="#ede9fe" stroke="#8b5cf6" stroke-width="1"/>
<text x="396" y="123" text-anchor="middle" font-size="10" fill="#3b0764">V · I · P · T · flow</text>

<!-- Fuel cell -->
<rect x="454" y="48" width="96" height="70" rx="8" fill="#fff1f2" stroke="#ef4444" stroke-width="1.5"/>
<text x="502" y="65"  text-anchor="middle" font-size="12" font-weight="700" fill="#7f1d1d">⚡ Fuel cell</text>
<text x="502" y="80"  text-anchor="middle" font-size="10" fill="#991b1b">AIRCELL 3000</text>
<text x="502" y="95"  text-anchor="middle" font-size="10" fill="#991b1b">3 kW · PEM</text>
<rect x="458" y="108" width="88" height="22" rx="4" fill="#fee2e2" stroke="#ef4444" stroke-width="1"/>
<text x="502" y="123" text-anchor="middle" font-size="10" fill="#7f1d1d">V · I · P · T · η</text>

<!-- H2 tank -->
<rect x="560" y="48" width="96" height="70" rx="8" fill="#f0f9ff" stroke="#0ea5e9" stroke-width="1.5"/>
<text x="608" y="65"  text-anchor="middle" font-size="12" font-weight="700" fill="#0c4a6e">⚗ H₂ tank</text>
<text x="608" y="80"  text-anchor="middle" font-size="10" fill="#0369a1">TH540-50</text>
<text x="608" y="95"  text-anchor="middle" font-size="10" fill="#0369a1">500 bar · 10.8 kg</text>
<rect x="564" y="108" width="88" height="22" rx="4" fill="#e0f2fe" stroke="#0ea5e9" stroke-width="1"/>
<text x="608" y="123" text-anchor="middle" font-size="10" fill="#0c4a6e">P · T · level · leak</text>

<!-- Battery BESS -->
<rect x="666" y="48" width="96" height="70" rx="8" fill="#f0fdf4" stroke="#22c55e" stroke-width="1.5"/>
<text x="714" y="65"  text-anchor="middle" font-size="12" font-weight="700" fill="#14532d">🔋 BESS</text>
<text x="714" y="80"  text-anchor="middle" font-size="10" fill="#166534">LFP · 100 kWh</text>
<text x="714" y="95"  text-anchor="middle" font-size="10" fill="#166534">SoC 10–90 %</text>
<rect x="670" y="108" width="88" height="22" rx="4" fill="#dcfce7" stroke="#22c55e" stroke-width="1"/>
<text x="714" y="123" text-anchor="middle" font-size="10" fill="#14532d">V · I · SoC · T · SoH</text>

<!-- Sensor type legend row -->
<rect x="14" y="146" width="752" height="74" rx="8" fill="rgba(255,255,255,0.7)" stroke="#e2e8f0" stroke-width="1"/>
<text x="390" y="164" text-anchor="middle" font-size="11" font-weight="700" fill="#374151">Sensor types deployed</text>

<!-- Sensor chips -->
<rect x="30"  y="172" width="85" height="34" rx="6" fill="#fff7ed" stroke="#f59e0b" stroke-width="1"/>
<text x="72"  y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#78350f">⚡ Voltage</text>
<text x="72"  y="198" text-anchor="middle" font-size="9"  fill="#92400e">Hall-effect / shunt</text>

<rect x="124" y="172" width="85" height="34" rx="6" fill="#fff7ed" stroke="#f59e0b" stroke-width="1"/>
<text x="166" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#78350f">〜 Current</text>
<text x="166" y="198" text-anchor="middle" font-size="9"  fill="#92400e">CT clamp · shunt</text>

<rect x="218" y="172" width="85" height="34" rx="6" fill="#eff6ff" stroke="#3b82f6" stroke-width="1"/>
<text x="260" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#1e3a8a">▲ Pressure</text>
<text x="260" y="198" text-anchor="middle" font-size="9"  fill="#1d4ed8">Piezo · strain gauge</text>

<rect x="312" y="172" width="85" height="34" rx="6" fill="#fff1f2" stroke="#ef4444" stroke-width="1"/>
<text x="354" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#7f1d1d">🌡 Temperature</text>
<text x="354" y="198" text-anchor="middle" font-size="9"  fill="#991b1b">PT100 · thermocouple</text>

<rect x="406" y="172" width="100" height="34" rx="6" fill="#fee2e2" stroke="#ef4444" stroke-width="1"/>
<text x="456" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#7f1d1d">💧 H₂ leak detect</text>
<text x="456" y="198" text-anchor="middle" font-size="9"  fill="#991b1b">Catalytic · electrochem</text>

<rect x="515" y="172" width="85" height="34" rx="6" fill="#f0fdf4" stroke="#22c55e" stroke-width="1"/>
<text x="557" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#14532d">⚗ Flow rate</text>
<text x="557" y="198" text-anchor="middle" font-size="9"  fill="#166534">Coriolis · MFC</text>

<rect x="609" y="172" width="85" height="34" rx="6" fill="#faf5ff" stroke="#8b5cf6" stroke-width="1"/>
<text x="651" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#3b0764">📊 Power quality</text>
<text x="651" y="198" text-anchor="middle" font-size="9"  fill="#5b21b6">PQ analyser · THD</text>

<rect x="703" y="172" width="55" height="34" rx="6" fill="#f8fafc" stroke="#94a3b8" stroke-width="1"/>
<text x="730" y="186" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">🌦 Weather</text>
<text x="730" y="198" text-anchor="middle" font-size="9"  fill="#475569">GHI · wind</text>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- ARROWS L1 → L2                                                  -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<line x1="78"  y1="232" x2="78"  y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>
<line x1="184" y1="232" x2="184" y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>
<line x1="290" y1="232" x2="290" y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>
<line x1="396" y1="232" x2="396" y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>
<line x1="502" y1="232" x2="502" y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>
<line x1="608" y1="232" x2="608" y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>
<line x1="714" y1="232" x2="714" y2="268" stroke="#94a3b8" stroke-width="1.2" fill="none" marker-end="url(#arr2)"/>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- LAYER 2: DATA ACQUISITION                                       -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<rect x="14" y="268" width="752" height="130" rx="12" fill="#f8fafc" stroke="#64748b" stroke-width="1.5" stroke-dasharray="6 3"/>
<text x="390" y="288" text-anchor="middle" font-size="13" font-weight="700" fill="#1e293b">Layer 2 — Data acquisition &amp; communication</text>

<!-- DAQ block -->
<rect x="30"  y="298" width="200" height="80" rx="8" fill="#e2e8f0" stroke="#475569" stroke-width="1.5"/>
<text x="130" y="318" text-anchor="middle" font-size="12" font-weight="700" fill="#1e293b">DAQ / Data acquisition</text>
<text x="130" y="334" text-anchor="middle" font-size="10" fill="#475569">Analog &amp; digital I/O · sampling 10 s</text>
<text x="130" y="349" text-anchor="middle" font-size="10" fill="#475569">Signal conditioning · ADC 16-bit</text>
<text x="130" y="364" text-anchor="middle" font-size="10" fill="#475569">Anti-aliasing · timestamp · buffer</text>

<!-- Arrow DAQ → comms -->
<line x1="230" y1="338" x2="278" y2="338" stroke="#475569" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- Communication interfaces -->
<rect x="278" y="298" width="460" height="80" rx="8" fill="#e2e8f0" stroke="#475569" stroke-width="1.5"/>
<text x="508" y="318" text-anchor="middle" font-size="12" font-weight="700" fill="#1e293b">Communication interfaces</text>

<!-- Comms protocol chips -->
<rect x="290" y="328" width="70" height="38" rx="5" fill="#fff" stroke="#94a3b8" stroke-width="1"/>
<text x="325" y="344" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">Modbus</text>
<text x="325" y="358" text-anchor="middle" font-size="9"  fill="#475569">RTU / TCP</text>

<rect x="370" y="328" width="70" height="38" rx="5" fill="#fff" stroke="#94a3b8" stroke-width="1"/>
<text x="405" y="344" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">CAN bus</text>
<text x="405" y="358" text-anchor="middle" font-size="9"  fill="#475569">IEC 11898</text>

<rect x="450" y="328" width="70" height="38" rx="5" fill="#fff" stroke="#94a3b8" stroke-width="1"/>
<text x="485" y="344" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">Ethernet</text>
<text x="485" y="358" text-anchor="middle" font-size="9"  fill="#475569">IEC 61850</text>

<rect x="530" y="328" width="70" height="38" rx="5" fill="#fff" stroke="#94a3b8" stroke-width="1"/>
<text x="565" y="344" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">OPC-UA</text>
<text x="565" y="358" text-anchor="middle" font-size="9"  fill="#475569">IEC 62541</text>

<rect x="610" y="328" width="70" height="38" rx="5" fill="#fff" stroke="#94a3b8" stroke-width="1"/>
<text x="645" y="344" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">MQTT</text>
<text x="645" y="358" text-anchor="middle" font-size="9"  fill="#475569">IoT broker</text>

<rect x="690" y="328" width="40" height="38" rx="5" fill="#fff" stroke="#94a3b8" stroke-width="1"/>
<text x="710" y="344" text-anchor="middle" font-size="10" font-weight="600" fill="#1e293b">RS485</text>
<text x="710" y="358" text-anchor="middle" font-size="9"  fill="#475569">serial</text>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- ARROWS L2 → L3                                                  -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<line x1="390" y1="398" x2="390" y2="432" stroke="#475569" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<line x1="200" y1="398" x2="200" y2="432" stroke="#475569" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<line x1="580" y1="398" x2="580" y2="432" stroke="#475569" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- LAYER 3: SUPERVISORY                                            -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<rect x="14" y="432" width="752" height="198" rx="12" fill="#fafaf9" stroke="#374151" stroke-width="1.5" stroke-dasharray="6 3"/>
<text x="390" y="452" text-anchor="middle" font-size="13" font-weight="700" fill="#111827">Layer 3 — Supervisory control, monitoring &amp; diagnostics</text>

<!-- EMS -->
<rect x="30"  y="462" width="158" height="148" rx="8" fill="#1e293b" stroke="#475569" stroke-width="1.5"/>
<text x="109" y="484" text-anchor="middle" font-size="12" font-weight="700" fill="#f1f5f9">EMS Brain</text>
<text x="109" y="500" text-anchor="middle" font-size="10" fill="#94a3b8">ems_brain.py</text>
<text x="109" y="516" text-anchor="middle" font-size="9"  fill="#64748b">Electrolyzer-first</text>
<text x="109" y="530" text-anchor="middle" font-size="9"  fill="#64748b">BESS charge mgmt</text>
<text x="109" y="544" text-anchor="middle" font-size="9"  fill="#64748b">FC dispatch logic</text>
<text x="109" y="558" text-anchor="middle" font-size="9"  fill="#64748b">Grid import/export</text>
<text x="109" y="572" text-anchor="middle" font-size="9"  fill="#64748b">30-min run guard</text>
<text x="109" y="586" text-anchor="middle" font-size="9"  fill="#64748b">10 s timestep</text>

<!-- Monitoring platform -->
<rect x="198" y="462" width="170" height="148" rx="8" fill="#eff6ff" stroke="#3b82f6" stroke-width="1.5"/>
<text x="283" y="484" text-anchor="middle" font-size="12" font-weight="700" fill="#1e3a8a">Monitoring platform</text>
<text x="283" y="500" text-anchor="middle" font-size="10" fill="#1d4ed8">Streamlit dashboard</text>
<text x="283" y="516" text-anchor="middle" font-size="9"  fill="#1d4ed8">9 live tabs · auto-refresh</text>
<text x="283" y="530" text-anchor="middle" font-size="9"  fill="#1d4ed8">KPI cards · trend charts</text>
<text x="283" y="544" text-anchor="middle" font-size="9"  fill="#1d4ed8">Plotly interactive viz</text>
<text x="283" y="558" text-anchor="middle" font-size="9"  fill="#1d4ed8">History buffer 120 ticks</text>
<text x="283" y="572" text-anchor="middle" font-size="9"  fill="#1d4ed8">LCOH accumulator</text>
<text x="283" y="586" text-anchor="middle" font-size="9"  fill="#1d4ed8">Scenario engine 365-d</text>

<!-- Diagnostic block -->
<rect x="378" y="462" width="170" height="148" rx="8" fill="#faf5ff" stroke="#8b5cf6" stroke-width="1.5"/>
<text x="463" y="484" text-anchor="middle" font-size="12" font-weight="700" fill="#3b0764">Diagnostic block</text>
<text x="463" y="500" text-anchor="middle" font-size="10" fill="#5b21b6">core_engine.py</text>
<text x="463" y="516" text-anchor="middle" font-size="9"  fill="#5b21b6">Alert system (error/warn)</text>
<text x="463" y="530" text-anchor="middle" font-size="9"  fill="#5b21b6">Thermal runaway detect</text>
<text x="463" y="544" text-anchor="middle" font-size="9"  fill="#5b21b6">H₂ leak mass-balance</text>
<text x="463" y="558" text-anchor="middle" font-size="9"  fill="#5b21b6">Stack SoH tracking</text>
<text x="463" y="572" text-anchor="middle" font-size="9"  fill="#5b21b6">BESS SoH degradation</text>
<text x="463" y="586" text-anchor="middle" font-size="9"  fill="#5b21b6">Subsystem fault flags</text>

<!-- HMI -->
<rect x="558" y="462" width="200" height="148" rx="8" fill="#fff7ed" stroke="#f59e0b" stroke-width="1.5"/>
<text x="658" y="484" text-anchor="middle" font-size="12" font-weight="700" fill="#78350f">HMI / Operator interface</text>
<text x="658" y="500" text-anchor="middle" font-size="10" fill="#92400e">shared_state.py</text>
<text x="658" y="516" text-anchor="middle" font-size="9"  fill="#92400e">Voice welcome briefing</text>
<text x="658" y="530" text-anchor="middle" font-size="9"  fill="#92400e">Live clock + tick counter</text>
<text x="658" y="544" text-anchor="middle" font-size="9"  fill="#92400e">WX badge (LIVE/cached)</text>
<text x="658" y="558" text-anchor="middle" font-size="9"  fill="#92400e">Weather manual override</text>
<text x="658" y="572" text-anchor="middle" font-size="9"  fill="#92400e">EV + BESS force controls</text>
<text x="658" y="586" text-anchor="middle" font-size="9"  fill="#92400e">Scenario parameters</text>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- ARROWS L3 → L4                                                  -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<line x1="250" y1="630" x2="250" y2="664" stroke="#374151" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>
<line x1="530" y1="630" x2="530" y2="664" stroke="#374151" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>

<!-- Bidirectional feedback arrows L3 ↔ L2 -->
<path d="M109 462 L109 430 L390 430" stroke="#1e293b" stroke-width="1.2" stroke-dasharray="4 3" fill="none" marker-end="url(#arr2)"/>
<text x="250" y="426" text-anchor="middle" font-size="9" fill="#475569">EMS dispatch commands</text>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- LAYER 4: CLOUD / DIGITAL TWIN                                   -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<rect x="14" y="664" width="752" height="192" rx="12" fill="#f0fdf4" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="6 3"/>
<text x="390" y="685" text-anchor="middle" font-size="13" font-weight="700" fill="#14532d">Layer 4 — Cloud · digital twin · predictive maintenance</text>

<!-- Digital twin block -->
<rect x="30"  y="696" width="330" height="140" rx="10" fill="#dcfce7" stroke="#22c55e" stroke-width="1.5"/>
<text x="195" y="718" text-anchor="middle" font-size="13" font-weight="700" fill="#14532d">LUMINIH2 Digital Twin</text>
<text x="195" y="734" text-anchor="middle" font-size="10" fill="#166534">Pre-deployment simulation · zagreb-h2-digitaltwin</text>

<!-- DT sub-modules -->
<rect x="42"  y="742" width="145" height="80" rx="6" fill="#bbf7d0" stroke="#22c55e" stroke-width="1"/>
<text x="114" y="758" text-anchor="middle" font-size="10" font-weight="700" fill="#14532d">Physics engines</text>
<text x="114" y="772" text-anchor="middle" font-size="9"  fill="#166534">energy_assets.py</text>
<text x="114" y="784" text-anchor="middle" font-size="9"  fill="#166534">hydrogen_assets.py</text>
<text x="114" y="796" text-anchor="middle" font-size="9"  fill="#166534">subsystems.py</text>
<text x="114" y="808" text-anchor="middle" font-size="9"  fill="#166534">weather_api.py</text>

<rect x="200" y="742" width="145" height="80" rx="6" fill="#bbf7d0" stroke="#22c55e" stroke-width="1"/>
<text x="272" y="758" text-anchor="middle" font-size="10" font-weight="700" fill="#14532d">Analysis tools</text>
<text x="272" y="772" text-anchor="middle" font-size="9"  fill="#166534">scenario_engine.py</text>
<text x="272" y="784" text-anchor="middle" font-size="9"  fill="#166534">optimizer.py</text>
<text x="272" y="796" text-anchor="middle" font-size="9"  fill="#166534">uncertainty_engine.py</text>
<text x="272" y="808" text-anchor="middle" font-size="9"  fill="#166534">ai_forecaster.py</text>

<!-- Predictive maintenance block -->
<rect x="394" y="696" width="358" height="140" rx="10" fill="#ede9fe" stroke="#7c3aed" stroke-width="1.5"/>
<text x="573" y="718" text-anchor="middle" font-size="13" font-weight="700" fill="#3b0764">Predictive maintenance engine</text>
<text x="573" y="734" text-anchor="middle" font-size="10" fill="#5b21b6">uncertainty_engine.py · Monte Carlo P10/P50/P90</text>

<!-- PM sub-modules -->
<rect x="406" y="742" width="158" height="80" rx="6" fill="#ddd6fe" stroke="#7c3aed" stroke-width="1"/>
<text x="485" y="758" text-anchor="middle" font-size="10" font-weight="700" fill="#3b0764">Degradation models</text>
<text x="485" y="772" text-anchor="middle" font-size="9"  fill="#5b21b6">Stack SoH Wöhler</text>
<text x="485" y="784" text-anchor="middle" font-size="9"  fill="#5b21b6">BESS cycle throughput</text>
<text x="485" y="796" text-anchor="middle" font-size="9"  fill="#5b21b6">Compressor MTBF</text>
<text x="485" y="808" text-anchor="middle" font-size="9"  fill="#5b21b6">Desiccant saturation</text>

<rect x="576" y="742" width="164" height="80" rx="6" fill="#ddd6fe" stroke="#7c3aed" stroke-width="1"/>
<text x="658" y="758" text-anchor="middle" font-size="10" font-weight="700" fill="#3b0764">AI forecasting</text>
<text x="658" y="772" text-anchor="middle" font-size="9"  fill="#5b21b6">LSTM v3.6 · 48h lookback</text>
<text x="658" y="784" text-anchor="middle" font-size="9"  fill="#5b21b6">maybe_retrain() 20 ticks</text>
<text x="658" y="796" text-anchor="middle" font-size="9"  fill="#5b21b6">P10/P50/P90 bands</text>
<text x="658" y="808" text-anchor="middle" font-size="9"  fill="#5b21b6">Scale-up projections</text>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- DATA FLOW LEGEND                                                 -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<rect x="14" y="876" width="752" height="164" rx="10" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
<text x="390" y="896" text-anchor="middle" font-size="13" font-weight="700" fill="#111827">Data flow summary</text>

<!-- Flow arrows explanation -->
<line x1="34"  y1="918" x2="94"  y2="918" stroke="#0ea5e9" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="100" y="922" font-size="11" fill="#111827" font-weight="500">Sensor → DAQ (analog signals, 10 s)</text>

<line x1="34"  y1="944" x2="94"  y2="944" stroke="#475569" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="100" y="948" font-size="11" fill="#111827" font-weight="500">DAQ → Supervisory (Modbus/OPC-UA/MQTT)</text>

<line x1="34"  y1="970" x2="94"  y2="970" stroke="#22c55e" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="100" y="974" font-size="11" fill="#111827" font-weight="500">Supervisory → Cloud (HTTP / Streamlit Cloud / GitHub)</text>

<line x1="34"  y1="996" x2="64"  y2="996" stroke="#1e293b" stroke-width="2" stroke-dasharray="5 3" fill="none" marker-end="url(#arr)"/>
<text x="70"  y="1000" font-size="11" fill="#111827" font-weight="500">EMS commands → DAQ (setpoints, on/off dispatch)</text>

<line x1="370" y1="918" x2="430" y2="918" stroke="#8b5cf6" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="436" y="922" font-size="11" fill="#111827" font-weight="500">Diagnostic alerts → HMI (real-time fault flags)</text>

<line x1="370" y1="944" x2="430" y2="944" stroke="#f59e0b" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="436" y="948" font-size="11" fill="#111827" font-weight="500">AI forecast → EMS (horizon 6h, P50 setpoint)</text>

<line x1="370" y1="970" x2="430" y2="970" stroke="#7c3aed" stroke-width="2" fill="none" marker-end="url(#arr)"/>
<text x="436" y="974" font-size="11" fill="#111827" font-weight="500">Pred. maintenance → operator (maintenance alerts)</text>

<text x="390" y="1028" text-anchor="middle" font-size="11" fill="#64748b">Hardware: Zagreb hub · Software: Python 3.11 · Streamlit ≥1.35 · Plotly ≥5.20 · NumPy ≥1.26</text>
<text x="390" y="1046" text-anchor="middle" font-size="11" fill="#64748b">Standards: IEC 62541 (OPC-UA) · IEC 61850 (power) · ISO 14687 (H₂ purity) · DIN ISO 3696 (water)</text>

</svg>
</body></html>"""

    components.html(arch_html, height=1120, scrolling=True)

# =============================================================================
# AUTO-REFRESH
# =============================================================================
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh*1000, key="lumi_v42_r")
except ImportError:
    import time; time.sleep(refresh); st.rerun()
