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
    """Initialise the SQLite database on startup."""
    init_db()
    logger.info("365 Advisers API started (v3.0 — modular architecture)")
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

logger.info(f"Mounted {len(app.routes)} routes across 10 routers")


# ── Dev Server ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
