# =============================================================================
# main.py — LUMINIH2 Digital Twin Dashboard v4.0
# Dark Industrial Theme · Zagreb, Croatia
# =============================================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np
import pytz

from config import Config, validate_config
from energy_assets import SolarSystem, WindSystem, BatteryBESS
from hydrogen_assets import ElectrolyzerS30, HydrogenStorageChain, FuelCellAircell
from ems_brain import EMSBrain
from ai_forecaster import AIPredictor
from weather_api import WeatherProvider
from core_engine import TickEngine, LCOHAccumulator, AlertSystem, HistoryBuffer

st.set_page_config(page_title="LUMINIH2 Digital Twin", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp{background:#0d1117;color:#e6edf3}
.block-container{padding:.75rem 1.5rem 1rem}
.lumi-header{background:#161b22;border:1px solid #30363d;border-left:4px solid #00d4ff;border-radius:8px;padding:14px 20px;margin-bottom:16px}
.kpi{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 16px}
.kpi-lbl{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.06em;margin:0}
.kpi-val{font-size:24px;font-weight:600;margin:3px 0 2px}
.kpi-sub{font-size:11px;color:#8b949e;margin:0}
.kpi-green{color:#3fb950}.kpi-amber{color:#d29922}.kpi-red{color:#f85149}.kpi-blue{color:#58a6ff}.kpi-cyan{color:#00d4ff}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:#0d2c18;color:#3fb950;border:1px solid #1a4d2e}
.badge-amber{background:#2d1f00;color:#d29922;border:1px solid #5a3e00}
.badge-red{background:#2d0e0e;color:#f85149;border:1px solid #5a1e1e}
.badge-cyan{background:#001a22;color:#00d4ff;border:1px solid #004466}
.switch-log{background:#0d1117;border:1px solid #30363d;border-left:3px solid #00d4ff;border-radius:6px;padding:8px 14px;font-family:'Courier New',monospace;font-size:12px;color:#79c0ff;min-height:36px;margin:8px 0}
.sec-hdr{font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.08em;margin:14px 0 8px;border-bottom:1px solid #21262d;padding-bottom:5px}
.stTabs [data-baseweb="tab-list"]{background:#161b22;border-bottom:1px solid #30363d;gap:4px}
.stTabs [data-baseweb="tab"]{background:#0d1117;color:#8b949e;border-radius:6px 6px 0 0;padding:7px 16px;border:1px solid #30363d;border-bottom:none}
.stTabs [aria-selected="true"]{background:#161b22 !important;color:#00d4ff !important;border-color:#00d4ff !important}
section[data-testid="stSidebar"]{background:#0d1117;border-right:1px solid #30363d}
.alert-error{background:#2d0e0e;border:1px solid #f85149;border-radius:6px;padding:8px 14px;color:#f85149;font-size:13px;margin:4px 0}
.alert-warning{background:#2d1f00;border:1px solid #d29922;border-radius:6px;padding:8px 14px;color:#d29922;font-size:13px;margin:4px 0}
.alert-info{background:#001a22;border:1px solid #00d4ff;border-radius:6px;padding:8px 14px;color:#00d4ff;font-size:13px;margin:4px 0}
</style>
""", unsafe_allow_html=True)

DARK = dict(template="plotly_dark", paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
            font_color="#e6edf3", margin=dict(t=28,b=28,l=40,r=20))
C = dict(solar="#FFB347", wind="#58a6ff", bess="#3fb950", elec="#bc8cff",
         h2="#00d4ff", fc="#ff7b72", grid="#8b949e", ev="#79c0ff")
def mk(**kw): return {**DARK, **kw}

try:
    validate_config()
except AssertionError as e:
    st.error(f"Config error: {e}"); st.stop()

def _init():
    if "lumi_init" in st.session_state: return
    st.session_state.lumi_init    = True
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
    st.session_state.engine       = TickEngine(
        Config, st.session_state.solar, st.session_state.wind,
        st.session_state.bess, st.session_state.electrolyzer,
        st.session_state.h2_chain, st.session_state.fuel_cell,
        st.session_state.ems, st.session_state.forecaster,
        st.session_state.weather, st.session_state.lcoh_acc,
        st.session_state.alerts)
    st.session_state.sim_running  = True
    st.session_state.last_state   = None
    st.session_state.last_fc      = None
_init()

with st.sidebar:
    st.markdown("### ⚡ LUMINIH2 Control")
    st.session_state.sim_running = st.toggle("Live simulation", value=st.session_state.sim_running)
    refresh = st.slider("Refresh (sec)", 2, 15, 4)
    st.divider()
    st.markdown("### 🌦 Weather Override")
    use_ov = st.checkbox("Manual override")
    ov = None
    if use_ov:
        ov = {"irradiance": st.slider("Irradiance W/m²", 0, 1000, 500),
              "wind_ms":    st.slider("Wind m/s", 0.0, 25.0, 6.0, 0.1),
              "temp_c":     st.slider("Temp °C", -10, 45, 20)}
    st.divider()
    st.markdown("### 🔋 EV & Grid")
    ev_demand   = st.slider("EV demand (kW)", 0.0, Config.EV_CHARGER_POWER_KW, 10.0, 0.5)
    force_bess  = st.checkbox("Force BESS charge from grid")
    st.divider()
    if st.button("🔄 Reset"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()
    st.caption(f"v4.0 · {Config.location.city}")

if st.session_state.sim_running:
    s, fc_res = st.session_state.engine.run(override=ov, ev_demand_kw=ev_demand,
                                             force_bess_charge=force_bess)
    st.session_state.history.append(s)
    st.session_state.last_state = s
    st.session_state.last_fc    = fc_res

s    = st.session_state.last_state
hist = st.session_state.history.df
alrt = st.session_state.alerts

if s is None:
    st.info("Starting…"); st.stop()

now_s = datetime.now(pytz.timezone("Europe/Zagreb")).strftime("%H:%M:%S")

st.markdown(f"""
<div class="lumi-header">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
    <div><span style="font-size:20px;font-weight:700;color:#00d4ff;">⚡ LUMINIH2</span>
    <span style="font-size:13px;color:#8b949e;margin-left:10px;">Digital Twin v4.0 · Zagreb</span></div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
      <span style="font-size:22px;font-weight:700;letter-spacing:.06em;">{now_s}</span>
      <span class="badge badge-cyan">● LIVE</span>
      <span class="badge badge-green">Tick #{s.tick}</span>
      <span class="badge {'badge-green' if s.wx_source=='live' else 'badge-amber'}">WX:{s.wx_source.upper()}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

for a in alrt.errors():
    st.markdown(f'<div class="alert-error">🚨 {a.message}</div>', unsafe_allow_html=True)
for a in alrt.warnings():
    st.markdown(f'<div class="alert-warning">⚠ {a.message}</div>', unsafe_allow_html=True)

def kpi(col, lbl, val, sub="", cls="kpi-cyan"):
    col.markdown(f'<div class="kpi"><p class="kpi-lbl">{lbl}</p>'
                 f'<p class="kpi-val {cls}">{val}</p>'
                 f'<p class="kpi-sub">{sub}</p></div>', unsafe_allow_html=True)

k = st.columns(6)
kpi(k[0],"Generation",f"{s.total_gen_kw:.1f} kW",f"☀{s.solar_kw:.1f} + 💨{s.wind_kw:.1f}","kpi-amber")
kpi(k[1],"BESS SoC",f"{s.bess_soc_pct:.1f}%",f"{s.bess_temp_c:.1f}°C · SoH {s.bess_soh_pct:.1f}%",
    "kpi-green" if s.bess_soc_pct>40 else "kpi-red")
kpi(k[2],"H₂ Rate",f"{s.h2_kg_h*1000:.1f} g/h",f"η {s.elec_eff_pct:.1f}%","kpi-cyan")
kpi(k[3],"H₂ Today",f"{s.cum_h2_kg:.3f} kg",f"CO₂ {s.cum_co2_kg:.2f} kg saved","kpi-cyan")
kpi(k[4],"LCOH",f"€{s.lcoh:.2f}/kg","✅ Target" if s.is_profitable else f"Target €{Config.LCOH_TARGET_EURO_KG}",
    "kpi-green" if s.is_profitable else "kpi-amber")
kpi(k[5],"Revenue",f"€{s.cum_revenue_eur:.2f}",f"Grid €{s.grid_rev_eur:.3f}/tick","kpi-green")

st.markdown(f'<div class="switch-log">⚡ EMS → {s.switching_event}</div>', unsafe_allow_html=True)

tabs = st.tabs(["🌍 Acquisition","⚗️ Production","🔋 Storage","🔌 Distribution","📊 Analytics","🛡 Safety"])

def hd(col=None):
    if len(hist)<2: return False
    if col and col in hist.columns: return hist[col].notna().any()
    return True

# ── TAB 1 ──────────────────────────────────────────────────────────────────
with tabs[0]:
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">Generation mix</p>', unsafe_allow_html=True)
        fig = go.Figure(go.Pie(
            values=[max(.01,s.solar_kw),max(.01,s.wind_kw),max(.01,s.grid_import_kw)],
            labels=["Solar","Wind","Grid"],hole=0.65,
            marker=dict(colors=[C["solar"],C["wind"],C["grid"]],
                        line=dict(color="#0d1117",width=2))))
        fig.add_annotation(text=f"<b>{s.total_gen_kw:.1f}</b><br>kW",showarrow=False,
                          font=dict(size=14,color="#e6edf3"),x=0.5,y=0.5,xref="paper",yref="paper")
        fig.update_layout(**mk(height=260,showlegend=True,legend=dict(orientation="h",y=-0.1,font_size=11)))
        st.plotly_chart(fig,use_container_width=True)

        if hd("wx_irradiance"):
            st.markdown('<p class="sec-hdr">Irradiance trend</p>', unsafe_allow_html=True)
            f2=go.Figure()
            f2.add_trace(go.Scatter(x=hist["time"],y=hist["wx_irradiance"],fill="tozeroy",
                fillcolor="rgba(255,179,71,.12)",line=dict(color=C["solar"],width=2),name="W/m²"))
            f2.update_layout(**mk(height=170,yaxis_title="W/m²"))
            st.plotly_chart(f2,use_container_width=True)

    with c2:
        st.markdown('<p class="sec-hdr">AI forecast — 6 h</p>', unsafe_allow_html=True)
        fc=st.session_state.last_fc
        if fc and hasattr(fc,"points") and fc.points:
            fdf=pd.DataFrame({"h":[f"+{p.hour_offset+1}h" for p in fc.points],
                              "v":[p.value for p in fc.points],
                              "lo":[p.lower_bound for p in fc.points],
                              "hi":[p.upper_bound for p in fc.points]})
            f3=go.Figure()
            f3.add_trace(go.Scatter(x=fdf["h"],y=fdf["hi"],line=dict(width=0),showlegend=False))
            f3.add_trace(go.Scatter(x=fdf["h"],y=fdf["lo"],fill="tonexty",
                fillcolor="rgba(0,212,255,.10)",line=dict(width=0),name="Confidence"))
            f3.add_trace(go.Scatter(x=fdf["h"],y=fdf["v"],line=dict(color=C["h2"],width=2),
                mode="lines+markers",marker=dict(size=5),name="Forecast"))
            f3.update_layout(**mk(height=220,yaxis_title="W/m²"))
            st.plotly_chart(f3,use_container_width=True)
        else:
            st.info("Accumulating data for AI training…")

        st.markdown('<p class="sec-hdr">Weather telemetry</p>', unsafe_allow_html=True)
        wc=st.columns(3)
        wc[0].metric("Temp",f"{s.wx_temp_c:.1f}°C")
        wc[1].metric("Wind",f"{s.wx_wind_ms:.1f} m/s")
        wc[2].metric("Humidity",f"{s.wx_humidity:.0f}%")
        wc2=st.columns(3)
        wc2[0].metric("Irradiance",f"{s.wx_irradiance:.0f} W/m²")
        wc2[1].metric("Soiling",f"{s.wx_soiling:.3f}")
        wc2[2].metric("Precip",f"{s.wx_precip_mm:.1f} mm")

# ── TAB 2 ──────────────────────────────────────────────────────────────────
with tabs[1]:
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">Power allocation</p>', unsafe_allow_html=True)
        if hd():
            f5=go.Figure()
            SERIES=[("bess_charge_kw",C["bess"],"rgba(63,185,80,.6)","BESS charge"),
                    ("elec_kw",C["elec"],"rgba(188,140,255,.6)","Electrolyzer"),
                    ("ev_kw",C["ev"],"rgba(121,192,255,.6)","EV charger"),
                    ("grid_export_kw",C["grid"],"rgba(139,148,158,.6)","Grid export")]
            for col,color,fill,name in SERIES:
                if col in hist.columns:
                    f5.add_trace(go.Scatter(x=hist["time"],y=hist[col],stackgroup="one",
                        name=name,line=dict(color=color,width=1),fillcolor=fill))
            f5.update_layout(**mk(height=240,yaxis_title="kW"))
            st.plotly_chart(f5,use_container_width=True)

        st.markdown('<p class="sec-hdr">Stack SoH</p>', unsafe_allow_html=True)
        f6=go.Figure(go.Indicator(mode="gauge+number",value=s.elec_soh_pct,
            title={"text":"Stack SoH (%)"},
            gauge={"axis":{"range":[70,100],"tickcolor":"#8b949e"},"bar":{"color":C["elec"]},
                   "bgcolor":"#161b22",
                   "steps":[{"range":[70,80],"color":"#2d0e0e"},{"range":[80,90],"color":"#2d1f00"},
                             {"range":[90,100],"color":"#0d2c18"}],
                   "threshold":{"line":{"color":C["fc"],"width":2},"value":80}}))
        f6.update_layout(**mk(height=200))
        st.plotly_chart(f6,use_container_width=True)

    with c2:
        if hd("h2_kg_h"):
            st.markdown('<p class="sec-hdr">H₂ production</p>', unsafe_allow_html=True)
            f7=go.Figure()
            f7.add_trace(go.Bar(x=hist["time"],y=(hist["h2_kg_h"]*1000).round(2),
                marker_color=C["h2"],marker_line_width=0,name="g/h"))
            f7.update_layout(**mk(height=200,yaxis_title="g H₂/h"))
            st.plotly_chart(f7,use_container_width=True)

        if hd("elec_eff_pct") and len(hist)>5:
            st.markdown('<p class="sec-hdr">Efficiency vs load</p>', unsafe_allow_html=True)
            f8=px.scatter(hist,x="elec_kw",y="elec_eff_pct",color="h2_kg_h",
                color_continuous_scale=[[0,"#161b22"],[1,C["h2"]]],
                labels={"elec_kw":"Power (kW)","elec_eff_pct":"Efficiency (%)"})
            f8.update_layout(**mk(height=180))
            st.plotly_chart(f8,use_container_width=True)

        ec=st.columns(3)
        ec[0].metric("Purity",f"{s.elec_purity:.4f}%")
        ec[1].metric("Water",f"{s.water_l_h:.3f} L/h")
        ec[2].metric("Heat rec.",f"{s.heat_kw:.2f} kW")

# ── TAB 3 ──────────────────────────────────────────────────────────────────
with tabs[2]:
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">BESS state of charge</p>', unsafe_allow_html=True)
        f9=go.Figure(go.Indicator(mode="gauge+number+delta",value=s.bess_soc_pct,
            delta={"reference":55.0,"valueformat":".1f"},title={"text":"SoC (%)"},
            gauge={"axis":{"range":[0,100],"tickcolor":"#8b949e"},"bar":{"color":C["bess"]},
                   "bgcolor":"#161b22",
                   "steps":[{"range":[0,Config.BATT_SOC_MIN*100],"color":"#2d0e0e"},
                             {"range":[Config.BATT_SOC_MIN*100,Config.BATT_SOC_MAX*100],"color":"#0d2c18"}],
                   "threshold":{"line":{"color":C["fc"],"width":2},"value":Config.BATT_SOC_MIN*100}}))
        f9.update_layout(**mk(height=230))
        st.plotly_chart(f9,use_container_width=True)

        if hd("bess_temp_c"):
            st.markdown('<p class="sec-hdr">BESS temperature</p>', unsafe_allow_html=True)
            f10=go.Figure()
            f10.add_trace(go.Scatter(x=hist["time"],y=hist["bess_temp_c"],
                line=dict(color=C["fc"],width=2),name="°C"))
            f10.add_hline(y=55,line_dash="dash",line_color=C["solar"],annotation_text="⚠55°C")
            f10.add_hline(y=Config.THERMAL_RUNAWAY_TEMP,line_dash="dash",
                line_color=C["fc"],annotation_text="🔥Runaway")
            f10.update_layout(**mk(height=170,yaxis_title="°C"))
            st.plotly_chart(f10,use_container_width=True)

    with c2:
        st.markdown('<p class="sec-hdr">Hydrogen tank levels</p>', unsafe_allow_html=True)
        f11=go.Figure(go.Bar(x=["Buffer","Main Tank","HRS Station"],
            y=[s.buffer_pct,s.main_tank_pct,s.hrs_pct],
            marker_color=[C["h2"],C["elec"],C["bess"]],marker_line_width=0,
            text=[f"{v:.1f}%" for v in [s.buffer_pct,s.main_tank_pct,s.hrs_pct]],
            textposition="outside"))
        f11.update_layout(**mk(height=230,yaxis_range=[0,115],yaxis_title="%"))
        st.plotly_chart(f11,use_container_width=True)

        f12=go.Figure(go.Indicator(mode="gauge+number",value=s.pressure_bar,
            title={"text":"Pressure (bar)"},
            gauge={"axis":{"range":[0,Config.SAFETY_MAX_PRESSURE_BAR],"tickcolor":"#8b949e"},
                   "bar":{"color":C["wind"]},"bgcolor":"#161b22",
                   "threshold":{"line":{"color":C["fc"],"width":2},
                                "value":Config.SAFETY_MAX_PRESSURE_BAR*.90}}))
        f12.update_layout(**mk(height=170))
        st.plotly_chart(f12,use_container_width=True)

        comp_cls="badge-green" if s.compressor_on else "badge-amber"
        st.markdown(f'Compressor: <span class="badge {comp_cls}">{"● ON" if s.compressor_on else "○ STANDBY"}</span>'
                   f' | Tank {s.tank_temp_c:.1f}°C',unsafe_allow_html=True)

# ── TAB 4 ──────────────────────────────────────────────────────────────────
with tabs[3]:
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">HRS 5 kg station</p>', unsafe_allow_html=True)
        st.progress(min(s.hrs_pct/100,1.0))
        hrs_c="badge-green" if s.hrs_pct>60 else "badge-amber"
        st.markdown(f'{s.hrs_pct:.1f}% | <span class="badge {hrs_c}">'
                   f'{"● READY" if s.hrs_pct>60 else "▼ FILLING"}</span>',unsafe_allow_html=True)

        f14=go.Figure(go.Indicator(mode="gauge+number",value=s.fc_kw,
            title={"text":f"Fuel cell (kW)  η={s.fc_eff_pct:.1f}%"},
            gauge={"axis":{"range":[0,Config.FC_POWER_NOM_KW*1.1],"tickcolor":"#8b949e"},
                   "bar":{"color":C["bess"]},"bgcolor":"#161b22"}))
        f14.update_layout(**mk(height=220))
        st.plotly_chart(f14,use_container_width=True)

    with c2:
        if hd("grid_export_kw"):
            st.markdown('<p class="sec-hdr">Grid export vs EV</p>', unsafe_allow_html=True)
            f15=go.Figure()
            f15.add_trace(go.Scatter(x=hist["time"],y=hist["grid_export_kw"],fill="tozeroy",
                fillcolor="rgba(139,148,158,.2)",line=dict(color=C["grid"],width=2),name="Grid export"))
            f15.add_trace(go.Scatter(x=hist["time"],y=hist["ev_kw"],fill="tozeroy",
                fillcolor="rgba(121,192,255,.2)",line=dict(color=C["ev"],width=2),name="EV load"))
            f15.update_layout(**mk(height=210,yaxis_title="kW"))
            st.plotly_chart(f15,use_container_width=True)

        f16=go.Figure(go.Pie(
            values=[max(.01,s.ev_kw),max(.01,s.grid_export_kw),max(.01,s.heat_kw)],
            labels=["EV","Grid","Heat"],hole=0.55,
            marker=dict(colors=[C["ev"],C["grid"],C["solar"]],
                        line=dict(color="#0d1117",width=2))))
        f16.update_layout(**mk(height=210,legend=dict(orientation="h",y=-0.15,font_size=11)))
        st.plotly_chart(f16,use_container_width=True)

# ── TAB 5 ──────────────────────────────────────────────────────────────────
with tabs[4]:
    sv=max(.1,s.solar_kw); wv=max(.1,s.wind_kw)
    bv=max(.1,s.bess_charge_kw); ev2=max(.1,s.elec_kw)
    evv=max(.1,s.ev_kw); gv=max(.1,s.grid_export_kw)
    f17=go.Figure(go.Sankey(arrangement="snap",
        node=dict(label=["Solar","Wind","BESS","Electrolyzer","H₂ Tank","EV","Grid"],
                  color=[C["solar"],C["wind"],C["bess"],C["elec"],C["h2"],C["ev"],C["grid"]],
                  pad=20,thickness=18,line=dict(color="#0d1117",width=.5)),
        link=dict(source=[0,1,0,1,2,3,4,4],target=[2,2,3,3,3,4,5,6],
                  value=[sv*.4,wv*.4,sv*.6,wv*.6,bv*.2,ev2,evv,gv],
                  color=["rgba(255,179,71,.25)","rgba(88,166,255,.25)",
                         "rgba(255,179,71,.25)","rgba(88,166,255,.25)",
                         "rgba(63,185,80,.2)","rgba(188,140,255,.25)",
                         "rgba(0,212,255,.25)","rgba(139,148,158,.2)"])))
    f17.update_layout(**mk(height=320))
    st.plotly_chart(f17,use_container_width=True)

    ac=st.columns(3)
    with ac[0]:
        if hd("lcoh") and hist["lcoh"].max()>0:
            f18=go.Figure()
            f18.add_trace(go.Scatter(x=hist["time"],y=hist["lcoh"],
                line=dict(color=C["elec"],width=2),name="LCOH"))
            f18.add_hline(y=Config.LCOH_TARGET_EURO_KG,line_dash="dash",line_color=C["bess"],
                annotation_text=f"Target {Config.LCOH_TARGET_EURO_KG}€",annotation_font_color=C["bess"])
            f18.update_layout(**mk(height=190,yaxis_title="€/kg"))
            st.plotly_chart(f18,use_container_width=True)
        lcls="kpi-green" if s.is_profitable else "kpi-amber"
        st.markdown(f'<p class="kpi-val {lcls}" style="font-size:18px">€{s.lcoh:.3f}/kg</p>',unsafe_allow_html=True)

    with ac[1]:
        if hd("co2_saved_kg"):
            f19=go.Figure(go.Bar(x=hist["time"],y=(hist["co2_saved_kg"]*1000).round(2),
                marker_color=C["bess"],marker_line_width=0))
            f19.update_layout(**mk(height=190,yaxis_title="g CO₂"))
            st.plotly_chart(f19,use_container_width=True)
        st.metric("CO₂ saved",f"{s.cum_co2_kg:.3f} kg")

    with ac[2]:
        st.metric("Total revenue",f"€{s.cum_revenue_eur:.3f}")
        st.metric("H₂ produced",f"{s.cum_h2_kg*1000:.1f} g")
        st.metric("Water used",f"{s.cum_water_l:.2f} L")
        st.metric("H₂ subsidy",f"€{s.cum_h2_kg*Config.GREEN_H2_SUBSIDY:.3f}")

# ── TAB 6 ──────────────────────────────────────────────────────────────────
with tabs[5]:
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<p class="sec-hdr">Health matrix</p>', unsafe_allow_html=True)
        def hrow(lbl,val,unit,ok,warn,fmt=".1f"):
            v=float(val)
            if ok[0]<=v<=ok[1]: cls,ic="kpi-green","●"
            elif warn[0]<=v<=warn[1]: cls,ic="kpi-amber","▲"
            else: cls,ic="kpi-red","✖"
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #21262d;">'
                       f'<span style="color:#8b949e;font-size:13px;">{lbl}</span>'
                       f'<span class="kpi-val {cls}" style="font-size:14px;">{ic} {v:{fmt}} {unit}</span></div>',
                       unsafe_allow_html=True)
        hrow("BESS SoC",s.bess_soc_pct,"%",(20,90),(15,95))
        hrow("BESS Temp",s.bess_temp_c,"°C",(10,45),(0,55))
        hrow("BESS SoH",s.bess_soh_pct,"%",(85,100),(75,100))
        hrow("Stack SoH",s.elec_soh_pct,"%",(85,100),(75,100))
        hrow("Pressure",s.pressure_bar,"bar",(30,600),(20,680))
        hrow("Tank Temp",s.tank_temp_c,"°C",(15,60),(10,75))
        hrow("H₂ Purity",s.elec_purity,"%",(99.99,100),(99.9,100),".4f")

    with c2:
        st.markdown('<p class="sec-hdr">Active alerts</p>', unsafe_allow_html=True)
        if not alrt.active:
            st.markdown('<div class="alert-info">✅ All systems nominal</div>',unsafe_allow_html=True)
        else:
            for a in alrt.active:
                cls={"error":"alert-error","warning":"alert-warning","info":"alert-info"}.get(a.level,"alert-info")
                ic={"error":"🚨","warning":"⚠","info":"ℹ"}.get(a.level,"ℹ")
                st.markdown(f'<div class="{cls}">{ic} <b>[{a.code}]</b> {a.message}'
                           f'<span style="float:right;opacity:.5">{a.ts}</span></div>',unsafe_allow_html=True)

        st.markdown('<p class="sec-hdr">Thresholds</p>', unsafe_allow_html=True)
        st.caption(f"Thermal runaway: {Config.THERMAL_RUNAWAY_TEMP}°C")
        st.caption(f"Max pressure: {Config.SAFETY_MAX_PRESSURE_BAR} bar")
        st.caption(f"Emergency SoC: {Config.EMERGENCY_SHUTDOWN_SOC*100:.0f}%")
        st.caption(f"Leak threshold: {Config.LEAK_DETECTION_THRESHOLD} kg/h")

        ld_c="badge-red" if s.leak_detected else "badge-green"
        st.markdown(f'<br><span class="badge {ld_c}" style="font-size:13px;padding:6px 14px;">'
                   f'{"⚠ LEAK DETECTED" if s.leak_detected else "✅ No leak"}</span>',
                   unsafe_allow_html=True)

# ── AUTO REFRESH ───────────────────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh*1000, key="lumi_r")
except ImportError:
    import time; time.sleep(refresh); st.rerun()
