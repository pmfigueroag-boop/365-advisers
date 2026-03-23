"""
src/routes/analysis.py
──────────────────────────────────────────────────────────────────────────────
Analysis API endpoints — extracted from main.py.

Provides:
  - /analysis/combined/stream  (SSE, primary)
  - /analysis/fundamental/stream (SSE)
  - /analysis/technical (JSON)
  - /analyze/stream (legacy SSE)
  - /analyze (legacy blocking)
  - /compare
  - /ticker-info
"""

from __future__ import annotations

import asyncio
import logging
import time as _time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.services.cache_manager import cache_manager
from src.orchestration.sse_streamer import sse, replay_fundamental_cache, replay_legacy_cache
from src.orchestration.analysis_pipeline import AnalysisPipeline
from src.engines.fundamental.graph import run_fundamental_stream
from src.data.market_data import fetch_technical_data
from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine
from src.engines.technical.formatter import build_technical_summary
from src.engines.technical.regime_detector import (
    TrendRegimeDetector,
    VolatilityRegimeDetector,
    combine_regime_adjustments,
)
from src.utils.helpers import sanitize_data

logger = logging.getLogger("365advisers.routes.analysis")

from src.auth.dependencies import get_current_user

router = APIRouter(tags=["Analysis"], dependencies=[Depends(get_current_user)])

# Cache aliases
cache = cache_manager.analysis
tech_cache = cache_manager.technical
fund_cache = cache_manager.fundamental
decision_cache = cache_manager.decision

# Pipeline instance
pipeline = AnalysisPipeline(fund_cache, tech_cache, decision_cache)


class AnalysisRequest(BaseModel):
    ticker: str


# ─── Combined Analysis (primary endpoint) ────────────────────────────────────

@router.get("/analysis/combined/stream")
async def combined_analysis_stream(ticker: str, force: bool = False):
    """SSE stream: Fundamental + Technical + Scoring + Decision."""
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    return StreamingResponse(
        pipeline.run_combined_stream(ticker, force),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Fundamental Analysis ────────────────────────────────────────────────────

@router.get("/analysis/fundamental/stream")
async def fundamental_analysis_stream(ticker: str, force: bool = False):
    """SSE stream for the Fundamental Analysis Engine."""
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    symbol = ticker.upper().strip()

    if not force:
        cached = fund_cache.get(symbol)
        if cached:
            logger.info(f"FUND-CACHE HIT for {symbol}")
            return StreamingResponse(
                replay_fundamental_cache(cached),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    async def event_generator():
        collected_events = []
        try:
            async for event_dict in run_fundamental_stream(symbol):
                event_name = event_dict.get("event", "")
                data = event_dict.get("data", {})
                yield sse(event_name, data)
                if event_name not in ("done", "error"):
                    collected_events.append({"event": event_name, "data": data})
            if collected_events:
                fund_cache.set(symbol, {"events": collected_events})
        except Exception as exc:
            import traceback; traceback.print_exc()
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─── Technical Analysis ──────────────────────────────────────────────────────

@router.get("/analysis/technical")
async def get_technical_analysis(ticker: str, force: bool = False):
    """Run the full Technical Engine + MTF analysis. Cache TTL: 15 minutes."""
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    symbol = ticker.upper().strip()

    if not force:
        cached = tech_cache.get(symbol)
        if cached:
            logger.info(f"TECH-CACHE HIT for {symbol}")
            return {**cached, "from_cache": True}

    start = _time.monotonic_ns() / 1e6
    try:
        tech_data = await asyncio.to_thread(fetch_technical_data, symbol)
        indicators = await asyncio.to_thread(IndicatorEngine.compute, tech_data)

        # ── Regime detection ──────────────────────────────────────────────
        raw_inds = tech_data.get("indicators", {})
        trend_regime = TrendRegimeDetector.detect(
            adx=raw_inds.get("adx", 20.0),
            plus_di=raw_inds.get("plus_di", 20.0),
            minus_di=raw_inds.get("minus_di", 20.0),
        )
        vol_regime = VolatilityRegimeDetector.detect(
            ohlcv=tech_data.get("ohlcv", []),
            current_bb_upper=raw_inds.get("bb_upper", 0.0),
            current_bb_lower=raw_inds.get("bb_lower", 0.0),
            current_atr=raw_inds.get("atr", 0.0),
        )
        regime_adj = combine_regime_adjustments(trend_regime, vol_regime)

        score = await asyncio.to_thread(
            ScoringEngine.compute, indicators, None, regime_adj
        )
        summary = build_technical_summary(
            ticker=symbol, tech_data=tech_data, result=indicators,
            score=score, processing_start_ms=start,
            trend_regime=trend_regime, vol_regime=vol_regime,
        )

        # ── Multi-Timeframe Analysis ──────────────────────────────────────
        mtf_block = None
        try:
            from src.data.providers.market_metrics import fetch_multi_timeframe
            from src.engines.technical.mtf_scorer import MultiTimeframeScorer

            exchange = tech_data.get("exchange", "NASDAQ")
            mtf_data = await asyncio.to_thread(fetch_multi_timeframe, symbol, exchange)
            if mtf_data:
                mtf_result = MultiTimeframeScorer.compute(mtf_data, regime_adjustments=regime_adj)
                mtf_block = {
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
                    f"MTF: {symbol} — aggregate={mtf_result.mtf_aggregate}, "
                    f"agreement={mtf_result.agreement_level} ({mtf_result.agreement_count}/4)"
                )
        except Exception as mtf_exc:
            logger.warning(f"MTF analysis failed for {symbol}: {mtf_exc}")

        summary["mtf"] = mtf_block
        summary["from_cache"] = False
        tech_cache.set(symbol, summary)
        return summary
    except Exception as exc:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500,
                            detail=f"Technical analysis failed for {symbol}: {str(exc)}")


# ─── Ticker Info ──────────────────────────────────────────────────────────────

@router.get("/ticker-info")
async def ticker_info(ticker: str):
    """Fast endpoint: name + price. Used when adding to watchlist."""
    import yfinance as yf
    symbol = ticker.upper().strip()

    cached = cache.get_ticker_info(symbol)
    if cached:
        return cached

    try:
        info = yf.Ticker(symbol).info or {}
        result = {
            "ticker": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "exchange": info.get("exchange", ""),
        }
        cache.set_ticker_info(symbol, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch ticker info: {e}")


# ─── Comparison ───────────────────────────────────────────────────────────────

@router.get("/compare")
async def compare_tickers(tickers: str):
    """Run analysis for up to 3 tickers in parallel."""
    raw = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not raw:
        raise HTTPException(status_code=400, detail="Provide at least one ticker")
    symbols = raw[:3]

    async def _run_single(symbol: str) -> dict:
        entry = cache.get(symbol)
        if entry:
            return {
                "ticker": symbol,
                "name": entry["data_ready"].get("name", symbol),
                "price": entry["data_ready"].get("price"),
                "from_cache": True,
                "agents": entry["agents"],
                "fundamental_metrics": entry["data_ready"].get("fundamental_metrics", {}),
                "dalio": entry["dalio"],
                "error": None,
            }
        try:
            from graph import app_graph
            initial_state = {
                "ticker": symbol,
                "financial_data": {}, "macro_data": {},
                "chart_data": {"prices": [], "cashflow": []},
                "agent_responses": [], "final_verdict": "", "dalio_response": {},
            }
            result = await app_graph.ainvoke(initial_state)
            f_data = result.get("financial_data", {})
            fundamentals = f_data.get("fundamental_engine", {})
            info = f_data.get("info", {})

            agents = [sanitize_data({
                "agent_name": r.get("agent_name", ""),
                "signal": r.get("signal", ""),
                "confidence": r.get("confidence", 0),
                "analysis": r.get("analysis", ""),
                "selected_metrics": r.get("selected_metrics", []),
            }) for r in result.get("agent_responses", [])]

            dalio = sanitize_data({
                "final_verdict": result.get("final_verdict", ""),
                "dalio_response": result.get("dalio_response", {}),
            })

            data_ready = sanitize_data({
                "ticker": symbol,
                "name": info.get("shortName") or info.get("longName") or symbol,
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "fundamental_metrics": fundamentals,
                "tech_indicators": f_data.get("tech_indicators", {}),
                "tradingview": f_data.get("tradingview", {}),
                "from_cache": False, "cached_at": None,
            })
            cache.set(symbol, data_ready, agents, dalio)

            return {
                "ticker": symbol,
                "name": data_ready.get("name", symbol),
                "price": data_ready.get("price"),
                "from_cache": False,
                "agents": agents,
                "fundamental_metrics": fundamentals,
                "dalio": dalio,
                "error": None,
            }
        except Exception as e:
            return {"ticker": symbol, "error": str(e), "agents": [], "dalio": {},
                    "fundamental_metrics": {}}

    results = await asyncio.gather(*[_run_single(s) for s in symbols])
    return sanitize_data({"results": list(results)})


# ─── Legacy Endpoints ─────────────────────────────────────────────────────────

@router.get("/analyze/stream")
async def analyze_stream(ticker: str, force: bool = False):
    """Legacy SSE endpoint. Serves from cache when available."""
    logger.warning(f"DEPRECATED: /analyze/stream called for {ticker} — migrate to /analysis/combined/stream")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")
    symbol = ticker.upper().strip()

    if not force:
        entry = cache.get(symbol)
        if entry:
            return StreamingResponse(
                replay_legacy_cache(symbol, entry),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                         "Connection": "keep-alive"},
            )

    async def _live():
        from graph import run_analysis_stream
        collected = {"data_ready": {}, "agents": [], "dalio": {}}
        async for event in run_analysis_stream(symbol):
            event_name = event.get("event")
            data = event.get("data", {})
            if event_name == "data_ready":
                data = dict(data)
                data["from_cache"] = False
                data["cached_at"] = None
                collected["data_ready"] = data
                yield sse("data_ready", data)
            elif event_name == "agent_update":
                collected["agents"].append(data)
                yield sse("agent_update", data)
            elif event_name == "dalio_verdict":
                collected["dalio"] = data
                yield sse("dalio_verdict", data)
            elif event_name == "done":
                if collected["data_ready"] and collected["agents"] and collected["dalio"]:
                    cache.set(symbol, collected["data_ready"], collected["agents"], collected["dalio"])
                yield sse("done", {})
            elif event_name == "error":
                yield sse("error", data)

    return StreamingResponse(
        _live(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@router.post("/analyze")
async def analyze_stock(request: AnalysisRequest):
    """Legacy blocking endpoint."""
    try:
        from graph import app_graph
        logger.info(f"Starting analysis for ticker: {request.ticker}")
        initial_state = {
            "ticker": request.ticker,
            "financial_data": {}, "macro_data": {},
            "chart_data": {"prices": [], "cashflow": []},
            "agent_responses": [], "final_verdict": "", "dalio_response": {},
        }
        result = await app_graph.ainvoke(initial_state)
        f_engine = result.get("financial_data", {}).get("fundamental_engine", {})
        return sanitize_data({
            "ticker": result.get("ticker", request.ticker),
            "agent_responses": result.get("agent_responses", []),
            "final_verdict": result.get("final_verdict", "No final verdict generated."),
            "chart_data": result.get("chart_data", {"prices": [], "cashflow": []}),
            "fundamental_metrics": f_engine,
            "dalio_response": result.get("dalio_response", {}),
            "tradingview": result.get("financial_data", {}).get("tradingview", {}),
        })
    except Exception as e:
        logger.error(f"CRITICAL ERROR in /analyze for {request.ticker}: {str(e)}")
        import traceback; traceback.print_exc()
        return sanitize_data({
            "ticker": request.ticker,
            "agent_responses": [],
            "final_verdict": f"Error during analysis: {str(e)}",
            "chart_data": {"prices": [], "cashflow": []},
        })
