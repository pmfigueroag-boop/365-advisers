"""
src/data/repositories/score_repository.py
──────────────────────────────────────────────────────────────────────────────
Repository: Opportunity Score persistence (read/write).

Encapsulates all database operations for the OpportunityScoreHistory table,
providing a clean interface for the Orchestration layer.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal, OpportunityScoreHistory, ScoreHistory

logger = logging.getLogger("365advisers.repositories.score")


class ScoreRepository:
    """Clean persistence interface for score-related data."""

    @staticmethod
    def save_opportunity_score(
        ticker: str,
        opportunity_score: float,
        dimensions: dict,
        full_breakdown: dict,
    ) -> bool:
        """
        Persist an Opportunity Score result to the database.

        Returns True on success, False on error.
        """
        try:
            with SessionLocal() as db:
                db.add(OpportunityScoreHistory(
                    ticker=ticker.upper(),
                    opportunity_score=opportunity_score,
                    business_quality=dimensions.get("business_quality", 0.0),
                    valuation=dimensions.get("valuation", 0.0),
                    financial_strength=dimensions.get("financial_strength", 0.0),
                    market_behavior=dimensions.get("market_behavior", 0.0),
                    score_breakdown_json=json.dumps(full_breakdown),
                ))
                db.commit()
            return True
        except Exception as exc:
            logger.warning(f"Error saving Opportunity Score for {ticker}: {exc}")
            return False

    @staticmethod
    def get_opportunity_history(ticker: str, limit: int = 90) -> list[dict]:
        """
        Retrieve the last N opportunity score records for a ticker.
        """
        try:
            with SessionLocal() as db:
                rows = (
                    db.query(OpportunityScoreHistory)
                    .filter(OpportunityScoreHistory.ticker == ticker.upper())
                    .order_by(OpportunityScoreHistory.recorded_at.desc())
                    .limit(min(limit, 365))
                    .all()
                )
                return [
                    {
                        "ticker": row.ticker,
                        "opportunity_score": row.opportunity_score,
                        "business_quality": row.business_quality,
                        "valuation": row.valuation,
                        "financial_strength": row.financial_strength,
                        "market_behavior": row.market_behavior,
                        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                    }
                    for row in rows
                ]
        except Exception as exc:
            logger.warning(f"Error reading Opportunity Score history for {ticker}: {exc}")
            return []

    @staticmethod
    def get_score_history(ticker: str, analysis_type: str, limit: int = 90) -> list[dict]:
        """
        Retrieve the last N score history records.
        Delegates to the existing get_score_history function for backward compat.
        """
        from src.data.database import get_score_history
        return get_score_history(ticker, analysis_type, limit)
