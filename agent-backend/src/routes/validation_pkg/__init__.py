"""
src/routes/validation_pkg/__init__.py
─────────────────────────────────────────────────────────────────────────────
Combined router that includes all QVF sub-routers.
"""

from fastapi import APIRouter

from src.routes.validation_pkg.backtest import router as backtest_router
from src.routes.validation_pkg.performance import router as performance_router
from src.routes.validation_pkg.walk_forward import router as walk_forward_router
from src.routes.validation_pkg.cost_analysis import router as cost_analysis_router
from src.routes.validation_pkg.advanced import router as advanced_router

router = APIRouter(
    prefix="/validation",
    tags=["Quantitative Validation Framework"],
)

router.include_router(backtest_router)
router.include_router(performance_router)
router.include_router(walk_forward_router)
router.include_router(cost_analysis_router)
router.include_router(advanced_router)
