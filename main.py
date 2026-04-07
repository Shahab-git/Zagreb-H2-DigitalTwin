import streamlit as st
import time

st.set_page_config(page_title="H2-TEST", layout="centered")

# ظاهر کاملاً متفاوت (سفید و ساده)
st.title("🚀 تست نهایی اتصال")
st.write("اگر این متن را می‌بینید، یعنی فایل main.py با موفقیت آپدیت شده است.")

# ایجاد یک اسلایدر برای تست دستی
val = st.slider("یک عدد را جابجا کنید تا از زنده بودن داشبورد مطمئن شوید:", 0, 100, 50)
st.success(f"عدد انتخاب شده: {val}")

# نمایش یک استاتوس ساده
st.metric(label="وضعیت مخزن هیدروژن", value="4.2 kg", delta="0.5 kg")

if st.button('کلیک کنید'):
    st.balloons() # برای تست بصری جذاب
