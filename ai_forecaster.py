# =============================================================================
# ai_forecaster.py — LUMINIH2 AI Energy Forecasting Engine
# Pure NumPy MLP — zero external dependencies (Streamlit Cloud safe)
# Version: 3.3
# =============================================================================

import logging
import warnings
import random
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np

warnings.filterwarnings("ignore")
logger = logging.getLogger("AIForecaster")

# ---------------------------------------------------------------------------
# Zagreb seasonal solar window (month -> (start_hour, end_hour))
# ---------------------------------------------------------------------------
_SOLAR_WINDOWS = {
    1: (8, 16), 2: (7, 17), 3: (6, 18), 4: (5, 20),
    5: (5, 20), 6: (4, 21), 7: (4, 21), 8: (5, 20),
    9: (6, 19), 10: (7, 18), 11: (7, 16), 12: (8, 16),
}


def _solar_available(hour: int, month: int) -> bool:
    start, end = _SOLAR_WINDOWS.get(month, (6, 20))
    return start <= hour <= end


# ---------------------------------------------------------------------------
# Pure-NumPy MinMaxScaler
# ---------------------------------------------------------------------------
class _Scaler:
    def __init__(self):
        self._min = 0.0
        self._rng = 1.0

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        self._min = float(X.min())
        self._rng = float(X.max() - X.min()) or 1.0
        return (X - self._min) / self._rng

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self._min) / self._rng

    def inverse(self, X: np.ndarray) -> np.ndarray:
        return X * self._rng + self._min


# ---------------------------------------------------------------------------
# Pure-NumPy 2-layer MLP (Adam optimiser, ReLU hidden, linear output)
# ---------------------------------------------------------------------------
class _MLP:
    def __init__(self, n_in: int = 24, h1: int = 64, h2: int = 32,
                 lr: float = 1e-3, epochs: int = 200, batch: int = 32):
        rng = np.random.default_rng(42)
        self.W1 = rng.normal(0, np.sqrt(2 / n_in), (n_in, h1))
        self.b1 = np.zeros(h1)
        self.W2 = rng.normal(0, np.sqrt(2 / h1), (h1, h2))
        self.b2 = np.zeros(h2)
        self.W3 = rng.normal(0, np.sqrt(2 / h2), (h2, 1))
        self.b3 = np.zeros(1)
        self.lr = lr
        self.epochs = epochs
        self.batch = batch
        self.loss_ = float("inf")

    def _fwd(self, X):
        self._z1 = X @ self.W1 + self.b1
        self._a1 = np.maximum(0, self._z1)
        self._z2 = self._a1 @ self.W2 + self.b2
        self._a2 = np.maximum(0, self._z2)
        self._z3 = self._a2 @ self.W3 + self.b3
        return self._z3

    def _step(self, X, y, t):
        b1, b2, eps = 0.9, 0.999, 1e-8
        n = len(X)
        out = self._fwd(X)
        d3 = (out - y.reshape(-1, 1)) / n

        gW3 = self._a2.T @ d3
        gb3 = d3.sum(0)
        d2 = (d3 @ self.W3.T) * (self._z2 > 0)
        gW2 = self._a1.T @ d2
        gb2 = d2.sum(0)
        d1 = (d2 @ self.W2.T) * (self._z1 > 0)
        gW1 = X.T @ d1
        gb1 = d1.sum(0)

        if not hasattr(self, "_m"):
            self._m = [np.zeros_like(g) for g in [gW1, gb1, gW2, gb2, gW3, gb3]]
            self._v = [np.zeros_like(g) for g in [gW1, gb1, gW2, gb2, gW3, gb3]]

        grads = [gW1, gb1, gW2, gb2, gW3, gb3]
        params = [self.W1, self.b1, self.W2, self.b2, self.W3, self.b3]
        for i, (g, p) in enumerate(zip(grads, params)):
            self._m[i] = b1 * self._m[i] + (1 - b1) * g
            self._v[i] = b2 * self._v[i] + (1 - b2) * g ** 2
            mh = self._m[i] / (1 - b1 ** t)
            vh = self._v[i] / (1 - b2 ** t)
            params[i] -= self.lr * mh / (np.sqrt(vh) + eps)

        (self.W1, self.b1, self.W2, self.b2, self.W3, self.b3) = params

    def fit(self, X: np.ndarray, y: np.ndarray):
        idx = np.arange(len(X))
        t = 0
        for _ in range(self.epochs):
            np.random.shuffle(idx)
            for s in range(0, len(X), self.batch):
                b = idx[s:s + self.batch]
                t += 1
                self._step(X[b], y[b], t)
        out = self._fwd(X).ravel()
        self.loss_ = float(np.mean((out - y) ** 2))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._fwd(X).ravel()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class ForecastPoint:
    hour_offset: int
    value: float
    lower_bound: float
    upper_bound: float
    confidence: float
    is_fallback: bool


@dataclass
class ForecastResult:
    points: List[ForecastPoint]
    model_trained: bool
    train_loss: float
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


# ---------------------------------------------------------------------------
# Main forecaster
# ---------------------------------------------------------------------------
class AIPredictor:
    WINDOW = 24
    MIN_TRAIN = 48
    UNC_BASE = 0.08
    UNC_GROW = 0.04

    def __init__(self):
        self.scaler = _Scaler()
        self.model: Optional[_MLP] = None
        self.is_trained = False
        self._train_loss = -1.0

    def train_on_historical_data(self, data) -> bool:
        data = np.array(data, dtype=float)
        if data.size < self.MIN_TRAIN:
            logger.warning("Not enough data to train (%d pts)", data.size)
            return False
        scaled = self.scaler.fit_transform(data.reshape(-1, 1)).ravel()
        X, y = [], []
        for i in range(self.WINDOW, len(scaled)):
            X.append(scaled[i - self.WINDOW:i])
            y.append(scaled[i])
        X, y = np.array(X), np.array(y)
        try:
            self.model = _MLP(n_in=self.WINDOW)
            self.model.fit(X, y)
            self.is_trained = True
            self._train_loss = round(self.model.loss_, 6)
            logger.info("Trained on %d pts — loss=%.5f", data.size, self._train_loss)
            return True
        except Exception as e:
            logger.error("Training failed: %s", e)
            self.is_trained = False
            return False

    def predict_future(self, last_24h_data, horizon_hours: int = 1,
                       current_dt: Optional[datetime] = None) -> ForecastResult:
        if current_dt is None:
            current_dt = datetime.now()
        working = np.array(last_24h_data, dtype=float).copy()
        points = []
        for offset in range(horizon_hours):
            target_hour = (current_dt.hour + offset + 1) % 24
            if self.is_trained and working.size >= self.WINDOW and self.model is not None:
                win = self.scaler.transform(working[-self.WINDOW:].reshape(-1, 1)).ravel()
                pred_s = self.model.predict(win.reshape(1, -1))[0]
                value = float(max(0.0, self.scaler.inverse(np.array([pred_s]))[0]))
                confidence = max(0.3, 1.0 - offset * 0.05)
                is_fb = False
            else:
                recent = working[-3:] if working.size >= 3 else working
                base = float(np.mean(recent)) if recent.size > 0 else 50.0
                angle = np.pi * (target_hour - 6) / 14
                value = float(max(0.0, base * max(0.0, np.sin(angle))))
                confidence = 0.40
                is_fb = True

            if not _solar_available(target_hour, current_dt.month):
                value = 0.0
                confidence = 1.0

            unc = (self.UNC_BASE + offset * self.UNC_GROW) * value
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

    def predict_next_hour(self, last_24h_data,
                          current_dt: Optional[datetime] = None) -> ForecastPoint:
        return self.predict_future(last_24h_data, 1, current_dt).points[0]


# ---------------------------------------------------------------------------
# Smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    hours = np.arange(72)
    data = np.array([
        max(0.0, 600 * np.sin(np.pi * ((h % 24) - 6) / 14) + random.gauss(0, 30))
        for h in hours
    ])
    fc = AIPredictor()
    ok = fc.train_on_historical_data(data)
    print(f"Trained: {ok}  loss={fc._train_loss}")
    res = fc.predict_future(data[-24:], 6, datetime(2025, 7, 15, 10))
    for p in res.points:
        print(f"  +{p.hour_offset+1}h  {p.value:7.1f}  [{p.lower_bound:.1f}–{p.upper_bound:.1f}]  conf={p.confidence}")
    night = fc.predict_future(data[-24:], 2, datetime(2025, 7, 15, 23))
    print(f"Night: {night.values}  (expect [0.0, 0.0])")
    print("✅ ai_forecaster v3.3 OK")
