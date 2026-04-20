# =============================================================================
# config.py — LUMINIH2 Digital Twin
# Integrated Green Hydrogen & E-Mobility Hub · Zagreb, Croatia
# Version: 3.2 (Streamlit-Ready · Power-Switching Optimised)
# =============================================================================
 
from dataclasses import dataclass, field
from typing import Dict
 
 
@dataclass(frozen=True)
class SystemClock:
    timestep_sec: int = 10
    prediction_horizon_hours: int = 24
 
 
@dataclass(frozen=True)
class Location:
    lat: float = 45.8150
    lon: float = 15.9819
    city: str = "Zagreb"
    country: str = "Croatia"
    timezone: str = "Europe/Zagreb"
 
 
@dataclass(frozen=True)
class Generation:
    """Hybrid PV + Wind generation parameters."""
    pv_capacity_kw: float = 50.0
    wind_capacity_kw: float = 30.0
    inverter_efficiency: float = 0.96
    soiling_loss_rate: float = 0.002        # 0.2% per day without rain
    turbulence_intensity_limit: float = 0.15  # Safety cutout threshold
 
    @property
    def total_capacity_kw(self) -> float:
        return self.pv_capacity_kw + self.wind_capacity_kw
 
 
@dataclass(frozen=True)
class BatteryStorage:
    """BESS — health monitoring & thermal safety."""
    capacity_kwh: float = 100.0
    soc_min: float = 0.15
    soc_max: float = 0.95
    max_charge_kw: float = 25.0
    max_discharge_kw: float = 25.0
    # Health
    cycle_life: int = 5000
    degradation_per_kwh: float = 1.2e-5    # SoH reduction per kWh throughput
    thermal_runaway_temp_c: float = 65.0
    emergency_shutdown_soc: float = 0.05
 
 
@dataclass(frozen=True)
class Electrolyzer:
    """PEM S30/30 — electrochemical physics."""
    p_min_kw: float = 0.74
    p_nom_kw: float = 3.0
    p_max_kw: float = 5.63
    degradation_rate: float = 0.0002
    water_consumption_l_kg: float = 9.0     # High-purity water per kg H₂
    stack_replacement_cost_eur: float = 2500.0
    purity_target_pct: float = 99.999
    # Electrochemical efficiency curve: load_kw → efficiency
    eff_curve: Dict[float, float] = field(
        default_factory=lambda: {0.74: 0.88, 3.0: 0.76, 5.63: 0.62}
    )
 
 
@dataclass(frozen=True)
class Thermodynamics:
    """Tanks, compressor, safety limits."""
    buffer_tank_capacity_kg: float = 2.0
    buffer_start_threshold: float = 0.30   # Compressor ON at 30% fill
    buffer_stop_threshold: float = 0.10
    main_tank_capacity_kg: float = 10.8
    main_tank_dispatch_threshold: float = 0.50
    compressor_power_kw: float = 1.5
    compressor_min_runtime_sec: int = 120   # Hysteresis guard
    joule_thomson_coeff: float = 0.5        # K/bar
    safety_max_pressure_bar: float = 700.0
    min_operating_pressure_bar: float = 30.0
    leak_detection_threshold_kg_h: float = 0.05
 
 
@dataclass(frozen=True)
class Downstream:
    """HRS fuelling station + fuel cell + EV charging."""
    hrs_tank_capacity_kg: float = 5.0
    fc_power_nom_kw: float = 5.0
    fc_h2_consumption_kg_kwh: float = 0.06
    ev_charger_power_kw: float = 22.0
    ev_min_power_kw: float = 2.0
 
 
@dataclass(frozen=True)
class Economics:
    """EU market prices, subsidies, carbon accounting."""
    grid_price_buy_eur_kwh: float = 0.22   # Croatia industrial rate
    grid_price_sell_eur_kwh: float = 0.12
    carbon_tax_eur_ton: float = 85.0       # EU ETS
    grid_co2_intensity_kg_kwh: float = 0.45
    green_h2_subsidy_eur_kg: float = 1.50  # EU Green Hydrogen subsidy
    co2_saved_per_kg_h2: float = 12.0      # vs SMR baseline
    lcoh_target_eur_kg: float = 4.5        # Levelised Cost of Hydrogen
    system_eff_target_pct: float = 72.0
 
 
@dataclass(frozen=True)
class Thermal:
    heat_recovery_factor: float = 0.25
    max_op_temp_c: float = 75.0
 
 
# =============================================================================
# POWER SWITCHING PRIORITIES
# EMS dispatches energy in this strict priority order:
#   1 → Charge BESS (security buffer)
#   2 → Feed Electrolyzer (green H₂ production)
#   3 → Supply EV chargers (via FC if needed)
#   4 → Export surplus to grid (revenue)
#   5 → Import from grid only if BESS < SOC_MIN (emergency)
# =============================================================================
@dataclass(frozen=True)
class PowerSwitching:
    bess_priority: int = 1
    electrolyzer_priority: int = 2
    ev_charger_priority: int = 3
    grid_export_priority: int = 4
    grid_import_priority: int = 5
 
    # Hysteresis bands to prevent rapid switching
    bess_charge_hysteresis_kw: float = 0.5
    elec_start_hysteresis_kw: float = 0.3
    grid_export_min_surplus_kw: float = 1.0  # Don't export tiny amounts
    grid_import_trigger_soc: float = 0.20    # Import only below 20% SoC
 
    # Ramp rates (kW/s) — prevents sharp load transients on electrolyzer
    electrolyzer_ramp_up_kw_s: float = 0.5
    electrolyzer_ramp_down_kw_s: float = 1.0
 
 
# =============================================================================
# MASTER CONFIG — single import point for all modules
# =============================================================================
class Config:
    clock = SystemClock()
    location = Location()
    generation = Generation()
    battery = BatteryStorage()
    electrolyzer = Electrolyzer()
    thermo = Thermodynamics()
    downstream = Downstream()
    economics = Economics()
    thermal = Thermal()
    power_switching = PowerSwitching()
 
    # Flat aliases kept for backward-compatibility with existing code
    TIMESTEP_SEC = clock.timestep_sec
    PREDICTION_HORIZON_HOURS = clock.prediction_horizon_hours
    LOCATION = {"lat": location.lat, "lon": location.lon, "city": location.city}
 
    PV_SYSTEM_CAPACITY_KW = generation.pv_capacity_kw
    WIND_SYSTEM_CAPACITY_KW = generation.wind_capacity_kw
    INVERTER_EFFICIENCY = generation.inverter_efficiency
    SOILING_LOSS_RATE = generation.soiling_loss_rate
    TURBULENCE_INTENSITY_LIMIT = generation.turbulence_intensity_limit
 
    BATT_CAPACITY_KWH = battery.capacity_kwh
    BATT_SOC_MIN = battery.soc_min
    BATT_SOC_MAX = battery.soc_max
    BATT_MAX_CHARGE_KW = battery.max_charge_kw
    BATT_MAX_DISCHARGE_KW = battery.max_discharge_kw
    BATT_CYCLE_LIFE = battery.cycle_life
    BATT_DEGRADATION_PER_KWH = battery.degradation_per_kwh
    THERMAL_RUNAWAY_TEMP = battery.thermal_runaway_temp_c
    EMERGENCY_SHUTDOWN_SOC = battery.emergency_shutdown_soc
 
    ELEC_P_MIN_KW = electrolyzer.p_min_kw
    ELEC_P_NOM_KW = electrolyzer.p_nom_kw
    ELEC_P_MAX_KW = electrolyzer.p_max_kw
    ELECTROLYZER_DEGRADATION_RATE = electrolyzer.degradation_rate
    ELEC_EFF_CURVE = electrolyzer.eff_curve
    WATER_CONSUMPTION_L_KG = electrolyzer.water_consumption_l_kg
    STACK_REPLACEMENT_COST = electrolyzer.stack_replacement_cost_eur
    PURITY_TARGET = electrolyzer.purity_target_pct
 
    BUFFER_TANK_CAPACITY_KG = thermo.buffer_tank_capacity_kg
    BUFFER_START_THRESHOLD = thermo.buffer_start_threshold
    BUFFER_STOP_THRESHOLD = thermo.buffer_stop_threshold
    MAIN_TANK_CAPACITY_KG = thermo.main_tank_capacity_kg
    MAIN_TANK_START_THRESHOLD = thermo.main_tank_dispatch_threshold
    COMPRESSOR_POWER_KW = thermo.compressor_power_kw
    COMPRESSOR_MIN_RUNTIME_SEC = thermo.compressor_min_runtime_sec
    JOULE_THOMSON_COEFF = thermo.joule_thomson_coeff
    SAFETY_MAX_PRESSURE_BAR = thermo.safety_max_pressure_bar
    MIN_OPERATING_PRESSURE_BAR = thermo.min_operating_pressure_bar
    LEAK_DETECTION_THRESHOLD = thermo.leak_detection_threshold_kg_h
 
    HRS_H2_TANK_CAPACITY_KG = downstream.hrs_tank_capacity_kg
    FC_POWER_NOM_KW = downstream.fc_power_nom_kw
    FC_H2_CONSUMPTION_KG_KWH = downstream.fc_h2_consumption_kg_kwh
    EV_CHARGER_POWER_KW = downstream.ev_charger_power_kw
    EV_MIN_POWER_KW = downstream.ev_min_power_kw
 
    GRID_PRICE_BUY = economics.grid_price_buy_eur_kwh
    GRID_PRICE_SELL = economics.grid_price_sell_eur_kwh
    CARBON_TAX_EUR_TON = economics.carbon_tax_eur_ton
    GRID_CO2_INTENSITY = economics.grid_co2_intensity_kg_kwh
    GREEN_H2_SUBSIDY = economics.green_h2_subsidy_eur_kg
    CO2_SAVED_PER_KG_H2 = economics.co2_saved_per_kg_h2
    LCOH_TARGET_EURO_KG = economics.lcoh_target_eur_kg
    SYSTEM_EFF_TARGET = economics.system_eff_target_pct
 
    HEAT_RECOVERY_FACTOR = thermal.heat_recovery_factor
    MAX_OP_TEMP_CELSIUS = thermal.max_op_temp_c
 
 
def validate_config() -> bool:
    """Run at startup — raises ValueError on bad config."""
    c = Config
    assert 0 < c.BATT_SOC_MIN < c.BATT_SOC_MAX < 1.0, "Bad BESS SoC bounds"
    assert c.ELEC_P_MIN_KW < c.ELEC_P_NOM_KW < c.ELEC_P_MAX_KW, "Bad electrolyzer power bounds"
    assert c.BUFFER_STOP_THRESHOLD < c.BUFFER_START_THRESHOLD, "Bad buffer thresholds"
    assert c.MIN_OPERATING_PRESSURE_BAR < c.SAFETY_MAX_PRESSURE_BAR, "Bad pressure bounds"
    assert 0 < c.INVERTER_EFFICIENCY <= 1.0, "Inverter efficiency out of range"
    return True
 
 
if __name__ == "__main__":
    validate_config()
    print("✅ LUMINIH2 Config v3.2 loaded — all validations passed.")
    print(f"   Location  : {Config.location.city}, {Config.location.country}")
    print(f"   Generation: {Config.generation.total_capacity_kw} kW total")
    print(f"   BESS      : {Config.BATT_CAPACITY_KWH} kWh  [{Config.BATT_SOC_MIN*100:.0f}–{Config.BATT_SOC_MAX*100:.0f}%]")
    print(f"   Electrolyzer: {Config.ELEC_P_MIN_KW}–{Config.ELEC_P_MAX_KW} kW")
    print(f"   Power Switching priorities: BESS→Elec→EV→Export→Import")
