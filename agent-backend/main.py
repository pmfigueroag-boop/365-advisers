"""
main_v2.py
──────────────────────────────────────────────────────────────────────────────
365 Advisers API — lean entrypoint (v4.0)

All business logic has been extracted to:
  - src/routes/          → API endpoints
  - src/orchestration/   → pipeline + SSE streaming
  - src/engines/         → analysis engines
  - src/data/            → providers + repositories

This file only handles: app creation, middleware, router mounts, startup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
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
    """Initialise the database, EDPL, and observability on startup."""
    init_db()

    # ── OpenTelemetry Initialisation ──────────────────────────────────
    from src.observability import init_telemetry
    init_telemetry(settings.OTEL_SERVICE_NAME)

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
    from src.data.external.contracts.filing_event import FilingEventData
    from src.data.external.contracts.asset_profile import AssetProfile
    from src.data.external.contracts.sentiment_signal import SentimentSignal
    from src.data.external.contracts.alternative_signal import AlternativeSignal
    from src.data.external.contracts.volatility_snapshot import VolatilitySnapshot
    from src.routes.providers import init_provider_routes
    from src.routes.market_data_api import init_market_data_routes
    from src.data.external.scheduler import SyncManager

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
            DataDomain.FILING_EVENTS: FilingEventData.empty,
            DataDomain.FUNDAMENTAL: AssetProfile.empty,
            DataDomain.ALTERNATIVE: AlternativeSignal.empty,
            DataDomain.VOLATILITY: VolatilitySnapshot.empty,
        },
    )
    sync_manager = SyncManager()

    # Store on app state for access by routes / engines
    app.state.edpl_registry = registry
    app.state.edpl_health = health_checker
    app.state.edpl_router = fallback_router

    # Inject into provider routes
    init_provider_routes(registry, health_checker)
    init_market_data_routes(fallback_router, sync_manager)

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

    # ── New adapters (multi-source integration layer) ─────────────────────
    if settings.ALPHA_VANTAGE_API_KEY and settings.EDPL_ENABLE_MARKET_DATA:
        from src.data.external.adapters.alpha_vantage import AlphaVantageAdapter
        av = AlphaVantageAdapter()
        registry.register(av)
        health_checker.register_provider(av.name, av.domain)
        logger.info("Alpha Vantage adapter registered")

    if settings.TWELVE_DATA_API_KEY and settings.EDPL_ENABLE_MARKET_DATA:
        from src.data.external.adapters.twelve_data import TwelveDataAdapter
        td = TwelveDataAdapter()
        registry.register(td)
        health_checker.register_provider(td.name, td.domain)
        logger.info("Twelve Data adapter registered")

    if settings.FMP_API_KEY and settings.EDPL_ENABLE_FUNDAMENTAL:
        from src.data.external.adapters.fmp import FMPAdapter
        fmp = FMPAdapter()
        registry.register(fmp)
        health_checker.register_provider(fmp.name, fmp.domain)
        logger.info("FMP adapter registered")

    if settings.EDPL_ENABLE_MACRO:
        from src.data.external.adapters.world_bank import WorldBankAdapter
        wb = WorldBankAdapter()
        registry.register(wb)
        health_checker.register_provider(wb.name, wb.domain)
        logger.info("World Bank adapter registered")

        from src.data.external.adapters.imf import IMFAdapter
        imf = IMFAdapter()
        registry.register(imf)
        health_checker.register_provider(imf.name, imf.domain)
        logger.info("IMF adapter registered")

    if settings.EDPL_ENABLE_SENTIMENT:
        from src.data.external.adapters.stocktwits import StocktwitsAdapter
        st = StocktwitsAdapter()
        registry.register(st)
        health_checker.register_provider(st.name, st.domain)
        logger.info("Stocktwits adapter registered")

    if settings.SANTIMENT_API_KEY and settings.EDPL_ENABLE_SENTIMENT:
        from src.data.external.adapters.santiment import SantimentAdapter
        san = SantimentAdapter()
        registry.register(san)
        health_checker.register_provider(san.name, san.domain)
        logger.info("Santiment adapter registered")

    if settings.EDPL_ENABLE_VOLATILITY:
        from src.data.external.adapters.cboe import CboeAdapter
        cboe = CboeAdapter()
        registry.register(cboe)
        health_checker.register_provider(cboe.name, cboe.domain)
        logger.info("Cboe adapter registered")

    # ── Commercial stubs (always register for capability introspection) ───
    from src.data.external.adapters.stubs import (
        MorningstarAdapter, SimilarwebAdapter, ThinknumAdapter, OptionMetricsAdapter,
    )
    for stub_cls in [MorningstarAdapter, SimilarwebAdapter, ThinknumAdapter, OptionMetricsAdapter]:
        stub = stub_cls()
        registry.register(stub)
        health_checker.register_provider(stub.name, stub.domain)

    logger.info("EDPL initialised — %d adapters registered across %d domains", sum(
        len(registry.get_all(d)) for d in registry.list_domains()
    ), len(registry.list_domains()))
    logger.info("365 Advisers API started (v3.4 — auth + observability + agent tools)")
    yield


# ── App Creation ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="365 Advisers API",
    version="5.0.0",
    description=(
        "Institutional-grade investment intelligence platform. "
        "Multi-agent analysis, portfolio construction, risk management, "
        "and alpha signal backtesting."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["*"],
)

# ── Rate Limiting ────────────────────────────────────────────────────────────

from src.middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware, max_requests=30, window_seconds=60)

# ── Audit Trail ───────────────────────────────────────────────────────────────
from src.middleware.audit import AuditMiddleware
app.add_middleware(AuditMiddleware)


# ── Router Mounts (Lazy — isolated import failures) ──────────────────────────

_ROUTER_REGISTRY: list[tuple[str, str]] = [
    ("src.routes.health",              "health"),
    ("src.routes.auth",                "auth"),
    ("src.routes.analysis",            "analysis"),
    ("src.routes.cache",               "cache"),
    ("src.routes.portfolio_risk",      "portfolio_risk"),
    ("src.routes.options_pricing",     "options_pricing"),
    ("src.routes.portfolio",           "portfolio"),
    ("src.routes.ideas",               "ideas"),
    ("src.routes.signals",             "signals"),
    ("src.routes.backtest",            "backtest"),
    ("src.routes.ranking",             "ranking"),
    ("src.routes.monitoring",          "monitoring"),
    ("src.routes.crowding",            "crowding"),
    ("src.routes.validation",          "validation"),
    ("src.routes.governance",          "governance"),
    ("src.routes.scorecard",           "scorecard"),
    ("src.routes.shadow",              "shadow"),
    ("src.routes.strategy",            "strategy"),
    ("src.routes.liquidity",           "liquidity"),
    ("src.routes.providers",           "providers"),
    ("src.routes.research",            "research"),
    ("src.routes.signal_lab",          "signal_lab"),
    ("src.routes.strategy_lab",        "strategy_lab"),
    ("src.routes.pilot",               "pilot"),
    ("src.routes.long_short",          "long_short"),
    ("src.routes.stat_arb",            "stat_arb"),
    ("src.routes.event_intelligence",  "event_intelligence"),
    ("src.routes.ml_signals",          "ml_signals"),
    ("src.routes.valuation",           "valuation"),
    ("src.routes.options",             "options"),
    ("src.routes.oms",                 "oms"),
    ("src.routes.multi_asset",         "multi_asset"),
    ("src.routes.capital_allocation",  "capital_allocation"),
    ("src.routes.risk",                "risk"),
    ("src.routes.market_feed",         "market_feed"),
    ("src.routes.portfolio_optimisation", "optimisation"),
    ("src.routes.factor_risk",         "factor_risk"),
    ("src.routes.attribution",         "attribution"),
    ("src.routes.event_backtester",    "event_backtester"),
    ("src.routes.compliance",          "compliance"),
    ("src.routes.dl_signals",          "dl_signals"),
    ("src.routes.nlp_signals",         "nlp_signals"),
    ("src.routes.alt_data",            "alt_data"),
    ("src.routes.rl_optimisation",     "rl_optimisation"),
    ("src.routes.market_data_api",     "market_data_api"),
    ("src.routes.alpha_intelligence",  "alpha_intelligence"),
    ("src.routes.super_alpha",         "super_alpha"),
    ("src.routes.investment_brain",    "investment_brain"),
    ("src.routes.autonomous_pm",       "autonomous_pm"),
    ("src.routes.ideas_backtest",      "ideas_backtest"),
    ("src.routes.screener",            "screener"),
    ("src.routes.agents",              "agents"),
    ("src.routes.audit",               "audit"),
    ("src.agents.mcp_server",          "mcp"),
    ("src.routes.costs",               "costs"),
    ("src.routes.alpha_research",      "alpha_research"),
    ("src.routes.ab_testing",          "ab_testing"),
    ("src.routes.prompt_versions",     "prompt_versions"),
    ("src.routes.ws_analysis",         "ws_analysis"),
]

import importlib

_loaded_routers = []
_failed_routers = []

for _module_path, _name in _ROUTER_REGISTRY:
    try:
        _mod = importlib.import_module(_module_path)
        _router = getattr(_mod, "router")
        app.include_router(_router)
        _loaded_routers.append(_name)
    except Exception as _exc:
        _failed_routers.append(_name)
        logger.error("Failed to mount router '%s' from %s: %s", _name, _module_path, _exc)

if _failed_routers:
    logger.warning("⚠ %d routers failed to load: %s", len(_failed_routers), _failed_routers)


# ── API v1 Versioned Routes ──────────────────────────────────────────────────
# All successfully loaded routes re-mounted under /v1/* prefix.

v1 = APIRouter(prefix="/v1")

for _module_path, _name in _ROUTER_REGISTRY:
    if _name not in _failed_routers:
        try:
            _mod = importlib.import_module(_module_path)
            v1.include_router(getattr(_mod, "router"))
        except Exception:
            pass  # Already logged above

app.include_router(v1)

logger.info(
    "Mounted %d/%d routers + /v1/ versioned group (v5.0)",
    len(_loaded_routers), len(_ROUTER_REGISTRY),
)


# ── Dev Server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=settings.UVICORN_WORKERS,
    )
