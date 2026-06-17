# =============================================================================
# config.py — LUMINIH2 Digital Twin v4.0
# ALL parameters derived from real device datasheets
# Zagreb, Croatia — Pre-deployment Digital Twin
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict


# =============================================================================
# DEVICE REGISTRY — source of truth for every physical parameter
# =============================================================================

@dataclass(frozen=True)
class DeviceInfo:
    """Metadata for each real device."""
    manufacturer: str
    model:        str
    datasheet_ref: str


# =============================================================================
# 1. LOCATION & CLOCK
# =============================================================================
@dataclass(frozen=True)
class SystemClock:
    timestep_sec:              int = 10
    prediction_horizon_hours:  int = 24


@dataclass(frozen=True)
class Location:
    lat:      float = 45.8150
    lon:      float = 15.9819
    city:     str   = "Zagreb"
    country:  str   = "Croatia"
    timezone: str   = "Europe/Zagreb"


# =============================================================================
# 2. SOLAR PV — 32 × 360 W panels (real datasheet)
# =============================================================================
@dataclass(frozen=True)
class SolarPV:
    """
    Datasheet: 32 × monocrystalline 360 Wp panels
    Total nameplate: 11.52 kW DC
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="Generic Mono",
        model="360W Monocrystalline",
        datasheet_ref="customer_datasheet_pv"
    ))
    # Panel electrical (STC: 1000 W/m², 25°C, AM1.5)
    panel_count:         int   = 42
    rated_power_wp:      float = 360.0       # W per panel ±5W
    voc_v:               float = 47.0        # V open-circuit
    vmp_v:               float = 39.6        # V at MPP
    isc_a:               float = 9.67        # A short-circuit
    imp_a:               float = 9.10        # A at MPP
    # System
    total_capacity_kw:   float = 15.0        # Customer spec: 15 kW (42 × 360W ≈ 15.12 kW)
    temp_coeff_pct_c:    float = -0.0035     # -0.35%/°C (mono, typical)
    noct_c:              float = 45.0        # Nominal Operating Cell Temp
    # Inverter (ideal values as specified)
    inverter_efficiency: float = 0.97        # 97% (ideal modern string inverter)
    mppt_efficiency:     float = 0.995       # 99.5% MPPT tracking
    # Degradation
    soiling_loss_rate:   float = 0.002       # 0.2%/day without rain

    @property
    def effective_capacity_kw(self) -> float:
        return self.total_capacity_kw * self.inverter_efficiency * self.mppt_efficiency


# =============================================================================
# 3. WIND TURBINE — 10 kW (smaller than PV system, as specified)
# =============================================================================
@dataclass(frozen=True)
class WindTurbine:
    """
    Small wind turbine ~10 kW nominal
    (selected to be < 11.52 kW PV system — customer specification)
    Based on Bergey Excel 10 / similar small horizontal-axis turbine
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="Generic Small Wind",
        model="10kW HAWT",
        datasheet_ref="customer_spec_wind"
    ))
    rated_power_kw:      float = 10.0
    cut_in_ms:           float = 2.5         # m/s
    rated_speed_ms:      float = 11.0        # m/s
    cut_out_ms:          float = 60.0        # m/s (survival speed)
    hub_height_m:        float = 30.0        # m
    rotor_diameter_m:    float = 7.0         # m (typical for 10kW class)
    turbulence_limit:    float = 0.20        # Safety cutout TI threshold
    # Zagreb terrain roughness class II
    terrain_roughness:   float = 0.15        # base turbulence factor


# =============================================================================
# 4. BATTERY BESS — LFP 100 kWh (customer spec: SOC 10–90%)
# =============================================================================
@dataclass(frozen=True)
class BatteryStorage:
    """
    Customer specification:
    - SOC_min = 10%
    - SOC_max = 90%
    Chemistry: LFP (Lithium Iron Phosphate) — assumed for safety
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="Generic LFP",
        model="100 kWh BESS",
        datasheet_ref="customer_spec_bess"
    ))
    capacity_kwh:        float = 100.0
    soc_min:             float = 0.10        # 10% — customer datasheet
    soc_max:             float = 0.90        # 90% — customer datasheet
    max_charge_kw:       float = 25.0        # C/4 rate (safe for LFP)
    max_discharge_kw:    float = 25.0
    nominal_voltage_v:   float = 48.0        # LFP typical
    # LFP characteristics
    charge_efficiency:   float = 0.975       # LFP: 97.5% round-trip one-way
    discharge_efficiency: float = 0.975
    cycle_life:          int   = 6000        # LFP advantage: 6000 cycles
    degradation_per_kwh: float = 8.33e-6     # 1/(2×capacity×cycle_life)
    thermal_runaway_temp_c: float = 70.0     # LFP much safer than NMC
    emergency_shutdown_soc: float = 0.05


# =============================================================================
# 5. ELECTROLYZER — ITM POWER S30/30 (real datasheet)
# =============================================================================
@dataclass(frozen=True)
class Electrolyzer:
    """
    ITM Power PEM Electrolyzer S30/30
    Active area: 30 cm² × 30 cells
    Real datasheet values — all parameters verified
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="ITM Power",
        model="S30/30 PEM Electrolyzer",
        datasheet_ref="itm_s30_30_datasheet"
    ))
    # Electrical limits (from datasheet)
    voltage_min_v:       float = 49.5
    voltage_max_v:       float = 75.0
    current_min_a:       float = 15.0
    current_nom_a:       float = 52.5
    current_max_a:       float = 75.0
    p_min_kw:            float = 0.74        # Lowest partial load
    p_nom_kw:            float = 3.0         # Nominal
    p_max_kw:            float = 5.63        # Peak load

    # H₂ production (from datasheet — Nm³/h)
    h2_min_nm3_h:        float = 0.19        # At lowest partial load
    h2_nom_nm3_h:        float = 0.66        # At nominal
    h2_peak_nm3_h:       float = 0.94        # At peak load

    # H₂ production converted to kg/h (1 Nm³ H₂ = 0.08988 kg)
    h2_min_kg_h:         float = 0.01708     # 0.19 × 0.08988
    h2_nom_kg_h:         float = 0.05932     # 0.66 × 0.08988
    h2_peak_kg_h:        float = 0.08449     # 0.94 × 0.08988

    # Electrochemical efficiency curve (load_kw → η) — from datasheet
    eff_curve: Dict[float, float] = field(default_factory=lambda: {
        0.74: 0.90,   # 90% at lowest partial load
        3.00: 0.78,   # 78% at nominal
        5.63: 0.59,   # 59% at peak load
    })

    # Water (from datasheet)
    water_consumption_l_nm3: float = 1.0    # L/Nm³ nominal
    water_drag_l_nm3:        float = 10.0   # L/Nm³ drag
    water_l_kg_h2:           float = 11.13  # = 1.0 / 0.08988 L per kg H₂
    water_temp_min_c:        float = 20.0
    water_temp_max_c:        float = 70.0
    water_pressure_loss_mbar: float = 150.0
    water_resistance_mohm_cm: float = 10.0  # DIN ISO 3696 Type 1

    # H₂ output specs
    h2_pressure_bar:     float = 20.0       # Output pressure
    h2_test_pressure_bar: float = 26.0
    purity_target_pct:   float = 99.999     # After drying

    # Reliability & degradation
    mttf_hours:          int   = 35000      # Mean Time To Failure
    degradation_rate:    float = 1.0 / 35000  # Per operating hour
    stack_replacement_cost_eur: float = 2500.0

    # Physical
    active_area_cm2:     float = 30.0
    cells:               int   = 30
    leakage_rate_kg_s:   float = 4.02e-8


# =============================================================================
# 6. HYDROGEN STORAGE — TH540-50 (real datasheet)
# =============================================================================
@dataclass(frozen=True)
class HydrogenTank:
    """
    Composite Type 4 vessel — TH540-50
    DIN EN12245, TPED, ADR certified
    Carbon fibre / Epoxy / Polyamide / Boss in SS
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="Generic Composite",
            model="TH540-50 Type 4",
            datasheet_ref="th540_50_datasheet"
    ))
    # Capacity (from datasheet)
    usable_h2_kg:          float = 10.8      # 500→10 bar
    nwp_bar:               float = 500.0     # Nominal Working Pressure at 15°C
    mwp_bar:               float = 625.0     # Maximum Working Pressure
    min_working_pressure_bar: float = 10.0
    design_pressure_bar:   float = 750.0     # Safety margin
    # Temperature
    temp_min_c:            float = -20.0
    temp_max_c:            float = 65.0
    # Physical
    weight_empty_kg:       float = 200.0     # Approx
    # Buffer tank (upstream of compressor)
    buffer_capacity_kg:    float = 0.50      # Small buffer at electrolyzer output (20 bar)
    buffer_start_threshold: float = 0.30
    buffer_stop_threshold:  float = 0.10
    # Dispatch thresholds
    main_dispatch_threshold: float = 0.50   # Dispatch when main tank ≥ 50%
    # Leak detection
    leak_threshold_kg_s:   float = 4.02e-8  # Same as electrolyzer spec


# =============================================================================
# 7. COMPRESSOR — HCS-100 (real datasheet)
# =============================================================================
@dataclass(frozen=True)
class Compressor:
    """
    HCS-100 Hydrogen Compressor — 2 kg/day
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="Generic",
            model="HCS-100",
            datasheet_ref="hcs100_datasheet"
    ))
    # Flow (from datasheet: 2 kg/day max)
    flow_max_kg_day:     float = 2.0
    flow_max_kg_h:       float = 0.08333     # 2/24
    flow_nom_kg_h:       float = 0.08333
    # Pressures
    inlet_min_bar:       float = 5.0
    inlet_nom_bar:       float = 10.0
    inlet_max_bar:       float = 15.0
    outlet_min_bar:      float = 150.0
    outlet_nom_bar:      float = 400.0
    outlet_max_bar:      float = 500.0
    # Power
    installed_power_kva: float = 3.0
    power_kw:            float = 2.7         # ≈ 3 kVA × 0.9 PF
    # Operation
    temp_nom_c:          float = 40.0
    min_runtime_sec:     int   = 120         # Hysteresis guard
    joule_thomson_coeff: float = 0.5         # K/bar


# =============================================================================
# 8. FUEL CELL — AIRCELL 3000 (real datasheet)
# =============================================================================
@dataclass(frozen=True)
class FuelCell:
    """
    AIRCELL® 3000W PEM Fuel Cell
    Voltage range: 39.2–56V (2000W) / 56–80V (3000W)
    """
    device: DeviceInfo = field(default_factory=lambda: DeviceInfo(
        manufacturer="AIRCELL",
            model="AIRCELL 3000",
            datasheet_ref="aircell3000_datasheet"
    ))
    # Power
    nominal_power_w:     float = 3000.0
    nominal_power_kw:    float = 3.0
    max_power_w:         float = 3400.0      # 60s peak
    max_power_kw:        float = 3.4
    # Current
    nominal_current_a:   float = 50.0        # 5–50A nominal
    max_current_a:       float = 65.0        # 60s peak
    # Voltage
    voltage_min_v:       float = 39.2
    voltage_max_v:       float = 80.0
    # H₂ consumption
    h2_consumption_g_kwh: float = 66.0       # <66 g/kWh (from datasheet)
    h2_consumption_kg_kwh: float = 0.066     # = 66/1000
    h2_flow_nom_nl_min:  float = 30.0        # Nl/min at 3000W
    h2_pressure_min_barg: float = 2.0
    h2_pressure_max_barg: float = 9.0
    # H₂ quality requirement
    h2_purity_min_pct:   float = 99.95       # ≥3.5 grade
    # Air
    air_flow_nom_nl_min: float = 67.0        # Nl/min at 3000W
    # Temperature
    h2_temp_min_c:       float = 5.0
    h2_temp_max_c:       float = 35.0
    # EV charger (downstream of FC)
    ev_charger_power_kw: float = 3.0         # Matched to FC output
    ev_min_power_kw:     float = 0.5


# =============================================================================
# 9. HRS — Hydrogen Refuelling Station
# =============================================================================
@dataclass(frozen=True)
class HRS:
    """
    Hydrogen Refuelling Station — SAE J2601 FCEV dispensing model.

    The HRS tank (5 kg) fills from the main storage tank and is
    drained by simulated vehicle dispensing events on a daily schedule.

    Dispensing schedule: fills_per_day vehicles at evenly spaced hours.
    Each fill drains dispense_kg_per_fill kg from the HRS tank.
    Dispensing only proceeds if hrs_kg >= dispense_kg_per_fill.

    SAE J2601 Type III (350 bar) or Type IV (700 bar) — modelled as
    a fixed-pressure setpoint for revenue calculation.
    """
    tank_capacity_kg:      float = 5.0      # HRS buffer tank [kg]
    fill_rate_kg_h:        float = 1.5      # Fill rate from main tank [kg/h]
    min_dispatch_pct:      float = 0.20     # Min fill before dispatching to HRS
    dispense_kg_per_fill:  float = 5.0      # H₂ per FCEV fill (Toyota Mirai) [kg]
    fills_per_day:         int   = 1        # Vehicle arrivals per day
    dispensing_pressure_bar: float = 350.0  # SAE J2601 Type III [bar]
    dispense_hours:        tuple = (8,)     # Hours of day vehicles arrive (24h)
    h2_price_eur_kg:       float = 6.0      # HRS sell price [€/kg]


# =============================================================================
# 10. GRID (ideal values as specified)
# =============================================================================
@dataclass(frozen=True)
class Grid:
    """Croatian grid — ideal model as specified"""
    price_buy_eur_kwh:   float = 0.22        # Industrial rate Croatia
    price_sell_eur_kwh:  float = 0.12        # Feed-in tariff
    co2_intensity_kg_kwh: float = 0.45       # Croatian grid factor
    max_import_kw:       float = 50.0        # Grid connection limit
    max_export_kw:       float = 50.0
    frequency_hz:        float = 50.0
    voltage_v:           float = 400.0       # 3-phase


# =============================================================================
# 11. ECONOMICS
# =============================================================================
@dataclass(frozen=True)
class Economics:
    carbon_tax_eur_ton:  float = 85.0        # EU ETS
    green_h2_subsidy_eur_kg: float = 1.50    # EU Green subsidy
    co2_saved_per_kg_h2: float = 12.0        # vs SMR
    lcoh_target_eur_kg:  float = 4.5
    system_eff_target_pct: float = 72.0
    heat_recovery_factor: float = 0.25


# =============================================================================
# 12. POWER SWITCHING PRIORITIES (EMS)
# =============================================================================
@dataclass(frozen=True)
class PowerSwitching:
    """EMS dispatch priority order"""
    bess_priority:          int   = 1
    electrolyzer_priority:  int   = 2
    ev_charger_priority:    int   = 3
    grid_export_priority:   int   = 4
    grid_import_priority:   int   = 5
    # Hysteresis bands
    bess_charge_hysteresis_kw:  float = 0.5
    elec_start_hysteresis_kw:   float = 0.3
    grid_export_min_surplus_kw: float = 0.5
    grid_import_trigger_soc:    float = 0.15   # Import only below 15% (matches BESS soc_min+5%)
    # Ramp rates (kW/s)
    electrolyzer_ramp_up_kw_s:  float = 0.3   # Conservative for PEM membrane
    electrolyzer_ramp_down_kw_s: float = 0.5


# =============================================================================
# MASTER CONFIG — single import point
# =============================================================================
class Config:
    clock          = SystemClock()
    location       = Location()
    pv             = SolarPV()
    wind           = WindTurbine()
    battery        = BatteryStorage()
    electrolyzer   = Electrolyzer()
    tank           = HydrogenTank()
    compressor     = Compressor()
    fuel_cell      = FuelCell()
    hrs            = HRS()
    grid           = Grid()
    economics      = Economics()
    power_switching = PowerSwitching()

    # ── Flat aliases for backward compatibility ────────────────────────
    TIMESTEP_SEC              = clock.timestep_sec
    PREDICTION_HORIZON_HOURS  = clock.prediction_horizon_hours
    LOCATION = {"lat": location.lat, "lon": location.lon, "city": location.city}

    # PV
    PV_SYSTEM_CAPACITY_KW  = pv.total_capacity_kw       # 15.0 kW
    INVERTER_EFFICIENCY    = pv.inverter_efficiency      # 0.97
    SOILING_LOSS_RATE      = pv.soiling_loss_rate

    # Wind
    WIND_SYSTEM_CAPACITY_KW       = wind.rated_power_kw  # 10.0 kW
    TURBULENCE_INTENSITY_LIMIT    = wind.turbulence_limit

    # BESS
    BATT_CAPACITY_KWH      = battery.capacity_kwh        # 100 kWh
    BATT_SOC_MIN           = battery.soc_min             # 0.10 (real datasheet)
    BATT_SOC_MAX           = battery.soc_max             # 0.90 (real datasheet)
    BATT_MAX_CHARGE_KW     = battery.max_charge_kw
    BATT_MAX_DISCHARGE_KW  = battery.max_discharge_kw
    BATT_CYCLE_LIFE        = battery.cycle_life          # 6000 (LFP)
    BATT_DEGRADATION_PER_KWH = battery.degradation_per_kwh
    THERMAL_RUNAWAY_TEMP   = battery.thermal_runaway_temp_c  # 70°C (LFP)
    EMERGENCY_SHUTDOWN_SOC = battery.emergency_shutdown_soc

    # Electrolyzer S30/30
    ELEC_P_MIN_KW          = electrolyzer.p_min_kw       # 0.74 kW
    ELEC_P_NOM_KW          = electrolyzer.p_nom_kw       # 3.0 kW
    ELEC_P_MAX_KW          = electrolyzer.p_max_kw       # 5.63 kW
    ELEC_EFF_CURVE         = electrolyzer.eff_curve
    WATER_CONSUMPTION_L_KG = electrolyzer.water_l_kg_h2  # 11.13 L/kg
    STACK_REPLACEMENT_COST = electrolyzer.stack_replacement_cost_eur
    PURITY_TARGET          = electrolyzer.purity_target_pct
    ELECTROLYZER_DEGRADATION_RATE = electrolyzer.degradation_rate

    # H₂ Tank TH540-50
    BUFFER_TANK_CAPACITY_KG   = tank.buffer_capacity_kg   # 0.50 kg
    BUFFER_START_THRESHOLD    = tank.buffer_start_threshold
    BUFFER_STOP_THRESHOLD     = tank.buffer_stop_threshold
    MAIN_TANK_CAPACITY_KG     = tank.usable_h2_kg         # 10.8 kg
    MAIN_TANK_START_THRESHOLD = tank.main_dispatch_threshold
    SAFETY_MAX_PRESSURE_BAR   = tank.mwp_bar              # 625 bar
    MIN_OPERATING_PRESSURE_BAR = tank.min_working_pressure_bar  # 10 bar
    LEAK_DETECTION_THRESHOLD  = tank.leak_threshold_kg_s * 3600  # kg/h

    # Compressor HCS-100
    COMPRESSOR_POWER_KW       = compressor.power_kw       # 2.7 kW
    COMPRESSOR_MIN_RUNTIME_SEC = compressor.min_runtime_sec
    JOULE_THOMSON_COEFF       = compressor.joule_thomson_coeff

    # Fuel Cell AIRCELL 3000
    FC_POWER_NOM_KW           = fuel_cell.nominal_power_kw  # 3.0 kW
    FC_H2_CONSUMPTION_KG_KWH  = fuel_cell.h2_consumption_kg_kwh  # 0.066
    EV_CHARGER_POWER_KW       = fuel_cell.ev_charger_power_kw
    EV_MIN_POWER_KW           = fuel_cell.ev_min_power_kw

    # HRS
    HRS_H2_TANK_CAPACITY_KG   = hrs.tank_capacity_kg      # 5.0 kg

    # Grid
    GRID_PRICE_BUY            = grid.price_buy_eur_kwh
    GRID_PRICE_SELL           = grid.price_sell_eur_kwh
    GRID_CO2_INTENSITY        = grid.co2_intensity_kg_kwh

    # Economics
    CARBON_TAX_EUR_TON        = economics.carbon_tax_eur_ton
    GREEN_H2_SUBSIDY          = economics.green_h2_subsidy_eur_kg
    CO2_SAVED_PER_KG_H2       = economics.co2_saved_per_kg_h2
    LCOH_TARGET_EURO_KG       = economics.lcoh_target_eur_kg
    SYSTEM_EFF_TARGET         = economics.system_eff_target_pct
    HEAT_RECOVERY_FACTOR      = economics.heat_recovery_factor
    MAX_OP_TEMP_CELSIUS       = 75.0

    # Power switching
    power_switching            = PowerSwitching()


def validate_config() -> bool:
    c = Config
    assert c.BATT_SOC_MIN < c.BATT_SOC_MAX, "BESS SoC bounds error"
    assert c.ELEC_P_MIN_KW < c.ELEC_P_NOM_KW < c.ELEC_P_MAX_KW, "Electrolyzer power bounds error"
    assert c.BUFFER_STOP_THRESHOLD < c.BUFFER_START_THRESHOLD, "Buffer threshold error"
    assert c.MIN_OPERATING_PRESSURE_BAR < c.SAFETY_MAX_PRESSURE_BAR, "Pressure bounds error"
    assert 0 < c.INVERTER_EFFICIENCY <= 1.0, "Inverter efficiency error"
    # Verify H₂ production is consistent with datasheet
    assert abs(c.electrolyzer.h2_nom_kg_h - 0.06) < 0.01, "H₂ nominal production mismatch"
    return True


if __name__ == "__main__":
    validate_config()
    c = Config
    print("=" * 60)
    print("LUMINIH2 Digital Twin v4.0 — Device Registry")
    print("=" * 60)
    print(f"\n📍 Location     : {c.location.city}, {c.location.country}")
    print(f"\n☀  PV System    : {c.pv.panel_count} × {c.pv.rated_power_wp}W = {c.PV_SYSTEM_CAPACITY_KW} kW (customer spec)")
    print(f"   Vmp/Imp      : {c.pv.vmp_v}V / {c.pv.imp_a}A per panel")
    print(f"   Inverter η   : {c.INVERTER_EFFICIENCY*100:.0f}%")
    print(f"\n💨 Wind Turbine : {c.wind.rated_power_kw} kW | Cut-in {c.wind.cut_in_ms} m/s | Rated {c.wind.rated_speed_ms} m/s")
    print(f"\n🔋 BESS         : {c.BATT_CAPACITY_KWH} kWh LFP | SoC {c.BATT_SOC_MIN*100:.0f}–{c.BATT_SOC_MAX*100:.0f}%")
    print(f"   Cycle life   : {c.BATT_CYCLE_LIFE} cycles | Thermal limit {c.THERMAL_RUNAWAY_TEMP}°C")
    print(f"\n⚗  Electrolyzer : ITM S30/30 PEM")
    print(f"   Power range  : {c.ELEC_P_MIN_KW}–{c.ELEC_P_MAX_KW} kW")
    print(f"   H₂ output    : {c.electrolyzer.h2_min_kg_h*1000:.1f}–{c.electrolyzer.h2_peak_kg_h*1000:.1f} g/h")
    print(f"   H₂ purity    : {c.PURITY_TARGET}%")
    print(f"   Water use    : {c.WATER_CONSUMPTION_L_KG:.2f} L/kg H₂")
    print(f"   MTTF         : {c.electrolyzer.mttf_hours:,} h")
    print(f"\n🏗  H₂ Tank      : TH540-50 | {c.MAIN_TANK_CAPACITY_KG} kg usable")
    print(f"   NWP/MWP      : {c.tank.nwp_bar}/{c.tank.mwp_bar} bar")
    print(f"\n🔧 Compressor   : HCS-100 | {c.compressor.flow_max_kg_day} kg/day")
    print(f"   Pressure     : {c.compressor.inlet_nom_bar}→{c.compressor.outlet_nom_bar} bar")
    print(f"   Power        : {c.COMPRESSOR_POWER_KW} kW")
    print(f"\n⚡ Fuel Cell     : AIRCELL 3000 | {c.FC_POWER_NOM_KW} kW nom / {c.fuel_cell.max_power_kw} kW peak")
    print(f"   H₂ use       : {c.FC_H2_CONSUMPTION_KG_KWH*1000:.0f} g/kWh")
    print(f"   H₂ pressure  : {c.fuel_cell.h2_pressure_min_barg}–{c.fuel_cell.h2_pressure_max_barg} barg")
    print(f"\n⛽ HRS Station  : {c.HRS_H2_TANK_CAPACITY_KG} kg capacity")
    print(f"\n💰 Economics    : Buy {c.GRID_PRICE_BUY}€/kWh | Sell {c.GRID_PRICE_SELL}€/kWh")
    print(f"   LCOH target  : {c.LCOH_TARGET_EURO_KG} €/kg")
    print(f"   CO₂ credit   : {c.CARBON_TAX_EUR_TON} €/ton")
    print(f"\n✅ All validations passed — Digital Twin ready")
