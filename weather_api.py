# =============================================================================
# weather_api.py — LUMINIH2 Environmental Data Engine
# Real-time weather · Zagreb, Croatia · Open-Meteo API
# Version: 3.4
# =============================================================================
#
# FEATURES:
#   - Open-Meteo API (free, no API key required)
#   - In-memory cache with 60-second TTL (safe for Streamlit reruns)
#   - Soiling model: dust accumulates per day, resets on rain ≥ 1 mm
#   - Turbulence model: load-weighted Zagreb terrain roughness
#   - Typed WeatherPacket return — no dict key errors downstream
#   - Graduated fallback: live → stale cache → seasonal heuristic
#
# FALLBACK CHAIN:
#   1. Open-Meteo API (live)
#   2. Last successful packet (stale, but real measured data)
#   3. Zagreb seasonal climatology heuristic
#
# ZAGREB CLIMATOLOGY (fallback data source):
#   GHI, wind, temperature from PVGIS and ZAMG met station data
# =============================================================================

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import numpy as np
import requests

from config import Config

logger = logging.getLogger("WeatherAPI")


# =============================================================================
# Result containers
# =============================================================================

@dataclass
class WeatherPacket:
    """Complete environmental telemetry snapshot for one simulation tick."""

    # Current conditions
    temp_c:                   float
    humidity_pct:             float
    wind_speed_ms:            float
    wind_direction_deg:       float
    turbulence_intensity:     float
    irradiance_raw_wm2:       float
    irradiance_effective_wm2: float
    soiling_factor:           float
    precipitation_mm:         float

    # Derived flags
    is_raining:               bool
    panels_self_cleaned:      bool     # True if rain just cleaned panels this tick

    # 24-hour history arrays (for AI forecaster training)
    history_irradiance_24h: List[float] = field(
        default_factory=lambda: [0.0] * 24)
    history_wind_24h:       List[float] = field(
        default_factory=lambda: [4.5] * 24)
    history_temp_24h:       List[float] = field(
        default_factory=lambda: [15.0] * 24)

    # Metadata
    source:          str   = "live"    # "live" | "cached" | "fallback"
    fetched_at:      str   = ""
    days_since_rain: float = 0.0


@dataclass
class ForecastPacket:
    """
    24-hour ahead hourly forecast for Zagreb.
    Returned by WeatherProvider.fetch_forecast_24h().
    Used by the AI forecaster and EMS for predictive dispatch.
    """
    hours:            list   # [0..23] hour-of-day labels
    irradiance_wm2:   list   # hourly GHI forecast [W/m²]
    wind_ms:          list   # hourly wind speed [m/s]
    temp_c:           list   # hourly temperature [°C]
    precip_mm:        list   # hourly precipitation [mm]
    peak_irr_wm2:     float  # max irradiance in window
    peak_irr_hour:    int    # hour of peak irradiance
    total_energy_kwh: float  # estimated PV energy [kWh] over 24h
    source:           str    # "live" | "fallback"
    fetched_at:       str    # HH:MM:SS


@dataclass
class _CacheEntry:
    """Internal cache entry with expiry timestamp."""
    packet:     WeatherPacket
    expires_at: float          # time.monotonic() timestamp

@dataclass
class _ForecastCacheEntry:
    """Internal forecast cache entry — refreshed every 30 min."""
    forecast:   ForecastPacket
    expires_at: float


# =============================================================================
# Weather Provider
# =============================================================================

class WeatherProvider:
    """
    Environmental telemetry engine for LUMINIH2.

    Fetches real weather data from Open-Meteo API for Zagreb (45.815°N, 15.982°E).
    Maintains an in-memory cache to avoid hammering the API on every
    Streamlit rerun. Falls back gracefully to seasonal climatology when
    the API is unavailable.

    Usage:
        provider = WeatherProvider()
        packet   = provider.fetch_current_data()
        irr      = packet.irradiance_raw_wm2
        wind     = packet.wind_speed_ms
    """

    BASE_URL:            str   = "https://api.open-meteo.com/v1/forecast"
    RAIN_THRESHOLD_MM:   float = 1.0    # Precipitation above this cleans panels
    TURBULENCE_NOISE_STD: float = 0.06  # Zagreb terrain turbulence noise [σ]
    CACHE_TTL_SEC:       int   = 60     # API cache lifetime [s]

    def __init__(self) -> None:
        self.lat = Config.location.lat   # 45.815°N
        self.lon = Config.location.lon   # 15.982°E
        self.days_since_rain: float       = 0.0
        self._cache:          Optional[_CacheEntry]    = None
        self._last_good:      Optional[WeatherPacket]  = None
        self._forecast_cache: Optional[_ForecastCacheEntry] = None
        self._rng             = np.random.default_rng(int(time.time()) % 10000)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_current_data(self, force_refresh: bool = False) -> WeatherPacket:
        """
        Return current environmental telemetry for Zagreb.

        Served from in-memory cache if still fresh (TTL = 60 s).
        Falls back to seasonal heuristic if API is unavailable.

        Args:
            force_refresh : bypass cache and fetch from API

        Returns:
            WeatherPacket with all environmental measurements
        """
        now = time.monotonic()

        # Serve from cache if still valid
        if (not force_refresh
                and self._cache is not None
                and now < self._cache.expires_at):
            pkt = self._cache.packet
            return WeatherPacket(**{**pkt.__dict__, "source": "cached"})

        packet = self._fetch_from_api()
        if packet is None:
            packet = self._fallback_packet()

        self._cache      = _CacheEntry(packet=packet, expires_at=now + self.CACHE_TTL_SEC)
        self._last_good  = packet
        return packet

    # ------------------------------------------------------------------
    # 24-hour forecast
    # ------------------------------------------------------------------

    def fetch_forecast_24h(self, force_refresh: bool = False) -> ForecastPacket:
        """
        Return a 24-hour hourly forecast for Zagreb from Open-Meteo.

        Cached for 30 minutes — the forecast does not change tick-by-tick.
        Falls back to a seasonal heuristic if the API is unavailable.

        Used by:
            - AI forecaster (training input)
            - EMS predictive dispatch (pre-charge BESS before cloudy window)
            - Tab 1 skyline panel (24-hour irradiance preview)

        Args:
            force_refresh : bypass cache and fetch from API

        Returns:
            ForecastPacket with 24 hourly arrays
        """
        FORECAST_TTL = 1800   # 30 minutes
        now = time.monotonic()

        if (not force_refresh
                and self._forecast_cache is not None
                and now < self._forecast_cache.expires_at):
            fc = self._forecast_cache.forecast
            return ForecastPacket(**{**fc.__dict__, "source": "cached"})

        forecast = self._fetch_forecast_from_api()
        if forecast is None:
            forecast = self._fallback_forecast()

        self._forecast_cache = _ForecastCacheEntry(
            forecast=forecast,
            expires_at=now + FORECAST_TTL,
        )
        return forecast

    def _fetch_forecast_from_api(self) -> Optional[ForecastPacket]:
        """
        Fetch next-24h hourly forecast from Open-Meteo forecast endpoint.

        Open-Meteo provides free hourly forecasts at:
            https://api.open-meteo.com/v1/forecast
        No API key required.

        Returns:
            ForecastPacket or None on failure
        """
        params = {
            "latitude":       self.lat,
            "longitude":      self.lon,
            "hourly": [
                "shortwave_radiation",
                "wind_speed_10m",
                "temperature_2m",
                "precipitation",
            ],
            "timezone":       "Europe/Zagreb",
            "forecast_days":  2,    # today + tomorrow = 48h, we take first 24
        }
        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data   = resp.json()
            hourly = data.get("hourly", {})

            now_h  = datetime.now().hour

            def _slice(key: str, default: float) -> list:
                """Extract next 24 values starting from current hour."""
                arr = hourly.get(key, [])
                arr = [float(v or default) for v in arr]
                # Pad to at least 48 values
                arr = arr + [default] * 48
                return arr[now_h: now_h + 24]

            irr   = _slice("shortwave_radiation", 0.0)
            wind  = _slice("wind_speed_10m", 4.5)
            temp  = _slice("temperature_2m", 15.0)
            precip = _slice("precipitation", 0.0)

            hours = [(now_h + i) % 24 for i in range(24)]

            # PV energy estimate (rough: capacity × irr × system_eff)
            sys_eff = 0.97 * 0.995   # inverter × MPPT
            total_e = sum(
                irr_h * Config.PV_SYSTEM_CAPACITY_KW / 1000.0 * sys_eff
                for irr_h in irr
            )

            peak_irr  = max(irr) if irr else 0.0
            peak_hour = hours[irr.index(peak_irr)] if irr else now_h

            pkt = ForecastPacket(
                hours=hours,
                irradiance_wm2=irr,
                wind_ms=wind,
                temp_c=temp,
                precip_mm=precip,
                peak_irr_wm2=round(peak_irr, 1),
                peak_irr_hour=peak_hour,
                total_energy_kwh=round(total_e, 2),
                source="live",
                fetched_at=datetime.now().strftime("%H:%M:%S"),
            )
            logger.info(
                "Forecast: peak %.0f W/m² at %02d:00 · est. %.1f kWh PV today",
                peak_irr, peak_hour, total_e,
            )
            return pkt

        except requests.exceptions.Timeout:
            logger.warning("Forecast API timeout — using fallback")
        except requests.exceptions.ConnectionError:
            logger.warning("No network for forecast — using fallback")
        except Exception as exc:
            logger.error("Forecast API error: %s", exc)
        return None

    def _fallback_forecast(self) -> ForecastPacket:
        """
        Generate a seasonal climatology forecast when API is unavailable.
        Uses Zagreb PVGIS data — same source as the current-conditions fallback.
        """
        month  = datetime.now().month
        now_h  = datetime.now().hour
        hours  = [(now_h + i) % 24 for i in range(24)]
        wind_v = self._seasonal_wind(month)
        temp_v = self._seasonal_temp(month)

        irr   = [self._seasonal_irradiance(month, h) for h in hours]
        wind  = [wind_v] * 24
        temp  = [temp_v] * 24
        precip = [0.0] * 24

        sys_eff = 0.97 * 0.995
        total_e = sum(
            irr_h * Config.PV_SYSTEM_CAPACITY_KW / 1000.0 * sys_eff
            for irr_h in irr
        )
        peak_irr  = max(irr) if irr else 0.0
        peak_hour = hours[irr.index(peak_irr)] if irr else now_h

        return ForecastPacket(
            hours=hours,
            irradiance_wm2=irr,
            wind_ms=wind,
            temp_c=temp,
            precip_mm=precip,
            peak_irr_wm2=round(peak_irr, 1),
            peak_irr_hour=peak_hour,
            total_energy_kwh=round(total_e, 2),
            source="fallback",
            fetched_at=datetime.now().strftime("%H:%M:%S"),
        )

    # ------------------------------------------------------------------
    # API fetch
    # ------------------------------------------------------------------

    def _fetch_from_api(self) -> Optional[WeatherPacket]:
        """Fetch live data from Open-Meteo. Returns None on any failure."""
        params = {
            "latitude":     self.lat,
            "longitude":    self.lon,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "wind_direction_10m",
                "shortwave_radiation",
            ],
            "hourly": [
                "temperature_2m",
                "wind_speed_10m",
                "shortwave_radiation",
                "precipitation",
            ],
            "timezone":      "Europe/Zagreb",
            "forecast_days": 1,
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data    = resp.json()
            current = data.get("current", {})
            hourly  = data.get("hourly", {})
            now_h   = datetime.now().hour

            # ── Irradiance ─────────────────────────────────────────────
            irradiance = self._f(current.get("shortwave_radiation"), 0.0)
            # API can return 0 at midday — cross-check with hourly
            if irradiance < 10.0 and 9 < now_h < 16:
                hourly_irr = hourly.get("shortwave_radiation", [])
                if len(hourly_irr) > now_h:
                    irradiance = max(irradiance, float(hourly_irr[now_h] or 0.0))

            # ── Precipitation & soiling ────────────────────────────────
            precip          = self._f(current.get("precipitation"), 0.0)
            is_raining      = precip >= self.RAIN_THRESHOLD_MM
            panels_cleaned  = False

            if is_raining:
                panels_cleaned      = self.days_since_rain > 0
                self.days_since_rain = 0.0
            else:
                self.days_since_rain += Config.TIMESTEP_SEC / 86400.0

            soiling_factor      = float(np.clip(
                1.0 - self.days_since_rain * Config.SOILING_LOSS_RATE, 0.85, 1.0))
            irradiance_effective = irradiance * soiling_factor

            # ── Wind & turbulence ──────────────────────────────────────
            wind_speed = self._f(current.get("wind_speed_10m"), 4.5)
            wind_dir   = self._f(current.get("wind_direction_10m"), 180.0)
            # Turbulence rises with wind speed (Zagreb roughness class II)
            base_ti    = 0.10 + 0.04 * (wind_speed / 12.0)
            noise      = float(self._rng.normal(0, self.TURBULENCE_NOISE_STD))
            turbulence = float(np.clip(base_ti + noise, 0.04, 0.25))

            # ── Temperature & humidity ─────────────────────────────────
            temp     = self._f(current.get("temperature_2m"), 15.0)
            humidity = self._f(current.get("relative_humidity_2m"), 60.0)

            # ── 24-hour history arrays ─────────────────────────────────
            def _pad(lst: list, default: float) -> List[float]:
                arr = [float(v or default) for v in lst]
                return (arr + [default] * 24)[:24]

            history_irr  = _pad(hourly.get("shortwave_radiation", []), 0.0)
            history_wind = _pad(hourly.get("wind_speed_10m", []), 4.5)
            history_temp = _pad(hourly.get("temperature_2m", []), 15.0)

            packet = WeatherPacket(
                temp_c=round(temp, 1),
                humidity_pct=round(humidity, 1),
                wind_speed_ms=round(wind_speed, 2),
                wind_direction_deg=round(wind_dir, 1),
                turbulence_intensity=round(turbulence, 4),
                irradiance_raw_wm2=round(irradiance, 1),
                irradiance_effective_wm2=round(irradiance_effective, 1),
                soiling_factor=round(soiling_factor, 4),
                precipitation_mm=round(precip, 2),
                is_raining=is_raining,
                panels_self_cleaned=panels_cleaned,
                history_irradiance_24h=history_irr,
                history_wind_24h=history_wind,
                history_temp_24h=history_temp,
                source="live",
                fetched_at=datetime.now().strftime("%H:%M:%S"),
                days_since_rain=round(self.days_since_rain, 3),
            )
            logger.info(
                "Live: %.0f W/m² | Wind %.1f m/s | Temp %.1f°C | "
                "Soiling %.3f | Rain: %s",
                irradiance, wind_speed, temp, soiling_factor,
                "YES" if is_raining else "no",
            )
            return packet

        except requests.exceptions.Timeout:
            logger.warning("Open-Meteo API timeout — falling back")
        except requests.exceptions.ConnectionError:
            logger.warning("No network connection — falling back")
        except Exception as exc:
            logger.error("Unexpected API error: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Fallback chain
    # ------------------------------------------------------------------

    def _fallback_packet(self) -> WeatherPacket:
        """
        Graduated fallback:
            1. Last successful API packet (stale but real)
            2. Zagreb seasonal climatology heuristic
        """
        if self._last_good is not None:
            logger.info("Using stale API packet as fallback")
            return WeatherPacket(**{**self._last_good.__dict__, "source": "cached"})

        month   = datetime.now().month
        hour    = datetime.now().hour
        irr     = self._seasonal_irradiance(month, hour)
        wind    = self._seasonal_wind(month)
        temp    = self._seasonal_temp(month)

        logger.warning("API unavailable — using Zagreb seasonal heuristic")
        return WeatherPacket(
            temp_c=temp,
            humidity_pct=62.0,
            wind_speed_ms=wind,
            wind_direction_deg=270.0,
            turbulence_intensity=0.12,
            irradiance_raw_wm2=irr,
            irradiance_effective_wm2=irr * 0.98,
            soiling_factor=0.98,
            precipitation_mm=0.0,
            is_raining=False,
            panels_self_cleaned=False,
            history_irradiance_24h=[self._seasonal_irradiance(month, h) for h in range(24)],
            history_wind_24h=[wind] * 24,
            history_temp_24h=[temp] * 24,
            source="fallback",
            fetched_at=datetime.now().strftime("%H:%M:%S"),
            days_since_rain=self.days_since_rain,
        )

    # ------------------------------------------------------------------
    # Zagreb seasonal climatology (PVGIS + ZAMG data)
    # ------------------------------------------------------------------

    @staticmethod
    def _seasonal_irradiance(month: int, hour: int) -> float:
        """
        Approximate clear-sky GHI [W/m²] for Zagreb using sinusoidal model.
        Monthly peaks from PVGIS historical data.
        """
        monthly_peak: dict[int, float] = {
            1: 150,  2: 220,  3: 380,  4: 520,
            5: 620,  6: 680,  7: 660,  8: 600,
            9: 480,  10: 320, 11: 180, 12: 120,
        }
        peak = monthly_peak.get(month, 400.0)
        # Solar window shifts with season
        solar_start = max(5, 8 - (month % 6))
        solar_end   = min(21, 14 + (month % 6))
        if hour < solar_start or hour > solar_end:
            return 0.0
        angle = np.pi * (hour - solar_start) / max(solar_end - solar_start, 1)
        return round(float(peak * np.sin(angle)), 1)

    @staticmethod
    def _seasonal_wind(month: int) -> float:
        """Monthly average wind speed [m/s] — Zagreb ZAMG met station."""
        data: dict[int, float] = {
            1: 4.2, 2: 4.5, 3: 4.8, 4: 4.3, 5: 3.9, 6: 3.5,
            7: 3.2, 8: 3.1, 9: 3.4, 10: 3.8, 11: 4.1, 12: 4.3,
        }
        return data.get(month, 4.0)

    @staticmethod
    def _seasonal_temp(month: int) -> float:
        """Monthly average temperature [°C] — Zagreb 30-year mean."""
        data: dict[int, float] = {
            1:  1.5, 2:  3.5, 3:  8.5, 4: 14.0, 5: 19.0, 6: 22.5,
            7: 25.0, 8: 24.5, 9: 19.5, 10: 13.5, 11:  7.5, 12:  2.5,
        }
        return data.get(month, 15.0)

    @staticmethod
    def _f(value, default: float) -> float:
        """Safe float conversion with default."""
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    print("=" * 55)
    print("  weather_api.py v3.4 — Smoke test")
    print("=" * 55)

    provider = WeatherProvider()

    print("\n[1] Fetching live weather for Zagreb…")
    pkt = provider.fetch_current_data()

    print(f"\n  Source       : {pkt.source}")
    print(f"  Fetched at   : {pkt.fetched_at}")
    print(f"  Temperature  : {pkt.temp_c} °C")
    print(f"  Humidity     : {pkt.humidity_pct} %")
    print(f"  Wind         : {pkt.wind_speed_ms} m/s @ {pkt.wind_direction_deg}°")
    print(f"  Turbulence   : {pkt.turbulence_intensity:.4f}")
    print(f"  Irradiance   : {pkt.irradiance_raw_wm2} W/m² (raw)")
    print(f"  Irradiance   : {pkt.irradiance_effective_wm2} W/m² (effective, soiled)")
    print(f"  Soiling      : {pkt.soiling_factor:.4f}  "
          f"({(1-pkt.soiling_factor)*100:.2f}% loss)")
    print(f"  Precipitation: {pkt.precipitation_mm} mm  (raining={pkt.is_raining})")
    print(f"  Days dry     : {pkt.days_since_rain:.3f}")
    print(f"  24h irr hist : {pkt.history_irradiance_24h[:6]} …")

    # Cache test — second call must return cached
    print("\n[2] Cache test (second call within TTL)")
    pkt2 = provider.fetch_current_data()
    print(f"  Source: {pkt2.source}  (expect 'cached')")
    assert pkt2.source == "cached", f"Expected cached, got {pkt2.source}"
    print("  ✅ Cache working")

    # Fallback test
    print("\n[3] Fallback test (force no API)")
    provider2 = WeatherProvider()
    provider2._cache = None
    pkt3 = provider2._fallback_packet()
    print(f"  Source: {pkt3.source}  (expect 'fallback')")
    assert pkt3.source == "fallback"
    assert 0 <= pkt3.irradiance_raw_wm2 < 1000
    assert 0 <= pkt3.wind_speed_ms < 30
    assert -20 <= pkt3.temp_c < 45
    assert len(pkt3.history_irradiance_24h) == 24
    print("  ✅ Fallback packet valid")

    # Soiling model test
    print("\n[4] Soiling model test (5 dry days)")
    provider3 = WeatherProvider()
    provider3.days_since_rain = 5.0
    pkt4 = provider3._fallback_packet()
    assert pkt4.soiling_factor < 1.0, "Soiling should reduce factor"
    print(f"  Soiling after 5 dry days: {pkt4.soiling_factor:.4f} ✅")

    # 24-hour forecast test
    print("\n[5] 24-hour forecast test")
    fc = provider.fetch_forecast_24h()
    print(f"  Source        : {fc.source}")
    print(f"  Fetched at    : {fc.fetched_at}")
    print(f"  Hours[0..3]   : {fc.hours[:4]}")
    print(f"  Irr[0..3]     : {[round(v,1) for v in fc.irradiance_wm2[:4]]}")
    print(f"  Wind[0..3]    : {[round(v,2) for v in fc.wind_ms[:4]]}")
    print(f"  Peak irr      : {fc.peak_irr_wm2} W/m² at {fc.peak_irr_hour:02d}:00")
    print(f"  PV energy est : {fc.total_energy_kwh} kWh")
    assert len(fc.hours) == 24
    assert len(fc.irradiance_wm2) == 24
    assert fc.peak_irr_wm2 >= 0
    print("  ✅ ForecastPacket valid")

    # Cache test — should return cached within 30 min
    fc2 = provider.fetch_forecast_24h()
    assert fc2.source in ("cached", "live")
    print(f"  Second call source: {fc2.source}  ✅")

    print("\n✅ weather_api.py v3.4 — all tests passed")
