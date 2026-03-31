# ems_brain.py
# Economic & Strategy Engine: LCOH, Carbon Credits, and Smart Dispatching
# Version: 3.0 (Industrial Realism)

from config import Config


class EMSBrain:
    def __init__(self):
        self.config = Config()

    def decide_energy_source(self, pv_available, wind_available, battery_soc):
        """Phase 1: Dynamic Source Selection (PV -> Wind -> Grid)"""
        # Prioritize Solar (Most sustainable/lowest cost)
        if pv_available >= self.config.ELEC_P_MIN_KW:
            return "Solar (PV)", pv_available
        # Secondary: Wind
        elif wind_available >= self.config.ELEC_P_MIN_KW:
            return "Wind Turbine", wind_available
        # Last Resort: Grid (Ensures stack membrane health)
        else:
            return "National Grid", self.config.ELEC_P_MIN_KW

    def manage_power_flow(self, incoming_power, current_soc):
        """Phase 2: Power Smoothing & Battery Protection"""
        power_to_battery = 0
        power_to_elec = 0

        # Charge battery first to ensure a stable supply buffer for the PEM stack
        if current_soc < self.config.BATT_SOC_MAX:
            power_to_battery = min(incoming_power, self.config.BATT_MAX_CHARGE_KW)
            power_to_elec = incoming_power - power_to_battery
        else:
            power_to_elec = incoming_power

        # Enforce S30/30 Physical Constraints
        power_to_elec = min(max(power_to_elec, 0), self.config.ELEC_P_MAX_KW)
        return power_to_battery, power_to_elec

    def hydrogen_logistics_control(self, buffer_level_kg, main_tank_kg, hrs_tank_kg):
        """Phase 3: Mass Flow Strategy (Buffer -> Main -> HRS/FC)"""
        # Compressor Hysteresis Logic
        buffer_percent = buffer_level_kg / self.config.BUFFER_TANK_CAPACITY_KG
        compressor_status = "OFF"
        if buffer_percent >= self.config.BUFFER_START_THRESHOLD:
            compressor_status = "ON"
        elif buffer_percent <= self.config.BUFFER_STOP_THRESHOLD:
            compressor_status = "OFF"

        # Dispatching Priority (HRS > Fuel Cell)
        main_tank_percent = main_tank_kg / self.config.MAIN_TANK_CAPACITY_KG
        dispatch_target = "Storage"

        if main_tank_percent >= self.config.MAIN_TANK_START_THRESHOLD:
            if hrs_tank_kg < self.config.HRS_H2_TANK_CAPACITY_KG:
                dispatch_target = "Refueling Station (HRS)"
            else:
                dispatch_target = "Fuel Cell (FC)"

        return compressor_status, dispatch_target

    def calculate_economics(self, h2_kg_produced, power_used_kw, source):
        """
        Phase 4: Levelized Cost of Hydrogen (LCOH) & Carbon Credits
        Calculates real-time financial viability based on the EU ETS market.
        """
        if h2_kg_produced <= 0:
            return {"lcoh": 0.0, "carbon_revenue": 0.0, "net_co2_kg": 0.0}

        # 1. Real-time Energy Cost
        if source == "National Grid":
            energy_cost = power_used_kw * self.config.GRID_PRICE_BUY
        else:
            # Operational cost for local renewables (Maintenance/O&M)
            energy_cost = power_used_kw * 0.02

            # 2. Levelized Cost of Hydrogen (LCOH) - Simplified for Real-time
        # Includes stack degradation factor (~0.45 EUR/hr estimation)
        hourly_depreciation = (power_used_kw / self.config.ELEC_P_MAX_KW) * 0.50
        total_cost = energy_cost + hourly_depreciation
        lcoh = total_cost / h2_kg_produced

        # 3. Carbon Arbitrage (vs Grey Hydrogen SMR)
        # SMR H2 produces ~12kg CO2 per 1kg H2
        co2_avoided = h2_kg_produced * self.config.CO2_SAVED_PER_KG_H2

        # Factor in Grid Intensity if source is Grid
        co2_emitted = 0
        if source == "National Grid":
            co2_emitted = power_used_kw * self.config.GRID_CO2_INTENSITY

        net_co2_saved = co2_avoided - co2_emitted
        # Financial Gain from EU Carbon Market (Carbon Credits)
        carbon_revenue = (net_co2_saved / 1000) * self.config.CARBON_TAX_EUR_TON

        # 4. Total Financial Benefit (Subsidy + Carbon)
        green_subsidy = h2_kg_produced * self.config.GREEN_H2_SUBSIDY

        return {
            "lcoh": float(lcoh),
            "carbon_revenue": float(carbon_revenue),
            "net_co2_kg": float(net_co2_saved),
            "subsidy_earned": float(green_subsidy)
        }

    def manage_fc_and_grid(self, fc_power_output, ev_demand):
        """Phase 5: Downstream Power Revenue (EV -> Grid)"""
        power_to_ev = min(fc_power_output, ev_demand)
        power_to_grid = max(0, fc_power_output - power_to_ev)

        # Economic impact of selling back to grid
        grid_revenue = power_to_grid * self.config.GRID_PRICE_SELL

        return {
            "p_ev": power_to_ev,
            "p_grid": power_to_grid,
            "revenue": grid_revenue
        }
