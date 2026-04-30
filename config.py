# =============================================================================
# main.py — LUMINIH2 Overview · Zagreb Digital Twin
# =============================================================================

import streamlit as st
import plotly.graph_objects as go

from shared import (inject_css, init_session, run_tick, sidebar_controls,
                    page_header, show_alerts, kpi, sec, C, mk, hd, autorefresh)
from config import Config

st.set_page_config(page_title="LUMINIH2 — Overview", page_icon="⚡",
                   layout="wide", initial_sidebar_state="expanded")
inject_css()
init_session()
refresh = sidebar_controls()
run_tick()

s    = st.session_state.last_state
hist = st.session_state.history.df

if s is None:
    st.info("Initialising…"); st.stop()

page_header("⚡ LUMINIH2 Digital Twin v4.1",
            "Integrated Green Hydrogen & E-Mobility Hub · Zagreb, Croatia")
show_alerts()

# ── KPI row ──────────────────────────────────────────────────────────────────
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

st.markdown(f'<div class="switch-log">⚡ EMS → {s.switching_event}</div>',
            unsafe_allow_html=True)

# ── Sankey + Device status ────────────────────────────────────────────────────
col_l, col_r = st.columns([3, 2])

with col_l:
    sec("Live energy flow")
    sv = max(0.1, s.solar_kw);    wv  = max(0.1, s.wind_kw)
    bv = max(0.1, s.bess_charge_kw); ev2 = max(0.1, s.elec_kw)
    evv = max(0.1, s.ev_kw);      h2v = max(0.1, s.h2_kg_h * 80)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=["Solar PV\n15 kW", "Wind\n10 kW", "BESS\n100 kWh",
                   "Electrolyzer\nS30/30", "H₂ Tank\nTH540-50",
                   "HRS 5 kg", "EV Charger", "Grid Export"],
            color=[C["solar"], C["wind"], C["bess"], C["elec"],
                   C["h2"], "#f97316", C["ev"], C["grid"]],
            pad=20, thickness=18, line=dict(color="#e2e8f0", width=0.5)),
        link=dict(
            source=[0, 1, 0, 1, 2, 3, 4, 4],
            target=[2, 2, 3, 3, 3, 4, 5, 6],
            value=[sv*.4, wv*.4, sv*.6, wv*.6, bv*.2, ev2, h2v, evv],
            color=["rgba(245,158,11,.25)", "rgba(59,130,246,.25)",
                   "rgba(245,158,11,.25)", "rgba(59,130,246,.25)",
                   "rgba(34,197,94,.2)", "rgba(139,92,246,.25)",
                   "rgba(14,165,233,.25)", "rgba(148,163,184,.2)"])))
    fig.update_layout(**mk(height=360))
    st.plotly_chart(fig, use_container_width=True)

    sec("Generation trend")
    if hd(hist):
        fg = go.Figure()
        fg.add_trace(go.Scatter(x=hist["time"], y=hist["solar_kw"],
            fill="tozeroy", fillcolor="rgba(245,158,11,.10)",
            line=dict(color=C["solar"], width=2), name="Solar kW"))
        fg.add_trace(go.Scatter(x=hist["time"], y=hist["wind_kw"],
            fill="tozeroy", fillcolor="rgba(59,130,246,.10)",
            line=dict(color=C["wind"], width=2), name="Wind kW"))
        fg.update_layout(**mk(height=180, yaxis_title="kW",
            legend=dict(orientation="h", y=1.1, font_size=11)))
        st.plotly_chart(fg, use_container_width=True)

with col_r:
    sec("Device status")
    devices = [
        ("☀",  "Solar PV System",     f"42×360W · {Config.PV_SYSTEM_CAPACITY_KW} kW",
         f"{s.solar_kw:.1f} kW",
         "green" if s.solar_kw > 0.5 else "gray",
         "PRODUCING" if s.solar_kw > 0.5 else "NIGHT", C["solar"]),
        ("💨", "Wind Turbine",         "10 kW HAWT · Hub 30m",
         f"{s.wind_kw:.1f} kW",
         "green" if s.wind_kw > 0.3 else "gray",
         s.wind_regime.replace("_", " ").upper(), C["wind"]),
        ("🔋", "BESS",                 "100 kWh LFP · SoC 10–90%",
         f"SoC {s.bess_soc_pct:.1f}% · {s.bess_temp_c:.1f}°C",
         "green" if s.bess_soc_pct > 30 else "red",
         "CHARGING" if s.bess_charge_kw > 0.1 else "IDLE", C["bess"]),
        ("⚗",  "Electrolyzer S30/30",  "ITM Power PEM · 0.74–5.63 kW",
         f"{s.h2_kg_h*1000:.2f} g/h H₂",
         "cyan" if s.elec_kw >= Config.ELEC_P_MIN_KW else "gray",
         f"LOAD {s.elec_kw:.2f} kW" if s.elec_kw >= Config.ELEC_P_MIN_KW else "STANDBY",
         C["elec"]),
        ("🏗",  "H₂ Storage TH540-50", "10.8 kg · NWP 500 bar",
         f"{s.main_tank_pct:.1f}% · {s.pressure_bar:.0f} bar",
         "cyan" if s.main_tank_pct > 10 else "amber",
         "COMP ON" if s.compressor_on else "PASSIVE", C["h2"]),
        ("⚡",  "Fuel Cell AIRCELL",    "3 kW nom · 0.066 kg H₂/kWh",
         f"{s.fc_kw:.3f} kW",
         "green" if s.fc_kw > 0.05 else "gray",
         "GENERATING" if s.fc_kw > 0.05 else "STANDBY", "#ef4444"),
    ]
    for icon, name, model, value, bk, status, color in devices:
        st.markdown(f"""
<div style="background:#ffffff;border:1px solid #e2e8f0;border-left:3px solid {color};
  border-radius:8px;padding:10px 14px;margin-bottom:8px;
  box-shadow:0 1px 3px rgba(0,0,0,.04)">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="font-size:14px;font-weight:600;color:#0f172a">{icon} {name}</div>
      <div style="font-size:11px;color:#64748b;margin-top:1px">{model}</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:14px;font-weight:700;color:{color};margin-bottom:3px">{value}</div>
      <span class="badge badge-{bk}">{status}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

autorefresh(refresh, "ov_r")
