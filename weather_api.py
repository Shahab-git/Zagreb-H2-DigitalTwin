#weather_api
# weather_api.py
import requests
import datetime
import numpy as np
from config import Config
import logging

logging.basicConfig(level=logging.INFO)


class WeatherProvider:
    def __init__(self):
        self.lat = Config.LOCATION["lat"]
        self.lon = Config.LOCATION["lon"]
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def fetch_current_data(self):
        """دریافت داده‌های زنده + اصلاح irradiance + پایداری سیستم"""

        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current_weather": True,
            "hourly": "temperature_2m,wind_speed_10m,shortwave_radiation",
            "timezone": "Europe/Zagreb",
            "forecast_days": 1
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            current = data.get('current_weather', {})
            hourly = data.get('hourly', {})

            # ⏱ ساعت فعلی
            now_hour = datetime.datetime.now().hour

            # 🌞 استخراج irradiance واقعی (اصلاح اصلی)
            if 'shortwave_radiation' in hourly:
                radiation_series = hourly['shortwave_radiation']

                # جلوگیری از out-of-range
                if len(radiation_series) > now_hour:
                    irradiance_now = radiation_series[now_hour]
                else:
                    irradiance_now = radiation_series[0]

                history = radiation_series[:24]
            else:
                irradiance_now = 50.0
                history = [50.0] * 24

            # 🧠 Anti-zero / Night / API glitch protection
            if irradiance_now is None or irradiance_now <= 0:
                irradiance_now = max(np.mean(history), 20.0)

            # 🌬️ Wind fallback
            wind_speed = current.get('windspeed', 4.5)
            if wind_speed is None:
                wind_speed = 4.5

            # 🌡️ Temperature fallback
            temp = current.get('temperature', 15.0)

            weather_packet = {
                "temp": float(temp),
                "wind_speed": float(wind_speed),
                "irradiance": float(irradiance_now),
                "history_24h": history
            }

            logging.info(
                f"📡 Weather Online (Zagreb): {irradiance_now:.1f} W/m2 | "
                f"{temp:.1f}°C | Wind {wind_speed:.1f} m/s"
            )

            return weather_packet

        except Exception as e:
            logging.warning(f"⚠️ API Error (Using Fallback): {e}")

            return {
                "temp": 15.0,
                "wind_speed": 4.5,
                "irradiance": 50.0,
                "history_24h": [50.0] * 24
            }