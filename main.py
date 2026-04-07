# main.py - TEST VERSION (Simplified & High Contrast)
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# --- 1. SETTINGS ---
st.set_page_config(page_title="LUMINIH2 TEST", layout="centered") # تغییر به حالت متمرکز

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .test-box { 
        border: 2px dashed #cbd5e1; padding: 20px; border-radius: 10px; 
        background: #f8fafc; margin-bottom: 20px;
    }
    h1 { color: #0f172a; border-bottom: 4px solid #38bdf8; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MINIMAL LOGIC ---
if 'init' not in st.session_state:
    st.session_state.update({'tank': 0.0, 'bess': 0.1, 'init': True})

# منطق ساده شده برای تست
st.session_state.tank = (st.session_state.tank + 0.1) % 5
st.session_state.bess = (st.session_state.bess + 0.01) % 1

# --- 3. UI RENDER (حذف اکثر نمودارها برای تست) ---

st.title("🧪 LUMINIH2 - TEST MODE")
st.write(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

# نمایش داده‌های خام به جای نمودارهای پیچیده
col1, col2 = st.columns(2)
with col1:
    st.markdown('<div class="test-box">', unsafe_allow_html=True)
    st.subheader("🔋 Battery Status")
    st.progress(st.session_state.bess)
    st.metric("SoC (%)", f"{st.session_state.bess*100:.1f}%")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="test-box">', unsafe_allow_html=True)
    st.subheader("💧 H2 Storage")
    # تنها نمودار باقی‌مانده برای تست بصری
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = st.session_state.tank,
        gauge = {'axis': {'range': [0, 5]}, 'bar': {'color': "#38bdf8"}}
    ))
    fig.update_layout(height=150, margin=dict(t=0, b=0, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# بخش فروش به شبکه (ساده شده)
st.info("System is currently prioritizing Battery & H2 Station.")

# REFRESH
time.sleep(1)
st.rerun()
