# =============================================================================
# subsystems.py — LUMINIH2 زیرسیستم‌های تکمیلی
# تصفیه آب · مدیریت O₂ · خشک‌کن H₂ · Warm-up الکترولایزر
# Version: 4.0
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import logging

logger = logging.getLogger("Subsystems")


# =============================================================================
# نتایج typed
# =============================================================================

@dataclass
class WaterResult:
    """نتیجه سیستم تصفیه آب"""
    raw_water_l_h:        float   # آب خام ورودی
    purified_l_h:         float   # آب تصفیه‌شده خروجی
    conductivity_us_cm:   float   # هدایت الکتریکی (باید < 0.1)
    resistance_mohm_cm:   float   # مقاومت (باید > 10)
    quality_ok:           bool    # True = کیفیت قابل قبول
    resin_saturation_pct: float   # درصد اشباع رزین (> 80% = تعویض)
    resin_warning:        bool
    power_kw:             float   # مصرف پمپ و UV


@dataclass
class O2Result:
    """نتیجه مدیریت O₂"""
    o2_flow_nm3_h:     float   # دبی O₂
    o2_pressure_bar:   float   # فشار (باید < 0.5 bar)
    vented_nm3_h:      float   # تخلیه به اتمسفر
    recovered_nm3_h:   float   # بازیابی (اگه سیستم داشته باشیم)
    safety_ok:         bool    # False = فشار بالا


@dataclass
class DryerResult:
    """نتیجه خشک‌کن H₂"""
    h2_in_kg_h:          float   # ورودی H₂ (مرطوب)
    h2_out_kg_h:         float   # خروجی H₂ (خشک)
    moisture_ppm:        float   # رطوبت خروجی (هدف < 5 ppm)
    dew_point_c:         float   # نقطه شبنم
    desiccant_pct:       float   # درصد اشباع دسیکنت (> 85% = احیا)
    desiccant_warning:   bool
    h2_loss_pct:         float   # اتلاف H₂ در فرآیند خشک‌کردن (~0.5%)
    power_kw:            float


@dataclass
class WarmupResult:
    """نتیجه warm-up الکترولایزر"""
    is_warm:             bool    # True = آماده کار
    warmup_time_min:     float   # زمان باقیمانده تا آماده‌شدن
    current_temp_c:      float   # دمای فعلی stack
    target_temp_c:       float   # دمای هدف
    efficiency_factor:   float   # ضریب بازده (1.0 = کامل)
    power_consumed_kw:   float   # توان مصرفی در حین warm-up
    cold_start:          bool    # True = شروع از دمای محیط


# =============================================================================
# ۱. سیستم تصفیه آب — Water Treatment (DIN ISO 3696 Type 1)
# =============================================================================

class WaterTreatment:
    """
    سیستم تصفیه آب برای الکترولایزر S30/30
    نیاز: مقاومت > 10 MΩ·cm (DIN ISO 3696 Type 1)
    شامل: فیلتر رزین تبادل یون + UV + پمپ
    """

    TARGET_RESISTANCE_MOHM = 10.0   # حداقل مقاومت مورد نیاز
    TARGET_CONDUCTANCE_US  = 0.1    # حداکثر هدایت [µS/cm]
    RESIN_CAPACITY_L       = 50.0   # حجم کارتریج رزین [L]
    RESIN_EXCHANGE_CAP     = 500.0  # ظرفیت تبادل [L آب]
    PUMP_POWER_KW          = 0.05   # توان پمپ [kW]
    UV_POWER_KW            = 0.02   # توان UV sterilizer [kW]

    def __init__(self):
        self._water_processed_l  = 0.0   # کل آب پردازش‌شده
        self._resin_used_l       = 0.0   # آب از طریق رزین
        self._last_check_l       = 0.0

    def process(self,
                demand_l_h: float,
                ambient_temp_c: float = 20.0,
                feed_conductivity_us: float = 500.0
                ) -> WaterResult:
        """
        تصفیه آب خام به آب Type 1

        Args:
            demand_l_h: نیاز آب الکترولایزر [L/h]
            ambient_temp_c: دمای محیط
            feed_conductivity_us: هدایت آب خام [µS/cm] (معمولاً 200-800)
        """
        if demand_l_h <= 0:
            return WaterResult(0, 0, 0.1, 10.0, True, self._resin_saturation(), False, 0)

        # ── فیلتر رزین ────────────────────────────────────────────────
        self._resin_used_l += demand_l_h * (1 / 3600)  # per second
        self._water_processed_l += demand_l_h * (1 / 3600)

        resin_sat = self._resin_saturation()

        # با پیشرفت اشباع، کیفیت کاهش می‌یابد
        quality_factor = max(0.1, 1.0 - (resin_sat / 100) * 0.9)
        conductivity = self.TARGET_CONDUCTANCE_US / quality_factor
        conductivity = float(np.clip(conductivity, 0.01, feed_conductivity_us))
        resistance = 1.0 / (conductivity * 1e-6) / 1e6  # MΩ·cm

        quality_ok = (conductivity <= self.TARGET_CONDUCTANCE_US * 1.5
                      and resistance >= self.TARGET_RESISTANCE_MOHM * 0.5)

        # آب خالص‌شده (کمی کمتر از ورودی به دلیل backwash)
        purified = demand_l_h * 0.92

        # هشدار رزین
        resin_warning = resin_sat > 80.0

        return WaterResult(
            raw_water_l_h=round(demand_l_h, 3),
            purified_l_h=round(purified, 3),
            conductivity_us_cm=round(conductivity, 4),
            resistance_mohm_cm=round(resistance, 2),
            quality_ok=quality_ok,
            resin_saturation_pct=round(resin_sat, 1),
            resin_warning=resin_warning,
            power_kw=round(self.PUMP_POWER_KW + self.UV_POWER_KW, 3),
        )

    def replace_resin(self):
        """تعویض کارتریج رزین"""
        self._resin_used_l = 0.0
        logger.info("رزین تصفیه آب تعویض شد")

    def _resin_saturation(self) -> float:
        return min(100.0, (self._resin_used_l / self.RESIN_EXCHANGE_CAP) * 100)


# =============================================================================
# ۲. مدیریت O₂ — Oxygen Handling
# =============================================================================

class OxygenHandler:
    """
    مدیریت O₂ خروجی الکترولایزر S30/30
    فشار خروجی: < 0.5 bar (datasheet)
    گزینه‌ها: تخلیه به اتمسفر / ذخیره و فروش
    """

    O2_MAX_PRESSURE_BAR = 0.5   # حد ایمنی از datasheet
    # نسبت تولید: به ازای هر kg H₂، 8 kg O₂ = 5.6 Nm³
    O2_NM3_PER_KG_H2 = 5.6

    def __init__(self, has_recovery_system: bool = False):
        self._has_recovery = has_recovery_system
        self._total_o2_nm3 = 0.0

    def process(self,
                h2_production_kg_h: float,
                ambient_pressure_bar: float = 1.013
                ) -> O2Result:
        """
        محاسبه و مدیریت O₂ خروجی
        """
        o2_flow = h2_production_kg_h * self.O2_NM3_PER_KG_H2
        self._total_o2_nm3 += o2_flow * (1 / 3600)

        # فشار O₂ (از datasheet: < 0.5 bar)
        o2_pressure = min(0.45, ambient_pressure_bar * 0.44)

        safety_ok = o2_pressure < self.O2_MAX_PRESSURE_BAR

        if self._has_recovery:
            recovered = o2_flow * 0.85
            vented = o2_flow * 0.15
        else:
            recovered = 0.0
            vented = o2_flow

        return O2Result(
            o2_flow_nm3_h=round(o2_flow, 4),
            o2_pressure_bar=round(o2_pressure, 3),
            vented_nm3_h=round(vented, 4),
            recovered_nm3_h=round(recovered, 4),
            safety_ok=safety_ok,
        )

    @property
    def total_o2_nm3(self) -> float:
        return round(self._total_o2_nm3, 3)


# =============================================================================
# ۳. خشک‌کن H₂ — Hydrogen Dryer
# =============================================================================

class HydrogenDryer:
    """
    خشک‌کن H₂ با دسیکنت (Pressure Swing Adsorption یا Desiccant)
    H₂ خروجی الکترولایزر مرطوب است — باید < 5 ppm رطوبت برسد
    برای پیل سوختی AIRCELL نیاز: < 5 ppm water (از datasheet)
    """

    TARGET_MOISTURE_PPM    = 5.0    # هدف: < 5 ppm (AIRCELL requirement)
    DESICCANT_CAPACITY_KG  = 2.0    # ظرفیت دسیکنت [kg H₂]
    H2_LOSS_PCT            = 0.005  # اتلاف H₂ در فرآیند (~0.5%)
    REGEN_POWER_KW         = 0.15   # توان احیای دسیکنت

    def __init__(self):
        self._h2_processed_kg  = 0.0
        self._desiccant_used   = 0.0

    def process(self,
                h2_kg_h: float,
                inlet_pressure_bar: float = 20.0,
                ambient_temp_c: float = 20.0
                ) -> DryerResult:
        """
        خشک‌کردن H₂ مرطوب

        Args:
            h2_kg_h: دبی H₂ ورودی [kg/h]
            inlet_pressure_bar: فشار ورودی (20 bar از S30/30)
            ambient_temp_c: دمای محیط
        """
        if h2_kg_h <= 0:
            return DryerResult(0, 0, 0.5, -60.0, self._desiccant_sat(), False, 0, 0)

        self._h2_processed_kg += h2_kg_h * (1 / 3600)
        self._desiccant_used  += h2_kg_h * (1 / 3600)

        desiccant_sat = self._desiccant_sat()

        # رطوبت خروجی — با اشباع دسیکنت بدتر می‌شود
        if desiccant_sat < 70:
            moisture_ppm = 0.5 + desiccant_sat * 0.03
        elif desiccant_sat < 85:
            moisture_ppm = 3.0 + (desiccant_sat - 70) * 0.2
        else:
            moisture_ppm = 6.0 + (desiccant_sat - 85) * 0.5

        moisture_ppm = float(np.clip(moisture_ppm, 0.1, 20.0))

        # نقطه شبنم (تقریبی)
        dew_point = -50 + (moisture_ppm / 5) * 30
        dew_point = float(np.clip(dew_point, -80, 20))

        # اتلاف H₂
        h2_loss = h2_kg_h * self.H2_LOSS_PCT
        h2_out = h2_kg_h - h2_loss

        desiccant_warning = desiccant_sat > 85.0

        # توان: فقط وقتی در حال احیا است
        power = self.REGEN_POWER_KW if desiccant_sat > 80 else 0.02

        return DryerResult(
            h2_in_kg_h=round(h2_kg_h, 5),
            h2_out_kg_h=round(h2_out, 5),
            moisture_ppm=round(moisture_ppm, 3),
            dew_point_c=round(dew_point, 1),
            desiccant_pct=round(desiccant_sat, 1),
            desiccant_warning=desiccant_warning,
            h2_loss_pct=round(self.H2_LOSS_PCT * 100, 2),
            power_kw=round(power, 3),
        )

    def regenerate_desiccant(self):
        """احیای دسیکنت"""
        self._desiccant_used = 0.0
        logger.info("دسیکنت خشک‌کن H₂ احیا شد")

    def _desiccant_sat(self) -> float:
        return min(100.0, (self._desiccant_used / self.DESICCANT_CAPACITY_KG) * 100)


# =============================================================================
# ۴. Warm-up الکترولایزر — Cold Start Model
# =============================================================================

class ElectrolyzerWarmup:
    """
    مدل گرم‌شدن الکترولایزر S30/30
    - دمای کاری: 20–70°C (از datasheet)
    - دمای بهینه: ~55°C
    - زمان گرم‌شدن از سرد: ~5 دقیقه
    - در دمای زیر 10°C: بازده کاهش می‌یابد
    """

    OPTIMAL_TEMP_C    = 55.0   # دمای بهینه کار
    MIN_TEMP_C        = 20.0   # حداقل دمای کاری (از datasheet)
    MAX_TEMP_C        = 70.0   # حداکثر دمای کاری (از datasheet)
    WARMUP_TIME_MIN   = 5.0    # زمان گرم‌شدن استاندارد [دقیقه]
    HEATING_POWER_KW  = 0.3    # توان المان گرمایش داخلی
    THERMAL_MASS      = 50.0   # جرم حرارتی تقریبی [kJ/°C]
    COOLING_RATE      = 0.02   # سرعت سرد شدن در استراحت [°C/min]

    def __init__(self, initial_temp_c: float = 20.0):
        self._stack_temp = initial_temp_c
        self._is_running = False
        self._run_minutes = 0.0

    def update(self,
               ambient_temp_c: float,
               power_input_kw: float,
               timestep_sec: int = 10
               ) -> WarmupResult:
        """
        به‌روزرسانی وضعیت حرارتی stack

        Args:
            ambient_temp_c: دمای محیط
            power_input_kw: توان ورودی به الکترولایزر
            timestep_sec: گام زمانی
        """
        dt_min = timestep_sec / 60.0
        cold_start = self._stack_temp < self.MIN_TEMP_C + 5

        if power_input_kw >= 0.74:  # در حال کار
            self._is_running = True
            self._run_minutes += dt_min

            # گرمای تولیدی از الکترولیز (22% اتلاف حرارتی)
            heat_gen_kw = power_input_kw * 0.22

            # گرمای المان داخلی (در warm-up)
            heater_kw = self.HEATING_POWER_KW if self._stack_temp < self.OPTIMAL_TEMP_C else 0.0

            # اتلاف گرما به محیط
            heat_loss_kw = max(0, (self._stack_temp - ambient_temp_c) * 0.05)

            # تغییر دما
            delta_temp = ((heat_gen_kw + heater_kw - heat_loss_kw)
                          * 60 * dt_min / (self.THERMAL_MASS / 1000))
            self._stack_temp += delta_temp
            self._stack_temp = float(np.clip(
                self._stack_temp, ambient_temp_c, self.MAX_TEMP_C
            ))

        else:  # استراحت
            self._is_running = False
            # سرد شدن طبیعی
            cooling = self.COOLING_RATE * dt_min
            self._stack_temp = max(ambient_temp_c, self._stack_temp - cooling)

        # آیا stack گرم شده؟
        is_warm = self._stack_temp >= self.MIN_TEMP_C + 5
        warmup_remaining = max(0.0,
            (self.OPTIMAL_TEMP_C - self._stack_temp) / 6.0)  # دقیقه

        # ضریب بازده حرارتی
        if self._stack_temp < self.MIN_TEMP_C:
            eff_factor = 0.70   # سرد — بازده خیلی کم
        elif self._stack_temp < self.MIN_TEMP_C + 10:
            eff_factor = 0.85   # در حال گرم شدن
        elif self._stack_temp <= self.OPTIMAL_TEMP_C:
            # بهبود خطی تا دمای بهینه
            eff_factor = 0.85 + 0.15 * (
                (self._stack_temp - self.MIN_TEMP_C) /
                (self.OPTIMAL_TEMP_C - self.MIN_TEMP_C)
            )
        elif self._stack_temp <= self.MAX_TEMP_C:
            # کاهش جزئی بعد از دمای بهینه
            eff_factor = 1.0 - 0.05 * (
                (self._stack_temp - self.OPTIMAL_TEMP_C) /
                (self.MAX_TEMP_C - self.OPTIMAL_TEMP_C)
            )
        else:
            eff_factor = 0.80   # داغ — shutdown خودکار

        power_consumed = self.HEATING_POWER_KW if not is_warm else 0.0

        return WarmupResult(
            is_warm=is_warm,
            warmup_time_min=round(warmup_remaining, 1),
            current_temp_c=round(self._stack_temp, 1),
            target_temp_c=self.OPTIMAL_TEMP_C,
            efficiency_factor=round(float(eff_factor), 3),
            power_consumed_kw=round(power_consumed, 3),
            cold_start=cold_start,
        )

    def reset(self, ambient_temp_c: float = 20.0):
        """ریست به دمای محیط (خاموش‌شدن)"""
        self._stack_temp = ambient_temp_c
        self._is_running = False
        self._run_minutes = 0.0

    @property
    def stack_temp(self) -> float:
        return self._stack_temp


# =============================================================================
# ۵. مدیر یکپارچه زیرسیستم‌ها
# =============================================================================

class SubsystemManager:
    """
    مدیریت یکپارچه همه زیرسیستم‌ها
    برای استفاده در TickEngine
    """

    def __init__(self, has_o2_recovery: bool = False):
        self.water   = WaterTreatment()
        self.oxygen  = OxygenHandler(has_recovery_system=has_o2_recovery)
        self.dryer   = HydrogenDryer()
        self.warmup  = ElectrolyzerWarmup(initial_temp_c=20.0)
        self._total_maintenance_cost = 0.0

    def tick(self,
             h2_kg_h: float,
             elec_power_kw: float,
             ambient_temp_c: float,
             timestep_sec: int = 10
             ) -> dict:
        """یک گام زمانی همه زیرسیستم‌ها"""

        # آب مورد نیاز
        water_demand = h2_kg_h * 11.13  # L/kg H₂

        wr = self.water.process(water_demand, ambient_temp_c)
        o2 = self.oxygen.process(h2_kg_h, 1.013)
        dr = self.dryer.process(h2_kg_h, 20.0, ambient_temp_c)
        wu = self.warmup.update(ambient_temp_c, elec_power_kw, timestep_sec)

        # H₂ نهایی بعد از خشک‌کن
        h2_final_kg_h = dr.h2_out_kg_h

        # توان کل زیرسیستم‌ها
        total_aux_kw = wr.power_kw + dr.power_kw + wu.power_consumed_kw

        # هشدارهای نگهداری
        maintenance_needed = []
        if wr.resin_warning:
            maintenance_needed.append("تعویض رزین تصفیه آب")
        if dr.desiccant_warning:
            maintenance_needed.append("احیای دسیکنت خشک‌کن")
        if not wr.quality_ok:
            maintenance_needed.append("⚠ کیفیت آب پایین — خطر membrane!")

        return {
            "water":        wr,
            "oxygen":       o2,
            "dryer":        dr,
            "warmup":       wu,
            "h2_final_kg_h": h2_final_kg_h,
            "aux_power_kw": total_aux_kw,
            "elec_eff_factor": wu.efficiency_factor,
            "maintenance":  maintenance_needed,
            "h2_dry_ok":   dr.moisture_ppm <= 5.0,
            "water_ok":    wr.quality_ok,
            "o2_safe":     o2.safety_ok,
            "stack_temp":  wu.current_temp_c,
        }

    def reset_electrolyzer(self, ambient_temp_c: float):
        """ریست الکترولایزر (بعد از خاموشی)"""
        self.warmup.reset(ambient_temp_c)


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    import time
    mgr = SubsystemManager(has_o2_recovery=False)

    print("=== تست زیرسیستم‌های LUMINIH2 ===\n")

    # شبیه‌سازی ۳۰ دقیقه کار (180 × 10s)
    print("شبیه‌سازی ۳۰ دقیقه کار الکترولایزر از سرد (ambient=5°C)...")
    for i in range(180):
        result = mgr.tick(
            h2_kg_h=0.0593,        # تولید نامی
            elec_power_kw=3.0,     # بار نامی
            ambient_temp_c=5.0,    # زمستان Zagreb
            timestep_sec=10,
        )
        if i in [0, 30, 60, 90, 120, 179]:
            wu = result["warmup"]
            dr = result["dryer"]
            print(f"  t={i*10:4}s | Stack {wu.current_temp_c:5.1f}°C | "
                  f"η×{wu.efficiency_factor:.3f} | "
                  f"H₂ moisture {dr.moisture_ppm:.2f} ppm | "
                  f"Warm:{wu.is_warm}")

    print(f"\nنتیجه نهایی:")
    wr = result["water"]
    o2 = result["oxygen"]
    dr = result["dryer"]
    wu = result["warmup"]
    print(f"  آب: هدایت {wr.conductivity_us_cm:.4f} µS/cm "
          f"(هدف < 0.1) | رزین {wr.resin_saturation_pct:.1f}%")
    print(f"  O₂: {o2.o2_flow_nm3_h:.4f} Nm³/h | "
          f"فشار {o2.o2_pressure_bar:.3f} bar | ایمن: {o2.safety_ok}")
    print(f"  H₂ خشک: {dr.moisture_ppm:.3f} ppm رطوبت "
          f"(هدف < 5 ppm) | اتلاف {dr.h2_loss_pct:.2f}%")
    print(f"  Stack: {wu.current_temp_c:.1f}°C | بازده ×{wu.efficiency_factor:.3f}")
    print(f"  توان کمکی: {result['aux_power_kw']:.3f} kW")
    print(f"  نگهداری: {result['maintenance'] or 'نیازی نیست'}")

    print("\n✅ subsystems.py v4.0 — همه زیرسیستم‌ها OK")
