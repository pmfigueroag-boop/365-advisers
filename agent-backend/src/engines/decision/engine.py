"""
src/engines/decision/engine.py
──────────────────────────────────────────────────────────────────────────────
DecisionEngine facade — synthesises all upstream results into a final
InvestmentDecision.

Accepts results from Fundamental, Technical, Scoring, and Sizing layers
and produces an InvestmentDecision (Layer 6 contract).
"""

from __future__ import annotations

import logging

from src.contracts.analysis import FundamentalResult, TechnicalResult
from src.contracts.scoring import OpportunityScoreResult
from src.contracts.sizing import PositionAllocation
from src.contracts.decision import InvestmentDecision, CIOMemo
from src.engines.decision.classifier import DecisionMatrix
from src.engines.composite_alpha.models import CompositeAlphaResult

logger = logging.getLogger("365advisers.engines.decision")


class DecisionEngine:
    """
    Façade for the Decision Engine (Layer 6).

    Usage:
        decision = await DecisionEngine.run(
            fundamental_result, technical_result,
            opportunity_score, position_allocation,
        )
    """

    @staticmethod
    async def run(
        fundamental: FundamentalResult,
        technical: TechnicalResult,
        opportunity: OpportunityScoreResult,
        sizing: PositionAllocation,
        use_llm_memo: bool = True,
        composite_alpha: CompositeAlphaResult | None = None,
    ) -> InvestmentDecision:
        """
        Produce the final investment decision.

        Steps:
          1. Classify investment position via DecisionMatrix
          2. Generate CIO memo (LLM-powered or rule-based)
          3. Package into InvestmentDecision contract

        Args:
            fundamental: FundamentalResult from the Fundamental Engine.
            technical: TechnicalResult from the Technical Engine.
            opportunity: OpportunityScoreResult from the Scoring Engine.
            sizing: PositionAllocation from the Position Sizing Engine.
            use_llm_memo: Whether to call the CIO Agent LLM for the memo.

        Returns:
            InvestmentDecision with classification, scores, and CIO memo.
        """
        # ── Step 1: Classify position ─────────────────────────────────────
        fundamental_score = fundamental.committee_verdict.score
        # Prefer purified score (alpha-validated) over original
        technical_score = technical.purified_score

        try:
            classification = DecisionMatrix.classify(fundamental_score, technical_score)
            investment_position = classification.get("position", "Neutral")
        except Exception as exc:
            logger.warning(f"DecisionMatrix failed: {exc}")
            investment_position = "Neutral"

        # ── Step 2: Generate CIO Memo ─────────────────────────────────────
        cio_memo = CIOMemo()
        if use_llm_memo:
            try:
                cio_memo = await _generate_cio_memo(
                    fundamental, technical, opportunity, sizing,
                    composite_alpha=composite_alpha,
                )
            except Exception as exc:
                logger.warning(f"CIO memo generation failed: {exc}")
                cio_memo = _generate_rule_based_memo(
                    fundamental, technical, opportunity,
                )
        else:
            cio_memo = _generate_rule_based_memo(
                fundamental, technical, opportunity,
            )

        # ── Step 3: Package result ────────────────────────────────────────
        return InvestmentDecision(
            ticker=fundamental.ticker,
            investment_position=investment_position,
            confidence_score=fundamental.committee_verdict.confidence,
            fundamental_aggregate=fundamental_score,
            technical_aggregate=technical_score,
            opportunity=opportunity,
            position_sizing=sizing,
            cio_memo=cio_memo,
        )


async def _generate_cio_memo(
    fundamental: FundamentalResult,
    technical: TechnicalResult,
    opportunity: OpportunityScoreResult,
    sizing: PositionAllocation,
    composite_alpha: CompositeAlphaResult | None = None,
) -> CIOMemo:
    """Use the CIO Agent LLM to produce a rich investment memo."""
    from src.engines.decision.cio_agent import generate_cio_memo as _cio_llm

    # Prepare input for the existing CIO agent
    analysis_data = {
        "fundamental_score": fundamental.committee_verdict.score,
        "fundamental_signal": fundamental.committee_verdict.signal,
        "consensus_narrative": fundamental.committee_verdict.consensus_narrative,
        "technical_score": technical.technical_score,
        "technical_signal": technical.signal,
        "purified_tech_score": technical.purified_score,
        "purified_tech_signal": technical.purified_signal,
        "purified_tech_evidence": technical.purified_evidence,
        "dynamic_fundamental_score": fundamental.dynamic_score,
        "dynamic_fundamental_signal": fundamental.dynamic_signal,
        "dynamic_fundamental_evidence": fundamental.dynamic_evidence,
        "opportunity_score": opportunity.opportunity_score,
        "dimensions": opportunity.dimensions.model_dump(),
        "sizing": sizing.model_dump(),
        "key_catalysts": fundamental.committee_verdict.key_catalysts,
        "key_risks": fundamental.committee_verdict.key_risks,
    }

    # Inject Composite Alpha Score context if available
    if composite_alpha is not None:
        top_categories = sorted(
            composite_alpha.subscores.items(),
            key=lambda x: x[1].score,
            reverse=True,
        )[:3]
        analysis_data["signal_environment"] = {
            "composite_alpha_score": composite_alpha.composite_alpha_score,
            "environment": composite_alpha.signal_environment.value,
            "top_categories": [
                {"name": k, "score": v.score} for k, v in top_categories
            ],
            "active_categories": composite_alpha.active_categories,
            "conflicts": composite_alpha.cross_category_conflicts,
        }

    try:
        raw_memo = await _cio_llm(
            ticker=fundamental.ticker,
            analysis_data=analysis_data,
        )

        return CIOMemo(
            thesis_summary=raw_memo.get("thesis_summary", ""),
            valuation_view=raw_memo.get("valuation_view", ""),
            technical_context=raw_memo.get("technical_context", ""),
            key_catalysts=raw_memo.get("key_catalysts", []),
            key_risks=raw_memo.get("key_risks", []),
        )
    except Exception as exc:
        logger.warning(f"CIO LLM memo failed, falling back to rule-based: {exc}")
        return _generate_rule_based_memo(fundamental, technical, opportunity)


def _generate_rule_based_memo(
    fundamental: FundamentalResult,
    technical: TechnicalResult,
    opportunity: OpportunityScoreResult,
) -> CIOMemo:
    """Deterministic fallback memo when LLM is unavailable."""
    verdict = fundamental.committee_verdict

    # Simple thesis based on scores
    opp = opportunity.opportunity_score
    if opp >= 7.5:
        thesis = f"Strong investment opportunity with score {opp}/10."
    elif opp >= 5.0:
        thesis = f"Moderate opportunity with score {opp}/10. Mixed signals."
    else:
        thesis = f"Below-average opportunity with score {opp}/10. Caution advised."

    return CIOMemo(
        thesis_summary=thesis,
        valuation_view=f"Fundamental score: {verdict.score}/10, "
                       f"Signal: {verdict.signal}",
        technical_context=f"Technical score: {technical.technical_score}/10, "
                         f"Signal: {technical.signal}, "
                         f"Volatility: {technical.volatility_condition}",
        key_catalysts=verdict.key_catalysts[:5],
        key_risks=verdict.key_risks[:5],
    )
