# hydrogen_assets.py (Dynamic Version)
import numpy as np
from config import Config

# =========================================================
# 🔷 Electrolyzer (PEM S30/30)
# =========================================================
class ElectrolyzerS30:
    def __init__(self):
        self.p_min = Config.ELEC_P_MIN_KW
        self.p_nom = Config.ELEC_P_NOM_KW
        self.power_pts = list(Config.ELEC_EFF_CURVE.keys())
        self.eff_pts = list(Config.ELEC_EFF_CURVE.values())
        self.degradation = 0.0

    def calculate_production(self, input_power_kw):
        if input_power_kw < self.p_min:
            return 0.0, 0.0, 0.0

        input_power_kw = min(input_power_kw, self.p_nom)
        current_eff = np.interp(input_power_kw, self.power_pts, self.eff_pts)
        self.degradation += 1e-6 * input_power_kw
        current_eff *= (1 - self.degradation)

        useful_energy = input_power_kw * current_eff
        h2_produced_kg_h = useful_energy / 33.33  # LHV assumption

        waste_power = input_power_kw * (1 - current_eff)
        recovered_heat_kw = waste_power * Config.HEAT_RECOVERY_FACTOR

        return h2_produced_kg_h, current_eff, recovered_heat_kw


# =========================================================
# 🔷 Hydrogen Storage Chain
# =========================================================
class HydrogenStorageChain:
    def __init__(self):
        self.buffer_kg = 0.0
        self.main_tank_kg = 0.0
        self.h2_station_kg = 0.0

        self.buffer_max = Config.BUFFER_TANK_CAPACITY_KG
        self.main_max = Config.MAIN_TANK_CAPACITY_KG
        self.station_max = Config.HRS_H2_TANK_CAPACITY_KG

        self.compressor_active = False
        self.runtime = 0

    def manage_chain(self, h2_in_kg_h, compressor_power_kw):
        dt = Config.TIMESTEP_SEC

        # --- 1. پر کردن بافر ---
        self.buffer_kg += h2_in_kg_h * dt / 3600
        self.buffer_kg = min(self.buffer_kg, self.buffer_max)

        # --- 2. مدیریت کمپرسور با hysteresis ---
        buffer_soc = self.buffer_kg / max(self.buffer_max, 1e-3)
        if not self.compressor_active and buffer_soc >= Config.BUFFER_START_THRESHOLD:
            self.compressor_active = True
            self.runtime = 0
        elif self.compressor_active:
            self.runtime += dt
            if buffer_soc <= Config.BUFFER_STOP_THRESHOLD and self.runtime >= Config.COMPRESSOR_MIN_RUNTIME_SEC:
                self.compressor_active = False

        # --- 3. فشرده‌سازی و انتقال به مخزن اصلی ---
        flow_kg_h = 0.0
        if self.compressor_active and compressor_power_kw > 0:
            compressor_flow_kg_h = compressor_power_kw * 0.05  # مثال صنعتی
            transfer = min(self.buffer_kg, compressor_flow_kg_h * dt / 3600)
            self.buffer_kg -= transfer
            self.main_tank_kg = min(self.main_tank_kg + transfer, self.main_max)
            flow_kg_h = transfer * 3600 / dt

        # --- 4. سوخت‌رسانی به ایستگاه HRS (Main Tank ≥ 50٪) ---
        main_soc = self.main_tank_kg / max(self.main_max, 1e-3)
        if main_soc >= 0.50 and self.h2_station_kg < self.station_max:
            gap_to_target = self.station_max - self.h2_station_kg
            refuel_rate = 1.0  # kg/h فرضی
            refuel = min(self.main_tank_kg, refuel_rate * dt / 3600, gap_to_target)
            self.main_tank_kg -= refuel
            self.h2_station_kg += refuel

        return flow_kg_h


# =========================================================
# 🔷 Fuel Cell (AIRCELL)
# =========================================================
class FuelCellAircell:
    def __init__(self):
        self.nominal_p = Config.FC_POWER_NOM_KW
        self.cons_rate = Config.FC_H2_CONSUMPTION_G_KWH / 1000  # kg/kWh

    def generate_power(self, h2_available_kg, demand_kw):
        if demand_kw <= 0 or h2_available_kg <= 0:
            return 0.0, 0.0, 0.0

        dt = Config.TIMESTEP_SEC
        p_out = min(demand_kw, self.nominal_p)
        h2_needed = (p_out * self.cons_rate) * dt / 3600
        h2_used = min(h2_needed, h2_available_kg)

        load_ratio = p_out / self.nominal_p
        eff = 0.45 + 0.15 * load_ratio
        heat_kw = p_out * (1 - eff) * Config.HEAT_RECOVERY_FACTOR

        return p_out, h2_used, heat_kw