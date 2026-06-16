# =============================================================================
# shared.py — LUMINIH2 Shared Resources
# White theme · Session state · KPI helpers · Auto-refresh
# Version: 4.2
# =============================================================================
#
# WHAT THIS MODULE PROVIDES:
#   - WHITE_CSS        : complete white industrial theme CSS string
#   - inject_css()     : injects CSS into Streamlit page
#   - C / PLOT / mk()  : Plotly colour palette and white template helpers
#   - kpi()            : renders a KPI card in a Streamlit column
#   - sec()            : renders a section header
#   - badge()          : returns an inline HTML badge string
#   - alert_box()      : renders a coloured alert banner
#   - health_row()     : renders one row of the Safety health matrix
#   - hd()             : checks if history DataFrame has data
#   - now_zagreb()     : returns current Zagreb datetime
#   - init_session()   : initialises all st.session_state objects once
#   - run_tick()       : runs one physics tick and updates session state
#   - sidebar_controls(): renders sidebar and returns refresh interval
#   - page_header()    : renders the top header bar
#   - show_alerts()    : renders active alert banners
#   - autorefresh()    : triggers periodic rerun
# =============================================================================

from __future__ import annotations

import streamlit as st
from datetime import datetime, timezone, timedelta

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
# Plotly colour palette & white template
# =============================================================================

C: dict[str, str] = dict(
    solar="#f59e0b", wind="#3b82f6", bess="#22c55e", elec="#8b5cf6",
    h2="#0ea5e9",   fc="#ef4444",   grid="#94a3b8", ev="#60a5fa",
    co2="#22c55e",  water="#3b82f6", o2="#f59e0b",
)

PLOT: dict = dict(
    template="plotly_white",
    paper_bgcolor="#ffffff",
    plot_bgcolor="#f8fafc",
    font_color="#0f172a",
    margin=dict(t=28, b=28, l=44, r=16),
)


def mk(**kw) -> dict:
    """Merge extra kwargs into the base Plotly white layout dict."""
    return {**PLOT, **kw}


# =============================================================================
# White industrial CSS theme
# =============================================================================

WHITE_CSS = """
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
section[data-testid="stSidebar"] label{color:#1e293b !important;font-weight:500}
section[data-testid="stSidebar"] p{color:#1e293b !important}

.page-header{background:#ffffff;border:1px solid #e2e8f0;border-left:4px solid var(--accent,#0ea5e9);
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
"""


def inject_css() -> None:
    """Inject the white industrial theme CSS into the Streamlit page."""
    st.markdown(WHITE_CSS, unsafe_allow_html=True)


# =============================================================================
# UI helper functions
# =============================================================================

def kpi(col, lbl: str, val: str, sub_: str = "", cls: str = "kpi-cyan") -> None:
    """Render a KPI card inside a Streamlit column."""
    col.markdown(
        f'<div class="kpi">'
        f'<p class="kpi-lbl">{lbl}</p>'
        f'<p class="kpi-val {cls}">{val}</p>'
        f'<p class="kpi-sub">{sub_}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def sec(title: str) -> None:
    """Render a section header."""
    st.markdown(f'<p class="sec-hdr">{title}</p>', unsafe_allow_html=True)


def badge(text: str, kind: str = "cyan") -> str:
    """Return an inline HTML badge string."""
    return f'<span class="badge badge-{kind}">{text}</span>'


def alert_box(text: str, kind: str = "info") -> None:
    """Render a coloured alert banner (info | warning | error)."""
    st.markdown(f'<div class="alert-{kind}">{text}</div>', unsafe_allow_html=True)


def health_row(
    lbl:   str,
    val:   float,
    unit:  str,
    ok:    tuple[float, float],
    warn:  tuple[float, float],
    fmt:   str = ".1f",
) -> None:
    """
    Render one row of the Safety tab health matrix.

    Green if val is in ok range, amber if in warn range, red otherwise.

    Args:
        lbl  : metric label
        val  : current value
        unit : unit string (e.g. "°C", "%", "bar")
        ok   : (min, max) green range
        warn : (min, max) amber range
        fmt  : format string for the value
    """
    v = float(val)
    if ok[0] <= v <= ok[1]:
        cls, ic = "kpi-green", "●"
    elif warn[0] <= v <= warn[1]:
        cls, ic = "kpi-amber", "▲"
    else:
        cls, ic = "kpi-red", "✖"
    st.markdown(
        f'<div class="health-row">'
        f'<span style="color:#1e293b;font-size:13px;font-weight:500">{lbl}</span>'
        f'<span class="kpi-val {cls}" style="font-size:14px">'
        f'{ic} {v:{fmt}} {unit}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def hd(hist, col: str | None = None) -> bool:
    """Return True if history DataFrame has at least 2 rows (and col exists)."""
    if len(hist) < 2:
        return False
    if col:
        return col in hist.columns and hist[col].notna().any()
    return True


def now_zagreb() -> datetime:
    """Return current datetime in Zagreb timezone (UTC+2)."""
    return datetime.now(timezone(timedelta(hours=2)))


# =============================================================================
# Session state initialisation
# =============================================================================

def init_session() -> None:
    """
    Initialise all st.session_state objects exactly once per session.

    Called at the top of main.py. All physics objects are created here
    and persist across Streamlit reruns via session_state.
    """
    if "lumi_v42" in st.session_state:
        return

    st.session_state.lumi_v42     = True
    validate_config()

    # Physics assets
    st.session_state.solar        = SolarSystem()
    st.session_state.wind         = WindSystem()
    st.session_state.bess         = BatteryBESS(0.55)
    st.session_state.electrolyzer = ElectrolyzerS30()
    st.session_state.h2_chain     = HydrogenStorageChain()
    st.session_state.fuel_cell    = FuelCellAircell()

    # Control & intelligence
    st.session_state.ems          = EMSBrain()
    st.session_state.forecaster   = AIPredictor()
    st.session_state.weather      = WeatherProvider()

    # Core engine
    st.session_state.lcoh_acc     = LCOHAccumulator()
    st.session_state.alerts       = AlertSystem()
    st.session_state.history      = HistoryBuffer(maxlen=120)
    st.session_state.subsystems   = SubsystemManager()
    st.session_state.engine       = TickEngine(
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
        st.session_state.lcoh_acc,
        st.session_state.alerts,
    )

    # Analysis tools
    st.session_state.optimizer    = EconomicOptimizer(Config)
    st.session_state.scenario_eng = ScenarioEngine(Config)
    st.session_state.uncertainty  = UncertaintyEngine(Config)   # ← added v4.2

    # Persistent database (v4.3) — writes every tick to luminih2_data.db
    try:
        _db = Database()
        st.session_state.db = _db
        st.session_state.engine.db = _db   # attach so TickEngine can write
    except Exception as _db_err:
        import logging as _lg
        _lg.getLogger('shared').warning(
            'Database unavailable — running without persistence: %s', _db_err)
        st.session_state.db = None
        st.session_state.engine.db = None

    # Result state
    st.session_state.sim_running  = True
    st.session_state.last_state   = None
    st.session_state.last_fc      = None
    st.session_state.sub_result   = None
    st.session_state.annual_report = None
    st.session_state.opt_result   = None
    st.session_state.unc_report   = None                        # ← added v4.2

    # Sidebar control values
    st.session_state.ev_demand    = 2.0
    st.session_state.force_bess   = False
    st.session_state.wx_override  = None
    st.session_state.sc_h2_price  = 6.0
    st.session_state.sc_capex     = 250_000
    st.session_state.sc_opex      = 8_000
    st.session_state.sc_elec_mode = "h2_max"


# =============================================================================
# Physics tick
# =============================================================================

def run_tick() -> None:
    """
    Run one complete simulation tick and update session state.

    Sequence:
        1. Run TickEngine (weather → generation → EMS → H₂ → economics)
        2. Append result to HistoryBuffer
        3. Run SubsystemManager (water, O₂, dryer, warm-up)
        4. Retrain AI forecaster every 20 ticks (if enough history)
    """
    if not st.session_state.get("sim_running", True):
        return

    s, fc = st.session_state.engine.run(
        override=st.session_state.wx_override,
        ev_demand_kw=st.session_state.ev_demand,
        force_bess_charge=st.session_state.force_bess,
    )
    st.session_state.history.append(s)
    st.session_state.last_state = s
    st.session_state.last_fc    = fc

    # Persist to SQLite database
    _db = st.session_state.get('db')
    if _db is not None:
        try:
            _db.write_tick(s)
        except Exception as _e:
            pass   # never let DB errors crash the simulation

    # Subsystems tick
    sub = st.session_state.subsystems.tick(
        h2_kg_h=s.h2_kg_h,
        elec_power_kw=s.elec_kw,
        ambient_temp_c=s.wx_temp_c,
        timestep_sec=Config.TIMESTEP_SEC,
    )
    st.session_state.sub_result = sub

    # AI retraining — needs ≥48 data points, runs every 20 ticks
    hist = st.session_state.history.df
    if "wx_irradiance" in hist.columns:
        irr = list(hist["wx_irradiance"].dropna())
        if len(irr) >= 48:
            st.session_state.forecaster.maybe_retrain(irr)


# =============================================================================
# Sidebar controls
# =============================================================================

def sidebar_controls() -> int:
    """
    Render sidebar controls and update session state values.

    Returns:
        refresh interval in seconds
    """
    with st.sidebar:
        st.markdown(
            '<div style="font-size:15px;font-weight:700;color:#0ea5e9;margin-bottom:10px;">'
            '⚡ LUMINIH2 Control</div>',
            unsafe_allow_html=True,
        )
        st.session_state.sim_running = st.toggle(
            "Live simulation",
            value=st.session_state.get("sim_running", True),
        )
        refresh = st.slider("Refresh (sec)", 2, 15, 4)
        st.divider()

        st.markdown("**🌦 Weather Override**")
        use_ov = st.checkbox("Manual override")
        if use_ov:
            st.session_state.wx_override = {
                "irradiance": st.slider("Irradiance W/m²", 0, 1000, 500),
                "wind_ms":    st.slider("Wind m/s", 0.0, 25.0, 6.0, 0.1),
                "temp_c":     st.slider("Temp °C", -10, 45, 20),
            }
        else:
            st.session_state.wx_override = None

        st.divider()
        st.markdown("**🔋 EV & Grid**")
        st.session_state.ev_demand  = st.slider(
            "EV demand (kW)", 0.0, Config.EV_CHARGER_POWER_KW, 2.0, 0.5)
        st.session_state.force_bess = st.checkbox("Force BESS charge from grid")

        st.divider()
        st.markdown("**📈 Scenario Settings**")
        st.session_state.sc_h2_price  = st.slider(
            "H₂ sell price (€/kg)", 3.0, 12.0, 6.0, 0.5)
        st.session_state.sc_capex     = st.number_input(
            "CAPEX (€)", value=250_000, step=10_000)
        st.session_state.sc_opex      = st.number_input(
            "OPEX/yr (€)", value=8_000, step=500)
        st.session_state.sc_elec_mode = st.selectbox(
            "EMS mode", ["h2_max", "lcoh_opt", "grid_first"])

        st.divider()
        if st.button("🔄 Reset simulation"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.markdown(
            f"<small style='color:#374151'>v4.2 · {Config.location.city}, "
            f"{Config.location.country}<br>"
            f"PV {Config.PV_SYSTEM_CAPACITY_KW} kW · "
            f"Wind {Config.WIND_SYSTEM_CAPACITY_KW} kW</small>",
            unsafe_allow_html=True,
        )
    return refresh


# =============================================================================
# Page header
# =============================================================================

def page_header(
    title:    str,
    subtitle: str,
    accent:   str = "#0ea5e9",
) -> None:
    """Render the top header bar with live clock, tick counter, and WX badge."""
    now = now_zagreb()
    s   = st.session_state.last_state
    tick_n = s.tick if s else "—"
    wx_src = s.wx_source if s else "—"
    src_badge = "badge-green" if wx_src == "live" else "badge-amber"

    st.markdown(f"""
<div class="page-header" style="--accent:{accent}">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
    <div>
      <div style="font-size:19px;font-weight:700;color:{accent};">{title}</div>
      <div style="font-size:12px;color:#64748b;margin-top:2px;">{subtitle}</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span style="font-size:20px;font-weight:700;color:#0f172a;letter-spacing:.05em;">
        {now.strftime('%H:%M:%S')}
      </span>
      <span class="badge badge-cyan">● LIVE</span>
      <span class="badge badge-gray">Tick #{tick_n}</span>
      <span class="badge {src_badge}">WX: {wx_src.upper()}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# Alert display
# =============================================================================

def show_alerts() -> None:
    """Display all active alerts and subsystem maintenance messages."""
    alrt = st.session_state.alerts
    sub  = st.session_state.sub_result

    for a in alrt.errors():
        st.markdown(
            f'<div class="alert-error">🚨 [{a.code}] {a.message}</div>',
            unsafe_allow_html=True)
    for a in alrt.warnings():
        st.markdown(
            f'<div class="alert-warning">⚠ [{a.code}] {a.message}</div>',
            unsafe_allow_html=True)
    if sub:
        for m in sub.get("maintenance", []):
            st.markdown(
                f'<div class="alert-warning">🔧 {m}</div>',
                unsafe_allow_html=True)


# =============================================================================
# Auto-refresh
# =============================================================================

def autorefresh(refresh: int, key: str = "lumi_autorefresh") -> None:
    """
    Trigger a Streamlit rerun every `refresh` seconds.

    Uses streamlit-autorefresh if available, falls back to time.sleep + rerun.
    The sleep fallback blocks the server thread — use autorefresh package in prod.
    """
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=refresh * 1000, key=key)
    except ImportError:
        import time
        time.sleep(refresh)
        st.rerun()
