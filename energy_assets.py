# energy_assets.py (Dynamic Version - Fixed Tuple Issue)
import numpy as np
from config import Config

# =========================================================
# 🔷 Solar PV
# =========================================================
class SolarSystem:
    def __init__(self):
        self.capacity_kw = Config.PV_SYSTEM_CAPACITY_KW
        self.eff = Config.INVERTER_EFFICIENCY

    def get_power_output(self, irradiation=None, ambient_temp=None):
        """
        محاسبه توان PV بر اساس داده واقعی یا fallback
        خروجی همیشه float
        """
        if irradiation is None or irradiation <= 0:
            return 0.0  # فقط توان، بدون tuple

        # محاسبه دمای سلول (NOCT)
        t_cell = ambient_temp + (irradiation / 800) * (45 - 20)
        temp_coeff = -0.004
        temp_factor = 1 + temp_coeff * (t_cell - 25)

        raw_power = self.capacity_kw * (irradiation / 1000) * temp_factor
        power = raw_power * self.eff
        power = np.clip(power, 0.0, self.capacity_kw)

        return float(power)


# =========================================================
# 🔷 Wind
# =========================================================
class WindSystem:
    def __init__(self):
        self.capacity_kw = Config.WIND_SYSTEM_CAPACITY_KW

    def get_power_output(self, wind_speed=None):
        """
        محاسبه توان باد بر اساس داده واقعی یا fallback
        خروجی همیشه float
        """
        if wind_speed is None or wind_speed <= 0:
            return 0.0

        cut_in = 3.0
        rated = 12.0
        cut_out = 25.0

        if wind_speed < cut_in or wind_speed > cut_out:
            return 0.0
        elif wind_speed >= rated:
            return float(self.capacity_kw)
        else:
            ratio = (wind_speed - cut_in) / (rated - cut_in)
            power = self.capacity_kw * (ratio ** 3)
            return float(power)


# =========================================================
# 🔷 Battery (BESS)
# =========================================================
class BatteryBESS:
    def __init__(self):
        self.capacity_kwh = Config.BATT_CAPACITY_KWH
        self.soc = 0.5
        self.min_soc = Config.BATT_SOC_MIN
        self.max_soc = Config.BATT_SOC_MAX
        self.max_charge_kw = Config.BATT_MAX_CHARGE_KW
        self.max_discharge_kw = Config.BATT_MAX_DISCHARGE_KW
        self.charge_eff = getattr(Config, "BATT_CHARGE_EFF", 0.95)
        self.discharge_eff = getattr(Config, "BATT_DISCHARGE_EFF", 0.95)
        self.degradation = 0.0

    def get_max_charge_power(self):
        if self.soc >= self.max_soc:
            return 0.0
        if self.soc > 0.90:
            reduction_factor = (self.max_soc - self.soc) / (self.max_soc - 0.90)
            return self.max_charge_kw * max(0, reduction_factor)
        return self.max_charge_kw

    def update_soc(self, net_power_kw):
        dt_hour = Config.TIMESTEP_SEC / 3600.0

        if net_power_kw > 0:
            actual_p = min(net_power_kw, self.get_max_charge_power())
            energy_change = actual_p * self.charge_eff * dt_hour
        else:
            actual_p = max(net_power_kw, -self.max_discharge_kw)
            energy_change = (actual_p / self.discharge_eff) * dt_hour

        throughput = abs(energy_change)
        self.degradation += throughput * 1.5e-6
        effective_capacity = self.capacity_kwh * (1 - self.degradation)

        current_energy = self.soc * effective_capacity
        new_energy = current_energy + energy_change
        self.soc = np.clip(new_energy / effective_capacity, self.min_soc, self.max_soc)

        return self.soc