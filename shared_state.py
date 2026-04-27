# =============================================================================
# shared_state.py — LUMINIH2 Shared State & Styling
# Common CSS, color palette, and session state initialization
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
from subsystems import SubsystemManager
from optimizer import EconomicOptimizer
from scenario_engine import ScenarioEngine

# =============================================================================
# COLOR PALETTE
# =============================================================================
C = dict(
    solar="#FFB347", wind="#58a6ff", bess="#3fb950",
    elec="#bc8cff", h2="#00d4ff", fc="#ff7b72",
    grid="#8b949e", ev="#79c0ff", co2="#3fb950",
    water="#58a6ff", o2="#d29922", heat="#ff7b72",
)

DARK = dict(
    template="plotly_dark",
    paper_bgcolor="#161b22",
    plot_bgcolor="#0d1117",
    font_color="#e6edf3",
    margin=dict(t=28, b=28, l=44, r=16),
)

def mk(**kw):
    return {**DARK, **kw}

# =============================================================================
# CSS — injected on every page
# =============================================================================
CSS = """
<style>
/* ── Base: White / Light Industrial ── */
.stApp{background:#ffffff !important;color:#0f172a}
.block-container{background:#ffffff;padding:.6rem 1.5rem 1rem}

/* Header */
.page-header{background:#ffffff;border:1px solid #e2e8f0;
  border-left:4px solid var(--accent,#0ea5e9);border-radius:10px;
  padding:14px 20px;margin-bottom:16px;
  box-shadow:0 1px 6px rgba(0,0,0,.06)}

/* KPI cards */
.kpi{background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;
  padding:12px 16px;height:100%;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.kpi-lbl{font-size:11px;color:#64748b;text-transform:uppercase;
  letter-spacing:.06em;margin:0;font-weight:500}
.kpi-val{font-size:22px;font-weight:700;margin:4px 0 2px}
.kpi-sub{font-size:11px;color:#94a3b8;margin:0}
.kpi-green{color:#16a34a}.kpi-amber{color:#d97706}.kpi-red{color:#dc2626}
.kpi-blue{color:#2563eb}.kpi-cyan{color:#0284c7}.kpi-purple{color:#7c3aed}
.kpi-orange{color:#ea580c}.kpi-gray{color:#64748b}

/* Device card */
.device-card{background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;
  padding:14px 18px;margin-bottom:10px;
  box-shadow:0 1px 4px rgba(0,0,0,.04);transition:box-shadow .2s}
.device-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.09)}
.device-title{font-size:15px;font-weight:600;color:#0f172a;margin:0 0 2px}
.device-model{font-size:12px;color:#64748b;margin:0 0 10px}

/* Badges */
.badge{display:inline-block;padding:2px 9px;border-radius:20px;
  font-size:11px;font-weight:600}
.badge-green{background:#dcfce7;color:#15803d;border:1px solid #bbf7d0}
.badge-amber{background:#fef9c3;color:#a16207;border:1px solid #fde68a}
.badge-red{background:#fee2e2;color:#b91c1c;border:1px solid #fecaca}
.badge-cyan{background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd}
.badge-purple{background:#ede9fe;color:#7c3aed;border:1px solid #ddd6fe}
.badge-blue{background:#dbeafe;color:#1d4ed8;border:1px solid #bfdbfe}
.badge-gray{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0}

/* Section header */
.sec-hdr{font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.08em;margin:14px 0 8px;
  border-bottom:1px solid #f1f5f9;padding-bottom:5px}

/* EMS log */
.ems-log{background:#f8fafc;border:1px solid #e2e8f0;
  border-left:3px solid #0ea5e9;border-radius:6px;
  padding:8px 14px;font-family:'Courier New',monospace;
  font-size:12px;color:#0369a1;min-height:36px;margin:8px 0}

/* Alert banners */
.alert-error{background:#fee2e2;border:1px solid #fecaca;border-radius:8px;
  padding:8px 14px;color:#b91c1c;font-size:13px;margin:4px 0}
.alert-warning{background:#fef9c3;border:1px solid #fde68a;border-radius:8px;
  padding:8px 14px;color:#92400e;font-size:13px;margin:4px 0}
.alert-info{background:#e0f2fe;border:1px solid #bae6fd;border-radius:8px;
  padding:8px 14px;color:#0369a1;font-size:13px;margin:4px 0}

/* Health row */
.health-row{display:flex;justify-content:space-between;
  padding:7px 0;border-bottom:1px solid #f1f5f9}

/* Stat grid */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.stat-item{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
  padding:8px 12px}
.stat-lbl{font-size:10px;color:#64748b;text-transform:uppercase;margin:0;font-weight:500}
.stat-val{font-size:16px;font-weight:600;color:#0f172a;margin:2px 0 0}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{background:#f8fafc;
  border-bottom:1px solid #e2e8f0;gap:4px}
.stTabs [data-baseweb="tab"]{background:#ffffff;color:#475569;
  border-radius:8px 8px 0 0;padding:7px 14px;
  border:1px solid #e2e8f0;border-bottom:none;font-size:13px;font-weight:500}
.stTabs [aria-selected="true"]{background:#0ea5e9 !important;
  color:#ffffff !important;border-color:#0ea5e9 !important}

/* Sidebar */
section[data-testid="stSidebar"]{background:#f8fafc !important;
  border-right:1px solid #e2e8f0}

/* Progress */
.stProgress>div>div>div{background:#0ea5e9 !important}

/* Metric */
[data-testid="stMetricValue"]{color:#0f172a !important}
</style>
"""

def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
# KPI helper
# =============================================================================
def kpi(col, lbl: str, val: str, sub: str = "", cls: str = "kpi-cyan"):
    col.markdown(
        f'<div class="kpi">'
        f'<p class="kpi-lbl">{lbl}</p>'
        f'<p class="kpi-val {cls}">{val}</p>'
        f'<p class="kpi-sub">{sub}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "cyan") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def alert(text: str, kind: str = "info"):
    st.markdown(f'<div class="alert-{kind}">{text}</div>', unsafe_allow_html=True)


def sec(title: str):
    st.markdown(f'<p class="sec-hdr">{title}</p>', unsafe_allow_html=True)


# =============================================================================
# SESSION STATE INIT
# =============================================================================
def init_session():
    if "lumi_shared" in st.session_state:
        return
    st.session_state.lumi_shared  = True
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


def run_tick():
    """Run one physics tick — call from any page."""
    if not st.session_state.sim_running:
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


def sidebar_controls(refresh_default: int = 4) -> int:
    """Render standard sidebar controls, return refresh interval."""
    with st.sidebar:
        st.markdown(
            '<div style="font-size:16px;font-weight:700;color:#00d4ff;'
            'margin-bottom:12px;">⚡ LUMINIH2</div>',
            unsafe_allow_html=True,
        )
        st.session_state.sim_running = st.toggle(
            "Live simulation", value=st.session_state.sim_running)
        refresh = st.slider("Refresh (s)", 2, 15, refresh_default)
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
        st.markdown("**🔋 Load**")
        st.session_state.ev_demand  = st.slider(
            "EV demand (kW)", 0.0, Config.EV_CHARGER_POWER_KW, 2.0, 0.5)
        st.session_state.force_bess = st.checkbox("Force BESS charge")

        st.divider()
        if st.button("🔄 Reset"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        st.caption(f"v4.1 · {Config.location.city}")
        st.caption(f"PV {Config.PV_SYSTEM_CAPACITY_KW} kW · "
                   f"Wind {Config.WIND_SYSTEM_CAPACITY_KW} kW")
    return refresh


def get_state():
    return st.session_state.last_state

def get_hist():
    return st.session_state.history.df

def get_sub():
    return st.session_state.sub_result

def get_alrt():
    return st.session_state.alerts

def now_zagreb() -> datetime:
    return datetime.now(timezone(timedelta(hours=2)))

# =============================================================================
# VOICE WELCOME — inject into any page
# =============================================================================
def inject_voice_welcome():
    """
    Injects an animated white-theme welcome banner with Web Speech API.
    Call once at the top of main.py after inject_css().
    """
    import pytz
    from datetime import datetime as dt_cls
    now = dt_cls.now(pytz.timezone("Europe/Zagreb"))
    day   = now.strftime("%A")
    date  = now.strftime("%B %d, %Y")
    time_ = now.strftime("%H:%M")
    hour  = now.hour
    greet = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")

    st.components.v1.html(f"""
<!DOCTYPE html>
<html>
<head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
body{{background:transparent}}
.wc{{background:linear-gradient(135deg,#f0f9ff,#f8fafc,#f0fdf4);
  border:1px solid #bae6fd;border-left:4px solid #0ea5e9;
  border-radius:12px;padding:16px 20px;display:flex;align-items:center;gap:16px;
  box-shadow:0 2px 12px rgba(14,165,233,.10);margin-bottom:4px}}
.sb{{width:48px;height:48px;border-radius:50%;border:none;cursor:pointer;flex-shrink:0;
  background:linear-gradient(135deg,#0ea5e9,#6366f1);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 12px rgba(14,165,233,.35);transition:all .2s}}
.sb:hover{{transform:scale(1.06)}}
.sb.sp{{background:linear-gradient(135deg,#22c55e,#0ea5e9);
  animation:pulse 1.2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{box-shadow:0 4px 12px rgba(34,197,94,.4)}}
  50%{{box-shadow:0 4px 22px rgba(34,197,94,.7)}}}}
.wt{{flex:1}}
.wg{{font-size:15px;font-weight:600;color:#0f172a}}
.wd{{font-size:12px;color:#0369a1;margin-top:3px;font-weight:500}}
.wm{{font-size:11px;color:#64748b;margin-top:5px;min-height:18px}}
.wr{{display:flex;align-items:center;gap:2px;height:20px;margin-top:6px}}
.wb{{width:3px;border-radius:2px;background:#0ea5e9;height:3px}}
</style>
</head>
<body>
<div class="wc">
  <button class="sb" id="sb" onclick="go()" title="Play welcome briefing">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff"
         stroke-width="2.2" stroke-linecap="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg>
  </button>
  <div class="wt">
    <div class="wg">{greet} — Welcome to LUMINIH2 Digital Twin</div>
    <div class="wd">{day}, {date} · Zagreb {time_}</div>
    <div class="wm" id="wm">Click the speaker for your system briefing</div>
    <div class="wr" id="wr"></div>
  </div>
</div>
<script>
let spk=false, wi=null, bars=[];
const syn=window.speechSynthesis;

function buildBars(){{
  const r=document.getElementById('wr'); r.innerHTML=''; bars=[];
  for(let i=0;i<26;i++){{
    const b=document.createElement('div'); b.className='wb';
    r.appendChild(b); bars.push(b);
  }}
}}
function wave(on){{
  if(wi) clearInterval(wi);
  if(!on){{ bars.forEach(b=>b.style.height='3px'); return; }}
  wi=setInterval(()=>{{
    bars.forEach((b,i)=>{{
      const h=Math.round(3+Math.abs(Math.sin(Date.now()/180+i*.45))*16);
      b.style.height=h+'px';
      b.style.background=h>12?'#22c55e':'#0ea5e9';
    }});
  }},55);
}}
function go(){{
  if(!syn) return;
  if(spk){{ syn.cancel(); spk=false;
    document.getElementById('sb').classList.remove('sp');
    wave(false); document.getElementById('wm').textContent='Briefing stopped.'; return; }}
  buildBars();
  const text=`{greet}. Welcome to LUMINIH2 Digital Twin. `+
    `Today is {day}, {date}. The time in Zagreb is {time_}. `+
    `The system is active. All devices are online. `+
    `Solar capacity is 15 kilowatts with 42 panels. Wind turbine rated at 10 kilowatts. `+
    `Electrolyzer S30 30 is ready. Battery storage is at 55 percent. `+
    `Have a productive session.`;
  document.getElementById('wm').textContent='Playing briefing…';
  const u=new SpeechSynthesisUtterance(text);
  u.lang='en-GB'; u.rate=0.90; u.pitch=1.0;
  const vs=syn.getVoices();
  const v=vs.find(x=>x.lang==='en-GB')||vs.find(x=>x.lang.startsWith('en'));
  if(v) u.voice=v;
  u.onstart=()=>{{spk=true;document.getElementById('sb').classList.add('sp');wave(true);}};
  u.onend=u.onerror=()=>{{spk=false;document.getElementById('sb').classList.remove('sp');
    wave(false);document.getElementById('wm').textContent='Briefing complete. Click to replay.';}};
  syn.cancel(); syn.speak(u);
}}
setTimeout(go, 800);
</script>
</body>
</html>
""", height=110, scrolling=False)
