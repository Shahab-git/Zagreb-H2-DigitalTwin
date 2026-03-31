# energy_assets.py
# High-Fidelity Generation & Storage Engine (Zagreb Hub)
# Version: 3.0 (Industrial Realism)

import numpy as np
from config import Config


# =========================================================
# ☀️ Solar PV System (Advanced Thermal & Soiling Model)
# =========================================================
class SolarSystem:
    def __init__(self):
        self.capacity_kw = Config.PV_SYSTEM_CAPACITY_KW
        self.inv_eff = Config.INVERTER_EFFICIENCY
        self.temp_coeff = -0.004  # -0.4%/°C (Standard Monocrystalline)

    def get_power_output(self, irradiance_raw, ambient_temp, soiling_factor=1.0):
        """
        Calculates AC power output considering temperature derating and panel soiling.
        """
        if irradiance_raw is None or irradiance_raw <= 0:
            return 0.0

        # 1. Apply Environmental Soiling (Dust/Pollution)
        effective_irradiance = irradiance_raw * soiling_factor

        # 2. Cell Temperature Modeling (NOCT formula)
        # Tcell = Tamb + (Irradiance/800) * (NOCT - 20)
        noct = 45.0
        t_cell = ambient_temp + (effective_irradiance / 800.0) * (noct - 20.0)

        # 3. Thermal Derating Factor
        # Standard Test Conditions (STC) are at 25°C
        thermal_factor = 1.0 + self.temp_coeff * (t_cell - 25.0)

        # 4. DC to AC Conversion
        raw_dc_power = self.capacity_kw * (effective_irradiance / 1000.0) * thermal_factor
        ac_power = raw_dc_power * self.inv_eff

        return float(np.clip(ac_power, 0.0, self.capacity_kw))


# =========================================================
# 🌬️ Wind Turbine (Turbulence & Fatigue Model)
# =========================================================
class WindSystem:
    def __init__(self):
        self.capacity_kw = Config.WIND_SYSTEM_CAPACITY_KW
        self.cut_in = 3.0  # m/s
        self.rated = 12.0  # m/s
        self.cut_out = 25.0  # m/s

    def get_power_output(self, wind_speed, turbulence_intensity=0.1):
        """
        Calculates power using a cubic curve with turbulence-based safety derating.
        """
        if wind_speed is None or wind_speed < self.cut_in or wind_speed > self.cut_out:
            return 0.0

        # Turbulence Derating (High gustiness reduces aerodynamic efficiency)
        turbulence_loss = 1.0 - (max(0, turbulence_intensity - 0.1) * 0.5)

        if wind_speed >= self.rated:
            power = self.capacity_kw * turbulence_loss
        else:
            # Cubic power curve: P is proportional to v^3
            ratio = (wind_speed - self.cut_in) / (self.rated - self.cut_in)
            power = self.capacity_kw * (ratio ** 3) * turbulence_loss

        return float(np.clip(power, 0.0, self.capacity_kw))


# =========================================================
# 🔋 Battery (BESS) - Advanced SoH & Thermal Engine
# =========================================================
class BatteryBESS:
    def __init__(self):
        self.capacity_kwh = Config.BATT_CAPACITY_KWH
        self.soc = 0.50  # Start at 50%
        self.soh = 1.0  # State of Health (1.0 = 100%)
        self.total_throughput_kwh = 0.0

        # Internal parameters
        self.charge_eff = 0.96
        self.discharge_eff = 0.94

    def get_max_charge_power(self):
        """Dynamic charging limit based on SOC (CC-CV Profile imitation)."""
        if self.soc >= Config.BATT_SOC_MAX:
            return 0.0
        # Taper off charging power after 85% to protect cells
        if self.soc > 0.85:
            taper = (Config.BATT_SOC_MAX - self.soc) / (Config.BATT_SOC_MAX - 0.85)
            return Config.BATT_MAX_CHARGE_KW * taper
        return Config.BATT_MAX_CHARGE_KW

    def update_state(self, net_power_kw):
        """
        Updates SOC and SOH based on power flow and chemical degradation.
        """
        dt_h = Config.TIMESTEP_SEC / 3600.0

        # 1. Power Flow Logic
        if net_power_kw > 0:  # Charging
            p_actual = min(net_power_kw, self.get_max_charge_power())
            energy_delta = p_actual * self.charge_eff * dt_h
        else:  # Discharging
            p_actual = max(net_power_kw, -Config.BATT_MAX_DISCHARGE_KW)
            energy_delta = (p_actual / self.discharge_eff) * dt_h

        # 2. Health (SOH) Degradation
        # Real-world batteries degrade per unit of energy throughput
        throughput = abs(energy_delta)
        self.total_throughput_kwh += throughput

        # Industrial formula: Degradation based on Config's rated cycle life
        self.soh -= (throughput / (self.capacity_kwh * Config.BATT_CYCLE_LIFE))
        self.soh = max(0.70, self.soh)  # Assume 70% is "End of Life"

        # 3. Effective Capacity calculation
        effective_capacity = self.capacity_kwh * self.soh

        # 4. SOC Update
        current_energy = self.soc * effective_capacity
        new_energy = current_energy + energy_delta
        self.soc = np.clip(new_energy / effective_capacity, Config.BATT_SOC_MIN, Config.BATT_SOC_MAX)

        return {
            "soc": float(self.soc),
            "soh": float(self.soh),
            "throughput": float(self.total_throughput_kwh)
        }
