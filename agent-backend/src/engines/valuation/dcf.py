"""
src/engines/valuation/dcf.py
──────────────────────────────────────────────────────────────────────────────
Multi-stage Discounted Cash Flow (DCF) Model.

Three stages:
  Stage 1: High-growth period (explicit projections, default 5 years)
  Stage 2: Fade-to-terminal (linear decay from Stage 1 to terminal, default 3 years)
  Terminal: Gordon Growth Model (perpetuity value)

All cash flows are discounted at WACC to compute enterprise value.
"""

from __future__ import annotations

import logging

from src.engines.valuation.models import (
    DCFInput,
    DCFResult,
    CashFlowProjection,
    SensitivityCell,
)

logger = logging.getLogger("365advisers.valuation.dcf")


class DCFModel:
    """
    Multi-stage DCF valuation model.

    Usage:
        result = DCFModel.calculate(DCFInput(
            current_fcf=5000, wacc=0.10, shares_outstanding=1000, ...
        ))
    """

    @classmethod
    def calculate(cls, inputs: DCFInput) -> DCFResult:
        """Run a full DCF valuation with sensitivity table."""
        return cls._calculate_core(inputs, build_sensitivity=True)

    @classmethod
    def _calculate_core(
        cls,
        inputs: DCFInput,
        build_sensitivity: bool = False,
    ) -> DCFResult:
        """Core DCF logic (shared between main calc and sensitivity cells)."""
        projections: list[CashFlowProjection] = []
        fcf = inputs.current_fcf
        total_years = inputs.stage1_years + inputs.stage2_years

        # ── Stage 1: High growth ─────────────────────────────────────────
        for year in range(1, inputs.stage1_years + 1):
            fcf = fcf * (1 + inputs.growth_rate_stage1)
            df = 1 / (1 + inputs.wacc) ** year
            pv = fcf * df
            projections.append(CashFlowProjection(
                year=year, stage="stage1",
                growth_rate=inputs.growth_rate_stage1,
                fcf=round(fcf, 2), discount_factor=round(df, 6),
                present_value=round(pv, 2),
            ))

        # ── Stage 2: Fade to terminal ────────────────────────────────────
        if inputs.stage2_years > 0:
            g_start = inputs.growth_rate_stage1
            g_end = inputs.terminal_growth_rate
            for i in range(inputs.stage2_years):
                year = inputs.stage1_years + i + 1
                t = (i + 1) / (inputs.stage2_years + 1)
                g = g_start + t * (g_end - g_start)
                fcf = fcf * (1 + g)
                df = 1 / (1 + inputs.wacc) ** year
                pv = fcf * df
                projections.append(CashFlowProjection(
                    year=year, stage="stage2",
                    growth_rate=round(g, 4), fcf=round(fcf, 2),
                    discount_factor=round(df, 6), present_value=round(pv, 2),
                ))

        # ── Terminal Value (Gordon Growth Model) ─────────────────────────
        terminal_fcf = fcf * (1 + inputs.terminal_growth_rate)
        denom = inputs.wacc - inputs.terminal_growth_rate
        if denom <= 0:
            logger.warning("WACC ≤ terminal growth — using 1%% spread")
            denom = 0.01

        terminal_value = terminal_fcf / denom
        df_terminal = 1 / (1 + inputs.wacc) ** total_years
        pv_terminal = terminal_value * df_terminal

        # ── Aggregation ──────────────────────────────────────────────────
        sum_pv = sum(p.present_value for p in projections)
        ev = sum_pv + pv_terminal
        equity = ev - inputs.net_debt
        fv_per_share = equity / inputs.shares_outstanding

        # Sensitivity
        sensitivity = cls._build_sensitivity_table(inputs) if build_sensitivity else []

        return DCFResult(
            ticker=inputs.ticker, projections=projections,
            sum_pv_fcf=round(sum_pv, 2),
            terminal_value=round(terminal_value, 2),
            pv_terminal_value=round(pv_terminal, 2),
            enterprise_value=round(ev, 2),
            equity_value=round(equity, 2),
            fair_value_per_share=round(fv_per_share, 2),
            sensitivity=sensitivity, inputs_used=inputs,
        )

    @classmethod
    def _build_sensitivity_table(cls, inputs: DCFInput) -> list[SensitivityCell]:
        """Build WACC ±2% × terminal growth ±1% sensitivity table."""
        cells: list[SensitivityCell] = []
        wacc_range = [inputs.wacc + d for d in [-0.02, -0.01, 0, 0.01, 0.02]]
        tg_range = [inputs.terminal_growth_rate + d for d in [-0.01, -0.005, 0, 0.005, 0.01]]

        for wacc in wacc_range:
            if wacc <= 0.01:
                continue
            for tg in tg_range:
                if tg < 0 or tg >= wacc:
                    continue
                modified = inputs.model_copy(update={"wacc": wacc, "terminal_growth_rate": tg})
                result = cls._calculate_core(modified, build_sensitivity=False)
                cells.append(SensitivityCell(
                    wacc=round(wacc, 4),
                    terminal_growth=round(tg, 4),
                    fair_value=result.fair_value_per_share,
                ))
        return cells
