"""
src/engines/cost_model/engine.py
──────────────────────────────────────────────────────────────────────────────
Transaction Cost & Slippage Model — orchestrator.

Adjusts signal event returns for real-world market frictions:
  - Bid-ask spread (estimated via Corwin-Schultz or fixed)
  - Market impact  (Almgren-Chriss square-root model)
  - Execution slippage
  - Broker commissions

Produces cost-adjusted returns that plug transparently into the
existing metrics functions (compute_hit_rate, compute_sharpe, etc.).
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

import numpy as np
import pandas as pd

from src.engines.backtesting.metrics import (
    compute_avg_excess_return,
    compute_hit_rate,
    compute_sharpe,
)
from src.engines.backtesting.models import SignalEvent
from src.engines.cost_model.estimators import ImpactEstimator, SpreadEstimator
from src.engines.cost_model.models import (
    CostModelConfig,
    CostModelReport,
    CostResilience,
    SignalCostProfile,
    TradeCostBreakdown,
)

logger = logging.getLogger("365advisers.cost_model.engine")


def _classify_resilience(score: float) -> CostResilience:
    if score >= 0.70:
        return CostResilience.RESILIENT
    if score >= 0.40:
        return CostResilience.MODERATE
    return CostResilience.FRAGILE


def _classify_tier(sharpe: float, hit_rate: float) -> str:
    """Simplified tier after cost adjustment."""
    if sharpe >= 1.5 and hit_rate >= 0.60:
        return "A"
    if sharpe >= 0.8 and hit_rate >= 0.55:
        return "B"
    if sharpe >= 0.3 and hit_rate >= 0.50:
        return "C"
    return "D"


class CostModelEngine:
    """
    Applies transaction cost adjustments to signal events.

    Usage::

        engine = CostModelEngine()
        adjusted, breakdowns = engine.adjust_events(events, ohlcv_data)
        report = engine.build_report(events, adjusted, breakdowns, windows)
    """

    def __init__(self, config: CostModelConfig | None = None) -> None:
        self.config = config or CostModelConfig()
        self._spread_est = SpreadEstimator()
        self._impact_est = ImpactEstimator()

    # ── Public API ────────────────────────────────────────────────────────

    def adjust_events(
        self,
        events: list[SignalEvent],
        ohlcv_data: dict[str, pd.DataFrame],
        config: CostModelConfig | None = None,
    ) -> tuple[list[SignalEvent], list[TradeCostBreakdown]]:
        """
        Apply transaction cost adjustments to all events.

        Parameters
        ----------
        events : list[SignalEvent]
            Signal events with raw forward_returns already computed.
        ohlcv_data : dict[str, pd.DataFrame]
            OHLCV data keyed by ticker (for volume / volatility lookup).
        config : CostModelConfig | None
            Override config for this run.

        Returns
        -------
        tuple[list[SignalEvent], list[TradeCostBreakdown]]
            Cost-adjusted events and per-trade cost breakdowns.
        """
        cfg = config or self.config
        adjusted_events: list[SignalEvent] = []
        breakdowns: list[TradeCostBreakdown] = []

        for event in events:
            ticker_ohlcv = ohlcv_data.get(event.ticker)
            breakdown = self._compute_single_cost(event, ticker_ohlcv, cfg)
            breakdowns.append(breakdown)

            # Build adjusted event with cost-modified returns
            adj_fwd = dict(breakdown.adjusted_returns)
            adj_excess: dict[int, float] = {}
            for w, adj_ret in adj_fwd.items():
                bench_ret = event.benchmark_returns.get(w, 0.0)
                adj_excess[w] = round(adj_ret - bench_ret, 6)

            adjusted_events.append(event.model_copy(update={
                "forward_returns": adj_fwd,
                "excess_returns": adj_excess,
            }))

        logger.info(
            "COST-MODEL: Adjusted %d events (avg cost = %.1f bps)",
            len(events),
            (sum(b.total_cost for b in breakdowns) / max(len(breakdowns), 1)) * 10_000,
        )
        return adjusted_events, breakdowns

    def build_report(
        self,
        raw_events: list[SignalEvent],
        adjusted_events: list[SignalEvent],
        breakdowns: list[TradeCostBreakdown],
        windows: list[int],
        config: CostModelConfig | None = None,
    ) -> CostModelReport:
        """
        Build a full cost analysis report comparing raw vs adjusted metrics.

        Parameters
        ----------
        raw_events : list[SignalEvent]
            Original events (before cost adjustment).
        adjusted_events : list[SignalEvent]
            Events with cost-adjusted returns.
        breakdowns : list[TradeCostBreakdown]
            Per-trade cost decompositions.
        windows : list[int]
            Forward return windows (e.g. [5, 10, 20]).

        Returns
        -------
        CostModelReport
        """
        cfg = config or self.config
        profiles = self._compute_profiles(
            raw_events, adjusted_events, breakdowns, windows,
        )

        resilient = [
            p.signal_id for p in profiles
            if p.cost_resilience_class == CostResilience.RESILIENT
        ]
        fragile = [
            p.signal_id for p in profiles
            if p.cost_resilience_class == CostResilience.FRAGILE
        ]

        avg_drag = 0.0
        if profiles:
            avg_drag = sum(p.total_cost_drag_bps for p in profiles) / len(profiles)

        report = CostModelReport(
            config=cfg,
            signal_profiles=profiles,
            cost_resilient_signals=resilient,
            cost_fragile_signals=fragile,
            avg_cost_drag_bps=round(avg_drag, 2),
        )

        logger.info(
            "COST-MODEL: Report — %d signals, %d resilient, %d fragile, "
            "avg drag = %.1f bps",
            len(profiles), len(resilient), len(fragile), avg_drag,
        )
        return report

    # ── Internal ──────────────────────────────────────────────────────────

    def _compute_single_cost(
        self,
        event: SignalEvent,
        ohlcv: pd.DataFrame | None,
        cfg: CostModelConfig,
    ) -> TradeCostBreakdown:
        """Compute cost breakdown for a single event."""
        price = event.price_at_fire
        daily_vol = 0.0
        daily_volatility = 0.0
        spread_frac = cfg.fixed_spread_bps / 10_000

        if ohlcv is not None and not ohlcv.empty and price > 0:
            # Find the index closest to fired_date
            idx = self._find_date_idx(ohlcv, event.fired_date)

            if idx is not None and idx >= 1:
                # Volume at fire date
                if "Volume" in ohlcv.columns:
                    daily_vol = float(ohlcv["Volume"].values[idx])

                # Daily volatility (20-day rolling std of returns)
                start = max(0, idx - 20)
                closes = ohlcv["Close"].values[start:idx + 1]
                if len(closes) >= 2:
                    rets = np.diff(closes) / closes[:-1]
                    daily_volatility = float(np.std(rets)) if len(rets) > 0 else 0.0

                # Spread estimation
                spread_frac = self._spread_est.estimate(
                    ohlcv, idx,
                    method=cfg.spread_method.value,
                    fixed_bps=cfg.fixed_spread_bps,
                )

        # ── Component costs (per side) ────────────────────────────────────
        # Spread: half-spread per side
        spread_cost = spread_frac / 2

        # Market impact
        impact_cost = self._impact_est.compute(
            daily_volatility=daily_volatility,
            adv_shares=daily_vol,
            trade_usd=cfg.assumed_trade_usd,
            price=price,
            eta=cfg.eta,
        )

        # Slippage
        slippage_cost = cfg.slippage_bps / 10_000

        # Commission
        commission_cost = cfg.commission_bps / 10_000

        # Total (multiply by 2 for round-trip if configured)
        multiplier = 2.0 if cfg.round_trip else 1.0
        total = (spread_cost + impact_cost + slippage_cost + commission_cost) * multiplier

        # ── Adjust forward returns ────────────────────────────────────────
        raw_returns = dict(event.forward_returns)
        adjusted_returns: dict[int, float] = {}
        cost_drag: dict[int, float] = {}

        for w, raw_ret in raw_returns.items():
            adj = raw_ret - total
            adjusted_returns[w] = round(adj, 6)
            cost_drag[w] = round(raw_ret - adj, 6)

        return TradeCostBreakdown(
            signal_id=event.signal_id,
            ticker=event.ticker,
            fired_date=event.fired_date,
            price_at_fire=price,
            daily_volume=daily_vol,
            daily_volatility=round(daily_volatility, 6),
            spread_cost=round(spread_cost * multiplier, 6),
            impact_cost=round(impact_cost * multiplier, 6),
            slippage_cost=round(slippage_cost * multiplier, 6),
            commission_cost=round(commission_cost * multiplier, 6),
            total_cost=round(total, 6),
            raw_returns=raw_returns,
            adjusted_returns=adjusted_returns,
            cost_drag=cost_drag,
        )

    @staticmethod
    def _find_date_idx(ohlcv: pd.DataFrame, target: object) -> int | None:
        """Find the index of target date in an OHLCV DataFrame."""
        ts = pd.Timestamp(target)
        dates = ohlcv.index

        # Exact match
        exact = dates.get_indexer([ts], method="pad")
        if len(exact) > 0 and exact[0] >= 0:
            return int(exact[0])
        return None

    def _compute_profiles(
        self,
        raw_events: list[SignalEvent],
        adjusted_events: list[SignalEvent],
        breakdowns: list[TradeCostBreakdown],
        windows: list[int],
    ) -> list[SignalCostProfile]:
        """Compute per-signal cost profiles."""
        # Group by signal_id
        raw_by_sig: dict[str, list[SignalEvent]] = defaultdict(list)
        adj_by_sig: dict[str, list[SignalEvent]] = defaultdict(list)
        bd_by_sig: dict[str, list[TradeCostBreakdown]] = defaultdict(list)

        for e in raw_events:
            raw_by_sig[e.signal_id].append(e)
        for e in adjusted_events:
            adj_by_sig[e.signal_id].append(e)
        for b in breakdowns:
            bd_by_sig[b.signal_id].append(b)

        profiles: list[SignalCostProfile] = []

        for sig_id in raw_by_sig:
            raw_evts = raw_by_sig[sig_id]
            adj_evts = adj_by_sig.get(sig_id, [])
            bds = bd_by_sig.get(sig_id, [])

            if not raw_evts:
                continue

            # Raw metrics
            raw_hr = compute_hit_rate(raw_evts, windows)
            raw_sh = compute_sharpe(raw_evts, windows)
            raw_alpha = compute_avg_excess_return(raw_evts, windows)

            # Adjusted metrics
            adj_hr = compute_hit_rate(adj_evts, windows) if adj_evts else {}
            adj_sh = compute_sharpe(adj_evts, windows) if adj_evts else {}
            net_alpha = compute_avg_excess_return(adj_evts, windows) if adj_evts else {}

            # Cost statistics
            avg_total_cost = sum(b.total_cost for b in bds) / max(len(bds), 1)
            avg_spread = sum(b.spread_cost for b in bds) / max(len(bds), 1)
            avg_impact = sum(b.impact_cost for b in bds) / max(len(bds), 1)
            avg_slip = sum(b.slippage_cost for b in bds) / max(len(bds), 1)
            avg_comm = sum(b.commission_cost for b in bds) / max(len(bds), 1)

            # Cost drag in bps (annualized approximation)
            cost_drag_bps = avg_total_cost * 10_000

            # Breakeven: raw alpha / 2 (assuming round-trip)
            target_w = max(windows)
            raw_alpha_val = raw_alpha.get(target_w, 0.0)
            breakeven = (raw_alpha_val / 2) * 10_000 if raw_alpha_val > 0 else 0.0

            # Cost resilience: net_alpha / raw_alpha
            net_alpha_val = net_alpha.get(target_w, 0.0)
            if raw_alpha_val > 0:
                resilience = max(0.0, min(1.0, net_alpha_val / raw_alpha_val))
            else:
                resilience = 0.0

            # Tier after adjustment
            adj_sharpe_val = adj_sh.get(target_w, 0.0)
            adj_hr_val = adj_hr.get(target_w, 0.0)
            tier = _classify_tier(adj_sharpe_val, adj_hr_val)

            profiles.append(SignalCostProfile(
                signal_id=sig_id,
                signal_name="",
                total_events=len(raw_evts),
                raw_sharpe=raw_sh,
                adjusted_sharpe=adj_sh,
                raw_hit_rate=raw_hr,
                adjusted_hit_rate=adj_hr,
                raw_alpha=raw_alpha,
                net_alpha=net_alpha,
                avg_total_cost=round(avg_total_cost, 6),
                avg_spread_cost=round(avg_spread, 6),
                avg_impact_cost=round(avg_impact, 6),
                avg_slippage_cost=round(avg_slip, 6),
                avg_commission_cost=round(avg_comm, 6),
                total_cost_drag_bps=round(cost_drag_bps, 2),
                cost_adjusted_tier=tier,
                breakeven_cost_bps=round(breakeven, 2),
                cost_resilience_score=round(resilience, 4),
                cost_resilience_class=_classify_resilience(resilience),
            ))

        profiles.sort(key=lambda p: p.cost_resilience_score, reverse=True)
        return profiles
