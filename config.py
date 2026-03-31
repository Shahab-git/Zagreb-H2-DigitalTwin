# config.py
# Digital Twin: Integrated Green Hydrogen & E-Mobility Hub (Zagreb, Croatia)
# Version: 3.0 (Industrial High-Fidelity)

class Config:
    # === 1. SYSTEM CLOCK & LOCATION ===
    TIMESTEP_SEC = 10  # Real-time simulation step
    LOCATION = {"lat": 45.8150, "lon": 15.9819, "city": "Zagreb"}
    PREDICTION_HORIZON_HOURS = 24

    # === 2. HYBRID GENERATION (Environmental Realism) ===
    PV_SYSTEM_CAPACITY_KW = 50.0  # Scaled for industrial pilot
    WIND_SYSTEM_CAPACITY_KW = 30.0
    INVERTER_EFFICIENCY = 0.96
    SOILING_LOSS_RATE = 0.002  # 0.2% efficiency drop per day without rain
    TURBULENCE_INTENSITY_LIMIT = 0.15  # Max wind turbulence before safety cutout

    # === 3. ENERGY STORAGE (BESS Health Monitoring) ===
    BATT_CAPACITY_KWH = 100.0
    BATT_SOC_MIN = 0.15
    BATT_SOC_MAX = 0.95
    BATT_MAX_CHARGE_KW = 25.0
    BATT_MAX_DISCHARGE_KW = 25.0
    # Health (SoH) parameters
    BATT_CYCLE_LIFE = 5000  # Rated cycles before EoL
    BATT_DEGRADATION_PER_KWH = 1.2e-5  # SoH reduction per kWh throughput
    THERMAL_RUNAWAY_TEMP = 65.0  # Critical Celsius threshold

    # === 4. ELECTROLYZER PHYSICS (PEM S30/30) ===
    ELEC_P_MIN_KW = 0.74
    ELEC_P_NOM_KW = 3.0
    ELEC_P_MAX_KW = 5.63
    # Electrochemical Curve: Load vs Efficiency
    ELEC_EFF_CURVE = {0.74: 0.88, 3.0: 0.76, 5.63: 0.62}
    WATER_CONSUMPTION_L_KG = 9.0  # Stoichiometric high-purity water demand
    STACK_REPLACEMENT_COST = 2500.0  # EUR
    PURITY_TARGET = 99.999  # % H2 Purity

    # === 5. THERMODYNAMICS & LOGISTICS ===
    BUFFER_TANK_CAPACITY_KG = 2.0
    BUFFER_START_THRESHOLD = 0.30  # Compressor starts at 30%
    BUFFER_STOP_THRESHOLD = 0.10

    MAIN_TANK_CAPACITY_KG = 10.8
    MAIN_TANK_START_THRESHOLD = 0.50  # Dispatching starts at 50%

    COMPRESSOR_POWER_KW = 1.5
    JOULE_THOMSON_COEFF = 0.5  # K/bar cooling/heating effect
    SAFETY_MAX_PRESSURE_BAR = 700.0
    LEAK_DETECTION_THRESHOLD = 0.05  # kg/h unexplained loss

    # === 6. DOWNSTREAM CONSUMPTION (HRS & FC) ===
    HRS_H2_TANK_CAPACITY_KG = 5.0  # Required fuel for station
    FC_POWER_NOM_KW = 5.0
    FC_H2_CONSUMPTION_KG_KWH = 0.06  # Hydrogen used per kWh generated

    EV_CHARGER_POWER_KW = 22.0  # Level 2 Fast Charger
    EV_MIN_POWER_KW = 2.0

    # === 7. GRID INTERACTION & ECONOMICS (EU Market) ===
    GRID_PRICE_BUY = 0.22  # EUR/kWh (Croatia Industrial Rate)
    GRID_PRICE_SELL = 0.12  # EUR/kWh
    CARBON_TAX_EUR_TON = 85.0  # EU ETS Market Price
    GRID_CO2_INTENSITY = 0.45  # kg CO2/kWh (Local Grid Factor)
    GREEN_H2_SUBSIDY = 1.50  # EUR/kg (EU Green Subsidy)

    # === 8. KEY PERFORMANCE INDICATORS (KPIs) ===
    CO2_SAVED_PER_KG_H2 = 12.0  # vs Steam Methane Reforming
    LCOH_TARGET_EURO_KG = 4.5  # Levelized Cost of Hydrogen Target
    SYSTEM_EFF_TARGET = 72.0  # Overall System Target (%)

    # === 9. SAFETY & THERMAL MANAGEMENT ===
    HEAT_RECOVERY_FACTOR = 0.25  # Heat recycled for local heating
    MAX_OP_TEMP_CELSIUS = 75.0
    EMERGENCY_SHUTDOWN_SOC = 0.05  # Critical battery shutdown


print("🚀 Industrial-Grade Digital Twin Configuration [English] Loaded Successfully.")
