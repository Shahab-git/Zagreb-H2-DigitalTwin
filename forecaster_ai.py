import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler
import warnings
import logging

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings("ignore")


class AIPredictor:
    """پیش‌بینی تابش خورشیدی یا انرژی تجدیدپذیر با شبکه عصبی MLP"""

    def __init__(self):
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.model = MLPRegressor(
            hidden_layer_sizes=(64, 32),
            activation='relu',
            solver='adam',
            max_iter=1000,
            warm_start=True,
            random_state=42
        )
        self.is_trained = False

    def train_on_historical_data(self, data):
        """
        آموزش مدل روی داده‌های واقعی (تابش خورشیدی یا تولید انرژی)
        - data: آرایه ۱ بعدی با حداقل 24 داده (ساعتی)
        """
        data = np.array(data, dtype=float)
        if data.size < 24:
            logging.warning("⚠️ AI Forecaster: Not enough data to train. Minimum 24 points required.")
            return

        # نرمال‌سازی
        scaled_data = self.scaler.fit_transform(data.reshape(-1, 1))

        # ساخت X و y با پنجره 24 ساعته
        X, y = [], []
        for i in range(24, len(scaled_data)):
            X.append(scaled_data[i-24:i, 0])
            y.append(scaled_data[i, 0])

        X, y = np.array(X), np.array(y)
        if X.size == 0:
            logging.warning("⚠️ AI Forecaster: Training data window too small. Skipping training.")
            return

        self.model.fit(X, y)
        self.is_trained = True
        logging.info("🧠 AI Forecaster: Model trained successfully on historical data.")

    def predict_next_hours(self, last_24h_data, hours=1):
        """
        پیش‌بینی n ساعت آینده
        - last_24h_data: آخرین 24 داده
        - hours: تعداد ساعت‌های آینده برای پیش‌بینی
        """
        last_24h_data = np.array(last_24h_data, dtype=float)
        predictions = []

        for _ in range(hours):
            if not self.is_trained or last_24h_data.size < 24:
                # fallback: میانگین آخرین 6 داده یا 0
                fallback = float(np.mean(last_24h_data[-6:])) if last_24h_data.size > 0 else 0.0
                logging.info(f"⚠️ AI Forecaster: Using fallback prediction {fallback:.2f} W/m²")
                predictions.append(fallback)
                # اضافه کردن پیش‌بینی به داده‌ها برای ساعت بعد
                last_24h_data = np.append(last_24h_data, fallback)
                continue

            # آماده‌سازی ورودی و نرمال‌سازی
            recent_scaled = self.scaler.transform(last_24h_data[-24:].reshape(-1, 1)).reshape(1, 24)
            pred_scaled = self.model.predict(recent_scaled)
            pred_final = self.scaler.inverse_transform(pred_scaled.reshape(-1, 1))
            pred_value = max(0.0, float(pred_final[0][0]))
            predictions.append(pred_value)

            # اضافه کردن پیش‌بینی به داده‌ها برای گام بعد
            last_24h_data = np.append(last_24h_data, pred_value)

        return predictions if hours > 1 else predictions[0]