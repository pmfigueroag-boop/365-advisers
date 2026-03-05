"""
src/engines/fundamental/engine.py
──────────────────────────────────────────────────────────────────────────────
FundamentalEngine facade — entry point for the Fundamental Analysis layer.

Wraps the existing LangGraph-based fundamental pipeline behind a clean
contract-based interface. Accepts a FundamentalFeatureSet (Layer 2) and
produces a FundamentalResult (Layer 3).

During the migration period, this facade delegates to the existing
`run_fundamental_stream()` generator and collects its SSE events.
"""

from __future__ import annotations

import asyncio
import json
import logging

from src.contracts.features import FundamentalFeatureSet
from src.contracts.analysis import FundamentalResult, AgentMemo, CommitteeVerdict

logger = logging.getLogger("365advisers.engines.fundamental")


class FundamentalEngine:
    """
    Façade for the Fundamental Analysis Engine (Layer 3a).

    Usage:
        features = extract_fundamental_features(financials)
        result = await FundamentalEngine.run(features)

    During migration, this wraps the existing LangGraph pipeline.
    Post-migration, this will directly orchestrate individual agents.
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
            FundamentalResult with agent memos, committee verdict, and
            research memo.
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

        return FundamentalResult(
            ticker=features.ticker,
            data_ready=data_ready,
            agent_memos=agent_memos,
            committee_verdict=committee_verdict,
            research_memo=research_memo,
        )


def _normalise_signal(raw_signal: str) -> str:
    """Normalise signal strings to standard BUY/HOLD/SELL."""
    s = raw_signal.upper().strip()
    if "BUY" in s or "STRONG_BUY" in s:
        return "BUY"
    if "SELL" in s or "STRONG_SELL" in s:
        return "SELL"
    return "HOLD"
