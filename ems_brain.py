# ems_brain.py
from config import Config


class EMSBrain:
    def __init__(self):
        self.config = Config()

    def decide_energy_source(self, pv_available, wind_available, battery_soc):
        """
        منطق سوئیچینگ خودکار بین منابع انرژی بر اساس اولویت
        """
        # اگر توان PV برای حداقل کارکرد الکترولایزر کافی بود
        if pv_available >= self.config.ELEC_P_MIN_KW:
            return "Solar (PV)", pv_available

        # در غیر این صورت سوئیچ به توربین باد
        elif wind_available >= self.config.ELEC_P_MIN_KW:
            return "Wind Turbine", wind_available

        # اگر هیچکدام نبود، سوئیچ به شبکه (Grid) برای حفظ پایداری
        else:
            return "National Grid", self.config.ELEC_P_MIN_KW

    def manage_battery_and_electrolyzer(self, incoming_power, current_soc):
        """
        اولویت با شارژ باتری برای جلوگیری از آسیب به الکترولایزر
        """
        power_to_electrolyzer = 0
        power_to_battery = 0

        # اگر باتری زیر سقف مجاز است، ابتدا شارژ شود
        if current_soc < self.config.BATT_SOC_MAX:
            power_to_battery = min(incoming_power, self.config.BATT_MAX_CHARGE_KW)
            remaining_power = incoming_power - power_to_battery

            # اگر بعد از شارژ باتری، توانی باقی ماند به الکترولایزر برود
            if remaining_power >= self.config.ELEC_P_MIN_KW:
                power_to_electrolyzer = min(remaining_power, self.config.ELEC_P_MAX_KW)
        else:
            # اگر باتری پر بود، کل توان به الکترولایزر برود
            power_to_electrolyzer = min(incoming_power, self.config.ELEC_P_MAX_KW)

        return power_to_battery, power_to_electrolyzer

    def hydrogen_logistics_control(self, buffer_level_kg, main_tank_kg, hrs_tank_kg):
        """
        مدیریت زنجیره فشرده‌سازی و توزیع هیدروژن
        """
        # ۱. کنترل کمپرسور (فعال سازی در ۳۰٪ بافر)
        buffer_percent = buffer_level_kg / self.config.BUFFER_TANK_CAPACITY_KG
        compressor_status = "OFF"
        if buffer_percent >= self.config.BUFFER_START_THRESHOLD:
            compressor_status = "ON"
        elif buffer_percent <= self.config.BUFFER_STOP_THRESHOLD:
            compressor_status = "OFF"

        # ۲. کنترل توزیع (ارسال به HRS در صورت پر بودن ۵۰٪ مخزن اصلی)
        main_tank_percent = main_tank_kg / self.config.MAIN_TANK_CAPACITY_KG
        dispatch_target = "Storage"

        if main_tank_percent >= self.config.MAIN_TANK_START_THRESHOLD:
            if hrs_tank_kg < self.config.HRS_H2_TANK_CAPACITY_KG:
                dispatch_target = "Refueling Station (HRS)"
            else:
                dispatch_target = "Fuel Cell (FC)"

        return compressor_status, dispatch_target

    def calculate_environmental_impact(self, h2_produced_kg):
        """محاسبه کاهش کربن لحظه‌ای"""
        return h2_produced_kg * self.config.CO2_SAVED_PER_KG_H2