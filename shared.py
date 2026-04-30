# =============================================================================
# shared.py — LUMINIH2 Shared Resources
# White theme · Session state · KPI helpers
# =============================================================================

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

# =============================================================================
# COLORS & TEMPLATE
# =============================================================================
C = dict(
    solar="#f59e0b", wind="#3b82f6", bess="#22c55e", elec="#8b5cf6",
    h2="#0ea5e9", fc="#ef4444", grid="#94a3b8", ev="#60a5fa",
    co2="#22c55e", water="#3b82f6", o2="#f59e0b",
)

PLOT = dict(
    template="plotly_white",
    paper_bgcolor="#ffffff",
    plot_bgcolor="#f8fafc",
    font_color="#0f172a",
    margin=dict(t=28, b=28, l=44, r=16),
)

def mk(**kw):
    return {**PLOT, **kw}

# =============================================================================
# WHITE THEME CSS
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
section[data-testid="stSidebar"]{background:#f8fafc !important;border-right:1px solid #e2e8f0 !important}
[data-testid="stSidebarContent"]{background:#f8fafc !important}

.page-header{background:#ffffff;border:1px solid #e2e8f0;border-left:4px solid var(--accent,#0ea5e9);
  border-radius:8px;padding:14px 20px;margin-bottom:16px;box-shadow:0 1px 6px rgba(0,0,0,.05)}

.kpi{background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:12px 16px;
  height:100%;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.kpi-lbl{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin:0;font-weight:500}
.kpi-val{font-size:22px;font-weight:700;margin:3px 0 2px}
.kpi-sub{font-size:11px;color:#94a3b8;margin:0}
.kpi-green{color:#16a34a}.kpi-amber{color:#d97706}.kpi-red{color:#dc2626}
.kpi-blue{color:#2563eb}.kpi-cyan{color:#0284c7}.kpi-purple{color:#7c3aed}

.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:#dcfce7;color:#15803d;border:1px solid #bbf7d0}
.badge-amber{background:#fef9c3;color:#a16207;border:1px solid #fde68a}
.badge-red{background:#fee2e2;color:#b91c1c;border:1px solid #fecaca}
.badge-cyan{background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd}
.badge-purple{background:#ede9fe;color:#7c3aed;border:1px solid #ddd6fe}
.badge-gray{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0}

.switch-log{background:#f0f9ff;border:1px solid #bae6fd;border-left:3px solid #0ea5e9;
  border-radius:6px;padding:8px 14px;font-family:'Courier New',monospace;
  font-size:12px;color:#0369a1;min-height:36px;margin:8px 0}

.sec-hdr{font-size:12px;font-weight:600;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.08em;margin:14px 0 8px;border-bottom:1px solid #f1f5f9;padding-bottom:5px}

.stTabs [data-baseweb="tab-list"]{background:#f8fafc;border-bottom:1px solid #e2e8f0;gap:4px}
.stTabs [data-baseweb="tab"]{background:#ffffff;color:#475569;border-radius:6px 6px 0 0;
  padding:7px 14px;border:1px solid #e2e8f0;border-bottom:none;font-size:13px;font-weight:500}
.stTabs [aria-selected="true"]{background:#0ea5e9 !important;color:#ffffff !important;border-color:#0ea5e9 !important}

.alert-error{background:#fee2e2;border:1px solid #fecaca;border-radius:6px;
  padding:8px 14px;color:#b91c1c;font-size:13px;margin:4px 0}
.alert-warning{background:#fef9c3;border:1px solid #fde68a;border-radius:6px;
  padding:8px 14px;color:#92400e;font-size:13px;margin:4px 0}
.alert-info{background:#e0f2fe;border:1px solid #bae6fd;border-radius:6px;
  padding:8px 14px;color:#0369a1;font-size:13px;margin:4px 0}

.health-row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f1f5f9}
[data-testid="stMetricValue"]{color:#0f172a !important}
.stProgress>div>div>div{background:#0ea5e9 !important}
.stButton>button{background:#0ea5e9 !important;color:#ffffff !important;
  border:none !important;border-radius:8px !important;font-weight:500 !important}
.stButton>button:hover{background:#0284c7 !important}
</style>
"""

def inject_css():
    st.markdown(WHITE_CSS, unsafe_allow_html=True)

# =============================================================================
# KPI HELPERS
# =============================================================================
def kpi(col, lbl, val, sub_="", cls="kpi-cyan"):
    col.markdown(
        f'<div class="kpi"><p class="kpi-lbl">{lbl}</p>'
        f'<p class="kpi-val {cls}">{val}</p>'
        f'<p class="kpi-sub">{sub_}</p></div>',
        unsafe_allow_html=True,
    )

def sec(title):
    st.markdown(f'<p class="sec-hdr">{title}</p>', unsafe_allow_html=True)

def badge(text, kind="cyan"):
    return f'<span class="badge badge-{kind}">{text}</span>'

def alert_box(text, kind="info"):
    st.markdown(f'<div class="alert-{kind}">{text}</div>', unsafe_allow_html=True)

def hd(hist, col=None):
    if len(hist) < 2:
        return False
    if col:
        return col in hist.columns and hist[col].notna().any()
    return True

def now_zagreb():
    return datetime.now(timezone(timedelta(hours=2)))

# =============================================================================
# SESSION STATE INIT
# =============================================================================
def init_session():
    if "lumi_init" in st.session_state:
        return
    st.session_state.lumi_init    = True
    validate_config()
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
    st.session_state.sub_result    = None
    st.session_state.annual_report = None
    st.session_state.opt_result    = None
    st.session_state.ev_demand     = 2.0
    st.session_state.force_bess    = False
    st.session_state.wx_override   = None
    st.session_state.sc_h2_price   = 6.0
    st.session_state.sc_capex      = 250000
    st.session_state.sc_opex       = 8000
    st.session_state.sc_elec_mode  = "h2_max"

def run_tick():
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
    sub = st.session_state.subsystems.tick(
        h2_kg_h=s.h2_kg_h,
        elec_power_kw=s.elec_kw,
        ambient_temp_c=s.wx_temp_c,
        timestep_sec=Config.TIMESTEP_SEC,
    )
    st.session_state.sub_result = sub

def sidebar_controls():
    with st.sidebar:
        st.markdown(
            '<div style="font-size:15px;font-weight:700;color:#0ea5e9;margin-bottom:10px;">'
            '⚡ LUMINIH2</div>', unsafe_allow_html=True)
        st.session_state.sim_running = st.toggle(
            "Live simulation", value=st.session_state.get("sim_running", True))
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
        st.session_state.force_bess = st.checkbox("Force BESS charge")

        st.divider()
        st.markdown("**📈 Scenario**")
        st.session_state.sc_h2_price  = st.slider("H₂ price (€/kg)", 3.0, 12.0, 6.0, 0.5)
        st.session_state.sc_capex     = st.number_input("CAPEX (€)", value=250000, step=10000)
        st.session_state.sc_opex      = st.number_input("OPEX/yr (€)", value=8000, step=500)
        st.session_state.sc_elec_mode = st.selectbox("EMS mode", ["h2_max", "lcoh_opt", "grid_first"])

        st.divider()
        if st.button("🔄 Reset"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        st.caption(f"v4.1 · {Config.location.city}")
        st.caption(f"PV {Config.PV_SYSTEM_CAPACITY_KW} kW · Wind {Config.WIND_SYSTEM_CAPACITY_KW} kW")
    return refresh

def page_header(title, subtitle, accent="#0ea5e9"):
    now = now_zagreb()
    s   = st.session_state.last_state
    tick_n = s.tick if s else "—"
    wx_src = s.wx_source if s else "—"
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
      <span class="badge {'badge-green' if wx_src=='live' else 'badge-amber'}">
        WX:{wx_src.upper()}
      </span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

def show_alerts():
    alrt = st.session_state.alerts
    sub  = st.session_state.sub_result
    for a in alrt.errors():
        st.markdown(f'<div class="alert-error">🚨 [{a.code}] {a.message}</div>',
                    unsafe_allow_html=True)
    for a in alrt.warnings():
        st.markdown(f'<div class="alert-warning">⚠ [{a.code}] {a.message}</div>',
                    unsafe_allow_html=True)
    if sub:
        for m in sub.get("maintenance", []):
            st.markdown(f'<div class="alert-warning">🔧 {m}</div>', unsafe_allow_html=True)

def autorefresh(refresh, key):
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=refresh * 1000, key=key)
    except ImportError:
        import time
        time.sleep(refresh)
        st.rerun()
