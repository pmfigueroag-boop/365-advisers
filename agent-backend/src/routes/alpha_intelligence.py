"""
src/routes/alpha_intelligence.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the Alpha Decision Intelligence Platform.

9 endpoints covering all 5 alpha engines + multi-strategy ranking +
alert stream + combined dashboard.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
from src.engines.alpha_macro.engine import AlphaMacroEngine
from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
from src.engines.alpha_event.engine import AlphaEventEngine
from src.engines.alpha_multi.engine import MultiStrategyAlphaEngine
from src.engines.alpha_alerts.engine import AlertEngine

logger = logging.getLogger("365advisers.routes.alpha_intelligence")

router = APIRouter(prefix="/alpha", tags=["Alpha Intelligence"])

# Engine instances (stateless — safe as singletons)
_fundamental = AlphaFundamentalEngine()
_macro = AlphaMacroEngine()
_sentiment = AlphaSentimentEngine()
_volatility = AlphaVolatilityEngine()
_event = AlphaEventEngine()
_multi = MultiStrategyAlphaEngine()
_alerts = AlertEngine()


# ── Fundamental ───────────────────────────────────────────────────────────────

@router.get("/fundamental/{symbol}")
async def fundamental_analysis(symbol: str) -> dict[str, Any]:
    """Fundamental score + subscore breakdown for a symbol."""
    # In production: fetch from FMP/AV/Finnhub via EDPL, extract features
    # For now: accept optional query params as a data bridge
    result = _fundamental.analyze(symbol.upper(), ratios={}, growth_data={})
    return {"symbol": symbol.upper(), "score": result.model_dump()}


@router.get("/fundamental/ranking")
async def fundamental_ranking() -> dict[str, Any]:
    """Top fundamentally attractive stocks."""
    # In production: iterate watchlist, score each
    return {"rankings": [], "message": "Provide ticker scores via POST for ranking"}


# ── Macro ─────────────────────────────────────────────────────────────────────

@router.get("/macro/dashboard")
async def macro_dashboard(
    gdp_growth: float = Query(default=2.5),
    inflation: float = Query(default=3.2),
    unemployment: float = Query(default=3.8),
    interest_rate: float = Query(default=5.25),
    yield_curve_spread: float = Query(default=0.3),
    pmi: float = Query(default=52),
) -> dict[str, Any]:
    """Macro regime detection + allocation suggestions."""
    indicators = {
        "gdp_growth": gdp_growth, "inflation": inflation,
        "unemployment": unemployment, "interest_rate": interest_rate,
        "yield_curve_spread": yield_curve_spread, "pmi": pmi,
    }
    result = _macro.analyze(indicators)
    return {"dashboard": result.model_dump()}


# ── Sentiment ─────────────────────────────────────────────────────────────────

@router.get("/sentiment/{symbol}")
async def sentiment_analysis(symbol: str) -> dict[str, Any]:
    """Sentiment score + hype/panic signals for a symbol."""
    # Data bridge: empty data returns neutral baseline
    result = _sentiment.analyze(symbol.upper(), {})
    return {"symbol": symbol.upper(), "score": result.model_dump()}


# ── Volatility ────────────────────────────────────────────────────────────────

@router.get("/volatility/dashboard")
async def volatility_dashboard(
    vix_current: float = Query(default=18.0),
    iv_rank: float = Query(default=45.0),
    realized_vol: float = Query(default=15.0),
    iv_current: float = Query(default=20.0),
    term_structure_slope: float = Query(default=0.5),
) -> dict[str, Any]:
    """Volatility regime + VIX analysis + risk indicators."""
    data = {
        "vix_current": vix_current, "iv_rank": iv_rank,
        "realized_vol": realized_vol, "iv_current": iv_current,
        "term_structure_slope": term_structure_slope,
        "vix_1yr_avg": 16.5, "vix_1yr_max": 35.0,
    }
    result = _volatility.analyze(data)
    return {"dashboard": result.model_dump()}


# ── Events ────────────────────────────────────────────────────────────────────

@router.get("/events/{symbol}")
async def event_analysis(symbol: str) -> dict[str, Any]:
    """Event timeline + catalyst scores + alerts for a symbol."""
    score = _event.score_ticker(symbol.upper(), [])
    return {"symbol": symbol.upper(), "score": score.model_dump()}


# ── Multi-Strategy Ranking ────────────────────────────────────────────────────

@router.post("/ranking")
async def alpha_ranking(ticker_scores: list[dict]) -> dict[str, Any]:
    """Multi-strategy asset ranking from sub-engine scores."""
    result = _multi.rank(ticker_scores)
    return {"ranking": result.model_dump()}


@router.get("/heatmap")
async def opportunity_heatmap() -> dict[str, Any]:
    """Opportunity heatmap (multi-dimension)."""
    return {"heatmap": [], "message": "POST to /alpha/ranking with ticker scores to generate heatmap"}


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def active_alerts() -> dict[str, Any]:
    """Active alert stream from all engines."""
    # In production: evaluate latest cached engine outputs
    stream = _alerts.evaluate()
    return {"alerts": stream.model_dump()}


# ── Combined Dashboard ────────────────────────────────────────────────────────

@router.get("/dashboard")
async def executive_dashboard() -> dict[str, Any]:
    """Combined executive intelligence dashboard."""
    # Aggregate latest state from all engines
    macro = _macro.analyze({
        "gdp_growth": 2.5, "inflation": 3.2, "unemployment": 3.8,
        "yield_curve_spread": 0.3, "pmi": 52,
    })
    vol = _volatility.analyze({"vix_current": 18.0, "iv_rank": 45})
    stream = _alerts.evaluate(macro_score=macro.score, vol_score=vol.score)

    return {
        "macro_regime": macro.score.regime.value,
        "macro_score": macro.score.composite_score,
        "vol_regime": vol.score.regime.value,
        "vol_risk": vol.score.composite_risk,
        "active_alerts": len(stream.alerts),
        "critical_alerts": stream.total_critical,
        "allocation": macro.allocation.model_dump(),
    }
