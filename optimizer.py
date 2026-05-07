# =============================================================================
# optimizer.py — LUMINIH2 Economic Operating Point Optimiser
# Best electrolyzer load for minimum LCOH or maximum profit
# Version: 4.1
# =============================================================================
#
# PURPOSE:
#   Sweep the S30/30 electrolyzer operating range (0.74–5.63 kW) and find
#   the power setpoint that minimises LCOH or maximises annual net profit,
#   given available renewable generation and H₂ market price.
#
# KEY INSIGHT:
#   Efficiency is highest at partial load (90% at 0.74 kW) but H₂ volume
#   is highest at peak load (59% at 5.63 kW). Optimal LCOH sits between
#   these extremes — typically close to nominal (3 kW) for renewable input.
#
# ANNUAL BASIS:
#   All annual projections assume 7,000 operating hours/year.
#   This is realistic for a system with Zagreb solar + wind availability.
#
# SENSITIVITY ANALYSIS:
#   annual_sensitivity() sweeps H₂ price and PV scale factor to show
#   how profit changes across realistic market and investment scenarios.
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

logger = logging.getLogger("Optimizer")

# Assumed annual operating hours for projections
ANNUAL_HOURS: float = 7000.0   # h/year (realistic for Zagreb climate)


# =============================================================================
# Result containers
# =============================================================================

@dataclass
class OptPoint:
    """A single operating point evaluation result."""
    elec_power_kw:      float   # Electrolyzer power setpoint [kW]
    h2_rate_kg_h:       float   # H₂ production rate [kg/h]
    efficiency_pct:     float   # Electrochemical efficiency [%]
    lcoh_eur_kg:        float   # Levelised Cost of Hydrogen [€/kg]
    annual_h2_kg:       float   # Projected annual H₂ production [kg]
    annual_revenue_eur: float   # Projected annual revenue [€]
    annual_cost_eur:    float   # Projected annual energy + stack cost [€]
    net_profit_eur:     float   # Projected net annual profit [€]
    label:              str     # Human-readable load label


@dataclass
class OptResult:
    """Complete optimisation result with best points and all sweep data."""
    best_lcoh_point:   OptPoint          # Point with minimum LCOH
    best_profit_point: OptPoint          # Point with maximum net profit
    all_points:        List[OptPoint]    # Full sweep (50 points)
    recommendation:    str               # Recommended setpoint statement
    reason:            str               # Explanation of recommendation


# =============================================================================
# Economic Optimiser
# =============================================================================

class EconomicOptimizer:
    """
    Sweep the S30/30 electrolyzer operating range and find the optimal
    power setpoint for minimum LCOH or maximum annual profit.

    Usage:
        opt = EconomicOptimizer(Config)
        result = opt.find_optimal_operating_point(
            available_power_kw=8.0,
            h2_price_eur_kg=6.0,
            source="renewable",
        )
        sens = opt.annual_sensitivity(h2_prices=[4,6,8], pv_scales=[1,2])
    """

    def __init__(self, config) -> None:
        self.cfg = config

    # ------------------------------------------------------------------
    # Main optimisation sweep
    # ------------------------------------------------------------------

    def find_optimal_operating_point(
        self,
        available_power_kw: float,
        grid_price_eur_kwh: float = 0.22,
        h2_price_eur_kg:    float = 6.0,
        source:             str   = "renewable",
    ) -> OptResult:
        """
        Find best electrolyzer operating point given available power.

        Sweeps 50 equally-spaced power points between P_MIN and P_MAX,
        evaluating LCOH and annual profit at each point.

        Args:
            available_power_kw : total renewable power available [kW]
            grid_price_eur_kwh : grid electricity price for grid-source mode [€/kWh]
            h2_price_eur_kg    : H₂ market sell price [€/kg]
            source             : "renewable" (O&M cost only) or "grid" (full price)

        Returns:
            OptResult with best LCOH point, best profit point, and all 50 points
        """
        cfg    = self.cfg
        points: List[OptPoint] = []

        # Build sorted efficiency curve
        p_pts = sorted(cfg.ELEC_EFF_CURVE.keys())
        e_pts = [cfg.ELEC_EFF_CURVE[k] for k in p_pts]

        power_range = np.linspace(cfg.ELEC_P_MIN_KW, cfg.ELEC_P_MAX_KW, 50)

        for p_kw in power_range:
            # Stop if this point exceeds available generation
            if p_kw > available_power_kw:
                break

            # ── Efficiency from S30/30 curve ──────────────────────────
            eff = float(np.interp(p_kw, p_pts, e_pts))

            # ── H₂ production rate ────────────────────────────────────
            h2_kg_h = (p_kw * eff) / 33.33   # LHV of H₂ = 33.33 kWh/kg

            # ── Hourly cost ───────────────────────────────────────────
            if source == "grid":
                energy_cost_h = p_kw * grid_price_eur_kwh
            else:
                # Renewable: only O&M cost (no fuel cost)
                energy_cost_h = p_kw * 0.02

            # Stack depreciation (load-weighted per operating hour)
            load_factor  = p_kw / cfg.ELEC_P_MAX_KW
            stack_depr_h = load_factor * (
                cfg.STACK_REPLACEMENT_COST / cfg.electrolyzer.mttf_hours
            )

            total_cost_h = energy_cost_h + stack_depr_h

            # ── LCOH ──────────────────────────────────────────────────
            lcoh = total_cost_h / h2_kg_h if h2_kg_h > 1e-6 else 999.0

            # ── Annual projections ────────────────────────────────────
            annual_h2  = h2_kg_h * ANNUAL_HOURS
            annual_cost = total_cost_h * ANNUAL_HOURS
            annual_rev  = (
                annual_h2 * h2_price_eur_kg
                + annual_h2 * cfg.GREEN_H2_SUBSIDY
                + (annual_h2 * cfg.CO2_SAVED_PER_KG_H2 / 1000.0)
                * cfg.CARBON_TAX_EUR_TON
            )

            # ── Load label ────────────────────────────────────────────
            label = self._load_label(p_kw, cfg)

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

        # ── No feasible points ────────────────────────────────────────
        if not points:
            dummy = OptPoint(0, 0, 0, 999, 0, 0, 0, 0, "No production")
            return OptResult(
                best_lcoh_point=dummy,
                best_profit_point=dummy,
                all_points=[],
                recommendation="Insufficient power",
                reason=(f"Available power ({available_power_kw:.2f} kW) is below "
                        f"electrolyzer minimum ({cfg.ELEC_P_MIN_KW} kW)"),
            )

        # ── Best points ───────────────────────────────────────────────
        best_lcoh   = min(points, key=lambda p: p.lcoh_eur_kg)
        best_profit = max(points, key=lambda p: p.net_profit_eur)

        # ── Recommendation ────────────────────────────────────────────
        if source == "renewable":
            rec   = best_lcoh
            reason = (
                f"With renewable power, {rec.elec_power_kw:.2f} kW gives the "
                f"best LCOH = €{rec.lcoh_eur_kg:.3f}/kg "
                f"at η={rec.efficiency_pct:.1f}%"
            )
        else:
            if best_lcoh.lcoh_eur_kg <= cfg.LCOH_TARGET_EURO_KG:
                rec    = best_profit
                reason = (
                    f"Grid LCOH at nominal load = €{best_lcoh.lcoh_eur_kg:.3f}/kg "
                    f"is below target €{cfg.LCOH_TARGET_EURO_KG}/kg — "
                    f"optimise for profit at {rec.elec_power_kw:.2f} kW"
                )
            else:
                rec    = best_lcoh
                reason = (
                    f"Grid LCOH = €{best_lcoh.lcoh_eur_kg:.3f}/kg exceeds target "
                    f"€{cfg.LCOH_TARGET_EURO_KG}/kg — wait for renewable window"
                )

        return OptResult(
            best_lcoh_point=best_lcoh,
            best_profit_point=best_profit,
            all_points=points,
            recommendation=f"Recommended setpoint: {rec.elec_power_kw:.2f} kW",
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Sensitivity analysis
    # ------------------------------------------------------------------

    def annual_sensitivity(
        self,
        h2_prices:  Optional[List[float]] = None,
        pv_scales:  Optional[List[float]] = None,
    ) -> List[dict]:
        """
        Sweep H₂ price and PV scale factor for annual sensitivity analysis.

        Args:
            h2_prices : list of H₂ market prices to evaluate [€/kg]
            pv_scales : PV scale factors (1.0 = current 15 kW system)

        Returns:
            List of dicts with pv_scale, h2_price, best_lcoh,
            annual_h2, net_profit, profitable for each combination
        """
        if h2_prices is None:
            h2_prices = [4.0, 5.0, 6.0, 7.0, 8.0]
        if pv_scales is None:
            pv_scales = [1.0, 1.5, 2.0]

        results = []
        for pv_s in pv_scales:
            for h2_p in h2_prices:
                # Available power = PV capacity × scale × average capacity factor
                available = self.cfg.PV_SYSTEM_CAPACITY_KW * pv_s * 0.7
                opt = self.find_optimal_operating_point(
                    available_power_kw=available,
                    h2_price_eur_kg=h2_p,
                    source="renewable",
                )
                bp = opt.best_profit_point
                results.append({
                    "pv_scale":   pv_s,
                    "h2_price":   h2_p,
                    "best_lcoh":  opt.best_lcoh_point.lcoh_eur_kg,
                    "annual_h2":  bp.annual_h2_kg,
                    "net_profit": bp.net_profit_eur,
                    "profitable": bp.net_profit_eur > 0,
                })
        return results

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _load_label(p_kw: float, cfg) -> str:
        """Return a human-readable label for an operating point."""
        if abs(p_kw - cfg.ELEC_P_MIN_KW) < 0.1:
            return "Min load"
        if abs(p_kw - cfg.ELEC_P_NOM_KW) < 0.2:
            return "Nominal"
        if abs(p_kw - cfg.ELEC_P_MAX_KW) < 0.1:
            return "Peak load"
        return f"{p_kw:.2f} kW"


# =============================================================================
# Smoke-test
# =============================================================================

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from config import Config, validate_config
    validate_config()

    opt = EconomicOptimizer(Config)

    print("=" * 60)
    print("  optimizer.py v4.1 — Economic Operating Point Optimiser")
    print("=" * 60)

    # ── Scenario 1: Renewable power (10 kW available) ─────────────────
    print("\n[1] Renewable power — 10 kW available, H₂ = €6/kg")
    r1 = opt.find_optimal_operating_point(
        available_power_kw=10.0, source="renewable", h2_price_eur_kg=6.0)

    print(f"  Best LCOH point  : {r1.best_lcoh_point.elec_power_kw:.2f} kW → "
          f"€{r1.best_lcoh_point.lcoh_eur_kg:.3f}/kg  "
          f"η={r1.best_lcoh_point.efficiency_pct:.1f}%")
    print(f"  Best profit point: {r1.best_profit_point.elec_power_kw:.2f} kW → "
          f"€{r1.best_profit_point.net_profit_eur:,.0f}/yr")
    print(f"  Recommendation   : {r1.recommendation}")
    print(f"  Reason           : {r1.reason}")

    # Table of every 10th point
    print(f"\n  {'Load (kW)':<10} {'H₂ (g/h)':<12} {'η%':<8} {'LCOH':<10} {'Net profit/yr'}")
    for p in r1.all_points[::10]:
        print(f"  {p.elec_power_kw:<10.2f} {p.h2_rate_kg_h*1000:<12.1f} "
              f"{p.efficiency_pct:<8.1f} €{p.lcoh_eur_kg:<9.3f} €{p.net_profit_eur:,.0f}")

    # ── Scenario 2: Grid power ─────────────────────────────────────────
    print("\n[2] Grid power — full range, H₂ = €6/kg")
    r2 = opt.find_optimal_operating_point(
        available_power_kw=Config.ELEC_P_MAX_KW,
        source="grid", h2_price_eur_kg=6.0)
    print(f"  Best LCOH   : €{r2.best_lcoh_point.lcoh_eur_kg:.3f}/kg "
          f"at {r2.best_lcoh_point.elec_power_kw:.2f} kW")
    print(f"  LCOH target : €{Config.LCOH_TARGET_EURO_KG}/kg")
    print(f"  Recommendation: {r2.recommendation}")

    # ── Scenario 3: Insufficient power ────────────────────────────────
    print("\n[3] Insufficient power (0.5 kW)")
    r3 = opt.find_optimal_operating_point(
        available_power_kw=0.5, source="renewable")
    assert not r3.all_points, "Expected empty points list"
    print(f"  Result: {r3.recommendation} ✅")

    # ── Sensitivity analysis ───────────────────────────────────────────
    print("\n[4] Sensitivity analysis")
    sens = opt.annual_sensitivity(
        h2_prices=[4.0, 6.0, 8.0],
        pv_scales=[1.0, 2.0],
    )
    print(f"  {'PV ×':<6} {'H₂ €/kg':<10} {'LCOH':<10} "
          f"{'H₂ kg/yr':<12} {'Net profit':<14} Profitable")
    for s in sens:
        print(f"  {s['pv_scale']:<6.1f} €{s['h2_price']:<9.1f} "
              f"€{s['best_lcoh']:<9.3f} {s['annual_h2']:<12.1f} "
              f"€{s['net_profit']:<13,.0f} "
              f"{'✅' if s['profitable'] else '❌'}")

    # ── Assertions ─────────────────────────────────────────────────────
    assert len(r1.all_points) > 0,         "Expected non-empty sweep"
    assert r1.best_lcoh_point.lcoh_eur_kg > 0, "LCOH must be positive"
    assert r1.best_profit_point.annual_h2_kg > 0, "Annual H₂ must be positive"
    assert len(sens) == 6,                 "Expected 3 prices × 2 scales = 6"
    print("\n✅ optimizer.py v4.1 — all tests passed")
