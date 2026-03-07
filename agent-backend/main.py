"""
main_v2.py
──────────────────────────────────────────────────────────────────────────────
365 Advisers API — lean entrypoint (v3.0)

All business logic has been extracted to:
  - src/routes/          → API endpoints
  - src/orchestration/   → pipeline + SSE streaming
  - src/engines/         → analysis engines
  - src/data/            → providers + repositories

This file only handles: app creation, middleware, router mounts, startup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.data.database import init_db

# ── Configuration ────────────────────────────────────────────────────────────

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(name)-28s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("365advisers.main")


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database and EDPL on startup."""
    init_db()

    # ── EDPL Initialisation ───────────────────────────────────────────────
    from src.data.external.registry import ProviderRegistry
    from src.data.external.health import HealthChecker
    from src.data.external.fallback import FallbackRouter
    from src.data.external.base import DataDomain
    from src.data.external.contracts.enhanced_market import EnhancedMarketData
    from src.data.external.contracts.etf_flows import ETFFlowData
    from src.data.external.contracts.options import OptionsIntelligence
    from src.data.external.contracts.institutional import InstitutionalFlowData
    from src.data.external.contracts.sentiment import NewsSentimentData
    from src.data.external.contracts.macro import MacroContext
    from src.routes.providers import init_provider_routes

    registry = ProviderRegistry()
    health_checker = HealthChecker(
        failure_threshold=settings.EDPL_CB_FAILURE_THRESHOLD,
        recovery_timeout=settings.EDPL_CB_RECOVERY_TIMEOUT,
    )
    fallback_router = FallbackRouter(
        registry=registry,
        health_checker=health_checker,
        null_factories={
            DataDomain.MARKET_DATA: EnhancedMarketData.empty,
            DataDomain.ETF_FLOWS: ETFFlowData.empty,
            DataDomain.OPTIONS: OptionsIntelligence.empty,
            DataDomain.INSTITUTIONAL: InstitutionalFlowData.empty,
            DataDomain.SENTIMENT: NewsSentimentData.empty,
            DataDomain.MACRO: MacroContext.default,
        },
    )

    # Store on app state for access by routes / engines
    app.state.edpl_registry = registry
    app.state.edpl_health = health_checker
    app.state.edpl_router = fallback_router

    # Inject into provider routes
    init_provider_routes(registry, health_checker)

    # ── Register concrete adapters (conditional on API keys) ─────────────
    if settings.POLYGON_API_KEY and settings.EDPL_ENABLE_MARKET_DATA:
        from src.data.external.adapters.polygon import PolygonAdapter
        polygon = PolygonAdapter()
        registry.register(polygon)
        health_checker.register_provider(polygon.name, polygon.domain)
        logger.info("Polygon.io adapter registered")

    if settings.EDPL_ENABLE_ETF_FLOWS:
        from src.data.external.adapters.etf_flows import ETFFlowAdapter
        etf = ETFFlowAdapter()
        registry.register(etf)
        health_checker.register_provider(etf.name, etf.domain)
        logger.info("ETF Flow adapter registered")

    if settings.EDPL_ENABLE_OPTIONS:
        from src.data.external.adapters.options import OptionsAdapter
        opts = OptionsAdapter()
        registry.register(opts)
        health_checker.register_provider(opts.name, opts.domain)
        logger.info("Options adapter registered")

    if settings.EDPL_ENABLE_INSTITUTIONAL:
        from src.data.external.adapters.institutional import InstitutionalAdapter
        inst = InstitutionalAdapter()
        registry.register(inst)
        health_checker.register_provider(inst.name, inst.domain)
        logger.info("Institutional adapter registered")

    if settings.EDPL_ENABLE_SENTIMENT:
        from src.data.external.adapters.news_sentiment import NewsSentimentAdapter
        sentiment = NewsSentimentAdapter()
        registry.register(sentiment)
        health_checker.register_provider(sentiment.name, sentiment.domain)
        logger.info("News/Sentiment adapter registered")

    if settings.EDPL_ENABLE_MACRO:
        from src.data.external.adapters.macro import MacroAdapter
        macro = MacroAdapter()
        registry.register(macro)
        health_checker.register_provider(macro.name, macro.domain)
        logger.info("Macro adapter registered")

    logger.info("EDPL initialised — %d adapters registered across %d domains", sum(
        len(registry.get_all(d)) for d in registry.list_domains()
    ), len(registry.list_domains()))
    logger.info("365 Advisers API started (v3.2 — full EDPL)")
    yield


# ── App Creation ─────────────────────────────────────────────────────────────

app = FastAPI(title="365 Advisers API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ────────────────────────────────────────────────────────────

from src.middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, max_requests=30, window_seconds=60)


# ── Router Mounts ────────────────────────────────────────────────────────────

from src.routes.health import router as health_router
from src.routes.analysis import router as analysis_router
from src.routes.cache import router as cache_router
from src.routes.portfolio import router as portfolio_router
from src.routes.ideas import router as ideas_router
from src.routes.signals import router as signals_router
from src.routes.backtest import router as backtest_router
from src.routes.ranking import router as ranking_router
from src.routes.monitoring import router as monitoring_router
from src.routes.crowding import router as crowding_router
from src.routes.validation import router as validation_router
from src.routes.governance import router as governance_router
from src.routes.scorecard import router as scorecard_router
from src.routes.shadow import router as shadow_router
from src.routes.strategy import router as strategy_router
from src.routes.liquidity import router as liquidity_router
from src.routes.providers import router as providers_router
from src.routes.research import router as research_router
from src.routes.signal_lab import router as signal_lab_router
from src.routes.strategy_lab import router as strategy_lab_router

app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(cache_router)
app.include_router(portfolio_router)
app.include_router(ideas_router)
app.include_router(signals_router)
app.include_router(backtest_router)
app.include_router(ranking_router)
app.include_router(monitoring_router)
app.include_router(crowding_router)
app.include_router(validation_router)
app.include_router(governance_router)
app.include_router(scorecard_router)
app.include_router(shadow_router)
app.include_router(strategy_router)
app.include_router(liquidity_router)
app.include_router(providers_router)
app.include_router(research_router)
app.include_router(signal_lab_router)
app.include_router(strategy_lab_router)

logger.info(f"Mounted {len(app.routes)} routes across 20 routers")


# ── Dev Server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
