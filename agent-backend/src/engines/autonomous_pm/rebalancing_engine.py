"""
src/engines/autonomous_pm/rebalancing_engine.py
──────────────────────────────────────────────────────────────────────────────
Rebalancing Engine — detects conditions that warrant portfolio rebalancing
and generates specific trade recommendations.

5 triggers: regime change, alpha score shift, risk escalation,
            weight drift, market events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.autonomous_pm.models import (
    APMPortfolio,
    APMPosition,
    PortfolioRiskReport,
    RebalanceAction,
    RebalanceRecommendation,
    RebalanceTrigger,
    RebalanceUrgency,
)

logger = logging.getLogger("365advisers.apm.rebalancing")


class RebalancingEngine:
    """
    Detects rebalance triggers and generates trade recommendations.

    Usage::

        engine = RebalancingEngine()
        rec = engine.evaluate(
            current_portfolio=portfolio,
            new_alpha_profiles=profiles,
            current_regime="expansion",
            previous_regime="recovery",
            risk_report=risk_report,
        )
    """

    # ── Thresholds ───────────────────────────────────────────────────────
    DRIFT_THRESHOLD = 0.05         # 5% weight drift
    ALPHA_SHIFT_THRESHOLD = 15.0   # 15-point alpha score change
    RISK_SCORE_THRESHOLD = 70.0    # risk score > 70 triggers escalation

    def evaluate(
        self,
        current_portfolio: APMPortfolio | None = None,
        new_alpha_profiles: list[dict] | None = None,
        current_regime: str = "expansion",
        previous_regime: str | None = None,
        risk_report: PortfolioRiskReport | None = None,
        market_events: list[dict] | None = None,
    ) -> RebalanceRecommendation:
        """
        Evaluate all rebalance triggers and generate recommendations.

        Returns a RebalanceRecommendation with fired triggers, urgency,
        and specific trade actions.
        """
        portfolio = current_portfolio
        profiles = new_alpha_profiles or []
        events = market_events or []

        triggers: list[RebalanceTrigger] = []
        actions: list[RebalanceAction] = []
        summaries: list[str] = []

        # ── Trigger 1: Regime change ─────────────────────────────────────
        if previous_regime and current_regime != previous_regime:
            triggers.append(RebalanceTrigger.REGIME_CHANGE)
            summaries.append(f"Regime changed from {previous_regime} to {current_regime}.")

        # ── Trigger 2: Alpha score shift ─────────────────────────────────
        if portfolio and profiles:
            alpha_map = {p.get("ticker", ""): _f(p.get("composite_alpha_score")) or 0 for p in profiles}
            for pos in portfolio.positions:
                new_alpha = alpha_map.get(pos.ticker)
                if new_alpha is not None:
                    delta = abs(new_alpha - pos.alpha_score)
                    if delta > self.ALPHA_SHIFT_THRESHOLD:
                        if RebalanceTrigger.ALPHA_SHIFT not in triggers:
                            triggers.append(RebalanceTrigger.ALPHA_SHIFT)
                        direction = "buy" if new_alpha > pos.alpha_score else "sell"
                        actions.append(RebalanceAction(
                            ticker=pos.ticker,
                            direction=direction,
                            current_weight=pos.weight,
                            target_weight=pos.weight * (1.1 if direction == "buy" else 0.8),
                            weight_change=pos.weight * (0.1 if direction == "buy" else -0.2),
                            reason=f"Alpha shifted by {delta:.0f} points ({pos.alpha_score:.0f} → {new_alpha:.0f})",
                        ))
                        summaries.append(f"{pos.ticker}: alpha shifted {delta:.0f}pts.")

            # Check for new high-alpha assets not in portfolio
            portfolio_tickers = {p.ticker for p in portfolio.positions}
            for p in profiles:
                ticker = p.get("ticker", "")
                alpha = _f(p.get("composite_alpha_score")) or 0
                if ticker and ticker not in portfolio_tickers and alpha > 70:
                    actions.append(RebalanceAction(
                        ticker=ticker,
                        direction="buy",
                        current_weight=0.0,
                        target_weight=0.05,
                        weight_change=0.05,
                        reason=f"New high-alpha candidate (score {alpha:.0f}) not in current portfolio",
                    ))

        # ── Trigger 3: Risk escalation ───────────────────────────────────
        if risk_report and risk_report.risk_score > self.RISK_SCORE_THRESHOLD:
            triggers.append(RebalanceTrigger.RISK_ESCALATION)
            summaries.append(f"Risk score at {risk_report.risk_score:.0f} exceeds threshold ({self.RISK_SCORE_THRESHOLD}).")
            # Suggest reducing risky positions
            for violation in risk_report.violations:
                for ticker in violation.affected_tickers[:3]:
                    actions.append(RebalanceAction(
                        ticker=ticker,
                        direction="sell",
                        weight_change=-0.02,
                        reason=f"Risk violation: {violation.title}",
                    ))

        # ── Trigger 4: Weight drift ──────────────────────────────────────
        if portfolio:
            n = len(portfolio.positions)
            if n > 0:
                equal_w = 1.0 / n
                for pos in portfolio.positions:
                    drift = abs(pos.weight - equal_w)
                    if drift > self.DRIFT_THRESHOLD:
                        if RebalanceTrigger.WEIGHT_DRIFT not in triggers:
                            triggers.append(RebalanceTrigger.WEIGHT_DRIFT)
                        target = round((pos.weight + equal_w) / 2, 4)
                        actions.append(RebalanceAction(
                            ticker=pos.ticker,
                            direction="sell" if pos.weight > target else "buy",
                            current_weight=pos.weight,
                            target_weight=target,
                            weight_change=round(target - pos.weight, 4),
                            reason=f"Weight drift of {drift:.1%} from equal-weight benchmark",
                        ))

        # ── Trigger 5: Market events ─────────────────────────────────────
        if events:
            triggers.append(RebalanceTrigger.MARKET_EVENT)
            for evt in events[:5]:
                ticker = evt.get("ticker", "")
                impact = evt.get("impact", "neutral")
                if ticker:
                    direction = "buy" if impact == "bullish" else "sell" if impact == "bearish" else "hold"
                    actions.append(RebalanceAction(
                        ticker=ticker,
                        direction=direction,
                        weight_change=0.02 if direction == "buy" else -0.02 if direction == "sell" else 0,
                        reason=f"Market event: {evt.get('headline', 'undisclosed')}",
                    ))
                    summaries.append(f"Event for {ticker}: {evt.get('headline', '')[:60]}")

        # ── Determine urgency ────────────────────────────────────────────
        urgency = self._assess_urgency(triggers, risk_report)

        # ── De-duplicate actions by ticker ───────────────────────────────
        seen: dict[str, RebalanceAction] = {}
        for a in actions:
            if a.ticker not in seen or abs(a.weight_change) > abs(seen[a.ticker].weight_change):
                seen[a.ticker] = a
        deduped_actions = list(seen.values())

        should_rebalance = len(triggers) > 0

        return RebalanceRecommendation(
            triggers_fired=triggers,
            urgency=urgency,
            actions=deduped_actions,
            summary=" | ".join(summaries) if summaries else "No rebalancing required.",
            should_rebalance=should_rebalance,
            regime_before=previous_regime or current_regime,
            regime_after=current_regime,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _assess_urgency(
        triggers: list[RebalanceTrigger],
        risk_report: PortfolioRiskReport | None,
    ) -> RebalanceUrgency:
        if RebalanceTrigger.RISK_ESCALATION in triggers:
            if risk_report and risk_report.risk_score > 85:
                return RebalanceUrgency.IMMEDIATE
            return RebalanceUrgency.HIGH
        if RebalanceTrigger.REGIME_CHANGE in triggers:
            return RebalanceUrgency.HIGH
        if len(triggers) >= 2:
            return RebalanceUrgency.MODERATE
        if triggers:
            return RebalanceUrgency.LOW
        return RebalanceUrgency.LOW


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
