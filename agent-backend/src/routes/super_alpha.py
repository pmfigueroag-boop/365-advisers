"""
src/routes/super_alpha.py
──────────────────────────────────────────────────────────────────────────────
REST API for the Super Alpha Engine — 8-factor quantitative scoring,
composite ranking, factor exposures, alerts, and explainability.

Endpoints:
  GET  /super-alpha/score/{symbol}    — full composite score + factor breakdown
  POST /super-alpha/ranking           — multi-asset ranking
  GET  /super-alpha/factors/{symbol}  — factor exposure detail
  GET  /super-alpha/dashboard         — executive summary
  GET  /super-alpha/alerts            — active alert stream
  GET  /super-alpha/regime            — market regime snapshot
  GET  /super-alpha/heatmap           — factor heatmap data
  POST /super-alpha/explain/{symbol}  — explainability report
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Body, Query
from pydantic import BaseModel, Field

from src.engines.super_alpha.engine import SuperAlphaEngine
from src.engines.super_alpha.alerts import SuperAlphaAlertEngine
from src.engines.super_alpha.models import FactorName

logger = logging.getLogger("365advisers.routes.super_alpha")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/super-alpha", tags=["Super Alpha Engine"], dependencies=[Depends(get_current_user)])

# Engine instances (stateless — safe as singletons)
_engine = SuperAlphaEngine()
_alert_engine = SuperAlphaAlertEngine()


# ── Request Models ────────────────────────────────────────────────────────────

class AssetDataInput(BaseModel):
    """Input data for a single asset."""
    ticker: str
    # Value
    pe_ratio: float | None = None
    ev_to_ebitda: float | None = None
    pb_ratio: float | None = None
    fcf_yield: float | None = None
    # Momentum
    return_3m: float | None = None
    return_6m: float | None = None
    return_12m: float | None = None
    price_to_sma200: float | None = None
    # Quality
    roic: float | None = None
    operating_margin: float | None = None
    earnings_stability: float | None = None
    debt_to_equity: float | None = None
    # Size
    market_cap: float | None = None
    avg_daily_volume_usd: float | None = None
    # Volatility
    vix_current: float | None = None
    iv_rank: float | None = None
    realized_vol: float | None = None
    iv_current: float | None = None
    term_structure_slope: float | None = None
    # Sentinel
    bullish_pct: float | None = None
    bearish_pct: float | None = None
    message_volume_24h: int | None = None
    message_volume_7d: int | None = None
    news_count: int | None = None
    # Macro
    gdp_growth: float | None = None
    inflation: float | None = None
    unemployment: float | None = None
    interest_rate: float | None = None
    yield_curve_spread: float | None = None
    pmi: float | None = None
    # Event
    events: list[dict] = Field(default_factory=list)


class RankingRequest(BaseModel):
    """Multi-asset ranking request."""
    assets: list[AssetDataInput]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/score/{symbol}")
async def score_asset(symbol: str) -> dict[str, Any]:
    """Full 8-factor Composite Alpha Score for a single asset."""
    # In production: pull data from EDPL cache / DB.
    # For now: use sensible defaults for demo
    data = _build_demo_data()
    profile = _engine.score_asset(symbol.upper(), data)
    return {"symbol": symbol.upper(), "profile": profile.model_dump()}


@router.post("/ranking")
async def rank_universe(request: RankingRequest) -> dict[str, Any]:
    """Rank multiple assets by Composite Alpha Score."""
    assets = [(a.ticker.upper(), a.model_dump()) for a in request.assets]
    ranking = _engine.rank_universe(assets)
    return {"ranking": ranking.model_dump()}


@router.get("/factors/{symbol}")
async def factor_exposures(symbol: str) -> dict[str, Any]:
    """Radar-chart-ready factor exposure for a single asset."""
    data = _build_demo_data()
    profile = _engine.score_asset(symbol.upper(), data)
    exposures = _engine.get_factor_exposures([profile])
    return {
        "symbol": symbol.upper(),
        "exposures": exposures[0].model_dump() if exposures else {},
    }


@router.get("/dashboard")
async def executive_dashboard() -> dict[str, Any]:
    """Executive summary: top/bottom assets, regime, alerts."""
    # Demo universe
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
               "META", "TSLA", "JPM", "V", "JNJ"]
    assets = [(t, _build_demo_data(t)) for t in tickers]
    ranking = _engine.rank_universe(assets)
    alerts = _alert_engine.evaluate(ranking.rankings)
    heatmap = _engine.get_factor_exposures(ranking.rankings)

    return {
        "ranking": ranking.model_dump(),
        "alerts": [a.model_dump() for a in alerts],
        "heatmap": [h.model_dump() for h in heatmap],
        "regime": ranking.market_regime,
    }


@router.get("/alerts")
async def active_alerts() -> dict[str, Any]:
    """Active alert stream from factor analysis."""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
    assets = [(t, _build_demo_data(t)) for t in tickers]
    ranking = _engine.rank_universe(assets)
    alerts = _alert_engine.evaluate(ranking.rankings)
    return {"alerts": [a.model_dump() for a in alerts], "total": len(alerts)}


@router.get("/regime")
async def market_regime() -> dict[str, Any]:
    """Current market regime snapshot from macro + volatility factors."""
    from src.engines.alpha_macro.engine import AlphaMacroEngine
    from src.engines.alpha_volatility.engine import AlphaVolatilityEngine

    macro = AlphaMacroEngine().analyze({
        "gdp_growth": 2.5, "inflation": 3.2, "unemployment": 3.8,
        "yield_curve_spread": 0.3, "pmi": 52,
    })
    vol = AlphaVolatilityEngine().analyze({"vix_current": 18.0, "iv_rank": 45})

    return {
        "macro_regime": macro.score.regime.value,
        "macro_score": macro.score.composite_score,
        "vol_regime": vol.score.regime.value,
        "vol_risk": vol.score.composite_risk,
        "allocation": macro.allocation.model_dump(),
    }


@router.get("/heatmap")
async def factor_heatmap() -> dict[str, Any]:
    """Factor heatmap across a demo universe."""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
               "META", "TSLA", "JPM", "V", "JNJ"]
    assets = [(t, _build_demo_data(t)) for t in tickers]
    ranking = _engine.rank_universe(assets)
    heatmap = _engine.get_factor_exposures(ranking.rankings)
    return {"heatmap": [h.model_dump() for h in heatmap]}


@router.post("/explain/{symbol}")
async def explainability_report(
    symbol: str,
    data: AssetDataInput | None = Body(default=None),
) -> dict[str, Any]:
    """Detailed factor decomposition with variable-level contributions."""
    asset_data = data.model_dump() if data else _build_demo_data(symbol.upper())
    profile = _engine.score_asset(symbol.upper(), asset_data)

    # Build breakdown
    breakdown = {}
    for factor_name in FactorName:
        fs = getattr(profile, factor_name.value, None)
        if fs:
            breakdown[factor_name.value] = {
                "score": fs.score,
                "signals": fs.signals,
                "data_quality": fs.data_quality,
                "variables": [v.model_dump() for v in fs.variables],
            }

    return {
        "symbol": symbol.upper(),
        "composite_alpha_score": profile.composite_alpha_score,
        "tier": profile.tier.value,
        "convergence_bonus": profile.convergence_bonus,
        "volatility_adjustment": profile.volatility_adjustment,
        "factor_agreement": profile.factor_agreement,
        "top_drivers": profile.top_drivers,
        "breakdown": breakdown,
    }


# ── Demo Data Helper ──────────────────────────────────────────────────────────

def _build_demo_data(ticker: str = "DEMO") -> dict:
    """
    Generate realistic demo data for testing and demonstration.
    In production: replaced by EDPL cache / DB lookups.
    """
    import hashlib
    seed = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)

    def _vary(base: float, pct: float = 0.3) -> float:
        # Deterministic pseudo-variation based on ticker
        offset = ((seed % 100) / 100.0 - 0.5) * 2 * pct
        return base * (1 + offset)

    return {
        # Value
        "pe_ratio": _vary(20, 0.5),
        "ev_to_ebitda": _vary(14, 0.4),
        "pb_ratio": _vary(3.5, 0.5),
        "fcf_yield": _vary(0.045, 0.6),
        # Momentum
        "return_3m": _vary(0.05, 2.0),
        "return_6m": _vary(0.08, 1.5),
        "return_12m": _vary(0.12, 1.5),
        "price_to_sma200": _vary(1.05, 0.15),
        # Quality
        "roic": _vary(0.15, 0.5),
        "operating_margin": _vary(0.18, 0.5),
        "earnings_stability": min(_vary(0.75, 0.3), 1.0),
        "debt_to_equity": max(_vary(1.2, 0.6), 0.1),
        # Size
        "market_cap": _vary(50e9, 0.8),
        "avg_daily_volume_usd": _vary(15e6, 0.7),
        # Volatility
        "vix_current": _vary(18, 0.4),
        "iv_rank": _vary(45, 0.5),
        "realized_vol": _vary(15, 0.4),
        "iv_current": _vary(20, 0.4),
        "vix_1yr_avg": 16.5,
        "vix_1yr_max": 35.0,
        # Sentiment
        "bullish_pct": _vary(55, 0.4),
        "bearish_pct": _vary(30, 0.5),
        "message_volume_24h": int(_vary(500, 0.8)),
        "message_volume_7d": int(_vary(3000, 0.6)),
        "news_count": int(_vary(8, 0.5)),
        # Macro
        "gdp_growth": 2.5,
        "inflation": 3.2,
        "unemployment": 3.8,
        "interest_rate": 5.25,
        "yield_curve_spread": 0.3,
        "pmi": 52,
        # Event
        "events": [],
    }
