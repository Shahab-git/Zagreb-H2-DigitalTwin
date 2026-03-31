# ems_brain.py (Advanced Integrated Version)
from config import Config


class EMSBrain:
    def __init__(self):
        self.config = Config()

    def decide_energy_source(self, pv_available, wind_available, battery_soc):
        """
        ۱. انتخاب منبع انرژی (Logic: PV -> Wind -> Grid)
        طبق سناریو: اگر PV کم بود به Wind و اگر آن هم نبود به Grid سوئیچ می‌شود.
        """
        if pv_available >= self.config.ELEC_P_MIN_KW:
            return "Solar (PV)", pv_available
        elif wind_available >= self.config.ELEC_P_MIN_KW:
            return "Wind Turbine", wind_available
        else:
            # سوئیچ به شبکه برای تأمین حداقل توان مورد نیاز الکترولایزر
            return "National Grid", self.config.ELEC_P_MIN_KW

    def manage_power_flow(self, incoming_power, current_soc):
        """
        ۲. پایداری تغذیه و اولویت شارژ باتری
        طبق سناریو: ابتدا باتری شارژ شود تا به الکترولایزر آسیب نرسد.
        """
        power_to_battery = 0
        power_to_elec = 0

        # اگر باتری به سقف ماکزیمم نرسیده، اولویت با شارژ است
        if current_soc < self.config.BATT_SOC_MAX:
            power_to_battery = min(incoming_power, self.config.BATT_MAX_CHARGE_KW)
            # توان باقی‌مانده پس از شارژ باتری به الکترولایزر می‌رود
            power_to_elec = incoming_power - power_to_battery
        else:
            # اگر باتری پر بود، کل توان در دسترس به الکترولایزر می‌رود
            power_to_elec = incoming_power

        # محدود کردن توان الکترولایزر بر اساس دیتاشیت (S30/30)
        power_to_elec = min(max(power_to_elec, 0), self.config.ELEC_P_MAX_KW)

        return power_to_battery, power_to_elec

    def hydrogen_logistics_control(self, buffer_level_kg, main_tank_kg, hrs_tank_kg):
        """
        ۳. مدیریت زنجیره هیدروژن (Buffer -> Compressor -> Main Tank -> HRS -> FC)
        """
        # --- کنترل کمپرسور (Hysteresis 30%) ---
        buffer_percent = buffer_level_kg / self.config.BUFFER_TANK_CAPACITY_KG
        compressor_status = "OFF"
        if buffer_percent >= self.config.BUFFER_START_THRESHOLD:
            compressor_status = "ON"
        elif buffer_percent <= self.config.BUFFER_STOP_THRESHOLD:
            compressor_status = "OFF"

        # --- اولویت‌بندی مصرف هیدروژن مخزن اصلی ---
        main_tank_percent = main_tank_kg / self.config.MAIN_TANK_CAPACITY_KG
        dispatch_target = "Storage"

        if main_tank_percent >= self.config.MAIN_TANK_START_THRESHOLD:
            # اولویت اول: ایستگاه سوخت‌گیری (تا ۵ کیلوگرم)
            if hrs_tank_kg < self.config.HRS_H2_TANK_CAPACITY_KG:
                dispatch_target = "Refueling Station (HRS)"
            # اولویت دوم: پیل سوختی (FC)
            else:
                dispatch_target = "Fuel Cell (FC)"

        return compressor_status, dispatch_target

    def manage_fc_and_grid(self, fc_power_output, ev_demand, grid_price):
        """
        ۴. مدیریت خروجی پیل سوختی (FC -> EV Station -> Grid)
        طبق سناریو: ابتدا شارژ کامل EV و سپس تزریق انرژی اضافی به شبکه.
        """
        power_to_ev = 0
        power_to_grid = 0

        # ابتدا تأمین نیاز ایستگاه شارژ وسایل برقی
        power_to_ev = min(fc_power_output, ev_demand)

        # انرژی اضافی تولید شده توسط FC
        excess_fc_power = fc_power_output - power_to_ev

        if excess_fc_power > 0:
            # تزریق به شبکه (می‌تواند بر اساس قیمت لحظه‌ای مدیریت شود)
            power_to_grid = excess_fc_power

        return power_to_ev, power_to_grid

    def calculate_environmental_impact(self, h2_produced_kg):
        """محاسبه کاهش کربن"""
        return h2_produced_kg * self.config.CO2_SAVED_PER_KG_H2