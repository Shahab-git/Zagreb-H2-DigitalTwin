import requests
import datetime
import numpy as np
import logging
import streamlit as st
from config import Config

# تنظیمات لاگ برای پایش در کنسول Streamlit
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WeatherEngine")

class WeatherProvider:
    """
    موتور پیشرفته محیطی برای دریافت تلمتری لحظه‌ای زاگرب.
    شامل محاسبات اثر گرد و غبار (Soiling) و توربولانس باد.
    """

    def __init__(self):
        self.lat = Config.LOCATION["lat"]
        self.lon = Config.LOCATION["lon"]
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        # ردیابی روزهای بدون باران برای محاسبه افت بازدهی پنل‌ها
        if 'days_since_rain' not in st.session_state:
            st.session_state.days_since_rain = 0

    @st.cache_data(ttl=900)  # ذخیره داده‌ها برای 15 دقیقه جهت بهینه‌سازی سرعت
    def fetch_current_data(_self):
        """دریافت داده‌های زنده و محاسبه فاکتورهای تخریب محیطی."""
        
        params = {
            "latitude": _self.lat,
            "longitude": _self.lon,
            "current": ["temperature_2m", "relative_humidity_2m", "precipitation", 
                        "wind_speed_10m", "shortwave_radiation"],
            "hourly": ["shortwave_radiation"],
            "timezone": "Europe/Berlin",
            "forecast_days": 1
        }

        try:
            response = requests.get(_self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            current = data.get('current', {})
            hourly = data.get('hourly', {})
            
            # --- 🌞 منطق تابش خورشیدی ---
            irradiance = current.get('shortwave_radiation', 0.0)
            now_hour = datetime.datetime.now().hour

            # اصلاح خطای احتمالی API در ساعات روز
            if irradiance is None or (11 < now_hour < 14 and irradiance < 10):
                irradiance_list = hourly.get('shortwave_radiation', [0.0]*24)
                irradiance = irradiance_list[now_hour] if len(irradiance_list) > now_hour else 0.0

            # --- 🌧️ تحلیل اثر گرد و غبار (Industrial Realism) ---
            precip = current.get('precipitation', 0.0)
            if precip > 0.5:  # باران بیش از 0.5 میلی‌متر پنل‌ها را تمیز می‌کند
                st.session_state.days_since_rain = 0
            else:
                # افزایش تدریجی کثیفی پنل‌ها بر اساس گام زمانی
                st.session_state.days_since_rain += (Config.TIMESTEP_SEC / 86400)

            # محاسبه ضریب Soiling (مثلاً 0.95 یعنی 5% افت توان به دلیل خاک)
            soiling_factor = max(0.88, 1.0 - (st.session_state.days_since_rain * Config.SOILING_LOSS_RATE))

            # --- 🌬️ باد و توربولانس زاگرب ---
            wind_speed = current.get('wind_speed_10m', 3.0)
            # ایجاد نوسان تصادفی برای واقعی‌تر شدن شبیه‌سازی باد
            turbulence = Config.TURBULENCE_INTENSITY_LIMIT * (1 + 0.15 * np.random.randn())

            weather_packet = {
                "temp": float(current.get('temperature_2m', 15.0)),
                "humidity": float(current.get('relative_humidity_2m', 50.0)),
                "wind_speed": float(wind_speed),
                "turbulence": abs(float(turbulence)),
                "irradiance_raw": float(irradiance),
                "irradiance_effective": float(irradiance * soiling_factor),
                "soiling_factor": float(soiling_factor),
                "precipitation": float(precip),
                "history_24h": hourly.get('shortwave_radiation', [0.0] * 24),
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
            }

            logger.info(f"📡 Telemetry Success (Zagreb): {irradiance} W/m2")
            return weather_packet

        except Exception as e:
            logger.error(f"⚠️ API Failure: {e}")
            return self._get_fallback_data()

    def _get_fallback_data(self):
        """ارائه داده‌های پیش‌فرض در صورت قطع ارتباط برای پایداری سیستم."""
        return {
            "temp": 18.0,
            "humidity": 45.0,
            "wind_speed": 4.0,
            "turbulence": 0.12,
            "irradiance_raw": 400.0,
            "irradiance_effective": 380.0,
            "soiling_factor": 0.95,
            "precipitation": 0.0,
            "history_24h": [0.0]*6 + [200.0, 400.0, 600.0, 800.0, 600.0, 400.0, 200.0] + [0.0]*11,
            "timestamp": "FALLBACK"
        }
