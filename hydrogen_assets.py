# hydrogen_assets.py
# High-Fidelity Physics Engine for Green Hydrogen Lifecycle
# Version: 3.0 (Industrial Realism)

import numpy as np
from config import Config


# =========================================================
# 🔷 Electrolyzer (PEM S30/30) - Electrochemical Layer
# =========================================================
class ElectrolyzerS30:
    def __init__(self):
        self.p_min = Config.ELEC_P_MIN_KW
        self.p_nom = Config.ELEC_P_NOM_KW
        self.p_max = Config.ELEC_P_MAX_KW
        self.power_pts = list(Config.ELEC_EFF_CURVE.keys())
        self.eff_pts = list(Config.ELEC_EFF_CURVE.values())

        # Health & Maintenance Metrics
        self.soh = 1.0  # State of Health (1.0 = 100%)
        self.total_hours = 0.0
        self.total_h2_produced = 0.0

    def calculate_production(self, input_power_kw, ambient_temp=20.0):
        """Calculates H2 mass, Efficiency, Waste Heat, Purity, and Water usage."""
        if input_power_kw < self.p_min:
            return {
                "h2_kg_h": 0.0, "eff": 0.0, "heat_kw": 0.0,
                "purity": 0.0, "water_l_h": 0.0, "soh": self.soh
            }

        # 1. Efficiency & Degradation Logic
        input_power_kw = min(input_power_kw, self.p_max)
        load_factor = input_power_kw / self.p_max

        current_eff = np.interp(input_power_kw, self.power_pts, self.eff_pts)

        # Apply SOH impact on efficiency
        current_eff *= (0.95 + 0.05 * self.soh)

        # 2. Mass Balance (H2 & Water)
        # Using LHV (Lower Heating Value) of 33.33 kWh/kg
        h2_produced_kg_h = (input_power_kw * current_eff) / 33.33
        water_usage_l_h = h2_produced_kg_h * Config.WATER_CONSUMPTION_L_KG

        # 3. Gas Purity Modeling (Cross-over effect increases at low load)
        # Higher load typically improves purity in PEM up to a point
        purity = Config.PURITY_TARGET - (0.005 * (1 - load_factor))

        # 4. Thermal Recovery
        waste_power = input_power_kw * (1 - current_eff)
        recovered_heat_kw = waste_power * Config.HEAT_RECOVERY_FACTOR

        # 5. Degradation Update (Every Timestep)
        # Real-world degradation based on stack hours and power intensity
        self.soh -= (Config.ELECTROLYZER_DEGRADATION_RATE * load_factor * (Config.TIMESTEP_SEC / 3600))
        self.total_hours += Config.TIMESTEP_SEC / 3600
        self.total_h2_produced += h2_produced_kg_h * (Config.TIMESTEP_SEC / 3600)

        return {
            "h2_kg_h": float(h2_produced_kg_h),
            "eff": float(current_eff),
            "heat_kw": float(recovered_heat_kw),
            "purity": float(purity),
            "water_l_h": float(water_usage_l_h),
            "soh": float(self.soh)
        }


# =========================================================
# 🔷 Hydrogen Storage & Compression - Thermodynamic Layer
# =========================================================
class HydrogenStorageChain:
    def __init__(self):
        self.buffer_kg = 0.0
        self.main_tank_kg = 0.0
        self.h2_station_kg = 0.0

        # Thermal State
        self.main_tank_temp = 20.0  # Celsius
        self.pressure_bar = Config.MIN_OPERATING_PRESSURE_BAR

        self.compressor_active = False
        self.runtime = 0

    def manage_chain(self, h2_in_kg_h):
        """Manages Buffer, Compressor (JT Effect), and HRS Dispatching."""
        dt = Config.TIMESTEP_SEC

        # --- 1. Buffer Accumulation ---
        self.buffer_kg += h2_in_kg_h * dt / 3600
        self.buffer_kg = min(self.buffer_kg, Config.BUFFER_TANK_CAPACITY_KG)

        # --- 2. Compressor Logic (Hysteresis) ---
        buffer_soc = self.buffer_kg / Config.BUFFER_TANK_CAPACITY_KG
        if not self.compressor_active and buffer_soc >= Config.BUFFER_START_THRESHOLD:
            self.compressor_active = True
            self.runtime = 0
        elif self.compressor_active:
            self.runtime += dt
            if buffer_soc <= Config.BUFFER_STOP_THRESHOLD and self.runtime >= Config.COMPRESSOR_MIN_RUNTIME_SEC:
                self.compressor_active = False

        # --- 3. Thermodynamics (Joule-Thomson & Compression Heat) ---
        flow_to_main_kg_h = 0.0
        if self.compressor_active:
            # Assume 1.5kW compressor can move ~0.8 kg/h at 350 bar
            transfer_rate = 0.8
            transfer = min(self.buffer_kg, transfer_rate * dt / 3600)

            self.buffer_kg -= transfer
            self.main_tank_kg = min(self.main_tank_kg + transfer, Config.MAIN_TANK_CAPACITY_KG)
            flow_to_main_kg_h = transfer * 3600 / dt

            # JT Effect / Heat of Compression: Temperature rises during filling
            self.main_tank_temp += (Config.JOULE_THOMSON_COEFF * 2.5 * (dt / 60))
        else:
            # Natural cooling toward ambient
            self.main_tank_temp = max(20.0, self.main_tank_temp - 0.01 * (dt / 60))

        # Update Pressure based on Ideal Gas Law (Simplified for Digital Twin)
        # P = (mRT)/V -> Pressure is proportional to mass and temp
        self.pressure_bar = (self.main_tank_kg / Config.MAIN_TANK_CAPACITY_KG) * Config.SAFETY_MAX_PRESSURE_BAR
        self.pressure_bar = max(Config.MIN_OPERATING_PRESSURE_BAR,
                                min(self.pressure_bar, Config.SAFETY_MAX_PRESSURE_BAR))

        # --- 4. Smart Dispatching to HRS (Priority 1) ---
        main_soc = self.main_tank_kg / Config.MAIN_TANK_CAPACITY_KG
        if main_soc >= Config.MAIN_TANK_START_THRESHOLD and self.h2_station_kg < Config.HRS_H2_TANK_CAPACITY_KG:
            refuel = min(self.main_tank_kg, 1.5 * dt / 3600)  # 1.5 kg/h transfer
            self.main_tank_kg -= refuel
            self.h2_station_kg += refuel

        return {
            "flow_kg_h": flow_to_main_kg_h,
            "temp_c": self.main_tank_temp,
            "pressure_bar": self.pressure_bar,
            "main_tank_kg": self.main_tank_kg,
            "buffer_kg": self.buffer_kg,
            "hrs_kg": self.h2_station_kg
        }


# =========================================================
# 🔷 Fuel Cell (AIRCELL) - Power Re-generation
# =========================================================
class FuelCellAircell:
    def __init__(self):
        self.nominal_p = Config.FC_POWER_NOM_KW
        self.cons_rate = Config.FC_H2_CONSUMPTION_KG_KWH
        self.soh = 1.0

    def generate_power(self, h2_available_kg, demand_kw):
        """Converts H2 back to Power with Heat Recovery."""
        if demand_kw <= 0 or h2_available_kg <= 0:
            return {"p_out": 0.0, "h2_used": 0.0, "heat_kw": 0.0}

        dt = Config.TIMESTEP_SEC
        p_out = min(demand_kw, self.nominal_p)

        # Consumption calculation
        h2_needed = (p_out * self.cons_rate) * (dt / 3600)
        h2_used_mass = min(h2_needed, h2_available_kg)

        # If we didn't have enough H2, scale down power output
        if h2_used_mass < h2_needed:
            p_out *= (h2_used_mass / h2_needed)

        # Efficiency logic: FC is most efficient at ~30-50% load
        load_ratio = p_out / self.nominal_p
        eff = 0.55 - (0.1 * abs(load_ratio - 0.4))

        waste_heat = p_out * (1 - eff) * Config.HEAT_RECOVERY_FACTOR

        return {
            "p_out": float(p_out),
            "h2_used_kg": float(h2_used_mass),
            "heat_kw": float(waste_heat),
            "eff": float(eff)
        }
