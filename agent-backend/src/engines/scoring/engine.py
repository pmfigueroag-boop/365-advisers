"""
src/engines/scoring/engine.py
──────────────────────────────────────────────────────────────────────────────
InstitutionalScoringEngine facade — combines fundamental and technical
analysis results into the 12-Factor Institutional Opportunity Score.

Accepts FundamentalResult + TechnicalResult (Layer 3 contracts) and
produces an OpportunityScoreResult (Layer 4 contract).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.contracts.analysis import FundamentalResult, TechnicalResult
from src.contracts.scoring import OpportunityScoreResult, DimensionScores, FactorBreakdown
from src.engines.scoring.opportunity_model import OpportunityModel

logger = logging.getLogger("365advisers.engines.scoring")


class InstitutionalScoringEngine:
    """
    Façade for the 12-Factor Institutional Scoring Engine (Layer 4).

    Usage:
        score = InstitutionalScoringEngine.run(fundamental_result, technical_result)
    """

    @staticmethod
    def run(
        fundamental: FundamentalResult,
        technical: TechnicalResult,
    ) -> OpportunityScoreResult:
        """
        Compute the Institutional Opportunity Score.

        Delegates to the existing OpportunityModel.calculate() but converts
        the typed contracts into the raw dict format it expects, then maps
        the output back into the OpportunityScoreResult contract.

        Args:
            fundamental: FundamentalResult from the Fundamental Engine.
            technical: TechnicalResult from the Technical Engine.

        Returns:
            OpportunityScoreResult with score, dimensions, and factor breakdown.
        """
        # ── Prepare inputs for the existing OpportunityModel ──────────────
        # The model expects: agent_memos (list[dict]), tech_result (dict),
        # committee_output (dict)

        agent_memos_raw = [
            {
                "agent": memo.agent_name,
                "signal": memo.signal,
                "conviction": memo.confidence,
                "memo": memo.analysis,
                "key_metrics_used": memo.selected_metrics,
            }
            for memo in fundamental.agent_memos
        ]

        tech_summary = technical.summary if technical.summary else {}

        committee_raw = {
            "score": fundamental.committee_verdict.score,
            "confidence": fundamental.committee_verdict.confidence,
            "signal": fundamental.committee_verdict.signal,
        }

        # ── Run the OpportunityModel ──────────────────────────────────────
        try:
            raw_result = OpportunityModel.calculate(
                agent_memos=agent_memos_raw,
                tech_result=tech_summary,
                committee_output=committee_raw,
            )
        except Exception as exc:
            logger.error(f"OpportunityModel.calculate failed: {exc}")
            return OpportunityScoreResult(
                recorded_at=datetime.now(tz=timezone.utc).isoformat(),
            )

        # ── Map to typed contract ─────────────────────────────────────────
        dims = raw_result.get("dimensions", {})
        factors = raw_result.get("factor_breakdown", {})

        return OpportunityScoreResult(
            opportunity_score=raw_result.get("opportunity_score", 5.0),
            dimensions=DimensionScores(
                business_quality=dims.get("business_quality", 5.0),
                valuation=dims.get("valuation", 5.0),
                financial_strength=dims.get("financial_strength", 5.0),
                market_behavior=dims.get("market_behavior", 5.0),
            ),
            factors=FactorBreakdown(
                # Business Quality
                competitive_moat=factors.get("competitive_moat", 5.0),
                management_capital_allocation=factors.get("management_capital_allocation", 5.0),
                industry_structure=factors.get("industry_structure", 5.0),
                # Valuation
                relative_valuation=factors.get("relative_valuation", 5.0),
                intrinsic_value_gap=factors.get("intrinsic_value_gap", 5.0),
                fcf_yield=factors.get("fcf_yield", 5.0),
                # Financial Strength
                balance_sheet_strength=factors.get("balance_sheet_strength", 5.0),
                earnings_stability=factors.get("earnings_stability", 5.0),
                growth_quality=factors.get("growth_quality", 5.0),
                # Market Behavior
                trend_strength=factors.get("trend_strength", 5.0),
                momentum=factors.get("momentum", 5.0),
                institutional_flow=factors.get("institutional_flow", 5.0),
            ),
            recorded_at=datetime.now(tz=timezone.utc).isoformat(),
        )
