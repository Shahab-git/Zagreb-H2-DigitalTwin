# =============================================================================
# uncertainty_engine.py — LUMINIH2 Probabilistic Performance Analysis
# Monte Carlo · P10/P50/P90 Confidence Intervals · Pilot Scale Honest Report
# Version: 1.1
# =============================================================================
#
# IMPORTANT CONTEXT:
#   LUMINIH2 is a PILOT / DEMONSTRATION project at 5.63 kW electrolyzer scale.
#   At this scale (~344 kg H₂/year), commercial LCOH targets (€4.5/kg incl.
#   CAPEX) are not achievable — this is true for ALL pilot H₂ projects.
#
#   This engine reports HONEST metrics for a pilot:
#   1. H₂ production volume (P10/P50/P90)
#   2. CO₂ offset vs Steam Methane Reforming
#   3. Operating LCOH (energy + stack depreciation, NO CAPEX amortisation)
#   4. Revenue self-sufficiency ratio
#   5. Scale-up projection to commercial viability
#   6. Technology demonstration KPIs
#
# MONTE CARLO SOURCES OF UNCERTAINTY:
#   • Zagreb weather variability (GHI ±15%, wind ±25% year-to-year)
#   • Panel power tolerance ±1.4% (datasheet: ±5W on 360W)
#   • Electrolyzer efficiency tolerance ±2% (datasheet tolerance)
#   • System availability variability (mean 96% ± 2%)
#   • Panel soiling variability (1–5% annual loss)
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np
import logging

logger = logging.getLogger("UncertaintyEngine")

# ── Uncertainty parameters ────────────────────────────────────────────────────
ZAGREB_GHI_CV       = 0.15    # ±15% year-to-year GHI variability
ZAGREB_WIND_CV      = 0.25    # ±25% year-to-year wind variability
PANEL_POWER_TOL     = 0.014   # ±1.4% panel power tolerance
ELEC_EFF_TOL        = 0.020   # ±2% electrolyzer efficiency tolerance
AVAILABILITY_MEAN   = 0.96    # 96% system availability
AVAILABILITY_STD    = 0.020   # ±2%
SOILING_LOSS_MIN    = 0.01    # 1% annual soiling (rainy year)
SOILING_LOSS_MAX    = 0.05    # 5% annual soiling (dry year)

# Zagreb 10-year climatology
ZAGREB_GHI  = {1:1.10,2:1.85,3:3.20,4:4.50,5:5.60,6:6.10,
               7:6.30,8:5.70,9:4.00,10:2.50,11:1.20,12:0.90}
ZAGREB_WIND = {1:4.2,2:4.5,3:4.8,4:4.3,5:3.9,6:3.5,
               7:3.2,8:3.1,9:3.4,10:3.8,11:4.1,12:4.3}
DAYS_IN_MONTH = [31,28,31,30,31,30,31,31,30,31,30,31]


# =============================================================================
# Result containers
# =============================================================================

@dataclass
class PercentileResult:
    metric:  str
    unit:    str
    p10:     float
    p50:     float
    p90:     float
    mean:    float
    std:     float

    @property
    def cv_pct(self) -> float:
        return round(self.std / max(abs(self.mean), 1e-9) * 100, 1)

    @property
    def band(self) -> str:
        half = (self.p90 - self.p10) / 2
        pct  = half / max(abs(self.p50), 1e-9) * 100
        return f"±{pct:.0f}%"

    @property
    def statement(self) -> str:
        return (f"{self.p50:.1f} {self.unit}  "
                f"[P10: {self.p10:.1f} — P90: {self.p90:.1f}]")


@dataclass
class ScaleUpProjection:
    """What would this system produce at commercial scale?"""
    electrolyzer_kw:  float
    h2_kg_year_p50:   float
    h2_ton_year:      float
    annual_revenue:   float
    op_lcoh:          float
    is_commercial:    bool


@dataclass
class UncertaintyReport:
    n_simulations:       int
    # Core production metrics
    annual_h2_kg:        PercentileResult
    daily_h2_g:          PercentileResult
    co2_offset_ton:      PercentileResult
    # Operational economics (no CAPEX)
    op_lcoh_eur_kg:      PercentileResult   # Operating LCOH only
    annual_op_revenue:   PercentileResult   # Revenue from H₂+subsidy+CO₂
    revenue_to_opex_pct: PercentileResult   # Self-sufficiency ratio
    # System performance
    electrolyzer_hours:  PercentileResult
    solar_kwh_year:      PercentileResult
    wind_kwh_year:       PercentileResult
    grid_independence:   PercentileResult
    # Sensitivity
    sensitivity:         Dict[str, float] = field(default_factory=dict)
    # Scale-up projections
    scale_up:            List[ScaleUpProjection] = field(default_factory=list)
    # Raw samples for Streamlit histogram plots
    samples_h2:          List[float] = field(default_factory=list)
    samples_lcoh:        List[float] = field(default_factory=list)
    samples_revenue:     List[float] = field(default_factory=list)
    # Risk flags
    p10_h2_above_tank_daily: bool = False  # Can system fill HRS daily at P10?


# =============================================================================
# Uncertainty Engine
# =============================================================================

class UncertaintyEngine:
    """
    Monte Carlo probabilistic performance analysis for LUMINIH2 pilot.
    Produces honest P10/P50/P90 intervals with correct pilot-scale economics.
    """

    def __init__(self, config):
        self.cfg = config
        self.rng = np.random.default_rng(42)

    def run(
        self,
        n_simulations:   int   = 500,
        h2_price_eur_kg: float = 6.0,
        opex_annual_eur: float = 8_000.0,
    ) -> UncertaintyReport:
        """Run Monte Carlo and return probabilistic report."""
        logger.info("Monte Carlo: %d simulations…", n_simulations)

        res = {k: [] for k in [
            "h2_kg", "daily_h2_g", "co2_ton",
            "op_lcoh", "op_revenue", "rev_opex_pct",
            "elec_hours", "solar_kwh", "wind_kwh", "grid_indep",
        ]}
        param_samples = {k: [] for k in [
            "ghi", "wind", "panel", "elec_eff", "avail", "soiling"]}

        for _ in range(n_simulations):
            # Sample parameters
            ghi_s   = float(self.rng.lognormal(0, ZAGREB_GHI_CV))
            wind_s  = float(self.rng.lognormal(0, ZAGREB_WIND_CV))
            panel_f = float(self.rng.normal(1.0, PANEL_POWER_TOL))
            eff_f   = float(self.rng.normal(1.0, ELEC_EFF_TOL))
            avail   = float(np.clip(self.rng.normal(AVAILABILITY_MEAN, AVAILABILITY_STD), 0.80, 1.0))
            soiling = float(self.rng.uniform(SOILING_LOSS_MIN, SOILING_LOSS_MAX))

            for k, v in zip(["ghi","wind","panel","elec_eff","avail","soiling"],
                            [ghi_s, wind_s, panel_f, eff_f, avail, soiling]):
                param_samples[k].append(v)

            r = self._year(ghi_s, wind_s, panel_f, eff_f, avail, soiling,
                           h2_price_eur_kg, opex_annual_eur)
            for k, v in r.items():
                res[k].append(v)

        # Build percentile results
        def P(key, metric, unit) -> PercentileResult:
            a = np.array(res[key])
            return PercentileResult(
                metric=metric, unit=unit,
                p10=round(float(np.percentile(a, 10)), 2),
                p50=round(float(np.percentile(a, 50)), 2),
                p90=round(float(np.percentile(a, 90)), 2),
                mean=round(float(a.mean()), 2),
                std=round(float(a.std()), 2),
            )

        h2_arr = np.array(res["h2_kg"])

        # Sensitivity via Pearson correlation with H₂ output
        sensitivity = {}
        labels = {"ghi":"Solar irradiance variability",
                  "wind":"Wind speed variability",
                  "panel":"Panel power tolerance",
                  "elec_eff":"Electrolyzer efficiency tolerance",
                  "avail":"System availability",
                  "soiling":"Panel soiling loss"}
        for k, label in labels.items():
            corr = float(np.corrcoef(param_samples[k], h2_arr)[0, 1])
            sensitivity[label] = round(abs(corr) * 100, 1)

        # Scale-up projections
        p50_h2  = float(np.percentile(h2_arr, 50))
        p50_lcoh = float(np.percentile(np.array(res["op_lcoh"]), 50))
        scale_ups = []
        for kw, label in [(5.63, "Pilot (current)"),
                          (100,  "Demo scale"),
                          (1000, "Commercial"),
                          (10000,"Utility scale")]:
            sf = kw / self.cfg.ELEC_P_NOM_KW
            h2y = p50_h2 * sf
            rev = h2y * (h2_price_eur_kg + self.cfg.GREEN_H2_SUBSIDY) + \
                  (h2y * self.cfg.CO2_SAVED_PER_KG_H2 / 1000) * self.cfg.CARBON_TAX_EUR_TON
            scale_ups.append(ScaleUpProjection(
                electrolyzer_kw=kw,
                h2_kg_year_p50=round(h2y, 0),
                h2_ton_year=round(h2y / 1000, 2),
                annual_revenue=round(rev, 0),
                op_lcoh=round(p50_lcoh, 2),
                is_commercial=(kw >= 1000),
            ))

        report = UncertaintyReport(
            n_simulations=n_simulations,
            annual_h2_kg    =P("h2_kg",        "Annual H₂ production",    "kg/year"),
            daily_h2_g      =P("daily_h2_g",   "Average daily H₂",        "g/day"),
            co2_offset_ton  =P("co2_ton",       "CO₂ offset vs SMR",       "ton/year"),
            op_lcoh_eur_kg  =P("op_lcoh",       "Operating LCOH",          "€/kg"),
            annual_op_revenue=P("op_revenue",   "Annual revenue",           "€/year"),
            revenue_to_opex_pct=P("rev_opex_pct","Revenue/OPEX ratio",     "%"),
            electrolyzer_hours=P("elec_hours",  "Electrolyzer run-time",   "h/year"),
            solar_kwh_year  =P("solar_kwh",     "Solar generation",        "kWh/year"),
            wind_kwh_year   =P("wind_kwh",      "Wind generation",         "kWh/year"),
            grid_independence=P("grid_indep",   "Grid independence",       "%"),
            sensitivity=dict(sorted(sensitivity.items(), key=lambda x: x[1], reverse=True)),
            scale_up=scale_ups,
            samples_h2=res["h2_kg"],
            samples_lcoh=res["op_lcoh"],
            samples_revenue=res["op_revenue"],
            p10_h2_above_tank_daily=(
                float(np.percentile(h2_arr, 10)) / 365 * 1000 >
                self.cfg.HRS_H2_TANK_CAPACITY_KG * 200  # 200g/day min HRS use
            ),
        )
        logger.info("Done. P50 H₂=%.1f kg/yr, Op.LCOH=€%.2f/kg",
                    report.annual_h2_kg.p50, report.op_lcoh_eur_kg.p50)
        return report

    # ------------------------------------------------------------------
    # Single-year simulation
    # ------------------------------------------------------------------

    def _year(self, ghi_s, wind_s, panel_f, eff_f, avail, soiling,
              h2_price, opex) -> dict:
        cfg = self.cfg
        h2_total = solar_total = wind_total = elec_h = 0.0
        op_cost = 0.0

        for mi, days in enumerate(DAYS_IN_MONTH):
            m = mi + 1
            ghi_avg  = ZAGREB_GHI[m]  * ghi_s
            wind_avg = ZAGREB_WIND[m] * wind_s

            for _ in range(days):
                # Daily weather
                ghi_day  = float(np.clip(
                    self.rng.normal(ghi_avg, ghi_avg * 0.15), 0, ghi_avg * 2.5))
                wind_day = float(np.clip(
                    self.rng.weibull(2.0) * wind_avg, 0, 25.0))

                # PV [kWh/day]
                pv_cap   = cfg.PV_SYSTEM_CAPACITY_KW * panel_f
                t_cell   = 20 + (ghi_day * 1000 / 24 / 800) * (45 - 20)
                therm_f  = max(0, 1 + cfg.pv.temp_coeff_pct_c * (t_cell - 25))
                sf       = max(0.90, 1.0 - soiling * 0.5)
                solar_d  = pv_cap * ghi_day * therm_f * sf * cfg.INVERTER_EFFICIENCY
                solar_total += solar_d

                # Wind [kWh/day]
                ci, rt = cfg.wind.cut_in_ms, cfg.wind.rated_speed_ms
                if wind_day < ci:
                    wind_d = 0.0
                elif wind_day >= rt:
                    wind_d = cfg.WIND_SYSTEM_CAPACITY_KW * 24
                else:
                    ratio  = (wind_day - ci) / (rt - ci)
                    wind_d = cfg.WIND_SYSTEM_CAPACITY_KW * (ratio ** 3) * 24
                wind_total += wind_d

                total_gen = (solar_d + wind_d) * avail

                # Electrolyzer-first dispatch
                if total_gen >= cfg.ELEC_P_MIN_KW:
                    hours = min(total_gen / cfg.ELEC_P_NOM_KW, 20.0) * avail
                    eff   = float(np.clip(
                        cfg.ELEC_EFF_CURVE[cfg.ELEC_P_NOM_KW] * eff_f, 0.50, 0.95))
                    h2_d  = (cfg.ELEC_P_NOM_KW * eff / 33.33) * hours
                    h2_total += h2_d
                    elec_h   += hours

                    # Operating cost (energy O&M + stack depreciation only)
                    load_f    = cfg.ELEC_P_NOM_KW / cfg.ELEC_P_MAX_KW
                    stack_h   = load_f * (cfg.STACK_REPLACEMENT_COST /
                                (cfg.ELEC_P_MAX_KW * cfg.electrolyzer.mttf_hours))
                    energy_h  = cfg.ELEC_P_NOM_KW * 0.02
                    op_cost  += (stack_h + energy_h) * hours

        # Annual operating economics
        co2_ton      = h2_total * cfg.CO2_SAVED_PER_KG_H2 / 1000
        co2_rev      = co2_ton * cfg.CARBON_TAX_EUR_TON
        subsidy      = h2_total * cfg.GREEN_H2_SUBSIDY
        h2_rev       = h2_total * h2_price
        op_revenue   = h2_rev + subsidy + co2_rev

        # Operating LCOH = operating costs only (no CAPEX)
        total_op_cost = op_cost + opex
        op_lcoh       = total_op_cost / max(h2_total, 0.001)

        # Revenue / OPEX ratio
        rev_opex_pct  = (op_revenue / max(opex, 1)) * 100

        # Grid independence
        total_elec_energy = elec_h * cfg.ELEC_P_NOM_KW
        grid_indep = float(np.clip(
            (solar_total + wind_total) / max(total_elec_energy, 1) * 100, 0, 100))

        return {
            "h2_kg":        round(h2_total, 2),
            "daily_h2_g":   round(h2_total / 365 * 1000, 1),
            "co2_ton":      round(co2_ton, 3),
            "op_lcoh":      round(op_lcoh, 3),
            "op_revenue":   round(op_revenue, 2),
            "rev_opex_pct": round(rev_opex_pct, 1),
            "elec_hours":   round(elec_h, 0),
            "solar_kwh":    round(solar_total, 0),
            "wind_kwh":     round(wind_total, 0),
            "grid_indep":   round(grid_indep, 1),
        }

    def print_report(self, rpt: UncertaintyReport):
        cfg = self.cfg
        W = 65
        print("\n" + "=" * W)
        print("  LUMINIH2 — PROBABILISTIC PERFORMANCE REPORT")
        print("  Pre-deployment Digital Twin · Zagreb, Croatia")
        print("  ITM S30/30 · TH540-50 · HCS-100 · AIRCELL 3000")
        print("=" * W)
        print(f"  Monte Carlo runs : {rpt.n_simulations:,}")
        print(f"  Confidence level : 80%  (P10 pessimistic → P90 optimistic)")
        print()

        # Production table
        print(f"  {'PRODUCTION & ENVIRONMENT':<32} {'P10':>7} {'P50':>7} {'P90':>7}  Unit")
        print(f"  {'-'*32} {'-'*7} {'-'*7} {'-'*7}  ----")
        for m in [rpt.annual_h2_kg, rpt.daily_h2_g, rpt.co2_offset_ton,
                  rpt.electrolyzer_hours, rpt.solar_kwh_year, rpt.wind_kwh_year,
                  rpt.grid_independence]:
            print(f"  {m.metric:<32} {m.p10:>7.1f} {m.p50:>7.1f} {m.p90:>7.1f}  {m.unit}")

        print()
        print(f"  {'OPERATIONAL ECONOMICS':<32} {'P10':>7} {'P50':>7} {'P90':>7}  Unit")
        print(f"  {'-'*32} {'-'*7} {'-'*7} {'-'*7}  ----")
        for m in [rpt.op_lcoh_eur_kg, rpt.annual_op_revenue, rpt.revenue_to_opex_pct]:
            print(f"  {m.metric:<32} {m.p10:>7.1f} {m.p50:>7.1f} {m.p90:>7.1f}  {m.unit}")

        print()
        print("  NOTE ON ECONOMICS:")
        print("  Operating LCOH excludes CAPEX amortisation (pilot project).")
        print("  Full LCOH including CAPEX requires commercial scale (≥1 MW).")

        print()
        print("  SENSITIVITY — Top drivers of H₂ production uncertainty")
        for i, (param, impact) in enumerate(list(rpt.sensitivity.items())[:5], 1):
            bar = "█" * int(impact / 5)
            print(f"  {i}. {param:<40} {impact:5.1f}%  {bar}")

        print()
        print("  SCALE-UP PATHWAY TO COMMERCIAL VIABILITY")
        print(f"  {'Scale':<20} {'Power':>8} {'H₂/year':>10} {'Revenue':>12}  {'Op.LCOH':>8}")
        print(f"  {'-'*20} {'-'*8} {'-'*10} {'-'*12}  {'-'*8}")
        for sc in rpt.scale_up:
            flag = "✅" if sc.is_commercial else "🔬"
            print(f"  {flag} {sc.electrolyzer_kw:>6.0f} kW  "
                  f"{sc.h2_ton_year:>8.1f} ton  "
                  f"€{sc.annual_revenue:>10,.0f}  "
                  f"€{sc.op_lcoh:>6.2f}/kg")

        print()
        print("  KEY STATEMENTS")
        h2 = rpt.annual_h2_kg; lc = rpt.op_lcoh_eur_kg
        rv = rpt.annual_op_revenue; co = rpt.co2_offset_ton
        print(f"  • H₂: {h2.p50:.0f} kg/year  (80% range: {h2.p10:.0f}–{h2.p90:.0f} kg)")
        print(f"  • Operating LCOH: €{lc.p50:.2f}/kg  (range: €{lc.p10:.2f}–€{lc.p90:.2f}/kg)")
        print(f"  • Annual revenue: €{rv.p50:,.0f}  (range: €{rv.p10:,.0f}–€{rv.p90:,.0f})")
        print(f"  • CO₂ offset: {co.p50:.1f} ton/year vs Steam Methane Reforming")
        print(f"  • System uncertainty: ±{h2.cv_pct:.0f}% driven by Zagreb weather variability")
        print("=" * W)


# =============================================================================
# Smoke-test
# =============================================================================
if __name__ == "__main__":
    import sys, os, time
    sys.path.insert(0, os.path.dirname(__file__))
    from config import Config, validate_config
    validate_config()

    engine = UncertaintyEngine(Config)
    print("Running 500 Monte Carlo simulations…")
    t0 = time.time()
    report = engine.run(n_simulations=500, h2_price_eur_kg=6.0, opex_annual_eur=8000)
    print(f"Completed in {time.time()-t0:.2f}s")
    engine.print_report(report)
    print(f"\n✅ uncertainty_engine.py v1.1 OK")
