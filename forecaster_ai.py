# ai_forecaster.py
# AI Energy Forecasting Engine: MLP-based Solar & Wind Prediction
# Version: 3.0 (Industrial Realism)

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler
import warnings
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings("ignore")


class AIPredictor:
    """
    Industrial AI Forecaster using Multi-Layer Perceptron (MLP) for
    Renewable Energy & Solar Irradiance Prediction.
    """

    def __init__(self):
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        # Optimized for time-series pattern recognition
        self.model = MLPRegressor(
            hidden_layer_sizes=(128, 64, 32),  # Deeper architecture for better features
            activation='relu',
            solver='adam',
            alpha=0.001,  # L2 regularization to prevent overfitting
            max_iter=2000,
            warm_start=True,
            random_state=42
        )
        self.is_trained = False
        self.history_window = 24  # 24-hour lookback window

    def _apply_physical_constraints(self, prediction, current_hour):
        """
        Post-processing: Ensures AI doesn't hallucinate solar energy at night.
        """
        # Zagreb Solar Window (approx 06:00 to 20:00 depending on season)
        if current_hour < 5 or current_hour > 21:
            return 0.0
        return max(0.0, float(prediction))

    def train_on_historical_data(self, data):
        """
        Trains the model on historical irradiance or power generation data.
        - data: 1D array with at least 48-72 data points for meaningful patterns.
        """
        data = np.array(data, dtype=float)
        if data.size < self.history_window * 2:
            logging.warning(f"🧠 AI Forecaster: Insufficient data ({data.size} pts). Need at least 48.")
            return

        # Normalization
        scaled_data = self.scaler.fit_transform(data.reshape(-1, 1))

        # Sliding Window Preparation
        X, y = [], []
        for i in range(self.history_window, len(scaled_data)):
            X.append(scaled_data[i - self.history_window:i, 0])
            y.append(scaled_data[i, 0])

        X, y = np.array(X), np.array(y)

        try:
            self.model.fit(X, y)
            self.is_trained = True
            logging.info("🧠 AI Forecaster: Model calibrated successfully on Zagreb telemetry.")
        except Exception as e:
            logging.error(f"🧠 AI Forecaster Training Error: {e}")

    def predict_future(self, last_24h_data, horizon_hours=1):
        """
        Predicts future energy availability for a given horizon.
        - last_24h_data: The most recent 24-hour sequence.
        - horizon_hours: Number of hours to forecast ahead.
        """
        last_24h_data = np.array(last_24h_data, dtype=float)
        forecasts = []
        current_hour = datetime.now().hour

        # Sliding window prediction loop
        working_data = last_24h_data.copy()

        for i in range(horizon_hours):
            if not self.is_trained or working_data.size < self.history_window:
                # Fallback to persistent forecasting (last known good average)
                fallback = float(np.mean(working_data[-3:])) if working_data.size > 0 else 50.0
                forecasts.append(fallback)
                working_data = np.append(working_data, fallback)
                continue

            # Scale and Predict
            input_window = self.scaler.transform(working_data[-self.history_window:].reshape(-1, 1)).reshape(1,
                                                                                                             self.history_window)
            pred_scaled = self.model.predict(input_window)
            pred_inv = self.scaler.inverse_transform(pred_scaled.reshape(-1, 1))

            # Apply Physical Realism
            pred_final = self._apply_physical_constraints(pred_inv[0][0], (current_hour + i + 1) % 24)
            forecasts.append(pred_final)

            # Feed prediction back for multi-step forecast
            working_data = np.append(working_data, pred_final)

        return forecasts if horizon_hours > 1 else forecasts[0]
