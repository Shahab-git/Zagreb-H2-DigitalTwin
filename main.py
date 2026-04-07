# main.py - NEW MINIMALIST DESIGN
import streamlit as st
import pandas as pd
from datetime import datetime
import time

# --- 1. تنظیمات ظاهری کاملاً جدید ---
st.set_page_config(page_title="LUMINIH2 REBORN", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stat-card {
        background: white;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        text-align: center;
        border-bottom: 5px solid #007bff;
    }
    .main-title {
        font-family: 'Helvetica';
        color: #1a1a1a;
        text-align: center;
        font-weight: 900;
        font-size: 50px;
        margin-bottom: 40px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. منطق ساده برای اطمینان از آپدیت ---
if 'init' not in st.session_state:
    st.session_state.update({'tank': 0.0, 'bess': 0.1, 'init': True})

# ایجاد تغییرات عددی برای تست بصری
st.session_state.tank = round((st.session_state.tank + 0.1) % 5, 2)
st.session_state.bess = round((st.session_state.bess + 0.01) % 1, 2)

# --- 3. بدنه اصلی (بدون لایه‌بندی - فقط کارت‌های اطلاعاتی) ---

st.markdown('<h1 class="main-title">LUMINIH2 STATION</h1>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.write("### 🔋 BATTERY")
    st.title(f"{st.session_state.bess * 100:.0f}%")
    st.progress(st.session_state.bess)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.write("### 💧 H2 TANK")
    st.title(f"{st.session_state.tank} kg")
    st.caption("Target: 5.0 kg")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.write("### 🌍 ZAGREB")
    st.metric("Status", "Operational")
    st.write(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    st.markdown('</div>', unsafe_allow_html=True)

# حذف نمودارهای سنگین (سایکی، پای‌چارت و غیره) برای تست سرعت و تغییر
st.write("---")
st.info("تمامی نمودارهای لایه ۴ و دیاگرام‌های پیچیده موقتاً حذف شدند تا تغییر کد تایید شود.")

# REFRESH
time.sleep(1)
st.rerun()
