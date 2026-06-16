# =============================================================================
# optimizer.py — LUMINIH2 Economic Operating Point Optimiser
# Best electrolyzer load for minimum LCOH or maximum profit
# Version: 4.2
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


@dataclass
class FullLCOHResult:
    """
    Investment-grade LCOH breakdown including CAPEX amortisation.

    The operating LCOH (from OptPoint) only covers energy + stack costs.
    The full LCOH adds annualised CAPEX spread over the project lifetime,
    discounted at the weighted average cost of capital (WACC).

    This is the number that appears in project finance term sheets and
    investor presentations — it reflects the true cost of green hydrogen
    including the initial investment.

    Formula:
        CRF = WACC × (1+WACC)^n / ((1+WACC)^n - 1)
        Annualised CAPEX = CAPEX × CRF
        Full LCOH = (Annualised CAPEX + Annual OPEX + Annual energy cost)
                    / Annual H₂ production
    """
    # Inputs
    elec_power_kw:       float   # Optimal electrolyzer setpoint [kW]
    capex_eur:           float   # Total capital expenditure [€]
    wacc_pct:            float   # Weighted average cost of capital [%]
    lifetime_years:      int     # Project lifetime [years]
    annual_h2_kg:        float   # Annual H₂ production [kg/yr]
    opex_annual_eur:     float   # Annual O&M cost [€/yr]

    # Capital recovery
    crf:                 float   # Capital recovery factor [dimensionless]
    capex_annualised:    float   # Annualised CAPEX [€/yr]

    # Cost breakdown [€/kg H₂]
    capex_lcoh:          float   # CAPEX contribution to LCOH [€/kg]
    opex_lcoh:           float   # OPEX contribution to LCOH [€/kg]
    energy_lcoh:         float   # Energy + stack contribution to LCOH [€/kg]
    full_lcoh_eur_kg:    float   # Total full LCOH [€/kg]

    # Economics
    operating_lcoh:      float   # Operating LCOH only (no CAPEX) [€/kg]
    h2_price_eur_kg:     float   # H₂ market price used [€/kg]
    annual_revenue_eur:  float   # Gross annual revenue [€/yr]
    annual_total_cost:   float   # Full annual cost (CAPEX+OPEX+energy) [€/yr]
    net_profit_eur:      float   # Annual net profit [€/yr]
    payback_years:       float   # Simple payback period [years]
    npv_eur:             float   # Net present value over lifetime [€]
    irr_pct:             float   # Internal rate of return [%]
    lcoe_eur_kwh:        float   # Levelised cost of electricity input [€/kWh]

    # Breakeven
    breakeven_h2_price:  float   # H₂ price needed to break even [€/kg]
    target_met:          bool    # True if full_lcoh ≤ LCOH target


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
    # Investment-grade full LCOH (CAPEX + WACC + lifetime)
    # ------------------------------------------------------------------

    def full_lcoh(
        self,
        capex_eur:        float = 250_000.0,
        wacc_pct:         float = 6.0,
        lifetime_years:   int   = 20,
        opex_annual_eur:  float = 8_000.0,
        h2_price_eur_kg:  float = 6.0,
        residual_pct:     float = 0.10,
        available_power_kw: float = 10.0,
        source:           str   = "renewable",
    ) -> FullLCOHResult:
        """
        Compute investment-grade LCOH including CAPEX amortisation.

        This is the bankable LCOH figure required for:
            - Project finance applications
            - EU Hydrogen Bank grant applications
            - Investor presentations
            - Policy LCOH benchmarking vs €4.5/kg EU target

        The operating LCOH (from find_optimal_operating_point) only covers
        energy and stack replacement costs. This method adds:
            - Annualised CAPEX via capital recovery factor (CRF)
            - Annual OPEX
            - Residual value of equipment at end of lifetime

        Args:
            capex_eur        : total capital expenditure [€]
                               (equipment + installation + grid connection)
            wacc_pct         : weighted average cost of capital [%]
                               (typical range: 4–10% for green H₂ projects)
            lifetime_years   : project economic lifetime [years]
                               (typical: 15–25 years for PEM systems)
            opex_annual_eur  : annual operations & maintenance cost [€/yr]
                               (typically 2–4% of CAPEX)
            h2_price_eur_kg  : H₂ market sell price [€/kg]
            residual_pct     : residual value of equipment at lifetime end
                               as fraction of CAPEX (typical 0.10 = 10%)
            available_power_kw : renewable power available for electrolyzer
            source           : "renewable" or "grid"

        Returns:
            FullLCOHResult with complete cost breakdown and investment metrics
        """
        cfg  = self.cfg
        wacc = wacc_pct / 100.0

        # ── Find optimal operating point ──────────────────────────────
        opt_res = self.find_optimal_operating_point(
            available_power_kw=available_power_kw,
            h2_price_eur_kg=h2_price_eur_kg,
            source=source,
        )
        best = opt_res.best_lcoh_point

        if not opt_res.all_points:
            # Not enough power — return zero result
            return FullLCOHResult(
                elec_power_kw=0, capex_eur=capex_eur, wacc_pct=wacc_pct,
                lifetime_years=lifetime_years, annual_h2_kg=0,
                opex_annual_eur=opex_annual_eur, crf=0,
                capex_annualised=capex_eur, capex_lcoh=999,
                opex_lcoh=999, energy_lcoh=999, full_lcoh_eur_kg=999,
                operating_lcoh=999, h2_price_eur_kg=h2_price_eur_kg,
                annual_revenue_eur=0, annual_total_cost=capex_eur,
                net_profit_eur=-capex_eur, payback_years=99,
                npv_eur=-capex_eur, irr_pct=-100, lcoe_eur_kwh=999,
                breakeven_h2_price=999, target_met=False,
            )

        annual_h2    = best.annual_h2_kg
        annual_energy_cost = best.annual_cost_eur

        # ── Capital recovery factor (annuity formula) ─────────────────
        # CRF converts a lump-sum CAPEX into equivalent annual payments
        # CRF = r(1+r)^n / ((1+r)^n - 1)
        if wacc > 0:
            crf = (wacc * (1 + wacc) ** lifetime_years /
                   ((1 + wacc) ** lifetime_years - 1))
        else:
            crf = 1.0 / lifetime_years   # zero WACC → straight-line

        # Residual value reduces effective CAPEX
        residual_pv   = residual_pct * capex_eur / (1 + wacc) ** lifetime_years
        net_capex     = capex_eur - residual_pv
        capex_annual  = net_capex * crf   # [€/yr]

        # ── Full annual cost ──────────────────────────────────────────
        annual_total  = capex_annual + opex_annual_eur + annual_energy_cost

        # ── Full LCOH breakdown [€/kg] ────────────────────────────────
        if annual_h2 > 0:
            capex_lcoh  = capex_annual / annual_h2
            opex_lcoh   = opex_annual_eur / annual_h2
            energy_lcoh = annual_energy_cost / annual_h2
            full_lcoh   = capex_lcoh + opex_lcoh + energy_lcoh
        else:
            capex_lcoh = opex_lcoh = energy_lcoh = full_lcoh = 999.0

        # ── Revenue ───────────────────────────────────────────────────
        annual_rev = (
            annual_h2 * h2_price_eur_kg
            + annual_h2 * cfg.GREEN_H2_SUBSIDY
            + (annual_h2 * cfg.CO2_SAVED_PER_KG_H2 / 1000.0)
            * cfg.CARBON_TAX_EUR_TON
        )
        net_profit = annual_rev - annual_total

        # ── Payback ───────────────────────────────────────────────────
        # Simple payback: CAPEX / (annual_rev - opex - energy_cost)
        op_profit = annual_rev - opex_annual_eur - annual_energy_cost
        payback   = capex_eur / op_profit if op_profit > 0 else 99.0

        # ── NPV ───────────────────────────────────────────────────────
        # NPV = sum of discounted annual cash flows - CAPEX
        annual_cf = annual_rev - opex_annual_eur - annual_energy_cost
        if wacc > 0:
            npv = annual_cf * (1 - (1 + wacc) ** (-lifetime_years)) / wacc                   - capex_eur                   + residual_pv
        else:
            npv = annual_cf * lifetime_years - capex_eur + residual_pv

        # ── IRR (Newton-Raphson) ──────────────────────────────────────
        irr_pct = self._compute_irr(capex_eur, annual_cf, residual_pv,
                                     lifetime_years)

        # ── LCOE (electricity input cost) ────────────────────────────
        annual_kwh_in = best.elec_power_kw * ANNUAL_HOURS
        lcoe = annual_energy_cost / annual_kwh_in if annual_kwh_in > 0 else 0.0

        # ── Breakeven H₂ price ────────────────────────────────────────
        # What H₂ price makes net_profit = 0?
        subsidy_co2_per_kg = (cfg.GREEN_H2_SUBSIDY
                              + cfg.CO2_SAVED_PER_KG_H2
                              / 1000.0 * cfg.CARBON_TAX_EUR_TON)
        if annual_h2 > 0:
            breakeven = (annual_total / annual_h2) - subsidy_co2_per_kg
        else:
            breakeven = 999.0

        return FullLCOHResult(
            elec_power_kw=round(best.elec_power_kw, 3),
            capex_eur=capex_eur,
            wacc_pct=wacc_pct,
            lifetime_years=lifetime_years,
            annual_h2_kg=round(annual_h2, 1),
            opex_annual_eur=opex_annual_eur,
            crf=round(crf, 5),
            capex_annualised=round(capex_annual, 2),
            capex_lcoh=round(capex_lcoh, 3),
            opex_lcoh=round(opex_lcoh, 3),
            energy_lcoh=round(energy_lcoh, 3),
            full_lcoh_eur_kg=round(full_lcoh, 3),
            operating_lcoh=round(best.lcoh_eur_kg, 3),
            h2_price_eur_kg=h2_price_eur_kg,
            annual_revenue_eur=round(annual_rev, 2),
            annual_total_cost=round(annual_total, 2),
            net_profit_eur=round(net_profit, 2),
            payback_years=round(min(payback, 99.0), 1),
            npv_eur=round(npv, 2),
            irr_pct=round(irr_pct, 2),
            lcoe_eur_kwh=round(lcoe, 4),
            breakeven_h2_price=round(max(breakeven, 0.0), 3),
            target_met=full_lcoh <= cfg.LCOH_TARGET_EURO_KG,
        )

    @staticmethod
    def _compute_irr(
        capex:        float,
        annual_cf:    float,
        residual_pv:  float,
        n:            int,
        tol:          float = 1e-6,
        max_iter:     int   = 200,
    ) -> float:
        """
        Compute IRR using Newton-Raphson iteration.

        IRR is the discount rate r that makes NPV = 0:
            NPV(r) = CF × (1-(1+r)^-n)/r + residual/(1+r)^n - CAPEX = 0

        Args:
            capex      : initial capital expenditure [€]
            annual_cf  : constant annual cash flow [€/yr]
            residual_pv: present value of residual at end of life [€]
            n          : project lifetime [years]

        Returns:
            IRR as percentage [%], clamped to [-100, 100]
        """
        if annual_cf <= 0:
            return -100.0

        # Initial guess
        r = 0.10   # 10%
        for _ in range(max_iter):
            if abs(r) < 1e-10:
                r = 1e-6
            # NPV and its derivative
            factor = (1 + r) ** n
            if source_mode := abs(factor - 1) < 1e-12:
                break
            pv_annuity = annual_cf * (1 - 1 / factor) / r
            pv_resid   = residual_pv / factor
            npv_r      = pv_annuity + pv_resid - capex

            # dNPV/dr
            d_annuity  = annual_cf * (
                (1 - 1/factor) / (-r**2)
                + n / (r * factor * (1 + r))
            )
            d_resid    = -n * residual_pv / (factor * (1 + r))
            d_npv      = d_annuity + d_resid

            if abs(d_npv) < 1e-10:
                break
            r_new = r - npv_r / d_npv
            if abs(r_new - r) < tol:
                r = r_new
                break
            r = float(np.clip(r_new, -0.99, 10.0))

        return float(np.clip(r * 100, -100.0, 100.0))

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
    print("  optimizer.py v4.2 — Economic Operating Point Optimiser")
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
    # ── Full LCOH test ────────────────────────────────────────────────
    print("\n[5] Investment-grade full LCOH")
    fl = opt.full_lcoh(
        capex_eur=250_000,
        wacc_pct=6.0,
        lifetime_years=20,
        opex_annual_eur=8_000,
        h2_price_eur_kg=6.0,
        available_power_kw=10.0,
        source="renewable",
    )
    print(f"  Optimal setpoint   : {fl.elec_power_kw:.2f} kW")
    print(f"  Annual H₂          : {fl.annual_h2_kg:.1f} kg/yr")
    print(f"  CRF (WACC 6%, 20y) : {fl.crf:.5f}")
    print(f"  CAPEX annualised   : €{fl.capex_annualised:,.0f}/yr")
    print(f"  ─────────────────────────────────────")
    print(f"  CAPEX → LCOH       : €{fl.capex_lcoh:.3f}/kg")
    print(f"  OPEX  → LCOH       : €{fl.opex_lcoh:.3f}/kg")
    print(f"  Energy→ LCOH       : €{fl.energy_lcoh:.3f}/kg")
    print(f"  ─────────────────────────────────────")
    print(f"  Operating LCOH     : €{fl.operating_lcoh:.3f}/kg  (no CAPEX)")
    print(f"  FULL LCOH          : €{fl.full_lcoh_eur_kg:.3f}/kg  (investment-grade)")
    print(f"  EU target €4.5/kg  : {'✅ MET' if fl.target_met else '❌ Above target'}")
    print(f"  ─────────────────────────────────────")
    print(f"  Payback            : {fl.payback_years:.1f} yr")
    print(f"  NPV (20 yr)        : €{fl.npv_eur:,.0f}")
    print(f"  IRR                : {fl.irr_pct:.1f}%")
    print(f"  LCOE (elec input)  : €{fl.lcoe_eur_kwh:.4f}/kWh")
    print(f"  Breakeven H₂ price : €{fl.breakeven_h2_price:.3f}/kg")

    assert fl.full_lcoh_eur_kg > 0,        "Full LCOH must be positive"
    assert fl.full_lcoh_eur_kg > fl.operating_lcoh, "Full LCOH must exceed operating"
    assert fl.capex_lcoh > 0,              "CAPEX component must be positive"
    assert 0 < fl.crf < 1,                 "CRF must be between 0 and 1"
    assert fl.annual_h2_kg > 0,            "Annual H₂ must be positive"
    print("  ✅ FullLCOHResult assertions passed")

    print("\n✅ optimizer.py v4.2 — all tests passed")
