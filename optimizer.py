# =============================================================================
# optimizer.py — LUMINIH2 بهینه‌ساز اقتصادی
# بهترین نقطه کار برای حداقل LCOH
# Version: 4.0
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import logging

logger = logging.getLogger("Optimizer")


# =============================================================================
# نتایج typed
# =============================================================================

@dataclass
class OptPoint:
    """یک نقطه بهینه"""
    elec_power_kw:      float
    h2_rate_kg_h:       float
    efficiency_pct:     float
    lcoh_eur_kg:        float
    annual_h2_kg:       float
    annual_revenue_eur: float
    annual_cost_eur:    float
    net_profit_eur:     float
    label:              str


@dataclass
class OptResult:
    """نتیجه کامل بهینه‌سازی"""
    best_lcoh_point:    OptPoint
    best_profit_point:  OptPoint
    all_points:         List[OptPoint]
    recommendation:     str
    reason:             str


# =============================================================================
# بهینه‌ساز
# =============================================================================

class EconomicOptimizer:
    """
    بهینه‌ساز نقطه کار الکترولایزر S30/30
    با توجه به قیمت برق، قیمت H₂، و هزینه stack
    """

    def __init__(self, config):
        self.cfg = config

    def find_optimal_operating_point(
        self,
        available_power_kw: float,
        grid_price_eur_kwh: float = 0.22,
        h2_price_eur_kg: float = 6.0,
        source: str = "renewable",
    ) -> OptResult:
        """
        پیدا کردن بهترین بار الکترولایزر

        Args:
            available_power_kw: توان تجدیدپذیر موجود
            grid_price_eur_kwh: قیمت برق گرید (برای مقایسه)
            h2_price_eur_kg: قیمت فروش H₂
            source: "renewable" | "grid"
        """
        cfg = self.cfg
        points: List[OptPoint] = []

        # بررسی تمام نقاط بار از min تا max
        power_range = np.linspace(cfg.ELEC_P_MIN_KW, cfg.ELEC_P_MAX_KW, 50)

        for p_kw in power_range:
            if p_kw > available_power_kw:
                break

            # بازده از منحنی S30/30
            eff = float(np.interp(
                p_kw,
                sorted(cfg.ELEC_EFF_CURVE.keys()),
                [cfg.ELEC_EFF_CURVE[k] for k in sorted(cfg.ELEC_EFF_CURVE.keys())]
            ))

            # تولید H₂
            h2_kg_h = (p_kw * eff) / 33.33

            # هزینه انرژی
            if source == "grid":
                energy_cost_h = p_kw * grid_price_eur_kwh
            else:
                energy_cost_h = p_kw * 0.02  # هزینه O&M تجدیدپذیر

            # استهلاک stack
            load_factor = p_kw / cfg.ELEC_P_MAX_KW
            stack_depr_h = load_factor * (
                cfg.STACK_REPLACEMENT_COST / cfg.electrolyzer.mttf_hours
            )

            total_cost_h = energy_cost_h + stack_depr_h

            # LCOH
            lcoh = total_cost_h / h2_kg_h if h2_kg_h > 0 else 999

            # سالانه (فرض ۷۰۰۰ ساعت/سال)
            annual_hours = 7000.0
            annual_h2 = h2_kg_h * annual_hours
            annual_cost = total_cost_h * annual_hours
            annual_rev = (annual_h2 * h2_price_eur_kg
                         + annual_h2 * cfg.GREEN_H2_SUBSIDY
                         + (annual_h2 * cfg.CO2_SAVED_PER_KG_H2 / 1000)
                         * cfg.CARBON_TAX_EUR_TON)

            # label
            if abs(p_kw - cfg.ELEC_P_MIN_KW) < 0.1:
                label = "حداقل بار"
            elif abs(p_kw - cfg.ELEC_P_NOM_KW) < 0.2:
                label = "بار نامی"
            elif abs(p_kw - cfg.ELEC_P_MAX_KW) < 0.1:
                label = "بار پیک"
            else:
                label = f"{p_kw:.1f} kW"

            points.append(OptPoint(
                elec_power_kw=round(p_kw, 3),
                h2_rate_kg_h=round(h2_kg_h, 5),
                efficiency_pct=round(eff * 100, 2),
                lcoh_eur_kg=round(lcoh, 3),
                annual_h2_kg=round(annual_h2, 1),
                annual_revenue_eur=round(annual_rev, 2),
                annual_cost_eur=round(annual_cost, 2),
                net_profit_eur=round(annual_rev - annual_cost, 2),
                label=label,
            ))

        if not points:
            dummy = OptPoint(0, 0, 0, 999, 0, 0, 0, 0, "بدون تولید")
            return OptResult(dummy, dummy, [], "توان کافی نیست", "توان موجود کمتر از حداقل بار الکترولایزر")

        # بهترین LCOH
        best_lcoh = min(points, key=lambda p: p.lcoh_eur_kg)
        # بهترین سود
        best_profit = max(points, key=lambda p: p.net_profit_eur)

        # توصیه
        if source == "renewable":
            rec_point = best_lcoh
            reason = (f"با برق تجدیدپذیر، بار {rec_point.elec_power_kw:.1f} kW "
                     f"بهترین LCOH = €{rec_point.lcoh_eur_kg:.3f}/kg را می‌دهد")
        else:
            if best_lcoh.lcoh_eur_kg <= self.cfg.LCOH_TARGET_EURO_KG:
                rec_point = best_profit
                reason = (f"LCOH در بار نامی €{best_lcoh.lcoh_eur_kg:.3f}/kg "
                         f"زیر هدف €{self.cfg.LCOH_TARGET_EURO_KG}/kg است")
            else:
                rec_point = best_lcoh
                reason = (f"با برق گرید، LCOH = €{best_lcoh.lcoh_eur_kg:.3f}/kg "
                         f"— بالای هدف. بهتر است صبر کنید")

        return OptResult(
            best_lcoh_point=best_lcoh,
            best_profit_point=best_profit,
            all_points=points,
            recommendation=f"Recommended load: {rec_point.elec_power_kw:.2f} kW",
            reason=reason,
        )

    def annual_sensitivity(
        self,
        h2_prices: List[float] = None,
        pv_scales: List[float] = None,
    ) -> List[dict]:
        """
        تحلیل حساسیت سالانه
        """
        if h2_prices is None:
            h2_prices = [4.0, 5.0, 6.0, 7.0, 8.0]
        if pv_scales is None:
            pv_scales = [1.0, 1.5, 2.0]

        results = []
        for pv_s in pv_scales:
            for h2_p in h2_prices:
                available = self.cfg.PV_SYSTEM_CAPACITY_KW * pv_s * 0.7
                opt = self.find_optimal_operating_point(
                    available, h2_price_eur_kg=h2_p
                )
                bp = opt.best_profit_point
                results.append({
                    "pv_scale":    pv_s,
                    "h2_price":    h2_p,
                    "best_lcoh":   opt.best_lcoh_point.lcoh_eur_kg,
                    "annual_h2":   bp.annual_h2_kg,
                    "net_profit":  bp.net_profit_eur,
                    "profitable":  bp.net_profit_eur > 0,
                })
        return results


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from config import Config, validate_config
    validate_config()

    opt = EconomicOptimizer(Config)

    print("=== بهینه‌سازی نقطه کار LUMINIH2 ===\n")

    # سناریو ۱: با برق تجدیدپذیر
    r1 = opt.find_optimal_operating_point(
        available_power_kw=10.0,
        source="renewable",
        h2_price_eur_kg=6.0,
    )
    print("📊 با برق تجدیدپذیر (10 kW موجود):")
    print(f"   بهترین LCOH   : €{r1.best_lcoh_point.lcoh_eur_kg:.3f}/kg "
          f"در {r1.best_lcoh_point.elec_power_kw:.2f} kW")
    print(f"   بهترین سود    : €{r1.best_profit_point.net_profit_eur:,.0f}/سال "
          f"در {r1.best_profit_point.elec_power_kw:.2f} kW")
    print(f"   توصیه         : {r1.recommendation}")
    print(f"   دلیل          : {r1.reason}")

    print(f"\n   {'بار (kW)':<10} {'H₂ (g/h)':<12} {'η%':<8} {'LCOH':<10} {'سود سالانه'}")
    for p in r1.all_points[::10]:
        print(f"   {p.elec_power_kw:<10.2f} {p.h2_rate_kg_h*1000:<12.1f} "
              f"{p.efficiency_pct:<8.1f} €{p.lcoh_eur_kg:<9.3f} €{p.net_profit_eur:,.0f}")

    # سناریو ۲: با برق گرید
    r2 = opt.find_optimal_operating_point(
        available_power_kw=5.63,
        source="grid",
        h2_price_eur_kg=6.0,
    )
    print(f"\n📊 با برق گرید:")
    print(f"   بهترین LCOH   : €{r2.best_lcoh_point.lcoh_eur_kg:.3f}/kg")
    print(f"   هدف LCOH      : €{Config.LCOH_TARGET_EURO_KG:.1f}/kg")
    print(f"   توصیه         : {r2.recommendation}")

    # تحلیل حساسیت
    print(f"\n📊 تحلیل حساسیت (قیمت H₂ vs مقیاس PV):")
    sens = opt.annual_sensitivity(
        h2_prices=[4.0, 6.0, 8.0],
        pv_scales=[1.0, 2.0],
    )
    print(f"   {'PV ×':<6} {'H₂ €/kg':<10} {'LCOH':<10} {'H₂ kg/y':<12} {'سود €/y':<12} {'سودده؟'}")
    for s in sens:
        print(f"   {s['pv_scale']:<6.1f} €{s['h2_price']:<9.1f} "
              f"€{s['best_lcoh']:<9.3f} {s['annual_h2']:<12.1f} "
              f"€{s['net_profit']:<12,.0f} {'✅' if s['profitable'] else '❌'}")

    print("\n✅ optimizer.py v4.0 OK")
