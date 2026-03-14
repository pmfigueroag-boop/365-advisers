"""
src/orchestration/analysis_pipeline.py
──────────────────────────────────────────────────────────────────────────────
AnalysisPipeline — the full analysis flow extracted from
main.py's combined_analysis_stream().

Orchestrates: Data → Features → Engines → Coverage → Scoring → Sizing → Decision
while emitting SSE events at each step.
"""

from __future__ import annotations

import asyncio
import logging
import time as _time
import json
import uuid

from src.orchestration.sse_streamer import sse
from src.engines.fundamental.graph import run_fundamental_stream
from src.data.market_data import fetch_technical_data
from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine as TechScoringModule
from src.engines.technical.formatter import build_technical_summary
from src.engines.technical.regime_detector import (
    TrendRegimeDetector,
    VolatilityRegimeDetector,
    combine_regime_adjustments,
)
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

    def __init__(self, fund_cache, tech_cache, decision_cache, edpl_router=None):
        self.fund_cache = fund_cache
        self.tech_cache = tech_cache
        self.decision_cache = decision_cache
        self._edpl_router = edpl_router  # Use app.state singleton when available

    async def run_combined_stream(self, ticker: str, force: bool = False):
        """
        Async generator that runs the full analysis pipeline.

        Event flow:
          1. data_ready          → fundamental ratios
          2. agent_memo × 4      → specialist analysts
          3. committee_verdict   → score + narrative
          4. research_memo       → 1-pager markdown
          5. technical_ready     → TechnicalSummary JSON
          6. source_coverage     → EDPL coverage report
          7. opportunity_score   → 12-factor score
          8. position_sizing     → allocation recommendation
          9. alpha_stack         → Alpha Signals + CASE + LLM Memos  ⭐ NEW
         10. decision_ready      → CIO Investment Memo (enriched with Alpha Stack)
         11. done
        """
        symbol = ticker.upper().strip()
        analysis_id = str(uuid.uuid4())
        fund_events: list[dict] = []
        tech_data: dict | None = None
        is_from_cache = False

        logger.info(f"[{analysis_id[:8]}] PIPELINE: Starting analysis for {symbol}")

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

                # Regime detection
                raw_inds = raw.get("indicators", {})
                trend_regime = TrendRegimeDetector.detect(
                    adx=raw_inds.get("adx", 20.0),
                    plus_di=raw_inds.get("plus_di", 20.0),
                    minus_di=raw_inds.get("minus_di", 20.0),
                )
                vol_regime = VolatilityRegimeDetector.detect(
                    ohlcv=raw.get("ohlcv", []),
                    current_bb_upper=raw_inds.get("bb_upper", 0.0),
                    current_bb_lower=raw_inds.get("bb_lower", 0.0),
                    current_atr=raw_inds.get("atr", 0.0),
                )
                regime_adj = combine_regime_adjustments(trend_regime, vol_regime)

                scores = await asyncio.to_thread(
                    TechScoringModule.compute, indicators, None, regime_adj
                )
                tech_data = build_technical_summary(
                    ticker=symbol, tech_data=raw, result=indicators,
                    score=scores, processing_start_ms=start,
                    trend_regime=trend_regime, vol_regime=vol_regime,
                )
                self.tech_cache.set(symbol, tech_data)
            except Exception as exc:
                import traceback; traceback.print_exc()
                yield sse("technical_ready", {"error": str(exc)})
                yield sse("done", {"from_cache": is_from_cache})
                return

        # ── Part 2b: Multi-Timeframe scoring (non-blocking) ──────────────
        try:
            from src.data.providers.market_metrics import fetch_multi_timeframe
            from src.engines.technical.mtf_scorer import MultiTimeframeScorer

            mtf_data = await asyncio.to_thread(fetch_multi_timeframe, symbol)
            if mtf_data and len(mtf_data) >= 2:
                mtf_result = MultiTimeframeScorer.compute(
                    mtf_data,
                    regime_adjustments=tech_data.get("regime", {}).get("weight_adjustments"),
                )
                tech_data["mtf"] = {
                    "mtf_aggregate": mtf_result.mtf_aggregate,
                    "mtf_signal": mtf_result.mtf_signal,
                    "agreement_level": mtf_result.agreement_level,
                    "agreement_count": mtf_result.agreement_count,
                    "bonus_applied": mtf_result.bonus_applied,
                    "timeframe_scores": [
                        {
                            "timeframe": ts.timeframe,
                            "score": ts.score,
                            "signal": ts.signal,
                            "trend": ts.trend_status,
                            "momentum": ts.momentum_status,
                        }
                        for ts in mtf_result.timeframe_scores
                    ],
                }
                logger.info(
                    f"PIPELINE: MTF for {symbol}: agg={mtf_result.mtf_aggregate}, "
                    f"agreement={mtf_result.agreement_level} ({mtf_result.agreement_count}/4)"
                )
        except Exception as exc:
            logger.warning(f"PIPELINE: MTF scoring failed for {symbol}: {exc}")
            # Non-fatal: single-TF analysis is still valid

        # ── Part 2c: Technical Analyst Agent (LLM memo, non-blocking) ─────
        technical_memo = None
        try:
            from src.engines.technical.analyst_agent import synthesize_technical_memo

            technical_memo = await asyncio.to_thread(
                synthesize_technical_memo,
                ticker=symbol,
                technical_summary=tech_data,
                regime=tech_data.get("regime"),
                mtf=tech_data.get("mtf"),
            )
            tech_data["technical_memo"] = technical_memo
            logger.info(f"PIPELINE: Technical Analyst memo generated for {symbol}")
        except Exception as exc:
            logger.warning(f"PIPELINE: Technical Analyst Agent failed for {symbol}: {exc}")
            # Non-fatal: technical data is still complete without the memo

        yield sse("technical_ready", tech_data)
        await asyncio.sleep(0)

        # Emit technical_memo as separate event for frontend streaming
        if technical_memo:
            yield sse("technical_memo", technical_memo)
            await asyncio.sleep(0)

        # ── Part 2.5: EDPL Source Coverage ──────────────────────────────
        filing_data = None
        geopolitical_data = None
        macro_ext_data = None
        sentiment_ext_data = None
        coverage_summary = None

        try:
            from src.data.external.coverage.tracker import CoverageTracker
            from src.data.external.base import DataDomain, ProviderRequest

            tracker = CoverageTracker(ticker=symbol)

            # Try to fetch enrichment data from EDPL (non-blocking)
            edpl_results = await self._fetch_edpl_enrichment(symbol, self._edpl_router)

            filing_data = edpl_results.get("filing_events")
            geopolitical_data = edpl_results.get("geopolitical")
            macro_ext_data = edpl_results.get("macro_extended")
            sentiment_ext_data = edpl_results.get("sentiment_extended")

            # Record coverage for each domain
            for domain_key, response in edpl_results.get("_responses", {}).items():
                try:
                    domain = DataDomain(domain_key)
                    tracker.record(domain, response, response.data)
                except Exception:
                    pass

            report = tracker.build_report()
            coverage_summary = {
                "sources": {
                    s.domain.value: s.status
                    for s in report.sources
                },
                "analysis_completeness": report.completeness_score,
                "completeness_label": report.completeness_label,
                "freshness_scores": {
                    s.domain.value: s.freshness.freshness.value
                    for s in report.sources
                    if s.freshness
                },
                "messages": report.messages,
                "unavailable": report.unavailable_domains,
                "partial": report.partial_domains,
            }

            yield sse("source_coverage", coverage_summary)
            logger.info(
                f"PIPELINE: Source coverage for {symbol}: "
                f"{report.completeness_score:.0f}/100 ({report.completeness_label})"
            )
        except Exception as exc:
            logger.debug(f"PIPELINE: EDPL coverage not available: {exc}")
            # Non-critical — continue pipeline without enrichment

        await asyncio.sleep(0)

        # ── Part 3: Institutional Opportunity Score ─────────────────────
        opportunity_data = None
        # Always recalculate scoring — even when fundamentals came from
        # cache, technical data may be fresh and scoring is cheap.
        if fund_events:
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

        # ── Part 4b: Alpha Stack Evaluation (Signals + CASE + LLM Memos) ──
        alpha_stack_context = None
        try:
            from src.engines.alpha_signals.evaluator import SignalEvaluator
            from src.engines.alpha_signals.combiner import SignalCombiner
            from src.engines.composite_alpha.engine import CompositeAlphaEngine
            from src.engines.alpha_decay import DecayEngine, ActivationTracker, DecayConfig
            from src.engines.alpha.alpha_memo_agent import synthesize_alpha_memo
            from src.engines.alpha.evidence_memo_agent import synthesize_evidence_memo
            from src.engines.alpha.signal_map_memo_agent import synthesize_signal_map_memo
            from src.engines.idea_generation.engine import IdeaGenerationEngine

            logger.info(f"PIPELINE: Evaluating Alpha signals for {symbol}")

            _evaluator = SignalEvaluator()
            _combiner = SignalCombiner()
            _decay_config = DecayConfig()
            _activation_tracker = ActivationTracker(config=_decay_config)
            _decay_engine = DecayEngine(tracker=_activation_tracker, config=_decay_config)
            _composite_engine = CompositeAlphaEngine()
            _ige = IdeaGenerationEngine()

            # Fetch features for signal evaluation
            fundamental_features = None
            technical_features = None

            try:
                from src.data.market_data import fetch_fundamental_data
                fund_raw = await asyncio.to_thread(fetch_fundamental_data, symbol)
                if fund_raw and "error" not in fund_raw:
                    fundamental_features = _ige._build_fundamental_features(symbol, fund_raw)
            except Exception:
                pass

            # OPTIMIZATION: Reuse existing tech_data instead of re-fetching
            try:
                if tech_data and "error" not in tech_data:
                    technical_features = _ige._build_technical_features(symbol, tech_data)
            except Exception:
                pass

            if fundamental_features or technical_features:
                # Compute worst-case data age for freshness penalty
                _ages = [
                    getattr(fundamental_features, 'data_age_hours', None),
                    getattr(technical_features, 'data_age_hours', None),
                ]
                _max_age = max((a for a in _ages if a is not None), default=None)

                # Evaluate signals
                profile = await asyncio.to_thread(
                    _evaluator.evaluate, symbol, fundamental_features, technical_features,
                )
                composite = _combiner.combine(profile)
                case_result = _composite_engine.compute(
                    profile, decay_engine=_decay_engine, data_age_hours=_max_age,
                )

                # Build response data for memo agents
                signal_data = {
                    "ticker": symbol,
                    "total_signals": profile.total_signals,
                    "fired_signals": profile.fired_signals,
                    "signals": [s.model_dump() for s in profile.signals if s.fired],
                    "category_summary": {
                        k: v.model_dump() for k, v in profile.category_summary.items()
                    },
                    "composite": composite.model_dump(),
                    "composite_alpha": {
                        "score": case_result.composite_alpha_score,
                        "environment": case_result.signal_environment.value,
                        "subscores": {
                            k: v.model_dump() for k, v in case_result.subscores.items()
                        },
                        "active_categories": case_result.active_categories,
                        "convergence_bonus": case_result.convergence_bonus,
                        "cross_category_conflicts": case_result.cross_category_conflicts,
                        "decay": {
                            "applied": case_result.decay_applied,
                            "average_freshness": case_result.average_freshness,
                            "expired_signals": case_result.expired_signal_count,
                            "freshness_level": case_result.freshness_level.value,
                        },
                    },
                }

                # Run 3 LLM memo agents concurrently
                alpha_memo_t = asyncio.to_thread(
                    synthesize_alpha_memo, ticker=symbol, signal_profile=signal_data,
                )
                evidence_memo_t = asyncio.to_thread(
                    synthesize_evidence_memo,
                    ticker=symbol,
                    composite_alpha=signal_data["composite_alpha"],
                    category_summary=signal_data["category_summary"],
                )
                signal_map_memo_t = asyncio.to_thread(
                    synthesize_signal_map_memo,
                    ticker=symbol,
                    signals=signal_data["signals"],
                    category_summary=signal_data["category_summary"],
                )

                alpha_memo, evidence_memo, signal_map_memo = await asyncio.gather(
                    alpha_memo_t, evidence_memo_t, signal_map_memo_t,
                    return_exceptions=True,
                )

                alpha_stack_context = {
                    "case_score": case_result.composite_alpha_score,
                    "environment": case_result.signal_environment.value,
                    "fired_signals": profile.fired_signals,
                    "total_signals": profile.total_signals,
                    "alpha_memo": alpha_memo if not isinstance(alpha_memo, Exception) else None,
                    "evidence_memo": evidence_memo if not isinstance(evidence_memo, Exception) else None,
                    "signal_map_memo": signal_map_memo if not isinstance(signal_map_memo, Exception) else None,
                }

                yield sse("alpha_stack", alpha_stack_context)
                logger.info(
                    f"PIPELINE: Alpha Stack for {symbol}: "
                    f"CASE={case_result.composite_alpha_score:.0f}, "
                    f"{profile.fired_signals}/{profile.total_signals} signals"
                )

        except Exception as exc:
            logger.warning(f"PIPELINE: Alpha Stack evaluation failed for {symbol}: {exc}")
            # Non-fatal — CIO can proceed without alpha context

        await asyncio.sleep(0)

        # ── Part 5: Decision Engine (CIO Memo — Enriched) ──────────────
        decision_data = self.decision_cache.get(symbol) if not force else None
        if decision_data and is_from_cache:
            logger.info(f"PIPELINE: Decision HIT for {symbol}")
        else:
            logger.info(f"PIPELINE: Running CIO Synthesizer for {symbol}")
            d_start = _time.monotonic_ns() / 1e6
            try:
                fund_score = fund_committee.get("score", 5.0)
                tech_score = (
                    tech_data.get("summary", {}).get("technical_score",
                        tech_data.get("technical_score", 5.0))
                    if tech_data else 5.0
                )
                fund_confidence = fund_committee.get("confidence", 0.5)

                metrics = DecisionMatrix.analyze(fund_score, tech_score, fund_confidence)

                # Prepare enrichment dicts for CIO Memo
                filing_dict = (
                    filing_data.model_dump(mode="json")
                    if filing_data and hasattr(filing_data, "model_dump")
                    else filing_data
                )
                geo_dict = (
                    geopolitical_data.model_dump(mode="json")
                    if geopolitical_data and hasattr(geopolitical_data, "model_dump")
                    else geopolitical_data
                )
                macro_dict = (
                    macro_ext_data.model_dump(mode="json")
                    if macro_ext_data and hasattr(macro_ext_data, "model_dump")
                    else macro_ext_data
                )
                sentiment_dict = (
                    sentiment_ext_data.model_dump(mode="json")
                    if sentiment_ext_data and hasattr(sentiment_ext_data, "model_dump")
                    else sentiment_ext_data
                )

                memo = await asyncio.to_thread(
                    synthesize_investment_memo,
                    ticker=symbol,
                    investment_position=metrics["investment_position"],
                    fundamental_verdict=fund_committee,
                    technical_summary=tech_data or {},
                    opportunity_data=opportunity_data or {},
                    position_data=position_data or {},
                    filing_context=filing_dict,
                    geopolitical_context=geo_dict,
                    macro_extended=macro_dict,
                    sentiment_context=sentiment_dict,
                    alpha_stack_context=alpha_stack_context,
                )

                d_elapsed = (_time.monotonic_ns() / 1e6) - d_start
                decision_data = {
                    "investment_position": metrics["investment_position"],
                    "confidence_score": metrics["confidence_score"],
                    "cio_memo": memo,
                    "position_sizing": position_data,
                    "elapsed_ms": round(d_elapsed),
                    "source_coverage": coverage_summary,
                }
                self.decision_cache.set(symbol, decision_data)
            except Exception as exc:
                logger.error(f"PIPELINE: CIO Synthesizer error: {exc}")
                decision_data = {"error": str(exc)}

        if decision_data:
            yield sse("decision_ready", decision_data)

        yield sse("done", {"from_cache": is_from_cache, "analysis_id": analysis_id})

    # ── EDPL Enrichment Helper ────────────────────────────────────────────

    @staticmethod
    async def _fetch_edpl_enrichment(ticker: str, edpl_router=None) -> dict:
        """
        Non-blocking EDPL fetch for enrichment data.

        Fetches 6 domains concurrently (all keyless or gracefully degrading):
          - FILING_EVENTS  (SEC EDGAR — keyless)
          - GEOPOLITICAL   (GDELT — keyless)
          - MACRO          (FRED/World Bank/IMF — keyless or free-tier key)
          - SENTIMENT      (StockTwits/GDELT — keyless)
          - VOLATILITY     (CBOE — keyless)
          - INSTITUTIONAL  (SEC 13F/yfinance fallback — keyless)

        Uses the provided edpl_router (from app.state singleton) when available,
        avoiding the creation of fresh instances that reset circuit breaker state.
        """
        results: dict = {"_responses": {}}

        try:
            from src.data.external.base import DataDomain, ProviderRequest

            router = edpl_router

            # Fallback: create new instances if no router provided
            if router is None:
                from src.data.external.registry import ProviderRegistry
                from src.data.external.health import HealthChecker
                from src.data.external.fallback import FallbackRouter
                registry = ProviderRegistry()
                health = HealthChecker()
                router = FallbackRouter(registry, health)

            # Fetch domains concurrently (timeout 5s each)
            async def _safe_fetch(domain: DataDomain) -> tuple:
                try:
                    req = ProviderRequest(domain=domain, ticker=ticker)
                    resp = await asyncio.wait_for(router.fetch(domain, req), timeout=5.0)
                    return domain.value, resp
                except asyncio.TimeoutError:
                    logger.debug(f"EDPL {domain.value} timed out for {ticker}")
                    return domain.value, None
                except Exception as exc:
                    logger.debug(f"EDPL {domain.value} error: {exc}")
                    return domain.value, None

            # Fetch all complementary domains concurrently
            domain_tasks = [
                _safe_fetch(DataDomain.FILING_EVENTS),     # SEC EDGAR (keyless)
                _safe_fetch(DataDomain.GEOPOLITICAL),       # GDELT (keyless)
                _safe_fetch(DataDomain.MACRO),              # FRED/World Bank/IMF
                _safe_fetch(DataDomain.SENTIMENT),          # StockTwits/news
                _safe_fetch(DataDomain.VOLATILITY),         # CBOE VIX/options
                _safe_fetch(DataDomain.INSTITUTIONAL),      # SEC 13F/insider
            ]

            fetched = await asyncio.gather(*domain_tasks)

            # Map results to enrichment keys
            _domain_to_key = {
                "filing_events": "filing_events",
                "geopolitical": "geopolitical",
                "macro": "macro_extended",
                "sentiment": "sentiment_extended",
                "volatility": "volatility_data",
                "institutional": "institutional_data",
            }

            for domain_key, resp in fetched:
                if resp and resp.ok:
                    results["_responses"][domain_key] = resp
                    enrichment_key = _domain_to_key.get(domain_key, domain_key)
                    results[enrichment_key] = resp.data

        except ImportError:
            logger.debug("EDPL not fully configured — skipping enrichment")
        except Exception as exc:
            logger.debug(f"EDPL enrichment failed: {exc}")

        return results

