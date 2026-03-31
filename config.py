# config.py
# Digital Twin Project: Green Hydrogen Production & E-Mobility Hub (Zagreb)

class Config:
    TIMESTEP_SEC = 10  # تایم‌استپ شبیه‌سازی به ثانیه

    # === ۱. لایه محیطی و داده (Environmental Layer) ===
    LOCATION = {"lat": 45.8150, "lon": 15.9819, "city": "Zagreb"}
    PREDICTION_HORIZON_HOURS = 24

    # === ۲. تولید و مدیریت انرژی (Hybrid Generation) ===
    PV_SYSTEM_CAPACITY_KW = 15.0
    WIND_SYSTEM_CAPACITY_KW = 5.0
    PV_MIN_USEFUL_KW = 2.0   # threshold برای PV مفید
    INVERTER_EFFICIENCY = 0.96
    BASE_LOAD_KW = 3.0

    # === ۳. ذخیره‌سازی باتری (BESS) ===
    BATT_CAPACITY_KWH = 30.0
    BATT_SOC_MIN = 0.10
    BATT_SOC_CRITICAL = 0.20
    BATT_SOC_MAX = 0.95
    BATT_MAX_CHARGE_KW = 10.0
    BATT_MAX_DISCHARGE_KW = 10.0
    BATTERY_DEGRADATION_RATE = 0.0001  # industrial realism

    # === ۴. تولید هیدروژن (Electrolyzer S30/30) ===
    ELEC_P_MIN_KW = 0.74
    ELEC_P_NOM_KW = 3.0
    ELEC_P_MAX_KW = 5.63
    ELEC_EFF_CURVE = {0.74: 0.90, 3.0: 0.78, 5.63: 0.59}
    H2_PRODUCTION_RATE_KG_PER_KWH = 0.02
    ELECTROLYZER_MIN_RUNTIME_SEC = 180
    ELECTROLYZER_DEGRADATION_RATE = 0.0002

    # === ۵. زنجیره ذخیره‌سازی و فشرده‌سازی (Storage Logic) ===
    BUFFER_TANK_CAPACITY_KG = 2.0
    BUFFER_START_THRESHOLD = 0.30
    BUFFER_STOP_THRESHOLD = 0.15
    MAIN_TANK_CAPACITY_KG = 10.8
    MAIN_TANK_START_THRESHOLD = 0.50
    MAIN_TANK_STOP_THRESHOLD = 0.30
    COMPRESSOR_POWER_KW = 3.0
    COMPRESSOR_P_NOM_KW = COMPRESSOR_POWER_KW  # هماهنگی با main.py
    COMPRESSOR_MIN_RUNTIME_SEC = 120
    SAFETY_MAX_PRESSURE_BAR = 625.0
    MIN_OPERATING_PRESSURE_BAR = 30.0

    # === ۶. ایستگاه‌ها و مصرف‌کننده‌ها (Downstream) ===
    HRS_H2_TANK_CAPACITY_KG = 5.0
    FC_POWER_NOM_KW = 3.0
    FC_H2_CONSUMPTION_G_KWH = 66.0
    FC_PRIORITY_ORDER = ["Battery", "EV_Station", "Grid"]

    EV_CHARGER_POWER_KW = 22.0
    EV_MIN_POWER_KW = 2.0
    EV_ENABLE_SOC = 0.40  # EV فقط زمانی شارژ می‌شود که SOC باتری کافی باشد

    # === ۷. تعامل با شبکه (Grid Strategy) ===
    GRID_PRICE_BUY = 0.22
    GRID_PRICE_SELL = 0.09
    GRID_IMPORT_LIMIT_KW = 10.0
    GRID_EXPORT_LIMIT_KW = 10.0
    GRID_LOW_PRICE_THRESHOLD = 0.15
    GRID_HIGH_PRICE_THRESHOLD = 0.25

    # === ۸. شاخص‌های اقتصادی و محیطی (KPI) ===
    CO2_SAVED_PER_KG_H2 = 22.0
    INVESTMENT_COST_EURO = 55000
    SYSTEM_EFF_TARGET = 65.0  # برای داشبورد و KPI

    # === ۹. ایمنی و حرارت ===
    HEAT_RECOVERY_FACTOR = 0.15
    MAX_OP_TEMP_CELSIUS = 70.0

print("🚀 Integrated Digital Twin Config (Industrial Ready) Loaded Successfully.")