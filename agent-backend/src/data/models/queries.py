"""
src/data/models/queries.py
─────────────────────────────────────────────────────────────────────────────
Standalone query functions for the database.
"""

from __future__ import annotations

from src.data.models.base import SessionLocal
from src.data.models.analysis import ScoreHistory


def get_score_history(ticker: str, analysis_type: str, limit: int = 90) -> list[dict]:
    """Return the last N score records for a ticker + analysis type."""
    symbol = ticker.upper()
    with SessionLocal() as db:
        rows = (
            db.query(ScoreHistory)
            .filter(
                ScoreHistory.ticker == symbol,
                ScoreHistory.analysis_type == analysis_type,
            )
            .order_by(ScoreHistory.recorded_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                "score": row.score,
                "signal": row.signal,
            }
            for row in reversed(rows)
        ]
