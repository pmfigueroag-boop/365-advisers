"""
src/routes/technical_ic.py
──────────────────────────────────────────────────────────────────────────────
Technical IC "War Room" API — SSE streaming and synchronous endpoints.

GET  /api/technical-ic/{ticker}/stream  — SSE stream of War Room session
POST /api/technical-ic/{ticker}/run     — Complete transcript (sync)
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.auth.dependencies import get_current_user
from src.utils.helpers import sanitize_data

logger = logging.getLogger("365advisers.routes.technical_ic")

router = APIRouter(
    prefix="/api/technical-ic",
    tags=["Technical IC"],
    dependencies=[Depends(get_current_user)],
)


async def _build_engine_data(ticker: str) -> dict:
    """
    Assemble the engine_data dict required by the War Room.

    Runs the full TechnicalEngine pipeline to produce real computed data
    that agents must cite — they cannot invent data.
    """
    from src.data.market_data import fetch_technical_data
    from src.engines.technical.indicators import IndicatorEngine
    from src.engines.technical.scoring import ScoringEngine
    from src.engines.technical.regime_detector import (
        TrendRegimeDetector, VolatilityRegimeDetector, combine_regime_adjustments,
    )
    from src.engines.technical.calibration import get_asset_context
    from src.engines.technical.formatter import build_technical_summary
    import time as _time

    start_ms = _time.monotonic_ns() / 1e6

    tech_data = await asyncio.to_thread(fetch_technical_data, ticker)
    if not tech_data or "error" in tech_data:
        raise ValueError(f"Failed to fetch technical data for {ticker}")

    indicators = await asyncio.to_thread(IndicatorEngine.compute, tech_data)

    # Regime detection
    raw_inds = tech_data.get("indicators", {})
    trend_regime = TrendRegimeDetector.detect(
        adx=raw_inds.get("adx", 20.0) or 20.0,
        plus_di=raw_inds.get("plus_di", 20.0) or 20.0,
        minus_di=raw_inds.get("minus_di", 20.0) or 20.0,
    )
    vol_regime = VolatilityRegimeDetector.detect(
        ohlcv=tech_data.get("ohlcv", []),
        current_bb_upper=raw_inds.get("bb_upper", 0.0) or 0.0,
        current_bb_lower=raw_inds.get("bb_lower", 0.0) or 0.0,
        current_atr=raw_inds.get("atr", 0.0) or 0.0,
    )
    regime_adj = combine_regime_adjustments(trend_regime, vol_regime)

    # Scoring
    price = tech_data.get("current_price", 0.0) or 0.0
    asset_ctx = get_asset_context(
        ohlcv=tech_data.get("ohlcv", []),
        ticker=ticker,
        price=price,
    )
    score = await asyncio.to_thread(
        ScoringEngine.compute, indicators, None, regime_adj,
        trend_regime.regime, price, asset_ctx,
    )

    module_scores = [
        {
            "name": "trend",
            "details": {
                "sma_50": indicators.trend.sma_50,
                "sma_200": indicators.trend.sma_200,
                "ema_20": indicators.trend.ema_20,
                "macd_value": indicators.trend.macd_value,
                "macd_signal": indicators.trend.macd_signal,
                "macd_histogram": indicators.trend.macd_histogram,
                "price_vs_sma50": indicators.trend.price_vs_sma50,
                "price_vs_sma200": indicators.trend.price_vs_sma200,
                "golden_cross": indicators.trend.golden_cross,
                "death_cross": indicators.trend.death_cross,
                "cross_age_bars": indicators.trend.cross_age_bars,
            },
        },
        {
            "name": "momentum",
            "details": {
                "rsi": indicators.momentum.rsi,
                "rsi_zone": indicators.momentum.rsi_zone,
                "stoch_k": indicators.momentum.stoch_k,
                "stoch_d": indicators.momentum.stoch_d,
                "divergence": indicators.momentum.divergence,
                "divergence_strength": indicators.momentum.divergence_strength,
            },
        },
        {
            "name": "volatility",
            "details": {
                "bb_position": indicators.volatility.bb_position,
                "bb_width": indicators.volatility.bb_width,
                "atr": indicators.volatility.atr,
                "atr_pct": indicators.volatility.atr_pct,
                "condition": indicators.volatility.condition,
            },
        },
        {
            "name": "volume",
            "details": {
                "obv_trend": indicators.volume.obv_trend,
                "volume_vs_avg": indicators.volume.volume_vs_avg,
                "volume_price_confirmation": indicators.volume.volume_price_confirmation,
            },
        },
        {
            "name": "structure",
            "details": {
                "nearest_resistance": indicators.structure.nearest_resistance,
                "nearest_support": indicators.structure.nearest_support,
                "distance_to_resistance_pct": indicators.structure.distance_to_resistance_pct,
                "distance_to_support_pct": indicators.structure.distance_to_support_pct,
                "market_structure": indicators.structure.market_structure,
                "breakout_probability": indicators.structure.breakout_probability,
                "patterns": indicators.structure.patterns,
                "level_strength": indicators.structure.level_strength,
            },
        },
    ]

    # MTF data for the MTF Specialist (best effort)
    mtf_data = None
    try:
        from src.data.providers.market_metrics import fetch_multi_timeframe
        from src.engines.technical.mtf_scorer import MultiTimeframeScorer

        exchange = tech_data.get("exchange", "NASDAQ")
        raw_mtf = await asyncio.to_thread(fetch_multi_timeframe, ticker, exchange)
        if raw_mtf:
            mtf_result = MultiTimeframeScorer.compute(raw_mtf, regime_adjustments=regime_adj)
            mtf_data = {
                ts.timeframe: {"trend": ts.trend_status}
                for ts in mtf_result.timeframe_scores
            }
            # Add MTF as a domain for the MTF Specialist agent
            module_scores.append({
                "name": "mtf",
                "details": {
                    "agreement_level": mtf_result.agreement_level,
                    "agreement_count": mtf_result.agreement_count,
                    "timeframe_trends": {
                        ts.timeframe: ts.trend_status
                        for ts in mtf_result.timeframe_scores
                    },
                },
            })
    except Exception as mtf_exc:
        logger.warning(f"MTF data unavailable for {ticker}: {mtf_exc}")

    # Sector-relative (best effort)
    sector_rel = {"status": "NO_DATA", "relative_strength": 0.0}
    try:
        from src.engines.technical.sector_relative import SectorRelativeModule
        sr_module = SectorRelativeModule()
        sr_result = sr_module.compute(
            price=price,
            indicators={"ticker": ticker},
            ohlcv=tech_data.get("ohlcv", []),
            ctx=asset_ctx,
        )
        sector_rel = {
            "status": sr_result.status,
            "relative_strength": sr_result.relative_strength,
            "sector_etf": sr_result.sector_etf,
        }
    except Exception as sr_exc:
        logger.warning(f"Sector-relative data unavailable for {ticker}: {sr_exc}")

    return {
        "module_scores": module_scores,
        "regime": {
            "trend_regime": trend_regime.regime,
            "adx": trend_regime.adx,
            "di_spread": trend_regime.di_spread,
            "volatility_regime": vol_regime.regime,
            "bb_width_ratio": vol_regime.bb_width_ratio,
            "atr_trend": vol_regime.atr_trend,
        },
        "asset_context": {
            "optimal_atr_pct": asset_ctx.optimal_atr_pct,
            "avg_daily_range_pct": asset_ctx.avg_daily_range_pct,
            "bb_width_median": asset_ctx.bb_width_median,
            "bars_available": asset_ctx.bars_available,
        },
        "sector_relative": sector_rel,
        "mtf_data": mtf_data,
        "current_price": price,
    }


# ─── SSE Streaming ───────────────────────────────────────────────────────────

async def _sse_generator(ticker: str):
    """Wrap War Room stream events into SSE text format."""
    try:
        engine_data = await _build_engine_data(ticker)

        from src.engines.technical.war_room.debate import TechnicalWarRoom
        debate = TechnicalWarRoom()
        async for event in debate.run_stream(ticker, engine_data):
            event_name = event.get("event", "tic_update")
            data = sanitize_data(event.get("data", {}))
            yield f"event: {event_name}\ndata: {json.dumps(data, default=str)}\n\n"

    except Exception as exc:
        logger.error(f"Tech IC stream error for {ticker}: {exc}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"


@router.get("/{ticker}/stream")
async def stream_technical_ic(ticker: str):
    """
    SSE stream of a full Technical IC War Room session.

    Events (in order):
      tic_members         — war room member identities
      tic_round_assess    — each agent's assessment (×6)
      tic_round_conflict  — each conflict pair
      tic_round_timeframe — each agent's timeframe reconciliation (×6)
      tic_round_vote      — each vote (×6)
      tic_verdict         — Head Technician's synthesis + action plan
      tic_done            — session complete
    """
    symbol = ticker.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    return StreamingResponse(
        _sse_generator(symbol),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{ticker}/run")
async def run_technical_ic(ticker: str):
    """Run a complete Technical IC session synchronously."""
    symbol = ticker.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    try:
        engine_data = await _build_engine_data(symbol)

        from src.engines.technical.war_room.debate import TechnicalWarRoom
        debate = TechnicalWarRoom()
        transcript = await debate.run_full(symbol, engine_data)
        return sanitize_data(transcript.model_dump(mode="json"))

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Tech IC run error for {symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
