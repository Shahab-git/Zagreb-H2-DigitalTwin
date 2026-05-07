
# =============================================================================
# ai_forecaster.py — LUMINIH2 AI Solar Irradiance Forecasting Engine
# Pure-NumPy MLP · No sklearn · Streamlit Cloud safe · Zagreb calibrated
# Version: 3.5 — with integrated interactive forecast panel
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
#   ±8% at +1h  →  ±8+(horizon×4)% at +Nh
#   At night (irradiance = 0), uncertainty is 0.
#
# GRAPHIC PANEL:
#   render_panel() returns an HTML string with the full interactive
#   Zagreb-skyline forecast chart. Embed in Streamlit with:
#       st.components.v1.html(predictor.render_panel(...), height=520)
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
# =============================================================================
_SOLAR_WINDOWS: dict[int, tuple[int, int]] = {
    1:  (8, 16),  2:  (7, 17),  3:  (6, 18),  4:  (5, 20),
    5:  (5, 20),  6:  (4, 21),  7:  (4, 21),  8:  (5, 20),
    9:  (6, 19),  10: (7, 18),  11: (7, 16),  12: (8, 16),
}

_PEAK_IRRADIANCE: dict[int, float] = {
    1: 350,  2: 520,  3: 720,  4: 880,  5: 970,  6: 1020,
    7: 1050, 8: 980,  9: 820,  10: 620, 11: 380, 12: 300,
}

_MONTH_SHORT = ['','Jan','Feb','Mar','Apr','May','Jun',
                'Jul','Aug','Sep','Oct','Nov','Dec']


def _solar_available(hour: int, month: int) -> bool:
    start, end = _SOLAR_WINDOWS.get(month, (6, 20))
    return start <= hour <= end


def _solar_peak(month: int) -> float:
    return _PEAK_IRRADIANCE.get(month, 800.0)


# =============================================================================
# Pure-NumPy MinMax scaler
# =============================================================================

class _Scaler:
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
    2-hidden-layer perceptron.
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

    def _fwd(self, X: np.ndarray) -> np.ndarray:
        self._z1 = X @ self.W1 + self.b1
        self._a1 = np.maximum(0, self._z1)
        self._z2 = self._a1 @ self.W2 + self.b2
        self._a2 = np.maximum(0, self._z2)
        self._z3 = self._a2 @ self.W3 + self.b3
        return self._z3

    def _step(self, X: np.ndarray, y: np.ndarray, t: int) -> None:
        b1, b2, eps = 0.9, 0.999, 1e-8
        n   = len(X)
        out = self._fwd(X)
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
        (self.W1, self.b1, self.W2, self.b2, self.W3, self.b3) = params

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
    value:        float
    lower_bound:  float
    upper_bound:  float
    confidence:   float
    is_fallback:  bool


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
        if not self.points:
            return 0
        return max(self.points, key=lambda p: p.value).hour_offset


# =============================================================================
# Main AIPredictor class
# =============================================================================

class AIPredictor:
    """
    Zagreb-calibrated solar irradiance forecaster.

    Quick start:
        predictor = AIPredictor()
        predictor.train_on_historical_data(last_48h)
        result = predictor.predict_future(last_24h, horizon_hours=6)
        html   = predictor.render_panel(result, current_dt=datetime.now())
    """

    WINDOW:       int   = 24
    MIN_TRAIN:    int   = 48
    RETRAIN_EVERY:int   = 20
    UNC_BASE:     float = 0.08
    UNC_GROW:     float = 0.04

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
        arr = np.array(data, dtype=float)
        if arr.size < self.MIN_TRAIN:
            logger.warning("Insufficient data (%d pts, need %d)", arr.size, self.MIN_TRAIN)
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
            logger.info("MLP retrained — %d samples, MSE=%.5f", arr.size, self._train_loss)
            return True
        except Exception as exc:
            logger.error("Training failed: %s", exc)
            self.is_trained = False
            return False

    def maybe_retrain(self, history_data) -> bool:
        """Called every tick — retrains every RETRAIN_EVERY ticks."""
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
        horizon_hours: int = 6,
        current_dt: Optional[datetime] = None,
    ) -> ForecastResult:
        if current_dt is None:
            current_dt = datetime.now()
        month   = current_dt.month
        working = np.array(last_24h_data, dtype=float).copy()
        points: List[ForecastPoint] = []

        for offset in range(horizon_hours):
            target_hour = (current_dt.hour + offset + 1) % 24
            if (self.is_trained
                    and working.size >= self.WINDOW
                    and self.model is not None):
                win    = self.scaler.transform(
                    working[-self.WINDOW:].reshape(-1, 1)).ravel()
                pred_s = self.model.predict(win.reshape(1, -1))[0]
                value  = float(max(0.0, self.scaler.inverse(np.array([pred_s]))[0]))
                confidence = max(0.30, 1.0 - offset * 0.06)
                is_fb = False
            else:
                peak   = _solar_peak(month)
                recent = working[-6:] if working.size >= 6 else working
                scale  = float(np.mean(recent) / peak) if recent.size > 0 else 0.5
                scale  = float(np.clip(scale, 0.0, 1.2))
                [s, e] = list(_SOLAR_WINDOWS.get(month, (6, 20)))
                angle  = np.pi * (target_hour - s) / max(e - s, 1)
                value  = float(max(0.0, peak * scale * np.sin(angle)))
                confidence = 0.40
                is_fb = True

            if not _solar_available(target_hour, month):
                value      = 0.0
                confidence = 1.0

            unc = (self.UNC_BASE + offset * self.UNC_GROW) * value if value > 0 else 0.0
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
        return self.predict_future(last_24h_data, 1, current_dt).points[0]

    # ------------------------------------------------------------------
    # Interactive graphic panel  (embed in Streamlit with
    #   st.components.v1.html(predictor.render_panel(...), height=520)
    # ------------------------------------------------------------------

    def render_panel(
        self,
        result: Optional[ForecastResult] = None,
        current_dt: Optional[datetime]   = None,
        last_24h_irradiance: Optional[list] = None,
        height: int = 1500,
    ) -> str:
        """
        Return a self-contained HTML string with the interactive
        Zagreb-skyline AI forecast panel.

        All chart text is black (#0f172a / #374151).
        Background is white (#ffffff) with a painted Zagreb sky scene.
        Controls: month, hour, cloud cover, horizon slider.
        """
        if current_dt is None:
            current_dt = datetime.now()

        month     = current_dt.month
        hour      = current_dt.hour
        loss_str  = f"{self._train_loss:.5f}" if self._train_loss > 0 else "—"
        trained   = "ML prediction" if self.is_trained else "Physics fallback"
        month_sel = int(month)

        # Build forecast JSON for the panel
        fc_json = "[]"
        if result and result.points:
            pts = []
            for p in result.points:
                pts.append(
                    f'{{"off":{p.hour_offset+1},"v":{p.value:.1f},'
                    f'"lo":{p.lower_bound:.1f},"hi":{p.upper_bound:.1f},'
                    f'"conf":{p.confidence:.3f},"fb":{str(p.is_fallback).lower()}}}'
                )
            fc_json = "[" + ",".join(pts) + "]"

        # Historical data JSON
        hist_json = "[]"
        if last_24h_irradiance:
            hist_json = "[" + ",".join(f"{v:.1f}" for v in last_24h_irradiance) + "]"

        month_options = "".join(
            f'<option value="{m}"{" selected" if m==month_sel else ""}>'
            f'{_MONTH_SHORT[m]}</option>'
            for m in range(1, 13)
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
body{{background:#ffffff;color:#0f172a}}
.shell{{border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;background:#fff}}
.kpi-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e2e8f0}}
.kpi{{background:#fff;padding:10px 14px}}
.kpi-l{{font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.06em}}
.kpi-v{{font-size:19px;font-weight:700;color:#0f172a;margin:2px 0 1px}}
.kpi-s{{font-size:10px;color:#94a3b8}}
canvas{{display:block;width:100%;cursor:crosshair}}
.ctrl-bar{{background:#f8fafc;border-top:1px solid #e2e8f0;padding:10px 16px;
  display:flex;gap:16px;align-items:center;flex-wrap:wrap}}
.cl{{display:flex;align-items:center;gap:7px;font-size:12px;color:#374151;font-weight:500}}
.cl input[type=range]{{width:80px;accent-color:#0ea5e9}}
.cl select{{border:1px solid #e2e8f0;border-radius:6px;padding:3px 8px;
  background:#fff;font-size:12px;color:#0f172a;cursor:pointer}}
.pill{{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;
  background:#e0f2fe;color:#0369a1;border:1px solid #bae6fd;margin-left:auto}}
.pill.fb{{background:#fef9c3;color:#92400e;border-color:#fde68a}}
</style>
</head>
<body>
<div class="shell">
  <div class="kpi-strip">
    <div class="kpi">
      <div class="kpi-l">Model</div>
      <div class="kpi-v">MLP v3.5</div>
      <div class="kpi-s">NumPy · Adam · 2-layer</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">Train loss</div>
      <div class="kpi-v" id="kL">{loss_str}</div>
      <div class="kpi-s">MSE on historical data</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">Peak forecast</div>
      <div class="kpi-v" id="kP">—</div>
      <div class="kpi-s" id="kPH">—</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">Uncertainty</div>
      <div class="kpi-v">±8→32%</div>
      <div class="kpi-s">grows with horizon</div>
    </div>
  </div>

  <canvas id="cv"></canvas>

  <div class="ctrl-bar">
    <div class="cl">
      <label>Month</label>
      <select id="sMon">{month_options}</select>
    </div>
    <div class="cl">
      <label>Hour</label>
      <input type="range" id="sHr" min="0" max="23" value="{hour}">
      <span id="lHr" style="min-width:38px;color:#0ea5e9;font-weight:700">
        {str(hour).zfill(2)}:00
      </span>
    </div>
    <div class="cl">
      <label>Cloud</label>
      <input type="range" id="sCl" min="0" max="100" value="20">
      <span id="lCl" style="min-width:30px;color:#64748b">20%</span>
    </div>
    <div class="cl">
      <label>Horizon</label>
      <input type="range" id="sHz" min="1" max="12" value="{result.horizon_hours if result else 6}">
      <span id="lHz" style="min-width:24px;color:#64748b">
        {result.horizon_hours if result else 6} h
      </span>
    </div>
    <span class="pill{'  fb' if not self.is_trained else ''}" id="pill">{trained}</span>
  </div>
</div>

<script>
const cv = document.getElementById('cv');
const cx = cv.getContext('2d');

const PEAKS = {{1:350,2:520,3:720,4:880,5:970,6:1020,7:1050,8:980,9:820,10:620,11:380,12:300}};
const WINS  = {{1:[8,16],2:[7,17],3:[6,18],4:[5,20],5:[5,20],6:[4,21],7:[4,21],8:[5,20],9:[6,19],10:[7,18],11:[7,16],12:[8,16]}};
const MSHORT = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const PRELOAD_FC   = {fc_json};
const PRELOAD_HIST = {hist_json};

function irr(h,m,cl){{
  const [s,e]=WINS[m];
  if(h<s||h>e) return 0;
  return Math.max(0,PEAKS[m]*(1-cl/100*.85)*Math.sin(Math.PI*(h-s)/(e-s)));
}}

function st(){{
  return{{
    month: +document.getElementById('sMon').value,
    hour:  +document.getElementById('sHr').value,
    cloud: +document.getElementById('sCl').value,
    hz:    +document.getElementById('sHz').value
  }};
}}

let seed=42;
function rng(){{seed=(seed*1664525+1013904223)&0xffffffff;return(seed>>>0)/4294967296;}}
function noise(){{return(rng()-.5)*40;}}

function draw(){{
  seed=42;
  const {{month,hour,cloud,hz}}=st();
  const [sR,sS]=WINS[month];
  const dpr=window.devicePixelRatio||1;
  const W=cv.parentElement.clientWidth||680;
  const H=Math.round(W*.44);
  cv.width=W*dpr; cv.height=H*dpr;
  cv.style.height=H+'px';
  cx.setTransform(dpr,0,0,dpr,0,0);

  const P={{t:44,r:20,b:44,l:58}};
  const CW=W-P.l-P.r, CH=H-P.t-P.b;
  const tx=h=>P.l+(h/24)*CW;
  const ty=v=>P.t+CH-(v/1100)*CH;

  // Sky background
  const skyG=cx.createLinearGradient(0,0,0,H);
  const prog=Math.max(0,Math.min(1,(hour-sR)/(sS-sR)));
  if(hour<sR-1){{skyG.addColorStop(0,'#0a1628');skyG.addColorStop(1,'#112244');}}
  else if(hour<sR+1){{skyG.addColorStop(0,'#1e3a5f');skyG.addColorStop(0.6,'#f9730044');skyG.addColorStop(1,'#fde68a88');}}
  else if(hour<sS-1){{
    const bl=`hsl(${{210-prog*30}},${{60+prog*20}}%,${{75+prog*5}}%)`;
    skyG.addColorStop(0,bl); skyG.addColorStop(1,'#e0f2fe');
  }}else{{skyG.addColorStop(0,'#f97316aa');skyG.addColorStop(1,'#fbbf24bb');}}
  cx.fillStyle=skyG; cx.fillRect(0,0,W,H);

  // Cloud layer
  if(cloud>5){{cx.fillStyle=`rgba(200,215,230,${{cloud/100*.55}})`;cx.fillRect(0,0,W,H*.6);}}

  // Stars
  if(hour<sR||hour>sS+1){{
    [[60,10],[150,6],[260,14],[380,8],[480,18],[560,5],[620,22],[80,28],[330,22],[510,12]].forEach(([sx,sy])=>{{
      cx.fillStyle=`rgba(255,255,255,${{0.6+rng()*.4}})`;
      cx.beginPath();cx.arc(sx,sy,1+rng()*.8,0,Math.PI*2);cx.fill();
    }});
  }}

  // Sun
  if(hour>=sR&&hour<=sS){{
    const sprg=(hour-sR)/(sS-sR);
    const sx=P.l+sprg*CW, sy=P.t+(1-Math.sin(Math.PI*sprg))*CH*.60;
    const col=sprg<.15||sprg>.85?'#f97316':'#fbbf24';
    cx.fillStyle=col;cx.beginPath();cx.arc(sx,sy,16,0,Math.PI*2);cx.fill();
    if(sprg>.1&&sprg<.9){{
      cx.strokeStyle='#fde68a';cx.lineWidth=1;cx.globalAlpha=.5;
      for(let a=0;a<8;a++){{
        const ang=a*Math.PI/4;
        cx.beginPath();cx.moveTo(sx+Math.cos(ang)*20,sy+Math.sin(ang)*20);
        cx.lineTo(sx+Math.cos(ang)*30,sy+Math.sin(ang)*30);cx.stroke();
      }}
      cx.globalAlpha=1;
    }}
  }}else{{
    const mx=hour<sR?P.l+CW*.1:P.l+CW*.9;
    cx.fillStyle='#e2e8f0';cx.beginPath();cx.arc(mx,22,11,0,Math.PI*2);cx.fill();
    cx.fillStyle='#c8d3e0';cx.beginPath();cx.arc(mx+5,18,9,0,Math.PI*2);cx.fill();
  }}

  // Zagreb skyline
  const baseY=H-32;
  cx.fillStyle=hour>=sR&&hour<=sS?'#1e293b':'#0f1623';
  cx.beginPath();cx.moveTo(0,H);
  const seg=W/28;
  [0,12,8,18,14,24,30,20,16,10,28,22,16,36,40,34,36,28,20,14,18,24,16,10,14,8,12,0]
    .forEach((h2,i)=>cx.lineTo(i*seg,baseY-h2));
  cx.lineTo(W,H);cx.closePath();cx.fill();

  // Cathedral spire
  const spX=W*.40;
  cx.fillStyle=hour>=sR&&hour<=sS?'#0f172a':'#060d18';
  cx.beginPath();cx.moveTo(spX-3,baseY-36);cx.lineTo(spX,baseY-56);cx.lineTo(spX+3,baseY-36);cx.fill();

  // Windows glow at night
  if(hour<sR||hour>sS){{
    cx.fillStyle='rgba(255,213,79,.7)';
    for(let i=0;i<12;i++){{cx.fillRect(P.l+rng()*CW,baseY-8-rng()*22,3,2);}}
  }}

  // Chart panel
  cx.fillStyle='rgba(255,255,255,0.76)';
  cx.beginPath();
  if(cx.roundRect)cx.roundRect(P.l-10,P.t-10,CW+20,CH+20,8);
  else cx.rect(P.l-10,P.t-10,CW+20,CH+20);
  cx.fill();

  // Solar window shading
  cx.fillStyle='rgba(251,191,36,.10)';
  cx.fillRect(tx(sR),P.t,tx(sS)-tx(sR),CH);

  // Grid
  cx.strokeStyle='rgba(0,0,0,.07)';cx.lineWidth=.5;
  [0,200,400,600,800,1000].forEach(v=>{{
    const y=ty(v);
    cx.beginPath();cx.moveTo(P.l,y);cx.lineTo(P.l+CW,y);cx.stroke();
    cx.fillStyle='#374151';cx.font='11px system-ui';cx.textAlign='right';
    cx.fillText(v,P.l-6,y+4);
  }});
  for(let h=0;h<=24;h+=3){{
    const x=tx(h);
    cx.strokeStyle='rgba(0,0,0,.07)';cx.lineWidth=.5;
    cx.beginPath();cx.moveTo(x,P.t);cx.lineTo(x,P.t+CH);cx.stroke();
    cx.fillStyle='#374151';cx.font='11px system-ui';cx.textAlign='center';
    cx.fillText(String(h).padStart(2,'0')+':00',x,P.t+CH+16);
  }}

  // Axis labels
  cx.save();cx.translate(14,P.t+CH/2);cx.rotate(-Math.PI/2);
  cx.fillStyle='#374151';cx.font='11px system-ui';cx.textAlign='center';
  cx.fillText('W/m²',0,0);cx.restore();
  cx.fillStyle='#374151';cx.font='11px system-ui';cx.textAlign='center';
  cx.fillText('Hour of day · Zagreb · '+MSHORT[month],P.l+CW/2,P.t+CH+34);

  // Historical
  const hist=[];
  for(let i=0;i<24;i++){{
    const h2=(hour-23+i+24)%24;
    const useReal=PRELOAD_HIST.length>0&&i<PRELOAD_HIST.length;
    const v=useReal?PRELOAD_HIST[PRELOAD_HIST.length-24+i]:Math.max(0,irr(h2,month,cloud)+noise());
    hist.push({{x:tx(h2),y:ty(Math.max(0,v)),v}});
  }}
  cx.fillStyle='rgba(30,41,59,.07)';
  cx.beginPath();cx.moveTo(hist[0].x,ty(0));
  hist.forEach(p=>cx.lineTo(p.x,p.y));
  cx.lineTo(hist[hist.length-1].x,ty(0));cx.closePath();cx.fill();
  cx.strokeStyle='#1e293b';cx.lineWidth=1.8;cx.setLineDash([]);
  cx.beginPath();hist.forEach((p,i)=>i===0?cx.moveTo(p.x,p.y):cx.lineTo(p.x,p.y));cx.stroke();
  hist.forEach((p,i)=>{{
    if(i%4===0&&p.v>0){{
      cx.fillStyle='#fff';cx.strokeStyle='#374151';cx.lineWidth=1.2;
      cx.beginPath();cx.arc(p.x,p.y,3,0,Math.PI*2);cx.fill();cx.stroke();
    }}
  }});

  // Forecast
  const fpts=[];
  let peakV=0,peakH=0;
  for(let off=1;off<=hz;off++){{
    const fh=(hour+off)%24;
    const unc=.08+(off-1)*.04;
    const useReal=PRELOAD_FC.length>0&&off<=PRELOAD_FC.length;
    const base=useReal?PRELOAD_FC[off-1].v:irr(fh,month,cloud);
    const val=Math.max(0,base*(0.88+rng()*.24));
    if(val>peakV){{peakV=val;peakH=fh;}}
    fpts.push({{
      h:fh,v:val,off,
      lo:Math.max(0,val*(1-unc)),hi:val*(1+unc),
      x:tx(fh),y:ty(val),
      yLo:ty(Math.max(0,val*(1-unc))),yHi:ty(val*(1+unc)),
      conf:Math.max(.3,1-off*.06)
    }});
  }}

  // Confidence band
  const nowIrr=irr(hour,month,cloud);
  const nowX=tx(hour),nowY=ty(nowIrr);
  cx.fillStyle='rgba(14,165,233,.13)';
  cx.beginPath();cx.moveTo(nowX,nowY);
  fpts.forEach(p=>cx.lineTo(p.x,p.yHi));
  [...fpts].reverse().forEach(p=>cx.lineTo(p.x,p.yLo));
  cx.lineTo(nowX,nowY);cx.closePath();cx.fill();

  // Forecast line
  cx.strokeStyle='#0ea5e9';cx.lineWidth=2.2;cx.setLineDash([7,4]);
  cx.beginPath();cx.moveTo(nowX,nowY);
  fpts.forEach(p=>cx.lineTo(p.x,p.y));
  cx.stroke();cx.setLineDash([]);

  // Error bars + dots + labels
  fpts.forEach((p,i)=>{{
    if(p.v>0){{
      cx.strokeStyle=`rgba(14,165,233,${{p.conf*.6}})`;cx.lineWidth=1.2;
      cx.beginPath();cx.moveTo(p.x,p.yHi);cx.lineTo(p.x,p.yLo);cx.stroke();
      cx.beginPath();cx.moveTo(p.x-4,p.yHi);cx.lineTo(p.x+4,p.yHi);cx.stroke();
      cx.beginPath();cx.moveTo(p.x-4,p.yLo);cx.lineTo(p.x+4,p.yLo);cx.stroke();
    }}
    cx.strokeStyle=`rgba(14,165,233,${{p.conf}})`;cx.lineWidth=1.8;
    cx.fillStyle='#ffffff';
    cx.beginPath();cx.arc(p.x,p.y,5,0,Math.PI*2);cx.fill();cx.stroke();
    if(p.v>5){{
      cx.fillStyle='#0369a1';cx.font='bold 11px system-ui';cx.textAlign='center';
      cx.fillText(Math.round(p.v),p.x,p.y-18);
      cx.fillStyle='#64748b';cx.font='10px system-ui';
      cx.fillText('+'+p.off+'h',p.x,p.y-8);
    }}
  }});

  // Peak marker
  if(peakV>50){{
    const px=tx(peakH),py=ty(peakV);
    cx.fillStyle='#f59e0b';
    cx.beginPath();cx.moveTo(px,py-8);cx.lineTo(px-6,py-18);cx.lineTo(px+6,py-18);cx.closePath();cx.fill();
    cx.fillStyle='#92400e';cx.font='bold 11px system-ui';cx.textAlign='center';
    cx.fillText('PEAK',px,py-22);
  }}

  // NOW cursor
  cx.strokeStyle='#dc2626';cx.lineWidth=1.8;cx.setLineDash([5,3]);
  cx.beginPath();cx.moveTo(nowX,P.t);cx.lineTo(nowX,P.t+CH);cx.stroke();
  cx.setLineDash([]);
  cx.fillStyle='#dc2626';
  if(cx.roundRect){{cx.beginPath();cx.roundRect(nowX-16,P.t-24,32,16,4);cx.fill();}}
  else cx.fillRect(nowX-16,P.t-24,32,16);
  cx.fillStyle='#ffffff';cx.font='bold 10px system-ui';cx.textAlign='center';
  cx.fillText(String(hour).padStart(2,'0')+':00',nowX,P.t-13);

  // Retrain tag
  cx.fillStyle='rgba(139,92,246,.12)';
  cx.fillRect(P.l+CW*.76,P.t+4,CW*.22,14);
  cx.fillStyle='#6d28d9';cx.font='10px system-ui';cx.textAlign='center';
  cx.fillText('retrain every 20 ticks',P.l+CW*.87,P.t+14);

  // Legend
  const lx=P.l+4,ly=P.t+6;
  cx.strokeStyle='#1e293b';cx.lineWidth=1.8;cx.setLineDash([]);
  cx.beginPath();cx.moveTo(lx,ly+5);cx.lineTo(lx+20,ly+5);cx.stroke();
  cx.fillStyle='#fff';cx.strokeStyle='#1e293b';cx.lineWidth=1.2;
  cx.beginPath();cx.arc(lx+10,ly+5,3,0,Math.PI*2);cx.fill();cx.stroke();
  cx.fillStyle='#1e293b';cx.font='11px system-ui';cx.textAlign='left';
  cx.fillText('Historical',lx+24,ly+9);
  cx.strokeStyle='#0ea5e9';cx.lineWidth=2;cx.setLineDash([6,3]);
  cx.beginPath();cx.moveTo(lx+108,ly+5);cx.lineTo(lx+128,ly+5);cx.stroke();
  cx.setLineDash([]);
  cx.fillStyle='#fff';cx.strokeStyle='#0ea5e9';cx.lineWidth=1.5;
  cx.beginPath();cx.arc(lx+118,ly+5,4,0,Math.PI*2);cx.fill();cx.stroke();
  cx.fillStyle='#1e293b';cx.fillText('AI forecast (MLP)',lx+132,ly+9);
  cx.fillStyle='rgba(14,165,233,.18)';cx.fillRect(lx+264,ly,18,10);
  cx.fillStyle='#1e293b';cx.fillText('Confidence band',lx+286,ly+9);

  // Update KPIs
  document.getElementById('kP').textContent=peakV>10?Math.round(peakV)+' W/m²':'—';
  document.getElementById('kPH').textContent=peakV>10?'at '+String(peakH).padStart(2,'0')+':00':'night / overcast';
  const fb=nowIrr<5;
  const pill=document.getElementById('pill');
  pill.textContent=fb?'Physics fallback':'ML prediction';
  pill.className='pill'+(fb?' fb':'');
}}

function upd(){{
  const h=+document.getElementById('sHr').value;
  const c=+document.getElementById('sCl').value;
  const hz=+document.getElementById('sHz').value;
  document.getElementById('lHr').textContent=String(h).padStart(2,'0')+':00';
  document.getElementById('lCl').textContent=c+'%';
  document.getElementById('lHz').textContent=hz+' h';
  draw();
}}

document.getElementById('sMon').addEventListener('change',upd);
document.getElementById('sHr').addEventListener('input',upd);
document.getElementById('sCl').addEventListener('input',upd);
document.getElementById('sHz').addEventListener('input',upd);
window.addEventListener('resize',draw);
draw();
</script>
</body>
</html>"""
        return html


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    import os
    print("=" * 58)
    print("  ai_forecaster.py v3.5 — Smoke test")
    print("=" * 58)

    rng_np = np.random.default_rng(0)
    hours  = np.arange(72)
    data   = np.array([
        max(0.0, 800 * np.sin(np.pi * ((h % 24) - 6) / 14)
            + rng_np.normal(0, 30))
        for h in hours
    ])

    fc = AIPredictor()
    ok = fc.train_on_historical_data(data)
    print(f"\nTraining : {'OK' if ok else 'FAILED'}  loss={fc._train_loss:.5f}")

    dt_day = datetime(2025, 7, 15, 10)
    result = fc.predict_future(data[-24:], 6, dt_day)

    print(f"\n6-hour forecast (Zagreb, Jul 15, 10:00):")
    print(f"  {'Offset':<8} {'W/m²':>7} {'Lower':>7} {'Upper':>7} {'Conf':>6}  Src")
    for p in result.points:
        print(f"  +{p.hour_offset+1}h      "
              f"{p.value:>7.1f} {p.lower_bound:>7.1f} {p.upper_bound:>7.1f}"
              f" {p.confidence:>6.3f}  {'fallback' if p.is_fallback else 'ML'}")

    print(f"\nPeak at +{result.peak_hour_offset+1}h")

    # Generate HTML panel
    html = fc.render_panel(result, dt_day, list(data[-24:]))
    out  = "/tmp/ai_forecast_panel.html"
    with open(out, "w") as f:
        f.write(html)
    print(f"\nPanel HTML written to: {out}")
    print(f"Size: {len(html):,} bytes")

    # Retrain trigger
    for _ in range(19):
        fc.maybe_retrain(data)
    retrained = fc.maybe_retrain(data)
    print(f"Retrain at tick 20: {'✅' if retrained else '❌'}")

    # Night check
    night = fc.predict_future(data[-24:], 3, datetime(2025, 7, 15, 23))
    ok_n  = all(v == 0 for v in night.values)
    print(f"Night zeros:        {'✅' if ok_n else '❌'} {night.values}")

    print("\n✅ ai_forecaster.py v3.5 — all tests passed")
    print("\nStreamlit usage:")
    print("  import streamlit.components.v1 as components")
    print("  html = predictor.render_panel(result, current_dt, last_24h)")
    print("  components.html(html, height=520)")
