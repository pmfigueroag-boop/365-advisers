"""
src/engines/fundamental/engine.py
──────────────────────────────────────────────────────────────────────────────
FundamentalEngine facade — entry point for the Fundamental Analysis layer.

Wraps the existing LangGraph-based fundamental pipeline behind a clean
contract-based interface. Accepts a FundamentalFeatureSet (Layer 2) and
produces a FundamentalResult (Layer 3).

Includes deterministic scoring from financial ratios and a signal guardrail
that prevents the LLM committee from contradicting quantitative evidence.
"""

from __future__ import annotations

import asyncio
import json
import logging

from src.contracts.features import FundamentalFeatureSet
from src.contracts.analysis import FundamentalResult, AgentMemo, CommitteeVerdict
from src.engines.fundamental.scoring import (
    FundamentalScoringEngine,
    apply_signal_guardrail,
    validate_llm_coherence,
)
from src.engines.fundamental.dynamic_scoring import DynamicFundamentalScoringEngine

logger = logging.getLogger("365advisers.engines.fundamental")


class FundamentalEngine:
    """
    Façade for the Fundamental Analysis Engine (Layer 3a).

    Usage:
        features = extract_fundamental_features(financials)
        result = await FundamentalEngine.run(features)

    The engine runs both the LLM pipeline (4 agents + committee) and
    a deterministic scoring module. If the LLM's signal contradicts the
    deterministic evidence, the guardrail overrides it.
    """

    @staticmethod
    async def run(
        features: FundamentalFeatureSet,
        stream_callback=None,
    ) -> FundamentalResult:
        """
        Execute the fundamental analysis pipeline.

        Args:
            features: Normalised FundamentalFeatureSet from Feature Layer.
            stream_callback: Optional async callable(event_type, data) for
                             SSE streaming progress updates.

        Returns:
            FundamentalResult with agent memos, committee verdict, deterministic
            score, and research memo.
        """
        from src.engines.fundamental.graph import run_fundamental_stream

        agent_memos: list[AgentMemo] = []
        committee_verdict = CommitteeVerdict()
        research_memo = ""
        data_ready: dict = {}

        try:
            async for event in run_fundamental_stream(features.ticker):
                event_type = event.get("event", "")
                event_data = event.get("data", {})

                if event_type == "data_ready":
                    data_ready = event_data
                    if stream_callback:
                        await stream_callback("data_ready", event_data)

                elif event_type == "agent_memo":
                    memo = AgentMemo(
                        agent_name=event_data.get("agent", "Unknown"),
                        signal=_normalise_signal(event_data.get("signal", "HOLD")),
                        confidence=event_data.get("conviction", 0.5),
                        analysis=event_data.get("memo", ""),
                        selected_metrics=event_data.get("key_metrics_used", []),
                    )
                    agent_memos.append(memo)
                    if stream_callback:
                        await stream_callback("agent_memo", event_data)

                elif event_type == "committee_verdict":
                    committee_verdict = CommitteeVerdict(
                        score=event_data.get("score", 5.0),
                        confidence=event_data.get("confidence", 0.5),
                        signal=_normalise_signal(event_data.get("signal", "HOLD")),
                        consensus_narrative=event_data.get("consensus_narrative", ""),
                        key_catalysts=event_data.get("key_catalysts", []),
                        key_risks=event_data.get("key_risks", []),
                    )
                    if stream_callback:
                        await stream_callback("committee_verdict", event_data)

                    # P4: LLM coherence check (score vs signal)
                    corrected_signal, was_corrected = validate_llm_coherence(
                        llm_score=committee_verdict.score,
                        llm_signal=committee_verdict.signal,
                    )
                    if was_corrected:
                        committee_verdict = CommitteeVerdict(
                            score=committee_verdict.score,
                            confidence=committee_verdict.confidence,
                            signal=corrected_signal,
                            consensus_narrative=committee_verdict.consensus_narrative,
                            key_catalysts=committee_verdict.key_catalysts,
                            key_risks=committee_verdict.key_risks,
                            allocation_recommendation=committee_verdict.allocation_recommendation,
                        )

                elif event_type == "research_memo":
                    research_memo = event_data.get("memo", "")
                    if stream_callback:
                        await stream_callback("research_memo", event_data)

                elif event_type == "error":
                    logger.error(f"Fundamental engine error for {features.ticker}: {event_data}")
                    if stream_callback:
                        await stream_callback("error", event_data)

        except Exception as exc:
            logger.error(f"FundamentalEngine.run failed for {features.ticker}: {exc}")

        # ── Deterministic Scoring ─────────────────────────────────────────
        deterministic_score = None
        deterministic_signal = None
        score_evidence: list[str] = []
        data_coverage = 0.0

        ratios = data_ready.get("ratios", {})
        if ratios:
            try:
                det_result = FundamentalScoringEngine.compute(ratios)
                deterministic_score = det_result.score
                deterministic_signal = det_result.signal
                score_evidence = det_result.evidence
                data_coverage = det_result.data_coverage

                logger.info(
                    f"Deterministic score for {features.ticker}: "
                    f"{det_result.score}/10 ({det_result.signal}), "
                    f"coverage={det_result.data_coverage:.0%}"
                )

                # ── Signal Guardrail ──────────────────────────────────────
                if deterministic_signal and committee_verdict.signal:
                    final_signal, was_overridden = apply_signal_guardrail(
                        llm_signal=committee_verdict.signal,
                        deterministic_signal=deterministic_signal,
                        deterministic_score=deterministic_score,
                    )
                    if was_overridden:
                        committee_verdict = CommitteeVerdict(
                            score=committee_verdict.score,
                            confidence=committee_verdict.confidence,
                            signal=final_signal,
                            consensus_narrative=committee_verdict.consensus_narrative,
                            key_catalysts=committee_verdict.key_catalysts,
                            key_risks=committee_verdict.key_risks,
                            allocation_recommendation=committee_verdict.allocation_recommendation,
                        )

            except Exception as exc:
                logger.warning(f"Deterministic scoring failed for {features.ticker}: {exc}")

        # ── Dynamic V3 Scoring (sector-calibrated) ────────────────────────
        dynamic_score_val = None
        dynamic_signal_val = None
        dynamic_evidence_val: list[str] = []

        if ratios:
            try:
                sector = data_ready.get("profile", {}).get("sector", "")
                dyn_result = DynamicFundamentalScoringEngine.compute(
                    ratios, sector=sector,
                )
                dynamic_score_val = dyn_result.aggregate
                dynamic_signal_val = dyn_result.signal
                dynamic_evidence_val = dyn_result.evidence
                logger.info(
                    f"Dynamic V3 score for {features.ticker}: "
                    f"{dyn_result.aggregate}/10 ({dyn_result.signal}), "
                    f"sector={dyn_result.sector_used}, "
                    f"gates={dyn_result.gates_passed}/{dyn_result.gates_total}"
                )
            except Exception as exc:
                logger.warning(f"Dynamic V3 scoring failed for {features.ticker}: {exc}")

        return FundamentalResult(
            ticker=features.ticker,
            data_ready=data_ready,
            agent_memos=agent_memos,
            committee_verdict=committee_verdict,
            research_memo=research_memo,
            deterministic_score=deterministic_score,
            deterministic_signal=deterministic_signal,
            score_evidence=score_evidence,
            data_coverage=data_coverage,
            dynamic_score=dynamic_score_val,
            dynamic_signal=dynamic_signal_val,
            dynamic_evidence=dynamic_evidence_val,
        )


def _normalise_signal(raw_signal: str) -> str:
    """Normalise signal strings preserving STRONG_BUY / STRONG_SELL granularity."""
    s = raw_signal.upper().strip()
    if s in ("STRONG_BUY", "STRONGBUY"):
        return "STRONG_BUY"
    if "BUY" in s:
        return "BUY"
    if s in ("STRONG_SELL", "STRONGSELL"):
        return "STRONG_SELL"
    if "SELL" in s:
        return "SELL"
    if "AVOID" in s:
        return "SELL"
    return "HOLD"
