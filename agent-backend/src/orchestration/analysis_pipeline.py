"""
src/orchestration/analysis_pipeline.py
──────────────────────────────────────────────────────────────────────────────
AnalysisPipeline — the full analysis flow extracted from
main.py's combined_analysis_stream().

Orchestrates: Data → Features → Engines → Scoring → Sizing → Decision
while emitting SSE events at each step.
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
import json

from src.orchestration.sse_streamer import sse
from src.engines.fundamental.graph import run_fundamental_stream
from src.data.market_data import fetch_technical_data
from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine as TechScoringModule
from src.engines.technical.formatter import build_technical_summary
from src.engines.scoring.opportunity_model import OpportunityModel
from src.engines.portfolio.position_sizing import PositionSizingModel
from src.engines.decision.classifier import DecisionMatrix
from src.engines.decision.cio_agent import synthesize_investment_memo
from src.data.database import SessionLocal, OpportunityScoreHistory

logger = logging.getLogger("365advisers.orchestration.pipeline")


class AnalysisPipeline:
    """
    Full analysis pipeline orchestrator.

    Extracted from main.py's combined_analysis_stream().
    Produces SSE events as an async generator.
    """

    def __init__(self, fund_cache, tech_cache, decision_cache):
        self.fund_cache = fund_cache
        self.tech_cache = tech_cache
        self.decision_cache = decision_cache

    async def run_combined_stream(self, ticker: str, force: bool = False):
        """
        Async generator that runs the full analysis pipeline.

        Event flow:
          1. data_ready          → fundamental ratios
          2. agent_memo × 4      → specialist analysts
          3. committee_verdict   → score + narrative
          4. research_memo       → 1-pager markdown
          5. technical_ready     → TechnicalSummary JSON
          6. opportunity_score   → 12-factor score
          7. position_sizing     → allocation recommendation
          8. decision_ready      → CIO Investment Memo
          9. done
        """
        symbol = ticker.upper().strip()
        fund_events: list[dict] = []
        tech_data: dict | None = None
        is_from_cache = False

        # ── Part 1: Fundamental Engine ──────────────────────────────────
        cached_fund = self.fund_cache.get(symbol) if not force else None
        if cached_fund:
            logger.info(f"PIPELINE: Fundamental HIT for {symbol}")
            is_from_cache = True
            fund_events = cached_fund["events"]
            for ev in fund_events:
                yield sse(ev["event"], ev["data"])
                await asyncio.sleep(0.02)
        else:
            async for ev_dict in run_fundamental_stream(symbol):
                event_name = ev_dict.get("event", "")
                data = ev_dict.get("data", {})
                if event_name not in ("done", "error"):
                    yield sse(event_name, data)
                    fund_events.append({"event": event_name, "data": data})
                elif event_name == "error":
                    yield sse("error", data)
                    return
            if fund_events:
                self.fund_cache.set(symbol, {"events": fund_events})

        fund_committee = next(
            (e["data"] for e in fund_events if e["event"] == "committee_verdict"), {}
        )

        # ── Part 2: Technical Engine ────────────────────────────────────
        cached_tech = self.tech_cache.get(symbol) if not force else None
        if cached_tech:
            logger.info(f"PIPELINE: Technical HIT for {symbol}")
            tech_data = cached_tech
        else:
            start = _time.monotonic_ns() / 1e6
            try:
                raw = await asyncio.to_thread(fetch_technical_data, symbol)
                indicators = await asyncio.to_thread(IndicatorEngine.compute, raw)
                scores = await asyncio.to_thread(TechScoringModule.compute, indicators)
                tech_data = build_technical_summary(
                    ticker=symbol, tech_data=raw, result=indicators,
                    score=scores, processing_start_ms=start,
                )
                self.tech_cache.set(symbol, tech_data)
            except Exception as exc:
                import traceback; traceback.print_exc()
                yield sse("technical_ready", {"error": str(exc)})
                yield sse("done", {"from_cache": is_from_cache})
                return

        yield sse("technical_ready", tech_data)
        await asyncio.sleep(0)

        # ── Part 3: Institutional Opportunity Score ─────────────────────
        opportunity_data = None
        if not is_from_cache or force:
            logger.info(f"PIPELINE: Calculating Opportunity Score for {symbol}")
            try:
                fund_ratios = next(
                    (e["data"].get("ratios", {}) for e in fund_events if e["event"] == "data_ready"), {}
                )
                fund_agents = [e["data"] for e in fund_events if e["event"] == "agent_memo"]

                if not fund_ratios and fund_events:
                    data_ready = next(
                        (e["data"] for e in fund_events if e["event"] == "data_ready"), {}
                    )
                    fund_ratios = (
                        data_ready.get("fundamental_metrics", {})
                        if "fundamental_metrics" in data_ready
                        else data_ready.get("ratios", {})
                    )

                opportunity_data = await asyncio.to_thread(
                    OpportunityModel.calculate,
                    fundamental_metrics=fund_ratios,
                    fundamental_agents=fund_agents,
                    technical_summary=tech_data or {},
                )

                # Persist to DB
                try:
                    with SessionLocal() as db:
                        db.add(OpportunityScoreHistory(
                            ticker=symbol,
                            opportunity_score=opportunity_data["opportunity_score"],
                            business_quality=opportunity_data["dimensions"]["business_quality"],
                            valuation=opportunity_data["dimensions"]["valuation"],
                            financial_strength=opportunity_data["dimensions"]["financial_strength"],
                            market_behavior=opportunity_data["dimensions"]["market_behavior"],
                            score_breakdown_json=json.dumps(opportunity_data),
                        ))
                        db.commit()
                except Exception as db_exc:
                    logger.warning(f"PIPELINE: DB persist error: {db_exc}")

            except Exception as exc:
                logger.warning(f"PIPELINE: Opportunity Score error: {exc}")
                import traceback; traceback.print_exc()
                opportunity_data = {"error": str(exc)}

        if opportunity_data:
            yield sse("opportunity_score", opportunity_data)
        await asyncio.sleep(0)

        # ── Part 4: Position Sizing ─────────────────────────────────────
        position_data = None
        if opportunity_data and "opportunity_score" in opportunity_data:
            logger.info(f"PIPELINE: Position Sizing for {symbol}")
            try:
                risk_cond = (
                    tech_data.get("summary", {}).get("volatility_condition", "NORMAL")
                    if tech_data else "NORMAL"
                )
                position_data = await asyncio.to_thread(
                    PositionSizingModel.calculate,
                    opportunity_score=opportunity_data["opportunity_score"],
                    risk_condition=risk_cond,
                )
                yield sse("position_sizing", position_data)
            except Exception as p_exc:
                logger.warning(f"PIPELINE: Position Sizing error: {p_exc}")
        await asyncio.sleep(0)

        # ── Part 5: Decision Engine (CIO Memo) ─────────────────────────
        decision_data = self.decision_cache.get(symbol) if not force else None
        if decision_data and is_from_cache:
            logger.info(f"PIPELINE: Decision HIT for {symbol}")
        else:
            logger.info(f"PIPELINE: Running CIO Synthesizer for {symbol}")
            d_start = _time.monotonic_ns() / 1e6
            try:
                fund_score = fund_committee.get("score", 5.0)
                tech_score = (
                    tech_data.get("technical_score", 5.0) if tech_data else 5.0
                )
                fund_confidence = fund_committee.get("confidence", 0.5)

                metrics = DecisionMatrix.analyze(fund_score, tech_score, fund_confidence)

                memo = await asyncio.to_thread(
                    synthesize_investment_memo,
                    ticker=symbol,
                    investment_position=metrics["investment_position"],
                    fundamental_verdict=fund_committee,
                    technical_summary=tech_data or {},
                    opportunity_data=opportunity_data or {},
                    position_data=position_data or {},
                )

                d_elapsed = (_time.monotonic_ns() / 1e6) - d_start
                decision_data = {
                    "investment_position": metrics["investment_position"],
                    "confidence_score": metrics["confidence_score"],
                    "cio_memo": memo,
                    "position_sizing": position_data,
                    "elapsed_ms": round(d_elapsed),
                }
                self.decision_cache.set(symbol, decision_data)
            except Exception as exc:
                logger.error(f"PIPELINE: CIO Synthesizer error: {exc}")
                decision_data = {"error": str(exc)}

        if decision_data:
            yield sse("decision_ready", decision_data)

        yield sse("done", {"from_cache": is_from_cache})
