"""
src/routes/alpha_research.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for Alpha Discrimination Tests (Quintile Spread).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from src.research.alpha_tests.models import AlphaSpreadResult, ScoreTestComparison

logger = logging.getLogger("365advisers.routes.alpha_research")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/research", tags=["Alpha Research"], dependencies=[Depends(get_current_user)])


@router.get(
    "/alpha-discrimination",
    response_model=AlphaSpreadResult,
    summary="Quintile Spread Test — single score",
)
async def alpha_discrimination_test(
    score_col: str = "opportunity_score",
    dedup_window: int = 5,
    n_buckets: int = 5,
) -> AlphaSpreadResult:
    """
    Run the Alpha Discrimination Test (Quintile Spread) for a single score.

    Tests whether the given score can rank assets by future return.
    """
    from src.research.alpha_tests.quintile_spread_test import run_full_test

    return run_full_test(
        score_col=score_col,
        dedup_window=dedup_window,
        n_buckets=n_buckets,
    )


@router.get(
    "/alpha-discrimination/compare",
    response_model=ScoreTestComparison,
    summary="Multi-score comparison",
)
async def alpha_discrimination_compare() -> ScoreTestComparison:
    """
    Run the Quintile Spread Test for all score dimensions and compare
    which score has the strongest predictive power.
    """
    from src.research.alpha_tests.quintile_spread_test import run_multi_score_comparison

    return run_multi_score_comparison()
