# main.py - FINAL INTEGRATED COMMAND CENTER
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. SETTINGS & STYLES ---
st.set_page_config(page_title="LUMINIH2 COMMAND", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: white; }
    .card { 
        background: #1e293b; padding: 20px; border-radius: 15px; 
        border-top: 4px solid #38bdf8; margin-bottom: 20px;
    }
    .metric-val { font-size: 24px; font-weight: bold; color: #38bdf8; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIMULATED DATA (Replace with your actual logic) ---
if 'init' not in st.session_state:
    st.session_state.update({'bess': 0.3, 'h2_tank': 1.2, 'station': 0.0, 'init': True})

# Logic: BESS -> H2 Tank -> H2 Station -> EV Hub -> Grid Sale
st.session_state.bess = min(0.95, st.session_state.bess + 0.01)
if st.session_state.bess > 0.5:
    st.session_state.h2_tank = min(10.0, st.session_state.h2_tank + 0.2)
    if st.session_state.h2_tank > 2.0:
        st.session_state.station = min(5.0, st.session_state.station + 0.5)

# --- 3. UI RENDER ---

st.title("🌐 مرکز فرماندهی LUMINIH2")
st.write(f"آخرین بروزرسانی زاگرب: {datetime.now().strftime('%H:%M:%S')}")

# بخش ۱: ورودی و ذخیره‌ساز (ترکیب لایه ۱ و ۲)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("⚡ تامین انرژی")
    st.write("منبع فعال: **Hybrid (Solar+Wind)**")
    st.metric("ورودی کل", "18.5 kW", "3.2 kW Grid")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🔋 وضعیت باطری (BESS)")
    st.progress(st.session_state.bess)
    st.write(f"سطح شارژ: {st.session_state.bess*100:.1f}%")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💧 زنجیره هیدروژن")
    st.write(f"مخزن اصلی: **{st.session_state.h2_tank:.2f} kg**")
    st.write(f"ایستگاه سوخت‌گیری: **{st.session_state.station:.1f}/5 kg**")
    st.markdown('</div>', unsafe_allow_html=True)

# بخش ۲: توزیع و تحلیل (ترکیب لایه ۳ و ۴)
st.markdown("### 📊 تحلیل خروجی و توزیع")
c1, c2 = st.columns([2, 1])

with c1:
    # نمودار جریان انرژی (Sankey)
    fig = go.Figure(go.Sankey(
        node=dict(label=["خورشید/باد", "باطری", "الکترولایزر", "مخزن H2", "ایستگاه EV", "فروش به شبکه"], color="#38bdf8"),
        link=dict(source=[0, 0, 2, 3, 3], target=[1, 2, 3, 4, 5], value=[10, 15, 12, 8, 4])
    ))
    fig.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font_color="white")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("💰 بازدهی مالی")
    st.metric("فروش به شبکه", "$12.40 /hr", "High Demand")
    st.metric("کاهش CO2", "4.2 kg/hr")
    st.markdown('</div>', unsafe_allow_html=True)

time.sleep(1)
st.rerun()
