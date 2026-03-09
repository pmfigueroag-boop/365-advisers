"""
src/engines/autonomous_pm/allocation_engine.py
──────────────────────────────────────────────────────────────────────────────
Asset Allocation Engine — determines optimal portfolio weights using
multiple quantitative methods adjusted by regime context.

Integrates PortfolioOptimisationEngine (Markowitz MVO) for numerical
optimisation.  Supports: risk parity, volatility targeting, factor
diversification, equal risk contribution, max Sharpe, min variance.
"""

from __future__ import annotations

import logging
import math

from src.engines.autonomous_pm.models import (
    AllocationMethodAPM,
    APMPortfolio,
    APMPosition,
)

logger = logging.getLogger("365advisers.apm.allocation")

# ── Regime weight adjustments ────────────────────────────────────────────────

_REGIME_VOL_TARGET: dict[str, float] = {
    "expansion": 0.16,
    "slowdown": 0.12,
    "recession": 0.08,
    "recovery": 0.14,
    "high_volatility": 0.06,
    "liquidity_expansion": 0.18,
}

_REGIME_DEFENSIVE_TILT: dict[str, float] = {
    "expansion": 0.0,
    "slowdown": 0.10,
    "recession": 0.25,
    "recovery": 0.05,
    "high_volatility": 0.20,
    "liquidity_expansion": 0.0,
}


class AllocationEngine:
    """
    Determines optimal asset weights using quantitative allocation methods.

    Usage::

        engine = AllocationEngine()
        portfolio = engine.optimise(
            portfolio=constructed_portfolio,
            asset_volatilities={"AAPL": 0.22, "MSFT": 0.18},
            correlations=correlation_matrix,
            regime="expansion",
        )
    """

    def optimise(
        self,
        portfolio: APMPortfolio,
        asset_volatilities: dict[str, float] | None = None,
        correlations: dict[str, dict[str, float]] | None = None,
        regime: str = "expansion",
        method: AllocationMethodAPM | None = None,
    ) -> APMPortfolio:
        """
        Re-weight portfolio positions using the specified allocation method.

        Parameters
        ----------
        portfolio : APMPortfolio
            Portfolio with initial positions from the Construction Engine.
        asset_volatilities : dict | None
            Annualized volatilities per ticker.
        correlations : dict | None
            Pairwise correlations {t1: {t2: corr, ...}, ...}.
        regime : str
            Current market regime.
        method : AllocationMethodAPM | None
            Override the portfolio's default method.
        """
        if not portfolio.positions:
            return portfolio

        alloc_method = method or portfolio.allocation_method
        vols = asset_volatilities or {}
        corr = correlations or {}

        # Ensure all tickers have a volatility estimate
        for pos in portfolio.positions:
            if pos.ticker not in vols:
                vols[pos.ticker] = 0.15 + (100 - pos.alpha_score) * 0.002  # proxy

        dispatch = {
            AllocationMethodAPM.RISK_PARITY: self._risk_parity,
            AllocationMethodAPM.VOLATILITY_TARGETING: self._volatility_targeting,
            AllocationMethodAPM.FACTOR_DIVERSIFICATION: self._factor_diversification,
            AllocationMethodAPM.EQUAL_RISK_CONTRIBUTION: self._equal_risk_contribution,
            AllocationMethodAPM.MAX_SHARPE: self._max_sharpe_proxy,
            AllocationMethodAPM.MIN_VARIANCE: self._min_variance,
        }

        allocator = dispatch.get(alloc_method, self._risk_parity)
        weights = allocator(portfolio.positions, vols, corr, regime)

        # Apply regime defensive tilt
        defensive_tilt = _REGIME_DEFENSIVE_TILT.get(regime, 0.0)
        if defensive_tilt > 0:
            weights = self._apply_defensive_tilt(weights, portfolio.positions, defensive_tilt)

        # Cap single position at 25%, normalize
        weights = self._cap_and_normalize(weights)

        # Update positions
        for pos in portfolio.positions:
            pos.weight = round(weights.get(pos.ticker, pos.weight), 4)

        portfolio.allocation_method = alloc_method
        portfolio.total_weight = round(sum(pos.weight for pos in portfolio.positions), 4)

        # Estimate portfolio volatility
        portfolio.expected_volatility = self._estimate_portfolio_vol(
            portfolio.positions, vols, corr,
        )

        return portfolio

    # ── Allocation Methods ───────────────────────────────────────────────

    def _risk_parity(
        self, positions: list[APMPosition], vols: dict, corr: dict, regime: str,
    ) -> dict[str, float]:
        """Inverse-volatility weighting."""
        inv_vols = {p.ticker: 1.0 / max(vols.get(p.ticker, 0.15), 0.01) for p in positions}
        total = sum(inv_vols.values())
        return {t: v / total for t, v in inv_vols.items()}

    def _volatility_targeting(
        self, positions: list[APMPosition], vols: dict, corr: dict, regime: str,
    ) -> dict[str, float]:
        """Target a regime-specific portfolio volatility."""
        target_vol = _REGIME_VOL_TARGET.get(regime, 0.14)
        weights: dict[str, float] = {}
        for p in positions:
            asset_vol = max(vols.get(p.ticker, 0.15), 0.01)
            # Scale weight inversely with vol, proportional to target
            raw = target_vol / asset_vol
            weights[p.ticker] = raw
        total = sum(weights.values()) or 1.0
        return {t: w / total for t, w in weights.items()}

    def _factor_diversification(
        self, positions: list[APMPosition], vols: dict, corr: dict, regime: str,
    ) -> dict[str, float]:
        """Weight to maximise factor diversity across positions."""
        weights: dict[str, float] = {}
        for p in positions:
            exposures = p.factor_exposures
            diversity_score = len(exposures) + sum(exposures.values())
            alpha_boost = p.alpha_score / 100
            weights[p.ticker] = diversity_score * alpha_boost + 0.1  # floor
        total = sum(weights.values()) or 1.0
        return {t: w / total for t, w in weights.items()}

    def _equal_risk_contribution(
        self, positions: list[APMPosition], vols: dict, corr: dict, regime: str,
    ) -> dict[str, float]:
        """Each asset contributes equally to portfolio risk (simplified)."""
        risk_budget = 1.0 / max(len(positions), 1)
        weights: dict[str, float] = {}
        for p in positions:
            asset_vol = max(vols.get(p.ticker, 0.15), 0.01)
            weights[p.ticker] = risk_budget / asset_vol
        total = sum(weights.values()) or 1.0
        return {t: w / total for t, w in weights.items()}

    def _max_sharpe_proxy(
        self, positions: list[APMPosition], vols: dict, corr: dict, regime: str,
    ) -> dict[str, float]:
        """Proxy max-Sharpe: weight proportional to alpha/vol ratio."""
        weights: dict[str, float] = {}
        for p in positions:
            asset_vol = max(vols.get(p.ticker, 0.15), 0.01)
            sharpe_proxy = p.alpha_score / (asset_vol * 100)
            weights[p.ticker] = max(sharpe_proxy, 0.01)
        total = sum(weights.values()) or 1.0
        return {t: w / total for t, w in weights.items()}

    def _min_variance(
        self, positions: list[APMPosition], vols: dict, corr: dict, regime: str,
    ) -> dict[str, float]:
        """Minimum variance: weight inversely proportional to vol squared."""
        weights: dict[str, float] = {}
        for p in positions:
            asset_vol = max(vols.get(p.ticker, 0.15), 0.01)
            weights[p.ticker] = 1.0 / (asset_vol ** 2)
        total = sum(weights.values()) or 1.0
        return {t: w / total for t, w in weights.items()}

    # ── Adjustments ──────────────────────────────────────────────────────

    @staticmethod
    def _apply_defensive_tilt(
        weights: dict[str, float],
        positions: list[APMPosition],
        tilt: float,
    ) -> dict[str, float]:
        """Shift weight toward lower-volatility positions in adverse regimes."""
        defensive_sectors = {"Healthcare", "Utilities", "Consumer Staples"}
        adjusted: dict[str, float] = {}
        for p in positions:
            w = weights.get(p.ticker, 0)
            if p.sector in defensive_sectors:
                w *= (1 + tilt)
            else:
                w *= (1 - tilt * 0.5)
            adjusted[p.ticker] = max(w, 0.0)
        total = sum(adjusted.values()) or 1.0
        return {t: v / total for t, v in adjusted.items()}

    @staticmethod
    def _cap_and_normalize(weights: dict[str, float], cap: float = 0.25) -> dict[str, float]:
        for t in weights:
            weights[t] = min(weights[t], cap)
        total = sum(weights.values()) or 1.0
        return {t: round(w / total, 6) for t, w in weights.items()}

    @staticmethod
    def _estimate_portfolio_vol(
        positions: list[APMPosition],
        vols: dict[str, float],
        corr: dict[str, dict[str, float]],
    ) -> float:
        """Simplified portfolio volatility estimate."""
        # Sum of weighted variances (ignoring covariance if corr not provided)
        weighted_var = 0.0
        for p in positions:
            v = vols.get(p.ticker, 0.15)
            weighted_var += (p.weight * v) ** 2
        # Add cross-terms with correlation if available
        for i, p1 in enumerate(positions):
            for p2 in positions[i + 1:]:
                c = corr.get(p1.ticker, {}).get(p2.ticker, 0.3)  # default 0.3
                v1 = vols.get(p1.ticker, 0.15)
                v2 = vols.get(p2.ticker, 0.15)
                weighted_var += 2 * p1.weight * p2.weight * v1 * v2 * c
        return round(math.sqrt(max(weighted_var, 0)), 4)
