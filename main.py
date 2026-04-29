# =============================================================================
# main.py — LUMINIH2 Digital Twin · Overview Dashboard
# White Industrial Theme · Voice Welcome · Zagreb, Croatia · v4.1
# =============================================================================

import streamlit as st
import streamlit.components.v1 as components
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
from scenario_engine import ScenarioEngine, ScenarioParams

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
# WHITE THEME CSS — force white on every Streamlit container
# =============================================================================
st.markdown("""
<style>
/* ── Force white background everywhere ── */
html, body { background-color: #ffffff !important; }
.stApp { background-color: #ffffff !important; color: #0f172a !important; }
.stApp > div { background-color: #ffffff !important; }
[data-testid="stAppViewContainer"] { background-color: #ffffff !important; }
[data-testid="stHeader"] { background-color: #ffffff !important; box-shadow: 0 1px 4px rgba(0,0,0,.06) !important; }
[data-testid="stToolbar"] { background-color: #ffffff !important; }
.main { background-color: #ffffff !important; }
.main .block-container { background-color: #ffffff !important; padding: .75rem 1.5rem 1.5rem; }
section[data-testid="stSidebar"] { background-color: #f8fafc !important; border-right: 1px solid #e2e8f0 !important; }
[data-testid="stSidebarContent"] { background-color: #f8fafc !important; }

/* ── Typography ── */
h1, h2, h3, h4, p, span, div, label { color: #0f172a; }
[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 12px !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* ── KPI cards ── */
.kpi {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 13px 15px;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
    transition: box-shadow .2s;
    height: 100%;
}
.kpi:hover { box-shadow: 0 4px 14px rgba(0,0,0,.09); }
.kpi-lbl { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: .07em; font-weight: 600; margin: 0; }
.kpi-val { font-size: 22px; font-weight: 700; margin: 4px 0 2px; }
.kpi-sub { font-size: 11px; color: #94a3b8; margin: 0; }
.kpi-green  { color: #16a34a; }
.kpi-amber  { color: #d97706; }
.kpi-red    { color: #dc2626; }
.kpi-blue   { color: #2563eb; }
.kpi-cyan   { color: #0284c7; }
.kpi-purple { color: #7c3aed; }
.kpi-orange { color: #ea580c; }
.kpi-gray   { color: #64748b; }

/* ── Header card ── */
.page-header {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #0ea5e9;
    border-radius: 10px;
    padding: 14px 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 6px rgba(0,0,0,.05);
}

/* ── Device cards ── */
.device-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 9px;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
    transition: box-shadow .2s;
}
.device-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,.09); }
.device-title { font-size: 14px; font-weight: 600; color: #0f172a; margin: 0 0 2px; }
.device-model { font-size: 11px; color: #64748b; margin: 0 0 8px; }

/* ── Badges ── */
.badge { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.badge-green  { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
.badge-amber  { background: #fef9c3; color: #a16207; border: 1px solid #fde68a; }
.badge-red    { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
.badge-cyan   { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
.badge-purple { background: #ede9fe; color: #7c3aed; border: 1px solid #ddd6fe; }
.badge-blue   { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
.badge-gray   { background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }

/* ── Section header ── */
.sec-hdr {
    font-size: 11px; font-weight: 600; color: #94a3b8;
    text-transform: uppercase; letter-spacing: .08em;
    margin: 14px 0 8px; border-bottom: 1px solid #f1f5f9; padding-bottom: 5px;
}

/* ── EMS log ── */
.ems-log {
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-left: 3px solid #0ea5e9;
    border-radius: 6px;
    padding: 8px 14px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    color: #0369a1;
    min-height: 36px;
    margin: 8px 0;
}

/* ── Alert banners ── */
.alert-error   { background: #fee2e2; border: 1px solid #fecaca; border-radius: 8px; padding: 8px 14px; color: #b91c1c; font-size: 13px; margin: 4px 0; }
.alert-warning { background: #fef9c3; border: 1px solid #fde68a; border-radius: 8px; padding: 8px 14px; color: #92400e; font-size: 13px; margin: 4px 0; }
.alert-info    { background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 8px; padding: 8px 14px; color: #0369a1; font-size: 13px; margin: 4px 0; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { background: #f8fafc; border-bottom: 1px solid #e2e8f0; gap: 4px; }
.stTabs [data-baseweb="tab"] {
    background: #ffffff; color: #475569;
    border-radius: 8px 8px 0 0; padding: 7px 16px;
    border: 1px solid #e2e8f0; border-bottom: none; font-size: 13px; font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: #0ea5e9 !important;
    color: #ffffff !important;
    border-color: #0ea5e9 !important;
}

/* ── Sidebar controls ── */
section[data-testid="stSidebar"] label { color: #374151 !important; font-size: 13px !important; }
section[data-testid="stSidebar"] .stSlider { color: #374151; }
.stToggle > label { color: #374151 !important; }

/* ── Divider ── */
hr { border-color: #e2e8f0 !important; }

/* ── Progress bar ── */
.stProgress > div > div > div { background: #0ea5e9 !important; }

/* ── Buttons ── */
.stButton > button {
    background: #0ea5e9 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}
.stButton > button:hover { background: #0284c7 !important; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# STARTUP VALIDATION
# =============================================================================
try:
    validate_config()
except AssertionError as e:
    st.error(f"Config validation failed: {e}")
    st.stop()

# =============================================================================
# SESSION STATE INIT
# =============================================================================
def _init():
    if "lumi_v41" in st.session_state:
        return
    st.session_state.lumi_v41     = True
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
    st.session_state.voice_played  = False
_init()

# Color palette
C = dict(solar="#f59e0b", wind="#3b82f6", bess="#22c55e", elec="#8b5cf6",
         h2="#0ea5e9", fc="#ef4444", grid="#94a3b8", ev="#60a5fa")
DARK = dict(template="plotly_white", paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc",
            font_color="#0f172a", margin=dict(t=28, b=28, l=44, r=16))
def mk(**kw): return {**DARK, **kw}
def kpi(col, lbl, val, sub="", cls="kpi-cyan"):
    col.markdown(
        f'<div class="kpi"><p class="kpi-lbl">{lbl}</p>'
        f'<p class="kpi-val {cls}">{val}</p>'
        f'<p class="kpi-sub">{sub}</p></div>',
        unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.markdown(
        '<div style="font-size:16px;font-weight:700;color:#0ea5e9;margin-bottom:12px;">'
        '⚡ LUMINIH2 Control</div>',
        unsafe_allow_html=True)
    st.session_state.sim_running = st.toggle(
        "Live simulation", value=st.session_state.sim_running)
    refresh = st.slider("Refresh (sec)", 2, 15, 4)
    st.divider()
    st.markdown("**🌦 Weather Override**")
    use_ov = st.checkbox("Manual override")
    ov = None
    if use_ov:
        ov = {
            "irradiance": st.slider("Irradiance W/m²", 0, 1000, 500),
            "wind_ms":    st.slider("Wind speed m/s", 0.0, 25.0, 6.0, 0.1),
            "temp_c":     st.slider("Temperature °C", -10, 45, 20),
        }
    st.divider()
    st.markdown("**🔋 Load Settings**")
    ev_demand  = st.slider("EV demand (kW)", 0.0, Config.EV_CHARGER_POWER_KW, 2.0, 0.5)
    force_bess = st.checkbox("Force BESS charge from grid")
    st.divider()
    if st.button("🔄 Reset simulation"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.caption(f"v4.1 · {Config.location.city}, {Config.location.country}")
    st.caption(f"PV {Config.PV_SYSTEM_CAPACITY_KW} kW · Wind {Config.WIND_SYSTEM_CAPACITY_KW} kW")

# =============================================================================
# PHYSICS TICK
# =============================================================================
zagreb_tz = timezone(timedelta(hours=2))
now_dt = datetime.now(zagreb_tz)

if st.session_state.sim_running:
    s, fc_res = st.session_state.engine.run(
        override=ov, ev_demand_kw=ev_demand, force_bess_charge=force_bess)
    st.session_state.history.append(s)
    st.session_state.last_state = s
    st.session_state.last_fc    = fc_res
    sub = st.session_state.subsystems.tick(
        h2_kg_h=s.h2_kg_h, elec_power_kw=s.elec_kw,
        ambient_temp_c=s.wx_temp_c, timestep_sec=Config.TIMESTEP_SEC)
    st.session_state.sub_result = sub

s    = st.session_state.last_state
hist = st.session_state.history.df
alrt = st.session_state.alerts
sub  = st.session_state.sub_result

if s is None:
    st.info("Initialising simulation…"); st.stop()

# =============================================================================
# VOICE WELCOME BANNER
# =============================================================================
hour     = now_dt.hour
greet    = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
day_str  = now_dt.strftime("%A")
date_str = now_dt.strftime("%B %d, %Y")
time_str = now_dt.strftime("%H:%M")

# Build alert text for voice
voice_alerts = ""
if alrt.errors():
    voice_alerts += f"{len(alrt.errors())} critical alert{'s' if len(alrt.errors())>1 else ''} require immediate attention. "
elif alrt.warnings():
    voice_alerts += f"{len(alrt.warnings())} warning{'s' if len(alrt.warnings())>1 else ''} detected. "
else:
    voice_alerts += "All systems are nominal. No active alerts. "

# Build forecast hint
fc_hint = ""
if st.session_state.last_fc and hasattr(st.session_state.last_fc, "points"):
    pts = st.session_state.last_fc.points
    if pts:
        peak = max(pts, key=lambda p: p.value)
        fc_hint = f"AI forecast shows peak solar irradiance of {peak.value:.0f} watts per square meter in {peak.hour_offset+1} hours. "

wx_text = ""
if s.wx_source == "live":
    wx_text = (f"Current weather in Zagreb: {s.wx_temp_c:.0f} degrees Celsius. "
               f"Wind speed {s.wx_wind_ms:.1f} meters per second. "
               f"Solar irradiance {s.wx_irradiance:.0f} watts per square meter. ")
else:
    wx_text = f"Weather data: {s.wx_temp_c:.0f} degrees Celsius in Zagreb. "

voice_script = (
    f"{greet}. Welcome to LUMINIH2 Digital Twin. "
    f"Today is {day_str}, {date_str}. The current time in Zagreb is {time_str}. "
    f"{wx_text}"
    f"System briefing: Total generation is {s.total_gen_kw:.1f} kilowatts — "
    f"{s.solar_kw:.1f} from solar and {s.wind_kw:.1f} from wind. "
    f"Battery storage is at {s.bess_soc_pct:.0f} percent state of charge. "
    f"The electrolyzer S30 30 is producing {s.h2_kg_h*1000:.1f} grams of hydrogen per hour. "
    f"Current LCOH is {s.lcoh:.2f} euros per kilogram — "
    f"{'below' if s.is_profitable else 'above'} the target of {Config.LCOH_TARGET_EURO_KG} euros. "
    f"{fc_hint}"
    f"{voice_alerts}"
    f"Total hydrogen produced this session: {s.cum_h2_kg*1000:.1f} grams. "
    f"Carbon dioxide offset: {s.cum_co2_kg:.3f} kilograms. "
    f"Have a productive session."
)

components.html(f"""
<!DOCTYPE html>
<html>
<head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
body{{background:transparent}}
.wc{{
  background:linear-gradient(135deg,#f0f9ff 0%,#f8fafc 60%,#f0fdf4 100%);
  border:1px solid #bae6fd;border-left:4px solid #0ea5e9;
  border-radius:12px;padding:16px 20px;
  display:flex;align-items:center;gap:16px;
  box-shadow:0 2px 12px rgba(14,165,233,.10);
}}
.sb{{
  width:52px;height:52px;border-radius:50%;border:none;cursor:pointer;flex-shrink:0;
  background:linear-gradient(135deg,#0ea5e9,#6366f1);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 14px rgba(14,165,233,.35);transition:all .2s;
}}
.sb:hover{{transform:scale(1.06);box-shadow:0 6px 20px rgba(14,165,233,.45)}}
.sb.speaking{{
  background:linear-gradient(135deg,#22c55e,#0ea5e9);
  animation:pulse 1.2s ease-in-out infinite;
}}
@keyframes pulse{{
  0%,100%{{box-shadow:0 4px 14px rgba(34,197,94,.4)}}
  50%{{box-shadow:0 4px 24px rgba(34,197,94,.75)}}
}}
.wt{{flex:1}}
.wg{{font-size:15px;font-weight:600;color:#0f172a;}}
.wd{{font-size:12px;color:#0369a1;margin-top:3px;font-weight:500;}}
.wm{{font-size:11px;color:#64748b;margin-top:5px;min-height:18px;line-height:1.4;}}
.wr{{display:flex;align-items:center;gap:2px;height:22px;margin-top:7px;}}
.wb{{width:3px;border-radius:2px;background:#0ea5e9;height:3px;transition:height .08s;}}
.rb{{
  background:none;border:1px solid #bae6fd;border-radius:8px;
  padding:4px 12px;font-size:11px;color:#0369a1;cursor:pointer;
  margin-top:8px;transition:all .15s;font-family:inherit;
}}
.rb:hover{{background:#e0f2fe;}}
</style>
</head>
<body>
<div class="wc">
  <button class="sb" id="sb" onclick="go()" title="Play system briefing">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
         stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg>
  </button>
  <div class="wt">
    <div class="wg">{greet} — Welcome to LUMINIH2 Digital Twin</div>
    <div class="wd">{day_str}, {date_str} &nbsp;·&nbsp; Zagreb {time_str}</div>
    <div class="wm" id="wm">Click the speaker for your personalised system briefing</div>
    <div class="wr" id="wr"></div>
    <button class="rb" onclick="go()">🔊 Replay briefing</button>
  </div>
</div>

<script>
const TEXT = `{voice_script.replace("`", "'")}`;
const syn  = window.speechSynthesis;
let spk=false, wi=null, bars=[];

function buildBars(){{
  const r=document.getElementById('wr');
  r.innerHTML=''; bars=[];
  for(let i=0;i<28;i++){{
    const b=document.createElement('div');
    b.className='wb'; r.appendChild(b); bars.push(b);
  }}
}}
function wave(on){{
  if(wi) clearInterval(wi);
  if(!on){{ bars.forEach(b=>b.style.height='3px'); return; }}
  wi=setInterval(()=>{{
    bars.forEach((b,i)=>{{
      const h=Math.round(3+Math.abs(Math.sin(Date.now()/180+i*.45))*18);
      b.style.height=h+'px';
      b.style.background=h>14?'#22c55e':'#0ea5e9';
    }});
  }},55);
}}
function go(){{
  if(!syn){{ alert('Speech not supported in this browser.'); return; }}
  if(spk){{
    syn.cancel(); spk=false;
    document.getElementById('sb').classList.remove('speaking');
    wave(false);
    document.getElementById('wm').textContent='Briefing stopped. Click to replay.';
    return;
  }}
  buildBars();
  document.getElementById('wm').textContent='Playing system briefing…';
  const u=new SpeechSynthesisUtterance(TEXT);
  u.lang='en-GB'; u.rate=0.90; u.pitch=1.0;
  const vs=syn.getVoices();
  const v=vs.find(x=>x.lang==='en-GB'&&x.name.includes('Daniel'))
          ||vs.find(x=>x.lang==='en-GB')
          ||vs.find(x=>x.lang.startsWith('en'));
  if(v) u.voice=v;
  u.onstart=()=>{{
    spk=true;
    document.getElementById('sb').classList.add('speaking');
    wave(true);
  }};
  u.onend=u.onerror=()=>{{
    spk=false;
    document.getElementById('sb').classList.remove('speaking');
    wave(false);
    document.getElementById('wm').textContent='Briefing complete. Click to replay.';
  }};
  syn.cancel();
  syn.speak(u);
}}
// Auto-play once on load
window.addEventListener('load', ()=>{{ setTimeout(go, 600); }});
</script>
</body>
</html>
""", height=130, scrolling=False)

# =============================================================================
# PAGE HEADER
# =============================================================================
st.markdown(f"""
<div class="page-header">
  <div style="display:flex;justify-content:space-between;align-items:center;
    flex-wrap:wrap;gap:10px;">
    <div>
      <div style="font-size:20px;font-weight:700;color:#0ea5e9;">
        ⚡ LUMINIH2 Digital Twin v4.1
      </div>
      <div style="font-size:13px;color:#64748b;margin-top:2px;">
        Integrated Green Hydrogen &amp; E-Mobility Hub · Zagreb, Croatia
      </div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <span style="font-size:22px;font-weight:700;color:#0f172a;
        letter-spacing:.05em;">{now_dt.strftime('%H:%M:%S')}</span>
      <span class="badge badge-green">● ACTIVE</span>
      <span class="badge badge-cyan">Tick #{s.tick}</span>
      <span class="badge {'badge-green' if s.wx_source=='live' else 'badge-amber'}">
        WX: {s.wx_source.upper()}
      </span>
      <span class="badge badge-purple">
        {s.source.split('(')[0].strip()[:16]}
      </span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Alerts
for a in alrt.errors():
    st.markdown(f'<div class="alert-error">🚨 <b>[{a.code}]</b> {a.message}</div>',
                unsafe_allow_html=True)
for a in alrt.warnings():
    st.markdown(f'<div class="alert-warning">⚠ <b>[{a.code}]</b> {a.message}</div>',
                unsafe_allow_html=True)
if sub:
    for m in sub.get("maintenance", []):
        st.markdown(f'<div class="alert-warning">🔧 {m}</div>', unsafe_allow_html=True)

# =============================================================================
# TOP KPI ROW
# =============================================================================
k = st.columns(6)
kpi(k[0], "Total Generation",
    f"{s.total_gen_kw:.1f} kW",
    f"☀ {s.solar_kw:.1f} kW + 💨 {s.wind_kw:.1f} kW", "kpi-amber")
kpi(k[1], "BESS State of Charge",
    f"{s.bess_soc_pct:.1f}%",
    f"SoH {s.bess_soh_pct:.1f}% · {s.bess_temp_c:.1f}°C",
    "kpi-green" if s.bess_soc_pct > 30 else "kpi-red")
kpi(k[2], "H₂ Production",
    f"{s.h2_kg_h*1000:.2f} g/h",
    f"η {s.elec_eff_pct:.1f}% · {s.elec_purity:.3f}% pure", "kpi-cyan")
kpi(k[3], "H₂ Total (session)",
    f"{s.cum_h2_kg:.4f} kg",
    f"CO₂ saved {s.cum_co2_kg:.3f} kg", "kpi-cyan")
kpi(k[4], "LCOH",
    f"€{s.lcoh:.2f}/kg",
    "✅ On target" if s.is_profitable else f"Target €{Config.LCOH_TARGET_EURO_KG}",
    "kpi-green" if s.is_profitable else "kpi-amber")
kpi(k[5], "Session Revenue",
    f"€{s.cum_revenue_eur:.3f}",
    f"Grid €{s.grid_rev_eur:.4f}/tick", "kpi-green")

# EMS log
st.markdown(
    f'<div class="ems-log">⚡ EMS Priority Dispatch → {s.switching_event}</div>',
    unsafe_allow_html=True)

# =============================================================================
# MAIN CONTENT — Sankey + Device Status
# =============================================================================
col_l, col_r = st.columns([3, 2])

with col_l:
    st.markdown('<p class="sec-hdr">Live energy flow</p>', unsafe_allow_html=True)

    sv  = max(0.1, s.solar_kw)
    wv  = max(0.1, s.wind_kw)
    bv  = max(0.1, s.bess_charge_kw)
    ev2 = max(0.1, s.elec_kw)
    evv = max(0.1, s.ev_kw)
    gv  = max(0.1, s.grid_export_kw)
    h2v = max(0.1, s.h2_kg_h * 80)

    fig_sk = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=["Solar PV\n15 kW", "Wind\n10 kW", "BESS\n100 kWh",
                   "Electrolyzer\nS30/30", "H₂ Tank\nTH540-50",
                   "HRS 5 kg", "EV Charger", "Grid Export"],
            color=[C["solar"], C["wind"], C["bess"], C["elec"],
                   C["h2"], "#f97316", C["ev"], C["grid"]],
            pad=20, thickness=18,
            line=dict(color="#e2e8f0", width=0.5),
        ),
        link=dict(
            source=[0, 1, 0, 1, 2, 3, 4, 4],
            target=[2, 2, 3, 3, 3, 4, 5, 6],
            value=[sv*0.4, wv*0.4, sv*0.6, wv*0.6,
                   bv*0.2, ev2, h2v, evv],
            color=["rgba(245,158,11,.25)", "rgba(59,130,246,.25)",
                   "rgba(245,158,11,.25)", "rgba(59,130,246,.25)",
                   "rgba(34,197,94,.2)", "rgba(139,92,246,.25)",
                   "rgba(14,165,233,.25)", "rgba(148,163,184,.2)"],
        ),
    ))
    fig_sk.update_layout(
        template="plotly_white", paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff", font_color="#0f172a",
        height=360, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig_sk, use_container_width=True)

    # Generation trend
    st.markdown('<p class="sec-hdr">Generation trend</p>', unsafe_allow_html=True)
    if len(hist) > 2:
        fg = go.Figure()
        fg.add_trace(go.Scatter(
            x=hist["time"], y=hist["solar_kw"],
            fill="tozeroy", fillcolor="rgba(245,158,11,.12)",
            line=dict(color=C["solar"], width=2), name="Solar kW"))
        fg.add_trace(go.Scatter(
            x=hist["time"], y=hist["wind_kw"],
            fill="tozeroy", fillcolor="rgba(59,130,246,.12)",
            line=dict(color=C["wind"], width=2), name="Wind kW"))
        fg.update_layout(**mk(height=180,
            yaxis_title="kW",
            legend=dict(orientation="h", y=1.1, font_size=11)))
        st.plotly_chart(fg, use_container_width=True)

with col_r:
    st.markdown('<p class="sec-hdr">Device status</p>', unsafe_allow_html=True)

    devices = [
        ("☀", "Solar PV System", f"42 × 360W · {Config.PV_SYSTEM_CAPACITY_KW} kW",
         f"{s.solar_kw:.1f} kW",
         "green" if s.solar_kw > 0.5 else "gray",
         "PRODUCING" if s.solar_kw > 0.5 else "NIGHT/STANDBY",
         C["solar"]),
        ("💨", "Wind Turbine", "10 kW HAWT · Hub 30m",
         f"{s.wind_kw:.1f} kW",
         "green" if s.wind_kw > 0.3 else "gray",
         s.wind_regime.replace("_"," ").upper(),
         C["wind"]),
        ("🔋", "BESS", "100 kWh LFP · SoC 10–90%",
         f"SoC {s.bess_soc_pct:.1f}% · {s.bess_temp_c:.1f}°C",
         "green" if s.bess_soc_pct > 30 else "red",
         "CHARGING" if s.bess_charge_kw > 0.1 else "IDLE",
         C["bess"]),
        ("⚗", "Electrolyzer S30/30", "ITM Power PEM · 0.74–5.63 kW",
         f"{s.h2_kg_h*1000:.2f} g/h H₂",
         "cyan" if s.elec_kw >= Config.ELEC_P_MIN_KW else "gray",
         f"LOAD {s.elec_kw:.2f} kW" if s.elec_kw >= Config.ELEC_P_MIN_KW else "STANDBY",
         C["elec"]),
        ("🏗", "H₂ Storage TH540-50", "10.8 kg · NWP 500 bar",
         f"{s.main_tank_pct:.1f}% · {s.pressure_bar:.0f} bar",
         "cyan" if s.main_tank_pct > 10 else "amber",
         "COMP ON" if s.compressor_on else "PASSIVE",
         C["h2"]),
        ("⚡", "Fuel Cell AIRCELL 3000", "3 kW nom · 0.066 kg H₂/kWh",
         f"{s.fc_kw:.3f} kW out",
         "green" if s.fc_kw > 0.05 else "gray",
         "GENERATING" if s.fc_kw > 0.05 else "STANDBY",
         "#ef4444"),
    ]

    for icon, name, model, value, bk, status, color in devices:
        st.markdown(f"""
<div class="device-card" style="border-left:3px solid {color}">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div class="device-title">{icon} {name}</div>
      <div class="device-model">{model}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:14px;font-weight:700;color:{color};margin-bottom:3px">{value}</div>
      <span class="badge badge-{bk}">{status}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# =============================================================================
# BOTTOM ROW — H₂ + BESS + AI Forecast
# =============================================================================
st.divider()
b1, b2, b3 = st.columns(3)

with b1:
    st.markdown('<p class="sec-hdr">H₂ production history</p>', unsafe_allow_html=True)
    if len(hist) > 2 and "h2_kg_h" in hist.columns:
        fh = go.Figure()
        fh.add_trace(go.Bar(
            x=hist["time"],
            y=(hist["h2_kg_h"] * 1000).round(3),
            marker_color=C["h2"], marker_line_width=0, name="g/h"))
        fh.add_hline(
            y=Config.electrolyzer.h2_nom_kg_h * 1000,
            line_dash="dash", line_color=C["elec"],
            annotation_text="Nominal",
            annotation_font_color=C["elec"])
        fh.update_layout(**mk(height=200, yaxis_title="g H₂/h"))
        st.plotly_chart(fh, use_container_width=True)

with b2:
    st.markdown('<p class="sec-hdr">BESS SoC & temperature</p>', unsafe_allow_html=True)
    if len(hist) > 2 and "bess_soc_pct" in hist.columns:
        fb = go.Figure()
        fb.add_trace(go.Scatter(
            x=hist["time"], y=hist["bess_soc_pct"],
            line=dict(color=C["bess"], width=2), name="SoC %",
            fill="tozeroy", fillcolor="rgba(34,197,94,.08)"))
        fb.add_trace(go.Scatter(
            x=hist["time"], y=hist["bess_temp_c"],
            line=dict(color=C["fc"], width=1.5, dash="dot"),
            name="Temp °C", yaxis="y2"))
        fb.add_hline(y=Config.BATT_SOC_MIN*100, line_dash="dash",
                     line_color="#dc2626", line_width=1,
                     annotation_text="Min SoC")
        fb.update_layout(**mk(height=200,
            yaxis=dict(title="SoC %", color=C["bess"]),
            yaxis2=dict(title="°C", overlaying="y", side="right",
                        color=C["fc"]),
            legend=dict(orientation="h", y=1.1, font_size=10)))
        st.plotly_chart(fb, use_container_width=True)

with b3:
    st.markdown('<p class="sec-hdr">AI solar forecast — 6 h</p>', unsafe_allow_html=True)
    fc = st.session_state.last_fc
    if fc and hasattr(fc, "points") and fc.points:
        fdf = pd.DataFrame({
            "h":  [f"+{p.hour_offset+1}h" for p in fc.points],
            "v":  [p.value for p in fc.points],
            "lo": [p.lower_bound for p in fc.points],
            "hi": [p.upper_bound for p in fc.points],
        })
        f3 = go.Figure()
        f3.add_trace(go.Scatter(x=fdf["h"], y=fdf["hi"],
            line=dict(width=0), showlegend=False))
        f3.add_trace(go.Scatter(x=fdf["h"], y=fdf["lo"],
            fill="tonexty", fillcolor="rgba(14,165,233,.10)",
            line=dict(width=0), name="Confidence"))
        f3.add_trace(go.Scatter(x=fdf["h"], y=fdf["v"],
            line=dict(color=C["h2"], width=2.5),
            mode="lines+markers",
            marker=dict(size=6, color=C["h2"]),
            name="Forecast W/m²"))
        f3.update_layout(**mk(height=200, yaxis_title="W/m²",
            legend=dict(orientation="h", y=1.1, font_size=10)))
        st.plotly_chart(f3, use_container_width=True)
    else:
        st.info("Accumulating data for AI training…")

# =============================================================================
# QUICK STATS FOOTER
# =============================================================================
st.divider()
st.markdown('<p class="sec-hdr">Session summary</p>', unsafe_allow_html=True)
fc_cols = st.columns(6)
fc_cols[0].metric("Water consumed",   f"{s.cum_water_l:.2f} L")
fc_cols[1].metric("O₂ produced",      f"{sub['oxygen'].o2_flow_nm3_h:.4f} Nm³/h" if sub else "—")
fc_cols[2].metric("Stack temp",       f"{sub['warmup'].current_temp_c:.1f}°C" if sub else "—")
fc_cols[3].metric("H₂ purity",        f"{s.elec_purity:.4f}%")
fc_cols[4].metric("Grid independence", f"{s.grid_import_kw:.2f} kW import")
fc_cols[5].metric("CO₂ credits",      f"€{(s.cum_co2_kg/1000)*Config.CARBON_TAX_EUR_TON:.4f}")

# =============================================================================
# AUTO-REFRESH
# =============================================================================
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh * 1000, key="main_r")
except ImportError:
    import time; time.sleep(refresh); st.rerun()
