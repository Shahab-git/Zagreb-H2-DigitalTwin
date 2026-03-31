# weather_api.py
# High-Fidelity Environmental Data Engine (Zagreb Hub)
# Version: 3.0 (Industrial Realism)

import requests
import datetime
import numpy as np
from config import Config
import logging

logging.basicConfig(level=logging.INFO)


class WeatherProvider:
    """
    Advanced Environmental Engine providing real-time telemetry for
    Solar Irradiance, Wind Turbulence, and Soiling Impact.
    """

    def __init__(self):
        self.lat = Config.LOCATION["lat"]
        self.lon = Config.LOCATION["lon"]
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        # Track days since last rain to calculate Soiling Loss
        self.days_since_rain = 0

    def fetch_current_data(self):
        """Fetches live telemetry + calculates environmental degradation factors."""

        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m",
                        "shortwave_radiation"],
            "hourly": ["temperature_2m", "wind_speed_10m", "shortwave_radiation", "precipitation"],
            "timezone": "Europe/Berlin",  # Zagreb/Central Europe
            "forecast_days": 1
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            current = data.get('current', {})
            hourly = data.get('hourly', {})

            # ⏱️ Synchronize with current hour
            now_hour = datetime.datetime.now().hour

            # --- 🌞 Solar Irradiance Logic ---
            irradiance = current.get('shortwave_radiation', 0.0)
            # API Glitch / Night Protection: If 0 at noon or None, use 1-hour lookahead/fallback
            if irradiance is None or (10 < now_hour < 15 and irradiance < 10):
                irradiance = hourly.get('shortwave_radiation', [50.0])[now_hour]

            # --- 🌧️ Soiling & Rain Logic (Industrial Realism) ---
            precip = current.get('precipitation', 0.0)
            if precip > 1.0:  # Significant rain cleans the panels
                self.days_since_rain = 0
            else:
                self.days_since_rain += (Config.TIMESTEP_SEC / 86400)  # Increment day fraction

            # Calculate current soiling factor (e.g., 0.98 = 2% loss)
            soiling_factor = max(0.85, 1.0 - (self.days_since_rain * Config.SOILING_LOSS_RATE))

            # --- 🌬️ Wind & Turbulence ---
            wind_speed = current.get('wind_speed_10m', 4.5)
            # Synthetic Turbulence Intensity (Realistic variation for Zagreb terrain)
            turbulence = Config.TURBULENCE_INTENSITY_LIMIT * (1 + 0.1 * np.random.randn())

            # --- 🌡️ Temperature & Humidity ---
            temp = current.get('temperature_2m', 15.0)
            humidity = current.get('relative_humidity_2m', 50.0)

            weather_packet = {
                "temp": float(temp),
                "humidity": float(humidity),
                "wind_speed": float(wind_speed),
                "turbulence": float(turbulence),
                "irradiance_raw": float(irradiance),
                "irradiance_effective": float(irradiance * soiling_factor),
                "soiling_factor": float(soiling_factor),
                "precipitation": float(precip),
                "history_24h": hourly.get('shortwave_radiation', [0.0] * 24)
            }

            logging.info(
                f"📡 Environmental Telemetry (Zagreb): {irradiance:.1f} W/m2 | "
                f"Soiling: {soiling_factor:.3f} | Temp: {temp:.1f}°C"
            )

            return weather_packet

        except Exception as e:
            logging.error(f"⚠️ Environmental API Failure: {e}")
            # Safe Industrial Fallback
            return {
                "temp": 15.0,
                "humidity": 50.0,
                "wind_speed": 4.5,
                "turbulence": 0.12,
                "irradiance_raw": 50.0,
                "irradiance_effective": 48.0,
                "soiling_factor": 0.98,
                "precipitation": 0.0,
                "history_24h": [50.0] * 24
            }
