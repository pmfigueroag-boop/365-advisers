"""
src/engines/portfolio/signal_portfolio_bridge.py
--------------------------------------------------------------------------
Signal → Portfolio Bridge — connects the signal validation stack to the
portfolio optimisation engine.

Flow
~~~~
1. Receives validated backtest data: events, attribution, walk-forward,
   perturbation, and top-bottom reports
2. Filters out signals flagged by the governor
3. Computes per-ticker expected returns from weighted signal excess returns
4. Estimates covariance matrix from historical excess returns
5. Feeds `expected_returns` + `covariance` into
   `PortfolioOptimisationEngine.optimise()`
6. Returns optimised portfolio weights with metadata

This is the missing link that converts "this signal has IC=0.08" into
"put 8.3% in AAPL and 3.1% in MSFT."
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent
from src.engines.backtesting.signal_attribution import AttributionReport
from src.engines.backtesting.perturbation_validator import PerturbationReport
from src.engines.backtesting.top_bottom_validator import TopBottomReport
from src.engines.portfolio.transaction_costs import (
    TransactionCostModel,
    CostModelConfig,
)
from src.engines.portfolio_optimisation.models import (
    OptimisationObjective,
    OptimisationResult,
    PortfolioConstraints,
)
from src.engines.portfolio_optimisation.engine import PortfolioOptimisationEngine
from src.engines.portfolio_optimisation.covariance_shrinkage import LedoitWolfShrinkage

logger = logging.getLogger("365advisers.portfolio.bridge")


# ── Contracts ────────────────────────────────────────────────────────────────

class SignalQuality(BaseModel):
    """Quality assessment for a single signal produced by the bridge."""
    signal_id: str
    ic: float = 0.0
    contribution_score: float = 0.0
    perturbation_sensitivity: float | None = None
    monotonicity_score: float | None = None
    spread: float | None = None
    is_usable: bool = True
    reject_reason: str = ""


class TickerExpectedReturn(BaseModel):
    """Expected return for a ticker derived from weighted signal data."""
    ticker: str
    expected_return: float = 0.0
    n_signals: int = 0
    n_events: int = 0
    source_signals: list[str] = Field(default_factory=list)


class BridgeResult(BaseModel):
    """Full output of the signal-to-portfolio bridge."""
    # Per-ticker
    ticker_returns: list[TickerExpectedReturn] = Field(default_factory=list)

    # Optimisation result (from PortfolioOptimisationEngine)
    optimisation: OptimisationResult | None = None

    # Metadata
    total_signals_evaluated: int = 0
    usable_signals: int = 0
    rejected_signals: int = 0
    tickers_in_portfolio: int = 0
    total_cost_drag: float = Field(
        0.0, description="Estimated annual transaction cost drag (%)",
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

_REF_WINDOW = 20


class SignalPortfolioBridge:
    """
    Bridge from signal validation stack to portfolio optimisation.

    Usage::

        bridge = SignalPortfolioBridge()
        result = bridge.construct(
            events=backtest_events,
            attribution=attribution_report,
            perturbation=perturbation_report,
            top_bottom=top_bottom_report,
        )
        print(result.optimisation.optimal_weights)
    """

    def __init__(
        self,
        objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE,
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.05,
        cost_config: CostModelConfig | None = None,
        min_ic: float = 0.0,
        max_sensitivity: float = 0.50,
        min_monotonicity: float = -1.0,
        use_shrinkage: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        objective : OptimisationObjective
            Optimisation target (MAX_SHARPE, MIN_VARIANCE, etc.)
        constraints : PortfolioConstraints | None
            Box/group constraints for the optimizer.
        risk_free_rate : float
            Annualized risk-free rate.
        cost_config : CostModelConfig | None
            Transaction cost model configuration.
        min_ic : float
            Minimum IC for a signal to be usable.
        max_sensitivity : float
            Maximum perturbation sensitivity allowed.
        min_monotonicity : float
            Minimum monotonicity score allowed.
        """
        self.objective = objective
        self.constraints = constraints or PortfolioConstraints(
            min_weight=0.0,
            max_weight=0.15,
            long_only=True,
        )
        self.risk_free_rate = risk_free_rate
        self.cost_model = TransactionCostModel(cost_config or CostModelConfig())
        self.min_ic = min_ic
        self.max_sensitivity = max_sensitivity
        self.min_monotonicity = min_monotonicity
        self.use_shrinkage = use_shrinkage

    def construct(
        self,
        events: list[SignalEvent],
        attribution: AttributionReport | None = None,
        perturbation: PerturbationReport | None = None,
        top_bottom: TopBottomReport | None = None,
    ) -> BridgeResult:
        """
        Full pipeline: events → quality filter → expected returns → optimise.
        """
        if not events:
            return BridgeResult()

        # Step 1: Assess signal quality
        quality_map = self._assess_signals(attribution, perturbation, top_bottom)

        # Step 2: Filter usable signals
        usable_ids = {
            sq.signal_id for sq in quality_map.values() if sq.is_usable
        }
        rejected = len(quality_map) - len(usable_ids)

        # Step 3: Compute per-ticker expected returns
        ticker_returns = self._compute_ticker_returns(events, usable_ids, quality_map)

        if not ticker_returns:
            return BridgeResult(
                total_signals_evaluated=len(quality_map),
                usable_signals=len(usable_ids),
                rejected_signals=rejected,
            )

        # Step 4: Estimate covariance matrix
        tickers = sorted(ticker_returns.keys())
        expected = {t: ticker_returns[t].expected_return for t in tickers}
        covariance = self._estimate_covariance(events, tickers, usable_ids)

        # Apply Ledoit-Wolf shrinkage if enabled
        if self.use_shrinkage and len(tickers) >= 2:
            n_obs = sum(len([e for e in events if e.ticker == t and e.signal_id in usable_ids]) for t in tickers) // len(tickers)
            shrinkage_result = LedoitWolfShrinkage.shrink(
                covariance, n_observations=max(n_obs, 2),
            )
            covariance = shrinkage_result.shrunk_covariance

        # Step 5: Optimise
        try:
            opt_result = PortfolioOptimisationEngine.optimise(
                expected_returns=expected,
                covariance=covariance,
                objective=self.objective,
                constraints=self.constraints,
                risk_free_rate=self.risk_free_rate,
            )
        except Exception as e:
            logger.error("BRIDGE: Optimisation failed: %s", e)
            opt_result = None

        # Step 6: Compute transaction cost drag
        cost_drag = 0.0
        if opt_result:
            cost_drag = self.cost_model.annual_cost_drag(
                opt_result.optimal_weights, rebalance_freq=12,
            )

        ticker_list = [ticker_returns[t] for t in tickers]

        result = BridgeResult(
            ticker_returns=ticker_list,
            optimisation=opt_result,
            total_signals_evaluated=len(quality_map),
            usable_signals=len(usable_ids),
            rejected_signals=rejected,
            tickers_in_portfolio=len(tickers),
            total_cost_drag=round(cost_drag, 4),
        )

        logger.info(
            "BRIDGE: %d signals → %d usable → %d tickers → optimised "
            "(objective=%s, cost_drag=%.2f%%)",
            len(quality_map), len(usable_ids), len(tickers),
            self.objective.value, cost_drag * 100,
        )

        return result

    # ── Internal ─────────────────────────────────────────────────────────

    def _assess_signals(
        self,
        attribution: AttributionReport | None,
        perturbation: PerturbationReport | None,
        top_bottom: TopBottomReport | None,
    ) -> dict[str, SignalQuality]:
        """Merge all validation data into signal quality assessments."""
        quality: dict[str, SignalQuality] = {}

        # Attribution data (IC, contribution)
        if attribution:
            for sc in attribution.signal_contributions:
                sq = SignalQuality(
                    signal_id=sc.signal_id,
                    ic=sc.ic,
                    contribution_score=sc.marginal_contribution,
                )
                # Gate: negative contribution (dilutive signal)
                if sc.is_dilutive:
                    sq.is_usable = False
                    sq.reject_reason = f"Negative alpha contribution: {sc.marginal_contribution:+.4f}"
                # Gate: IC too low
                elif sc.ic < self.min_ic:
                    sq.is_usable = False
                    sq.reject_reason = f"IC below minimum: {sc.ic:.4f} < {self.min_ic:.4f}"

                quality[sc.signal_id] = sq

        # Perturbation data
        if perturbation:
            for pr in perturbation.signal_results:
                sq = quality.get(pr.signal_id, SignalQuality(signal_id=pr.signal_id))
                sq.perturbation_sensitivity = pr.perturbation_sensitivity

                if pr.perturbation_sensitivity > self.max_sensitivity and sq.is_usable:
                    sq.is_usable = False
                    sq.reject_reason = (
                        f"Fragile: sensitivity={pr.perturbation_sensitivity:.2f} "
                        f"> {self.max_sensitivity:.2f}"
                    )
                quality[pr.signal_id] = sq

        # Top-Bottom data
        if top_bottom:
            for tb in top_bottom.signal_results:
                sq = quality.get(tb.signal_id, SignalQuality(signal_id=tb.signal_id))
                sq.monotonicity_score = tb.monotonicity_score
                sq.spread = tb.spread

                if tb.monotonicity_score < self.min_monotonicity and sq.is_usable:
                    sq.is_usable = False
                    sq.reject_reason = (
                        f"Non-monotonic: score={tb.monotonicity_score:.2f} "
                        f"< {self.min_monotonicity:.2f}"
                    )
                if tb.has_negative_spread and tb.is_significant and sq.is_usable:
                    sq.is_usable = False
                    sq.reject_reason = (
                        f"Inverse signal: spread={tb.spread:.4f}, "
                        f"t-stat={tb.spread_t_stat:.2f}"
                    )
                quality[tb.signal_id] = sq

        return quality

    def _compute_ticker_returns(
        self,
        events: list[SignalEvent],
        usable_ids: set[str],
        quality_map: dict[str, SignalQuality],
    ) -> dict[str, TickerExpectedReturn]:
        """Compute expected return per ticker from usable signal events."""
        # Group events by (ticker, signal_id)
        ticker_signal_returns: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list),
        )

        for e in events:
            if e.signal_id not in usable_ids:
                continue
            if _REF_WINDOW not in e.excess_returns:
                continue
            ticker_signal_returns[e.ticker][e.signal_id].append(
                e.excess_returns[_REF_WINDOW],
            )

        # Weighted aggregation
        results: dict[str, TickerExpectedReturn] = {}

        for ticker in sorted(ticker_signal_returns.keys()):
            sig_data = ticker_signal_returns[ticker]
            weighted_return = 0.0
            total_weight = 0.0
            n_events = 0
            signals_used = []

            for sig_id, returns in sig_data.items():
                sq = quality_map.get(sig_id)
                # Weight by IC (higher IC → more influence)
                weight = max(abs(sq.ic), 0.01) if sq else 0.01
                avg_ret = sum(returns) / len(returns)

                weighted_return += avg_ret * weight
                total_weight += weight
                n_events += len(returns)
                signals_used.append(sig_id)

            if total_weight > 0:
                expected = weighted_return / total_weight
                # Annualize: excess return per 20-day window → ~12.6 windows/year
                annualized = expected * (252 / _REF_WINDOW)

                results[ticker] = TickerExpectedReturn(
                    ticker=ticker,
                    expected_return=round(annualized, 6),
                    n_signals=len(signals_used),
                    n_events=n_events,
                    source_signals=signals_used,
                )

        return results

    def _estimate_covariance(
        self,
        events: list[SignalEvent],
        tickers: list[str],
        usable_ids: set[str],
    ) -> list[list[float]]:
        """Estimate covariance matrix from event excess returns."""
        # Collect per-ticker returns
        ticker_returns: dict[str, list[float]] = {t: [] for t in tickers}

        for e in events:
            if e.signal_id not in usable_ids:
                continue
            if e.ticker in ticker_returns and _REF_WINDOW in e.excess_returns:
                ticker_returns[e.ticker].append(e.excess_returns[_REF_WINDOW])

        n = len(tickers)
        cov = [[0.0] * n for _ in range(n)]

        for i in range(n):
            ri = ticker_returns[tickers[i]]
            if not ri:
                cov[i][i] = 0.04  # Default 20% annual vol → 0.04 variance
                continue
            mean_i = sum(ri) / len(ri)
            var_i = sum((r - mean_i) ** 2 for r in ri) / max(len(ri) - 1, 1)

            # Annualize
            ann_var_i = var_i * (252 / _REF_WINDOW)
            cov[i][i] = ann_var_i

            for j in range(i + 1, n):
                rj = ticker_returns[tickers[j]]
                if not rj:
                    continue
                # Simple covariance estimate
                min_len = min(len(ri), len(rj))
                if min_len < 5:
                    continue
                mean_j = sum(rj[:min_len]) / min_len
                mean_i_adj = sum(ri[:min_len]) / min_len
                cov_ij = sum(
                    (ri[k] - mean_i_adj) * (rj[k] - mean_j)
                    for k in range(min_len)
                ) / max(min_len - 1, 1)

                ann_cov_ij = cov_ij * (252 / _REF_WINDOW)
                cov[i][j] = ann_cov_ij
                cov[j][i] = ann_cov_ij

        return cov
