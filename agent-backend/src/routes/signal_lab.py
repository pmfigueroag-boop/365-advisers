"""
src/routes/signal_lab.py
─────────────────────────────────────────────────────────────────────────────
Signal Research Lab API — signal evaluation, comparison, and stability.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.engines.signal_lab import (
    SignalEvaluator,
    SignalComparator,
    StabilityAnalyzer,
    RedundancyDetector,
    LabReport,
)
from src.engines.research_data.signal_store import SignalStore

logger = logging.getLogger(__name__)
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/signal-lab", tags=["Signal Lab"], dependencies=[Depends(get_current_user)])


# ── Signal Evaluation ────────────────────────────────────────────────────────

@router.get("/evaluate/{signal_id}")
async def evaluate_signal(
    signal_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Evaluate a single signal's performance metrics."""
    fires = SignalStore.get_fires_for_signal(signal_id, start_date, end_date)
    evaluation = SignalEvaluator.evaluate(fires)
    return evaluation


@router.get("/evaluate")
async def evaluate_all_signals(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
):
    """Evaluate all signals in the library."""
    # Get all signal IDs from the store
    category_counts = SignalStore.count_by_category(start_date, end_date)

    evaluations = {}
    for cat in category_counts.keys():
        if category and cat != category:
            continue
        # For each category, we'd need signal IDs. Use a simpler approach:
        # evaluate by querying fires grouped by signal_id
        from src.data.database import SessionLocal
        from src.engines.research_data.models import SignalHistoryRecord
        from sqlalchemy import distinct

        with SessionLocal() as session:
            query = session.query(distinct(SignalHistoryRecord.signal_id)).filter_by(category=cat)
            if start_date:
                query = query.filter(SignalHistoryRecord.fire_date >= start_date)
            if end_date:
                query = query.filter(SignalHistoryRecord.fire_date <= end_date)
            signal_ids = [row[0] for row in query.all()]

        for sid in signal_ids:
            fires = SignalStore.get_fires_for_signal(sid, start_date, end_date)
            evaluations[sid] = SignalEvaluator.evaluate(fires)

    return {"evaluations": evaluations, "count": len(evaluations)}


# ── Signal Comparison ────────────────────────────────────────────────────────

@router.get("/compare/overlap")
async def compare_overlap(
    signal_ids: str = Query(..., description="Comma-separated signal IDs"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Compute overlap matrix between signals."""
    ids = [s.strip() for s in signal_ids.split(",") if s.strip()]
    signal_fires = {}
    for sid in ids:
        signal_fires[sid] = SignalStore.get_fires_for_signal(sid, start_date, end_date)

    overlap = SignalComparator.compute_overlap_matrix(signal_fires)
    return overlap


@router.get("/compare/redundant-pairs")
async def find_redundant_pairs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
):
    """Find signal pairs with high overlap (potential redundancy)."""
    # Load all signals
    signal_fires = _load_all_signal_fires(start_date, end_date)
    pairs = SignalComparator.find_redundant_pairs(signal_fires, threshold)
    return {"pairs": pairs, "count": len(pairs), "threshold": threshold}


@router.get("/compare/marginal-value")
async def marginal_value_ranking(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Rank signals by marginal information value."""
    signal_fires = _load_all_signal_fires(start_date, end_date)
    evaluations = [SignalEvaluator.evaluate(fires) for fires in signal_fires.values()]
    ranking = SignalComparator.compute_marginal_value(evaluations, signal_fires)
    return {"ranking": ranking}


# ── Stability ────────────────────────────────────────────────────────────────

@router.get("/stability/{signal_id}")
async def signal_stability(
    signal_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    bootstrap_samples: int = Query(100, ge=10, le=1000),
):
    """Run bootstrap and temporal stability analysis for a signal."""
    fires = SignalStore.get_fires_for_signal(signal_id, start_date, end_date)

    bootstrap = StabilityAnalyzer.bootstrap_stability(fires, n_samples=bootstrap_samples)
    temporal = StabilityAnalyzer.temporal_stability(fires)
    regime = StabilityAnalyzer.regime_stability(fires)

    return {
        "signal_id": signal_id,
        "total_fires": len(fires),
        "bootstrap": bootstrap,
        "temporal": temporal,
        "regime": regime,
    }


# ── Redundancy ───────────────────────────────────────────────────────────────

@router.get("/redundancy")
async def redundancy_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
):
    """Run full redundancy analysis across all signals."""
    signal_fires = _load_all_signal_fires(start_date, end_date)
    evaluations = {sid: SignalEvaluator.evaluate(fires) for sid, fires in signal_fires.items()}
    result = RedundancyDetector.analyze(signal_fires, evaluations, threshold)
    return result


# ── Full Report ──────────────────────────────────────────────────────────────

@router.get("/report")
async def full_lab_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    run_stability: bool = Query(True),
    overlap_threshold: float = Query(0.7, ge=0.0, le=1.0),
):
    """Generate a full signal lab report (may be slow for large signal libraries)."""
    signal_fires = _load_all_signal_fires(start_date, end_date)
    report = LabReport.generate(signal_fires, run_stability, overlap_threshold)
    return report


@router.get("/report/summary")
async def lab_report_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Generate a compact lab report summary."""
    signal_fires = _load_all_signal_fires(start_date, end_date)
    report = LabReport.generate(signal_fires, run_stability=False)
    return LabReport.generate_summary(report)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_all_signal_fires(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, list[dict]]:
    """Load all signal fires grouped by signal_id."""
    from src.data.database import SessionLocal
    from src.engines.research_data.models import SignalHistoryRecord
    from sqlalchemy import distinct

    with SessionLocal() as session:
        query = session.query(distinct(SignalHistoryRecord.signal_id))
        if start_date:
            query = query.filter(SignalHistoryRecord.fire_date >= start_date)
        if end_date:
            query = query.filter(SignalHistoryRecord.fire_date <= end_date)
        signal_ids = [row[0] for row in query.all()]

    signal_fires = {}
    for sid in signal_ids:
        signal_fires[sid] = SignalStore.get_fires_for_signal(sid, start_date, end_date)

    return signal_fires
