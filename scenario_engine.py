# =============================================================================
# scenario_engine.py — LUMINIH2 Scenario & Annual Simulation Engine
# شبیه‌سازی سریع ۳۶۵ روزه · Zagreb, Croatia
# Version: 4.0
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math
import numpy as np
import logging

logger = logging.getLogger("ScenarioEngine")

# =============================================================================
# Zagreb Climatology — ماهانه (داده واقعی اقلیمی)
# =============================================================================

# میانگین تابش افقی روزانه [kWh/m²/day] — Zagreb PVGIS
ZAGREB_MONTHLY_GHI = {
    1: 1.10, 2: 1.85, 3: 3.20, 4: 4.50, 5: 5.60, 6: 6.10,
    7: 6.30, 8: 5.70, 9: 4.00, 10: 2.50, 11: 1.20, 12: 0.90,
}

# میانگین سرعت باد [m/s] — Zagreb ایستگاه هواشناسی
ZAGREB_MONTHLY_WIND = {
    1: 4.2, 2: 4.5, 3: 4.8, 4: 4.3, 5: 3.9, 6: 3.5,
    7: 3.2, 8: 3.1, 9: 3.4, 10: 3.8, 11: 4.1, 12: 4.3,
}

# میانگین دما [°C]
ZAGREB_MONTHLY_TEMP = {
    1: 1.5,  2: 3.5,  3: 8.5,  4: 14.0, 5: 19.0, 6: 22.5,
    7: 25.0, 8: 24.5, 9: 19.5, 10: 13.5, 11: 7.5, 12: 2.5,
}

# روزهای بارانی در ماه (پاک‌کردن پنل)
ZAGREB_MONTHLY_RAIN_DAYS = {
    1: 12, 2: 11, 3: 12, 4: 13, 5: 13, 6: 12,
    7: 9,  8: 9,  9: 10, 10: 11, 11: 14, 12: 13,
}

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


# =============================================================================
# نتایج typed
# =============================================================================

@dataclass
class DailyResult:
    day:              int
    month:            int
    solar_kwh:        float
    wind_kwh:         float
    total_gen_kwh:    float
    h2_produced_kg:   float
    h2_to_hrs_kg:     float
    bess_cycles:      float
    grid_export_kwh:  float
    grid_import_kwh:  float
    lcoh_eur_kg:      float
    co2_saved_kg:     float
    revenue_eur:      float
    water_used_l:     float
    o2_produced_nm3:  float
    electrolyzer_hours: float
    soiling_loss_pct: float
    compressor_runs:  int


@dataclass
class MonthlyResult:
    month:            int
    month_name:       str
    solar_kwh:        float
    wind_kwh:         float
    h2_produced_kg:   float
    h2_to_hrs_kg:     float
    lcoh_eur_kg:      float
    co2_saved_kg:     float
    revenue_eur:      float
    water_used_l:     float
    o2_produced_nm3:  float
    grid_export_kwh:  float
    grid_import_kwh:  float
    bess_cycles:      float
    electrolyzer_hours: float
    avg_efficiency_pct: float
    days_profitable:  int


@dataclass
class AnnualReport:
    # تولید انرژی
    total_solar_kwh:      float
    total_wind_kwh:       float
    total_gen_kwh:        float
    # هیدروژن
    total_h2_kg:          float
    total_h2_to_hrs_kg:   float
    avg_daily_h2_kg:      float
    peak_daily_h2_kg:     float
    # اقتصاد
    total_revenue_eur:    float
    total_cost_eur:       float
    net_profit_eur:       float
    avg_lcoh_eur_kg:      float
    best_lcoh_eur_kg:     float
    worst_lcoh_eur_kg:    float
    payback_years:        float
    roi_pct:              float
    # محیط زیست
    total_co2_saved_kg:   float
    total_co2_saved_ton:  float
    co2_credits_eur:      float
    # آب
    total_water_l:        float
    total_o2_nm3:         float
    # سیستم
    total_bess_cycles:    float
    bess_remaining_life_pct: float
    electrolyzer_hours:   float
    stack_replacements:   int
    # گرید
    total_grid_export_kwh: float
    total_grid_import_kwh: float
    grid_independence_pct: float
    # ماهانه و روزانه
    monthly: List[MonthlyResult] = field(default_factory=list)
    daily:   List[DailyResult]   = field(default_factory=list)


@dataclass
class ScenarioParams:
    """پارامترهای قابل تنظیم برای هر سناریو"""
    name:               str   = "پیش‌فرض"
    # مقیاس توان
    pv_scale:           float = 1.0    # ضریب مقیاس PV (1.0 = 15kW)
    wind_scale:         float = 1.0    # ضریب مقیاس Wind
    bess_scale:         float = 1.0    # ضریب ظرفیت BESS
    # استراتژی EMS
    elec_priority_mode: str   = "h2_max"    # h2_max | lcoh_opt | grid_first
    bess_reserve_pct:   float = 0.20   # درصد ذخیره اضطراری BESS
    # قیمت‌گذاری
    grid_buy_eur:       float = 0.22
    grid_sell_eur:      float = 0.12
    h2_price_eur_kg:    float = 6.0    # قیمت فروش H₂ به ایستگاه
    # سرمایه‌گذاری
    capex_eur:          float = 250000.0   # سرمایه‌گذاری اولیه
    opex_annual_eur:    float = 8000.0     # هزینه سالانه نگهداری
    # شرایط محیطی
    soiling_clean_days: int   = 14     # هر چند روز پنل تمیز میشه
    wind_availability:  float = 0.95   # درصد زمان باد در دسترس


# =============================================================================
# Scenario Engine اصلی
# =============================================================================

class ScenarioEngine:
    """
    شبیه‌ساز سریع ۳۶۵ روزه LUMINIH2
    از داده‌های اقلیمی واقعی Zagreb + پارامترهای datasheet واقعی
    در چند ثانیه نتیجه کامل سالانه می‌دهد
    """

    MONTH_NAMES = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                   "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    MONTH_NAMES_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def __init__(self, config):
        self.cfg = config

    def run_annual(
        self,
        params: Optional[ScenarioParams] = None,
        seed: int = 42,
    ) -> AnnualReport:
        """
        شبیه‌سازی کامل ۳۶۵ روز — در < 1 ثانیه اجرا میشه
        """
        if params is None:
            params = ScenarioParams()

        rng = np.random.default_rng(seed)
        daily_results: List[DailyResult] = []

        # ── شبیه‌سازی روز به روز ──────────────────────────────────────
        day_of_year = 0
        for month_idx, days in enumerate(DAYS_IN_MONTH):
            m = month_idx + 1  # 1-12

            ghi_avg    = ZAGREB_MONTHLY_GHI[m]        # kWh/m²/day
            wind_avg   = ZAGREB_MONTHLY_WIND[m]        # m/s
            temp_avg   = ZAGREB_MONTHLY_TEMP[m]        # °C
            rain_days  = ZAGREB_MONTHLY_RAIN_DAYS[m]

            for d in range(days):
                day_of_year += 1

                # ── تابش روزانه با تغییرپذیری ───────────────────────
                ghi_day = float(np.clip(
                    ghi_avg * rng.lognormal(0, 0.25),
                    0, ghi_avg * 2.2
                ))

                # ── سرعت باد روزانه ──────────────────────────────────
                wind_day = float(np.clip(
                    rng.weibull(2.0) * wind_avg * params.wind_scale,
                    0, 25.0
                ))

                # ── دما ───────────────────────────────────────────────
                temp_day = temp_avg + rng.normal(0, 3.0)

                # ── soiling ───────────────────────────────────────────
                days_since_rain = d % max(1, 30 // rain_days)
                soiling = max(0.88, 1.0 - days_since_rain * self.cfg.SOILING_LOSS_RATE)

                # ── تولید PV [kWh/day] ───────────────────────────────
                # GHI → PV output
                pv_cap = self.cfg.PV_SYSTEM_CAPACITY_KW * params.pv_scale
                # NOCT temp correction
                t_cell = temp_day + (ghi_day * 1000 / 24 / 800) * (45 - 20)
                thermal_f = max(0, 1 + (-0.0035) * (t_cell - 25))
                solar_kwh = (pv_cap * ghi_day * thermal_f * soiling
                             * self.cfg.INVERTER_EFFICIENCY)
                solar_kwh = float(np.clip(solar_kwh, 0, pv_cap * 8))

                # ── تولید باد [kWh/day] ──────────────────────────────
                wind_cap = self.cfg.WIND_SYSTEM_CAPACITY_KW
                wind_kwh = self._wind_daily_kwh(wind_day, wind_cap, params)

                total_gen_kwh = solar_kwh + wind_kwh

                # ── EMS روزانه ────────────────────────────────────────
                dr = self._ems_daily(
                    total_gen_kwh, temp_day, params,
                    day_of_year, month_idx + 1, d
                )

                daily_results.append(DailyResult(
                    day=day_of_year, month=m,
                    solar_kwh=round(solar_kwh, 3),
                    wind_kwh=round(wind_kwh, 3),
                    total_gen_kwh=round(total_gen_kwh, 3),
                    h2_produced_kg=round(dr["h2_kg"], 4),
                    h2_to_hrs_kg=round(dr["h2_hrs_kg"], 4),
                    bess_cycles=round(dr["bess_cycles"], 4),
                    grid_export_kwh=round(dr["grid_export"], 3),
                    grid_import_kwh=round(dr["grid_import"], 3),
                    lcoh_eur_kg=round(dr["lcoh"], 3),
                    co2_saved_kg=round(dr["co2_kg"], 3),
                    revenue_eur=round(dr["revenue"], 4),
                    water_used_l=round(dr["water_l"], 3),
                    o2_produced_nm3=round(dr["o2_nm3"], 3),
                    electrolyzer_hours=round(dr["elec_hours"], 2),
                    soiling_loss_pct=round((1 - soiling) * 100, 2),
                    compressor_runs=dr["comp_runs"],
                ))

        # ── جمع‌بندی ماهانه ───────────────────────────────────────────
        monthly = self._aggregate_monthly(daily_results)

        # ── گزارش سالانه ──────────────────────────────────────────────
        return self._build_annual(daily_results, monthly, params)

    # ------------------------------------------------------------------
    # تولید باد روزانه
    # ------------------------------------------------------------------
    def _wind_daily_kwh(self, v_avg: float, cap_kw: float,
                         params: ScenarioParams) -> float:
        cut_in  = self.cfg.wind.cut_in_ms
        rated   = self.cfg.wind.rated_speed_ms
        cut_out = self.cfg.wind.cut_out_ms

        if v_avg < cut_in or v_avg > cut_out:
            return 0.0

        if v_avg >= rated:
            power_kw = cap_kw
        else:
            ratio = (v_avg - cut_in) / (rated - cut_in)
            power_kw = cap_kw * (ratio ** 3)

        # ساعات در دسترس در روز
        avail_hours = 24 * params.wind_availability
        return float(np.clip(power_kw * avail_hours, 0, cap_kw * 24))

    # ------------------------------------------------------------------
    # EMS روزانه — تخصیص انرژی
    # ------------------------------------------------------------------
    def _ems_daily(self, total_gen_kwh: float, temp_c: float,
                   params: ScenarioParams, day: int, month: int,
                   day_in_month: int) -> dict:
        cfg = self.cfg

        # ── ۱. شارژ BESS (اولویت اول) ────────────────────────────────
        bess_cap = cfg.BATT_CAPACITY_KWH * params.bess_scale
        bess_target_kwh = bess_cap * (cfg.BATT_SOC_MAX - cfg.BATT_SOC_MIN) * 0.5
        bess_charge = min(total_gen_kwh * 0.35, bess_target_kwh)
        energy_after_bess = max(0, total_gen_kwh - bess_charge)
        bess_cycles = bess_charge / bess_cap if bess_cap > 0 else 0

        # ── ۲. الکترولایزر (اولویت دوم) ─────────────────────────────
        # گرم‌شدن: اگه دما < 10°C، ۵ دقیقه warm-up (کاهش ۸% بازده)
        cold_start_penalty = 0.92 if temp_c < 10 else 1.0

        # بهینه‌ترین نقطه کار بر اساس حالت EMS
        if params.elec_priority_mode == "lcoh_opt":
            # بهترین بازده در بار نامی (3kW)
            elec_power_kw = min(energy_after_bess / 24, cfg.ELEC_P_NOM_KW)
        elif params.elec_priority_mode == "h2_max":
            # حداکثر تولید H₂ — نزدیک به بار پیک
            elec_power_kw = min(energy_after_bess / 18, cfg.ELEC_P_MAX_KW)
        else:
            elec_power_kw = min(energy_after_bess / 20, cfg.ELEC_P_NOM_KW)

        elec_power_kw = float(np.clip(elec_power_kw, 0, cfg.ELEC_P_MAX_KW))

        # ساعات کار الکترولایزر در روز
        if elec_power_kw >= cfg.ELEC_P_MIN_KW:
            elec_hours = min(energy_after_bess / max(elec_power_kw, 0.01), 20.0)
        else:
            elec_hours = 0.0

        # بازده از منحنی واقعی datasheet
        eff = self._elec_efficiency(elec_power_kw) * cold_start_penalty

        # تولید H₂ روزانه [kg]
        # H₂ nominal: 0.05932 kg/h at 3kW → scale by load
        h2_rate_kg_h = (elec_power_kw * eff) / 33.33
        h2_kg = h2_rate_kg_h * elec_hours

        # آب مصرفی: 11.13 L/kg H₂
        water_l = h2_kg * cfg.WATER_CONSUMPTION_L_KG

        # O₂ تولیدی: نسبت مولی 8:1 (O₂:H₂ by mass)
        # هر kg H₂ → 8 kg O₂ → 8/1.429 = 5.6 Nm³ O₂
        o2_nm3 = h2_kg * 5.6

        # ── ۳. فشرده‌سازی و ذخیره ─────────────────────────────────────
        # HCS-100: max 2 kg/day → اگه H₂ بیشتر بود، بافر میشه
        h2_compressed = min(h2_kg, 2.0)  # kg/day limit
        comp_runs = math.ceil(h2_compressed / 0.08333) if h2_compressed > 0 else 0

        # ── ۴. توزیع H₂ ──────────────────────────────────────────────
        # HRS: مصرف روزانه فرضی 1 kg/day (یک خودرو)
        h2_hrs_kg = min(h2_compressed * 0.6, 1.0)

        # ── ۵. برق مازاد ──────────────────────────────────────────────
        elec_energy_used = elec_power_kw * elec_hours
        compressor_energy = cfg.COMPRESSOR_POWER_KW * (comp_runs * 0.5 / 24)
        remaining = max(0, energy_after_bess - elec_energy_used - compressor_energy)
        grid_export = remaining * 0.85  # 85% قابل صادرات
        grid_import = 0.0

        # واردات از گرید اگه BESS کم بود
        if total_gen_kwh < cfg.ELEC_P_MIN_KW * 6:
            grid_import = max(0, cfg.ELEC_P_MIN_KW * 4 - total_gen_kwh) * 0.3

        # ── ۶. اقتصاد ─────────────────────────────────────────────────
        # هزینه انرژی
        energy_cost = grid_import * params.grid_buy_eur
        # هزینه استهلاک stack
        stack_depr = (elec_hours / cfg.electrolyzer.mttf_hours) * cfg.STACK_REPLACEMENT_COST
        total_cost = energy_cost + stack_depr

        # LCOH
        lcoh = (total_cost / h2_kg) if h2_kg > 0.001 else 0.0
        lcoh = min(lcoh, 20.0)  # cap برای روزهای بدون تولید

        # درآمد
        grid_rev = grid_export * params.grid_sell_eur
        h2_rev   = h2_hrs_kg * params.h2_price_eur_kg
        subsidy  = h2_kg * cfg.GREEN_H2_SUBSIDY
        co2_kg   = h2_kg * cfg.CO2_SAVED_PER_KG_H2
        co2_rev  = (co2_kg / 1000) * cfg.CARBON_TAX_EUR_TON
        revenue  = grid_rev + h2_rev + subsidy + co2_rev

        return {
            "h2_kg":       h2_kg,
            "h2_hrs_kg":   h2_hrs_kg,
            "bess_cycles": bess_cycles,
            "grid_export": grid_export,
            "grid_import": grid_import,
            "lcoh":        lcoh,
            "co2_kg":      co2_kg,
            "revenue":     revenue,
            "water_l":     water_l,
            "o2_nm3":      o2_nm3,
            "elec_hours":  elec_hours,
            "comp_runs":   comp_runs,
        }

    def _elec_efficiency(self, power_kw: float) -> float:
        """بازده از منحنی واقعی S30/30"""
        if power_kw < self.cfg.ELEC_P_MIN_KW:
            return 0.0
        pts = sorted(self.cfg.ELEC_EFF_CURVE.items())
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return float(np.interp(power_kw, xs, ys))

    # ------------------------------------------------------------------
    # جمع‌بندی ماهانه
    # ------------------------------------------------------------------
    def _aggregate_monthly(
        self, daily: List[DailyResult]
    ) -> List[MonthlyResult]:
        monthly = []
        for m in range(1, 13):
            days = [d for d in daily if d.month == m]
            if not days:
                continue
            h2_total = sum(d.h2_produced_kg for d in days)
            elec_h   = sum(d.electrolyzer_hours for d in days)
            eff_avg  = (h2_total / (elec_h * self.cfg.ELEC_P_NOM_KW / 33.33)
                        * 100 if elec_h > 0 else 0)

            monthly.append(MonthlyResult(
                month=m,
                month_name=self.MONTH_NAMES_EN[m - 1],
                solar_kwh=round(sum(d.solar_kwh for d in days), 2),
                wind_kwh=round(sum(d.wind_kwh for d in days), 2),
                h2_produced_kg=round(h2_total, 3),
                h2_to_hrs_kg=round(sum(d.h2_to_hrs_kg for d in days), 3),
                lcoh_eur_kg=round(
                    sum(d.lcoh_eur_kg * d.h2_produced_kg for d in days if d.h2_produced_kg > 0)
                    / max(h2_total, 0.001), 3),
                co2_saved_kg=round(sum(d.co2_saved_kg for d in days), 2),
                revenue_eur=round(sum(d.revenue_eur for d in days), 2),
                water_used_l=round(sum(d.water_used_l for d in days), 2),
                o2_produced_nm3=round(sum(d.o2_produced_nm3 for d in days), 2),
                grid_export_kwh=round(sum(d.grid_export_kwh for d in days), 2),
                grid_import_kwh=round(sum(d.grid_import_kwh for d in days), 2),
                bess_cycles=round(sum(d.bess_cycles for d in days), 2),
                electrolyzer_hours=round(elec_h, 1),
                avg_efficiency_pct=round(min(eff_avg, 100), 1),
                days_profitable=sum(
                    1 for d in days
                    if 0 < d.lcoh_eur_kg <= self.cfg.LCOH_TARGET_EURO_KG
                ),
            ))
        return monthly

    # ------------------------------------------------------------------
    # گزارش سالانه نهایی
    # ------------------------------------------------------------------
    def _build_annual(
        self,
        daily: List[DailyResult],
        monthly: List[MonthlyResult],
        params: ScenarioParams,
    ) -> AnnualReport:
        cfg = self.cfg

        total_solar    = sum(d.solar_kwh for d in daily)
        total_wind     = sum(d.wind_kwh for d in daily)
        total_gen      = total_solar + total_wind
        total_h2       = sum(d.h2_produced_kg for d in daily)
        total_h2_hrs   = sum(d.h2_to_hrs_kg for d in daily)
        total_revenue  = sum(d.revenue_eur for d in daily)
        total_co2      = sum(d.co2_saved_kg for d in daily)
        total_water    = sum(d.water_used_l for d in daily)
        total_o2       = sum(d.o2_produced_nm3 for d in daily)
        total_export   = sum(d.grid_export_kwh for d in daily)
        total_import   = sum(d.grid_import_kwh for d in daily)
        total_bess_cyc = sum(d.bess_cycles for d in daily)
        total_elec_h   = sum(d.electrolyzer_hours for d in daily)
        total_comp     = sum(d.compressor_runs for d in daily)

        # LCOH میانگین وزنی
        h2_days = [d for d in daily if d.h2_produced_kg > 0.001]
        if h2_days:
            avg_lcoh = (sum(d.lcoh_eur_kg * d.h2_produced_kg for d in h2_days)
                        / sum(d.h2_produced_kg for d in h2_days))
            best_lcoh  = min(d.lcoh_eur_kg for d in h2_days)
            worst_lcoh = max(d.lcoh_eur_kg for d in h2_days if d.lcoh_eur_kg > 0)
        else:
            avg_lcoh = worst_lcoh = 0.0
            best_lcoh = 0.0

        # هزینه‌های سالانه
        stack_cost   = (total_elec_h / cfg.electrolyzer.mttf_hours) * cfg.STACK_REPLACEMENT_COST
        compressor_maintenance = total_comp * 0.05  # €0.05 per run
        grid_cost    = total_import * params.grid_buy_eur
        total_cost   = (params.opex_annual_eur + stack_cost
                        + compressor_maintenance + grid_cost)
        net_profit   = total_revenue - total_cost

        # تعداد جایگزینی stack
        stack_replacements = int(total_elec_h / cfg.electrolyzer.mttf_hours)

        # عمر باقیمانده BESS
        bess_remaining = max(0, 1 - total_bess_cyc / cfg.BATT_CYCLE_LIFE) * 100

        # استقلال از گرید
        grid_independence = max(0, (1 - total_import / max(total_gen, 1)) * 100)

        # Payback و ROI
        if net_profit > 0:
            payback = params.capex_eur / net_profit
        else:
            payback = 99.0
        roi = (net_profit / params.capex_eur * 100) if params.capex_eur > 0 else 0

        # کربن کردیت
        co2_credits = (total_co2 / 1000) * cfg.CARBON_TAX_EUR_TON

        return AnnualReport(
            total_solar_kwh=round(total_solar, 1),
            total_wind_kwh=round(total_wind, 1),
            total_gen_kwh=round(total_gen, 1),
            total_h2_kg=round(total_h2, 2),
            total_h2_to_hrs_kg=round(total_h2_hrs, 2),
            avg_daily_h2_kg=round(total_h2 / 365, 4),
            peak_daily_h2_kg=round(max(d.h2_produced_kg for d in daily), 4),
            total_revenue_eur=round(total_revenue, 2),
            total_cost_eur=round(total_cost, 2),
            net_profit_eur=round(net_profit, 2),
            avg_lcoh_eur_kg=round(avg_lcoh, 3),
            best_lcoh_eur_kg=round(best_lcoh, 3),
            worst_lcoh_eur_kg=round(worst_lcoh, 3),
            payback_years=round(payback, 1),
            roi_pct=round(roi, 1),
            total_co2_saved_kg=round(total_co2, 1),
            total_co2_saved_ton=round(total_co2 / 1000, 3),
            co2_credits_eur=round(co2_credits, 2),
            total_water_l=round(total_water, 1),
            total_o2_nm3=round(total_o2, 1),
            total_bess_cycles=round(total_bess_cyc, 1),
            bess_remaining_life_pct=round(bess_remaining, 1),
            electrolyzer_hours=round(total_elec_h, 1),
            stack_replacements=stack_replacements,
            total_grid_export_kwh=round(total_export, 1),
            total_grid_import_kwh=round(total_import, 1),
            grid_independence_pct=round(grid_independence, 1),
            monthly=monthly,
            daily=daily,
        )

    # ------------------------------------------------------------------
    # مقایسه چند سناریو
    # ------------------------------------------------------------------
    def compare_scenarios(
        self, scenarios: List[ScenarioParams]
    ) -> List[AnnualReport]:
        results = []
        for s in scenarios:
            logger.info("Running scenario: %s", s.name)
            results.append(self.run_annual(s))
        return results


# =============================================================================
# Smoke-test
# =============================================================================
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from config import Config, validate_config
    validate_config()

    engine = ScenarioEngine(Config)

    print("در حال شبیه‌سازی ۳۶۵ روز...")
    import time
    t0 = time.time()
    report = engine.run_annual(ScenarioParams(name="پیش‌فرض"))
    elapsed = time.time() - t0

    print(f"\n✅ شبیه‌سازی در {elapsed:.2f} ثانیه کامل شد")
    print(f"\n{'='*55}")
    print(f"  گزارش سالانه LUMINIH2 — Zagreb")
    print(f"{'='*55}")
    print(f"  تولید خورشیدی   : {report.total_solar_kwh:,.0f} kWh")
    print(f"  تولید بادی      : {report.total_wind_kwh:,.0f} kWh")
    print(f"  کل تولید        : {report.total_gen_kwh:,.0f} kWh")
    print(f"\n  H₂ تولیدی       : {report.total_h2_kg:.2f} kg/year")
    print(f"  میانگین روزانه  : {report.avg_daily_h2_kg*1000:.1f} g/day")
    print(f"  H₂ به HRS       : {report.total_h2_to_hrs_kg:.2f} kg/year")
    print(f"\n  LCOH میانگین    : €{report.avg_lcoh_eur_kg:.3f}/kg")
    print(f"  LCOH بهترین     : €{report.best_lcoh_eur_kg:.3f}/kg")
    print(f"  هدف LCOH        : €{Config.LCOH_TARGET_EURO_KG:.1f}/kg")
    print(f"\n  درآمد کل        : €{report.total_revenue_eur:,.2f}")
    print(f"  هزینه کل        : €{report.total_cost_eur:,.2f}")
    print(f"  سود خالص        : €{report.net_profit_eur:,.2f}")
    print(f"  دوره بازگشت     : {report.payback_years:.1f} سال")
    print(f"  ROI             : {report.roi_pct:.1f}%")
    print(f"\n  CO₂ صرفه‌جویی   : {report.total_co2_saved_ton:.2f} تن")
    print(f"  کربن کردیت      : €{report.co2_credits_eur:.2f}")
    print(f"\n  آب مصرفی        : {report.total_water_l:.0f} L")
    print(f"  O₂ تولیدی       : {report.total_o2_nm3:.0f} Nm³")
    print(f"\n  ساعات الکترولایزر: {report.electrolyzer_hours:.0f} h")
    print(f"  جایگزینی stack  : {report.stack_replacements} بار")
    print(f"  استقلال گرید    : {report.grid_independence_pct:.1f}%")
    print(f"\n  بهترین ماه:")
    best_m = max(report.monthly, key=lambda x: x.h2_produced_kg)
    print(f"    {best_m.month_name}: {best_m.h2_produced_kg:.2f} kg H₂")
    print(f"\n  بدترین ماه:")
    worst_m = min(report.monthly, key=lambda x: x.h2_produced_kg)
    print(f"    {worst_m.month_name}: {worst_m.h2_produced_kg:.2f} kg H₂")

    # مقایسه سناریوها
    print(f"\n{'='*55}")
    print("  مقایسه سناریوها:")
    scenarios = [
        ScenarioParams(name="پیش‌فرض", elec_priority_mode="h2_max"),
        ScenarioParams(name="LCOH بهینه", elec_priority_mode="lcoh_opt"),
        ScenarioParams(name="PV ×۲", pv_scale=2.0, elec_priority_mode="h2_max"),
    ]
    reports = engine.compare_scenarios(scenarios)
    print(f"  {'سناریو':<15} {'H₂ (kg)':<12} {'LCOH (€/kg)':<14} {'سود (€)':<12} {'Payback'}")
    for sc, rp in zip(scenarios, reports):
        print(f"  {sc.name:<15} {rp.total_h2_kg:<12.2f} "
              f"{rp.avg_lcoh_eur_kg:<14.3f} "
              f"{rp.net_profit_eur:<12.2f} "
              f"{rp.payback_years:.1f}y")
