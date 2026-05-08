# =============================================================================
# shared_state.py — LUMINIH2 Shared State, Styling & Voice Welcome
# White industrial theme · Session state · Voice briefing
# Version: 4.2
# =============================================================================
#
# RELATIONSHIP TO shared.py:
#   shared.py        — primary module (UI helpers, session state, tick)
#   shared_state.py  — extended module with voice welcome panel
#
# WHAT THIS MODULE ADDS OVER shared.py:
#   - inject_voice_welcome() : animated speaker button + Web Speech API briefing
#   - device_card()          : styled device info card for the UI
#   - stat_grid()            : 2-column stat grid renderer
#   - get_state() / get_hist() / get_sub() / get_alrt() : convenience accessors
#
# NOTE:
#   This module re-exports everything from shared.py so pages only need
#   to import from shared_state if they want the voice welcome.
#   Otherwise import from shared.py directly.
# =============================================================================

from __future__ import annotations

import streamlit as st
from datetime import datetime, timezone, timedelta

# Re-export everything from shared.py
from shared import (
    C, PLOT, mk,
    WHITE_CSS, inject_css,
    kpi, sec, badge, alert_box, health_row, hd, now_zagreb,
    init_session, run_tick, sidebar_controls, page_header,
    show_alerts, autorefresh,
)

from config import Config


# =============================================================================
# Extended colour palette (adds device-specific colours)
# =============================================================================

C_EXT: dict[str, str] = {
    **C,
    "orange": "#ea580c",
    "gray":   "#64748b",
    "heat":   "#f97316",
}


# =============================================================================
# Convenience state accessors
# =============================================================================

def get_state():
    """Return the last TickState snapshot."""
    return st.session_state.get("last_state")


def get_hist():
    """Return the history DataFrame."""
    return st.session_state.history.df


def get_sub():
    """Return the last SubsystemManager result."""
    return st.session_state.get("sub_result")


def get_alrt():
    """Return the AlertSystem."""
    return st.session_state.alerts


# =============================================================================
# Extended UI helpers
# =============================================================================

def device_card(title: str, model: str, content_html: str = "") -> None:
    """
    Render a white device info card.

    Args:
        title        : device display name (e.g. "Electrolyzer")
        model        : device model string (e.g. "ITM S30/30")
        content_html : optional HTML body inside the card
    """
    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;'
        f'padding:14px 18px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,.04)">'
        f'<div style="font-size:15px;font-weight:600;color:#0f172a;margin:0 0 2px">{title}</div>'
        f'<div style="font-size:12px;color:#64748b;margin:0 0 10px">{model}</div>'
        f'{content_html}</div>',
        unsafe_allow_html=True,
    )


def stat_grid(items: list[tuple[str, str]]) -> None:
    """
    Render a 2-column stat grid.

    Args:
        items : list of (label, value) tuples
    """
    cells = "".join(
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
        f'padding:8px 12px">'
        f'<div style="font-size:10px;color:#64748b;text-transform:uppercase;'
        f'font-weight:500;margin:0">{lbl}</div>'
        f'<div style="font-size:16px;font-weight:600;color:#0f172a;margin:2px 0 0">{val}</div>'
        f'</div>'
        for lbl, val in items
    )
    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'{cells}</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# Voice Welcome Panel
# =============================================================================

def inject_voice_welcome(
    custom_message: str | None = None,
) -> None:
    """
    Inject an animated voice welcome panel with Web Speech API.

    Renders a speaker button that plays a system briefing when clicked.
    Auto-plays 0.8 seconds after page load.

    Args:
        custom_message : optional override for the spoken text.
                         If None, generates a standard system briefing.

    Usage in main.py:
        from shared_state import inject_voice_welcome
        inject_voice_welcome()
    """
    now   = datetime.now(timezone(timedelta(hours=2)))
    hour  = now.hour
    day   = now.strftime("%A")
    date  = now.strftime("%B %d, %Y")
    time_ = now.strftime("%H:%M")
    greet = ("Good morning" if hour < 12
             else "Good afternoon" if hour < 17
             else "Good evening")

    if custom_message:
        text_js = custom_message.replace("`", "'").replace("\n", " ")
    else:
        s = st.session_state.get("last_state")
        gen_kw  = f"{s.total_gen_kw:.1f}" if s else "unknown"
        soc_pct = f"{s.bess_soc_pct:.0f}" if s else "unknown"
        h2_g    = f"{s.h2_kg_h*1000:.1f}" if s else "unknown"

        text_js = (
            f"{greet}. Welcome to LUMINIH2 Digital Twin. "
            f"Today is {day}, {date}. Time in Zagreb is {time_}. "
            f"Current generation is {gen_kw} kilowatts. "
            f"Battery is at {soc_pct} percent state of charge. "
            f"Hydrogen rate is {h2_g} grams per hour. "
            f"All devices are online and nominal. "
            f"Have a productive session."
        )

    components_html = f"""<!DOCTYPE html>
<html><head>
<style>
*{{box-sizing:border-box;margin:0;padding:0;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
body{{background:transparent}}
.wc{{background:linear-gradient(135deg,#f0f9ff,#f8fafc,#f0fdf4);
  border:1px solid #bae6fd;border-left:4px solid #0ea5e9;
  border-radius:12px;padding:14px 18px;display:flex;align-items:center;gap:14px;
  box-shadow:0 2px 12px rgba(14,165,233,.10)}}
.sb{{width:46px;height:46px;border-radius:50%;border:none;cursor:pointer;flex-shrink:0;
  background:linear-gradient(135deg,#0ea5e9,#6366f1);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 12px rgba(14,165,233,.35);transition:all .2s}}
.sb:hover{{transform:scale(1.06)}}
.sb.sp{{background:linear-gradient(135deg,#22c55e,#0ea5e9);
  animation:pulse 1.2s ease-in-out infinite}}
@keyframes pulse{{
  0%,100%{{box-shadow:0 4px 12px rgba(34,197,94,.4)}}
  50%{{box-shadow:0 4px 22px rgba(34,197,94,.7)}}
}}
.wt{{flex:1}}
.wg{{font-size:14px;font-weight:600;color:#0f172a}}
.wd{{font-size:11px;color:#0369a1;margin-top:2px;font-weight:500}}
.wm{{font-size:11px;color:#64748b;margin-top:4px;min-height:16px}}
.wr{{display:flex;align-items:center;gap:2px;height:20px;margin-top:5px}}
.wb{{width:3px;border-radius:2px;background:#0ea5e9;height:3px;
  transition:height .08s,background .08s}}
</style>
</head>
<body>
<div class="wc">
  <button class="sb" id="sb" onclick="go()" title="Play system briefing">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff"
         stroke-width="2.2" stroke-linecap="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    </svg>
  </button>
  <div class="wt">
    <div class="wg">{greet} — LUMINIH2 Digital Twin</div>
    <div class="wd">{day}, {date} · Zagreb {time_}</div>
    <div class="wm" id="wm">Click the speaker for your system briefing</div>
    <div class="wr" id="wr"></div>
  </div>
</div>

<script>
var spk=false, wi=null, bars=[];
var syn=window.speechSynthesis;
var TEXT=`{text_js}`;

function buildBars(){{
  var r=document.getElementById('wr');
  r.innerHTML=''; bars=[];
  for(var i=0;i<26;i++){{
    var b=document.createElement('div');
    b.className='wb';
    r.appendChild(b);
    bars.push(b);
  }}
}}

function wave(on){{
  if(wi) clearInterval(wi);
  if(!on){{ bars.forEach(function(b){{b.style.height='3px';}}); return; }}
  wi=setInterval(function(){{
    bars.forEach(function(b,i){{
      var h=Math.round(3+Math.abs(Math.sin(Date.now()/180+i*0.45))*16);
      b.style.height=h+'px';
      b.style.background=h>12?'#22c55e':'#0ea5e9';
    }});
  }},55);
}}

function go(){{
  if(!syn) return;
  if(spk){{
    syn.cancel(); spk=false;
    document.getElementById('sb').classList.remove('sp');
    wave(false);
    document.getElementById('wm').textContent='Briefing stopped.';
    return;
  }}
  buildBars();
  document.getElementById('wm').textContent='Playing briefing\u2026';
  var u=new SpeechSynthesisUtterance(TEXT);
  u.lang='en-GB'; u.rate=0.90; u.pitch=1.0;
  var vs=syn.getVoices();
  var v=vs.find(function(x){{return x.lang==='en-GB';}}) ||
        vs.find(function(x){{return x.lang.startsWith('en');}});
  if(v) u.voice=v;
  u.onstart=function(){{
    spk=true;
    document.getElementById('sb').classList.add('sp');
    wave(true);
  }};
  u.onend=u.onerror=function(){{
    spk=false;
    document.getElementById('sb').classList.remove('sp');
    wave(false);
    document.getElementById('wm').textContent='Briefing complete. Click to replay.';
  }};
  syn.cancel();
  syn.speak(u);
}}

// Auto-play after 0.8s
setTimeout(go, 800);
</script>
</body></html>"""

    st.components.v1.html(components_html, height=110, scrolling=False)
