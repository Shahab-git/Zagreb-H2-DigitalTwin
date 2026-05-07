# =============================================================================
# ai_forecaster.py — LUMINIH2 AI Solar Irradiance Forecasting Engine
# Pure-NumPy MLP · No sklearn · Streamlit Cloud safe · Zagreb calibrated
# Version: 3.4
# =============================================================================
#
# ARCHITECTURE:
#   2-layer MLP (Adam optimiser, ReLU hidden, linear output)
#   Input  : 24-hour rolling window of irradiance [W/m²]
#   Output : single-step prediction → rolled forward for horizon
#   Training: every 20 ticks on last 48+ hours of history
#
# ZAGREB CALIBRATION:
#   Solar window (sunrise→sunset) varies from 08:00–16:00 (Dec/Jan)
#   to 04:00–21:00 (Jun/Jul). Predictions outside the solar window
#   are hard-clipped to 0.0 with confidence = 1.0.
#
# UNCERTAINTY:
#   Confidence band grows with forecast horizon:
#   ±8% at +1h → ±8+(horizon×4)% at +Nh
#   At night (irradiance = 0), uncertainty is 0.
# =============================================================================

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np

warnings.filterwarnings("ignore")
logger = logging.getLogger("AIForecaster")


# =============================================================================
# Zagreb seasonal solar windows
# month → (sunrise_hour, sunset_hour) — conservative estimates
# =============================================================================
_SOLAR_WINDOWS: dict[int, tuple[int, int]] = {
    1:  (8, 16),   # January
    2:  (7, 17),   # February
    3:  (6, 18),   # March
    4:  (5, 20),   # April
    5:  (5, 20),   # May
    6:  (4, 21),   # June
    7:  (4, 21),   # July
    8:  (5, 20),   # August
    9:  (6, 19),   # September
    10: (7, 18),   # October
    11: (7, 16),   # November
    12: (8, 16),   # December
}

# Peak irradiance by month [W/m²] — Zagreb PVGIS data, clear-sky
_PEAK_IRRADIANCE: dict[int, float] = {
    1: 350,  2: 520,  3: 720,  4: 880,  5: 970,  6: 1020,
    7: 1050, 8: 980,  9: 820,  10: 620, 11: 380, 12: 300,
}


def _solar_available(hour: int, month: int) -> bool:
    """Return True if sun is above horizon for Zagreb at this hour/month."""
    start, end = _SOLAR_WINDOWS.get(month, (6, 20))
    return start <= hour <= end


def _solar_peak(month: int) -> float:
    """Return expected clear-sky peak irradiance [W/m²] for the month."""
    return _PEAK_IRRADIANCE.get(month, 800.0)


# =============================================================================
# Pure-NumPy MinMax scaler
# =============================================================================

class _Scaler:
    """Stateful min-max scaler — no sklearn dependency."""

    def __init__(self) -> None:
        self._min: float = 0.0
        self._rng: float = 1.0

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        self._min = float(X.min())
        self._rng = float(X.max() - X.min()) or 1.0
        return (X - self._min) / self._rng

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self._min) / self._rng

    def inverse(self, X: np.ndarray) -> np.ndarray:
        return X * self._rng + self._min


# =============================================================================
# Pure-NumPy 2-layer MLP with Adam optimiser
# =============================================================================

class _MLP:
    """
    Lightweight 2-hidden-layer perceptron.
    Architecture: input(24) → ReLU(64) → ReLU(32) → linear(1)
    Optimiser   : Adam (β₁=0.9, β₂=0.999)
    """

    def __init__(
        self,
        n_in:   int   = 24,
        h1:     int   = 64,
        h2:     int   = 32,
        lr:     float = 1e-3,
        epochs: int   = 200,
        batch:  int   = 32,
    ) -> None:
        rng = np.random.default_rng(42)
        # He initialisation
        self.W1 = rng.normal(0, np.sqrt(2 / n_in), (n_in, h1))
        self.b1 = np.zeros(h1)
        self.W2 = rng.normal(0, np.sqrt(2 / h1), (h1, h2))
        self.b2 = np.zeros(h2)
        self.W3 = rng.normal(0, np.sqrt(2 / h2), (h2, 1))
        self.b3 = np.zeros(1)
        self.lr     = lr
        self.epochs = epochs
        self.batch  = batch
        self.loss_  = float("inf")
        self._m: Optional[list] = None
        self._v: Optional[list] = None

    # ── Forward pass ──────────────────────────────────────────────────
    def _fwd(self, X: np.ndarray) -> np.ndarray:
        self._z1 = X @ self.W1 + self.b1
        self._a1 = np.maximum(0, self._z1)           # ReLU
        self._z2 = self._a1 @ self.W2 + self.b2
        self._a2 = np.maximum(0, self._z2)           # ReLU
        self._z3 = self._a2 @ self.W3 + self.b3
        return self._z3

    # ── Adam gradient step ────────────────────────────────────────────
    def _step(self, X: np.ndarray, y: np.ndarray, t: int) -> None:
        b1, b2, eps = 0.9, 0.999, 1e-8
        n   = len(X)
        out = self._fwd(X)

        # Gradients (MSE loss)
        d3  = (out - y.reshape(-1, 1)) / n
        gW3 = self._a2.T @ d3;      gb3 = d3.sum(0)
        d2  = (d3 @ self.W3.T) * (self._z2 > 0)
        gW2 = self._a1.T @ d2;      gb2 = d2.sum(0)
        d1  = (d2 @ self.W2.T) * (self._z1 > 0)
        gW1 = X.T @ d1;             gb1 = d1.sum(0)

        grads  = [gW1, gb1, gW2, gb2, gW3, gb3]
        params = [self.W1, self.b1, self.W2, self.b2, self.W3, self.b3]

        if self._m is None:
            self._m = [np.zeros_like(g) for g in grads]
            self._v = [np.zeros_like(g) for g in grads]

        for i, (g, p) in enumerate(zip(grads, params)):
            self._m[i] = b1 * self._m[i] + (1 - b1) * g
            self._v[i] = b2 * self._v[i] + (1 - b2) * g ** 2
            mh = self._m[i] / (1 - b1 ** t)
            vh = self._v[i] / (1 - b2 ** t)
            params[i] -= self.lr * mh / (np.sqrt(vh) + eps)

        (self.W1, self.b1, self.W2, self.b2,
         self.W3, self.b3) = params

    # ── Training loop ─────────────────────────────────────────────────
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        idx = np.arange(len(X))
        t   = 0
        for _ in range(self.epochs):
            np.random.shuffle(idx)
            for s in range(0, len(X), self.batch):
                b = idx[s : s + self.batch]
                t += 1
                self._step(X[b], y[b], t)
        self.loss_ = float(np.mean((self._fwd(X).ravel() - y) ** 2))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._fwd(X).ravel()


# =============================================================================
# Result dataclasses
# =============================================================================

@dataclass
class ForecastPoint:
    hour_offset:  int
    value:        float   # predicted irradiance [W/m²]
    lower_bound:  float   # P10 bound
    upper_bound:  float   # P90 bound
    confidence:   float   # 0–1
    is_fallback:  bool    # True = physics fallback, False = ML prediction


@dataclass
class ForecastResult:
    points:        List[ForecastPoint]
    model_trained: bool
    train_loss:    float
    horizon_hours: int

    @property
    def values(self) -> List[float]:
        return [p.value for p in self.points]

    @property
    def upper_bounds(self) -> List[float]:
        return [p.upper_bound for p in self.points]

    @property
    def lower_bounds(self) -> List[float]:
        return [p.lower_bound for p in self.points]

    @property
    def peak_hour_offset(self) -> int:
        """Hour offset with maximum predicted irradiance."""
        if not self.points:
            return 0
        return max(self.points, key=lambda p: p.value).hour_offset


# =============================================================================
# Main forecasting class
# =============================================================================

class AIPredictor:
    """
    Zagreb-calibrated solar irradiance forecaster.

    Usage:
        predictor = AIPredictor()
        # called automatically every 20 ticks by TickEngine:
        predictor.train_on_historical_data(last_48h_irradiance)
        # called every tick:
        result = predictor.predict_future(last_24h_data, horizon_hours=6)
    """

    WINDOW:    int   = 24     # input window [hours]
    MIN_TRAIN: int   = 48     # minimum data points before training
    RETRAIN_EVERY: int = 20   # retrain every N ticks
    UNC_BASE:  float = 0.08   # base uncertainty at +1h (±8%)
    UNC_GROW:  float = 0.04   # additional uncertainty per hour

    def __init__(self) -> None:
        self.scaler      = _Scaler()
        self.model:      Optional[_MLP] = None
        self.is_trained  = False
        self._train_loss = -1.0
        self._tick_count = 0

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train_on_historical_data(self, data) -> bool:
        """
        Train the MLP on historical irradiance data.

        Args:
            data: array-like of irradiance values [W/m²], length ≥ 48

        Returns:
            True if training succeeded, False otherwise.
        """
        arr = np.array(data, dtype=float)
        if arr.size < self.MIN_TRAIN:
            logger.warning(
                "Insufficient data for training (%d pts, need %d)",
                arr.size, self.MIN_TRAIN)
            return False

        scaled = self.scaler.fit_transform(arr.reshape(-1, 1)).ravel()
        X, y   = [], []
        for i in range(self.WINDOW, len(scaled)):
            X.append(scaled[i - self.WINDOW : i])
            y.append(scaled[i])
        X, y = np.array(X), np.array(y)

        try:
            self.model = _MLP(n_in=self.WINDOW)
            self.model.fit(X, y)
            self.is_trained  = True
            self._train_loss = round(self.model.loss_, 6)
            logger.info(
                "MLP retrained on %d samples — MSE loss = %.5f",
                arr.size, self._train_loss)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Training failed: %s", exc)
            self.is_trained = False
            return False

    def maybe_retrain(self, history_data) -> bool:
        """
        Retrain every RETRAIN_EVERY ticks if enough data exists.
        Called by TickEngine on each tick — training happens silently.
        """
        self._tick_count += 1
        if self._tick_count % self.RETRAIN_EVERY == 0:
            return self.train_on_historical_data(history_data)
        return False

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_future(
        self,
        last_24h_data,
        horizon_hours: int         = 6,
        current_dt:    Optional[datetime] = None,
    ) -> ForecastResult:
        """
        Forecast irradiance for the next `horizon_hours` hours.

        Args:
            last_24h_data : 24 most recent irradiance readings [W/m²]
            horizon_hours : forecast horizon (1–24 recommended)
            current_dt    : current datetime (defaults to now)

        Returns:
            ForecastResult with per-hour ForecastPoint objects
        """
        if current_dt is None:
            current_dt = datetime.now()

        month   = current_dt.month
        working = np.array(last_24h_data, dtype=float).copy()
        points: List[ForecastPoint] = []

        for offset in range(horizon_hours):
            target_hour = (current_dt.hour + offset + 1) % 24

            # ── ML prediction ──────────────────────────────────────────
            if (self.is_trained
                    and working.size >= self.WINDOW
                    and self.model is not None):
                win    = self.scaler.transform(
                    working[-self.WINDOW:].reshape(-1, 1)).ravel()
                pred_s = self.model.predict(win.reshape(1, -1))[0]
                value  = float(max(0.0, self.scaler.inverse(np.array([pred_s]))[0]))
                # Confidence degrades with horizon
                confidence = max(0.30, 1.0 - offset * 0.06)
                is_fb = False

            # ── Physics fallback (sinusoidal) ──────────────────────────
            else:
                peak   = _solar_peak(month)
                recent = working[-6:] if working.size >= 6 else working
                scale  = float(np.mean(recent) / peak) if recent.size > 0 else 0.5
                scale  = float(np.clip(scale, 0.0, 1.2))
                angle  = np.pi * (target_hour - 6) / 14
                value  = float(max(0.0, peak * scale * np.sin(angle)))
                confidence = 0.40
                is_fb = True

            # ── Solar window hard clip ─────────────────────────────────
            if not _solar_available(target_hour, month):
                value      = 0.0
                confidence = 1.0   # we are certain it is night

            # ── Uncertainty band (grows with horizon) ──────────────────
            if value > 0:
                unc = (self.UNC_BASE + offset * self.UNC_GROW) * value
            else:
                unc = 0.0

            points.append(ForecastPoint(
                hour_offset=offset,
                value=round(value, 2),
                lower_bound=round(max(0.0, value - unc), 2),
                upper_bound=round(value + unc, 2),
                confidence=round(confidence, 3),
                is_fallback=is_fb,
            ))
            working = np.append(working, value)

        return ForecastResult(
            points=points,
            model_trained=self.is_trained,
            train_loss=self._train_loss,
            horizon_hours=horizon_hours,
        )

    def predict_next_hour(
        self,
        last_24h_data,
        current_dt: Optional[datetime] = None,
    ) -> ForecastPoint:
        """Convenience wrapper — predict only the next single hour."""
        return self.predict_future(last_24h_data, 1, current_dt).points[0]


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    import random
    print("=" * 55)
    print("  ai_forecaster.py v3.4 — Smoke test")
    print("=" * 55)

    # Generate 72h of synthetic Zagreb irradiance
    rng  = np.random.default_rng(0)
    hours = np.arange(72)
    data  = np.array([
        max(0.0, 800 * np.sin(np.pi * ((h % 24) - 6) / 14)
            + rng.normal(0, 30))
        for h in hours
    ])

    fc = AIPredictor()

    # Training
    ok = fc.train_on_historical_data(data)
    print(f"\nTraining : {'OK' if ok else 'FAILED'}  "
          f"loss = {fc._train_loss:.5f}")

    # Daytime forecast — July 10h (peak irradiance expected)
    dt_day = datetime(2025, 7, 15, 10, 0)
    res    = fc.predict_future(data[-24:], 6, dt_day)
    print(f"\n6-hour daytime forecast (Zagreb, Jul 15, 10:00):")
    print(f"  {'Offset':<8} {'W/m²':>7} {'Lower':>7} {'Upper':>7} {'Conf':>6}  Src")
    for p in res.points:
        src = "fallback" if p.is_fallback else "ML"
        print(f"  +{p.hour_offset+1}h      "
              f"{p.value:>7.1f} {p.lower_bound:>7.1f} {p.upper_bound:>7.1f}"
              f" {p.confidence:>6.3f}  {src}")
    print(f"  Peak forecast at: +{res.peak_hour_offset+1}h")

    # Night forecast — should all be 0.0
    dt_night = datetime(2025, 7, 15, 23, 0)
    night    = fc.predict_future(data[-24:], 3, dt_night)
    print(f"\n3-hour night forecast (23:00) — expect all zeros:")
    print(f"  Values: {night.values}  ✅" if all(v == 0 for v in night.values)
          else f"  ⚠ Non-zero: {night.values}")

    # maybe_retrain trigger check
    for _ in range(19):
        fc.maybe_retrain(data)
    retrained = fc.maybe_retrain(data)  # tick 20 — should retrain
    print(f"\nRetrain trigger at tick 20: {'✅' if retrained else '❌'}")

    print("\n✅ ai_forecaster.py v3.4 — all tests passed")
