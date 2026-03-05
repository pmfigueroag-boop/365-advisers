"""
src/data/repositories/portfolio_repository.py
──────────────────────────────────────────────────────────────────────────────
Repository: Portfolio persistence (read/write/list/delete).

Encapsulates all database operations for Portfolio and PortfolioPosition
tables, providing a clean interface for the Portfolio Engine and routes.
"""

from __future__ import annotations

import logging
from src.data.database import SessionLocal, Portfolio, PortfolioPosition

logger = logging.getLogger("365advisers.repositories.portfolio")


class PortfolioRepository:
    """Clean persistence interface for portfolio data."""

    @staticmethod
    def save_portfolio(
        name: str,
        strategy: str,
        risk_level: str,
        total_allocation: float,
        positions: list[dict],
    ) -> int | None:
        """
        Persist a portfolio and its positions.
        Returns the portfolio ID on success, None on error.
        """
        try:
            with SessionLocal() as db:
                portfolio = Portfolio(
                    name=name,
                    strategy=strategy,
                    risk_level=risk_level,
                    total_allocation=total_allocation,
                )
                db.add(portfolio)
                db.flush()  # get the portfolio.id

                for pos in positions:
                    db.add(PortfolioPosition(
                        portfolio_id=portfolio.id,
                        ticker=pos.get("ticker", ""),
                        target_weight=pos.get("target_weight", 0.0),
                        role=pos.get("role", "SATELLITE"),
                        sector=pos.get("sector", "Unknown"),
                        volatility_atr=pos.get("volatility_atr"),
                    ))
                db.commit()
                return portfolio.id
        except Exception as exc:
            logger.error(f"Error saving portfolio '{name}': {exc}")
            return None

    @staticmethod
    def list_portfolios() -> list[dict]:
        """List all saved portfolios with summary info."""
        try:
            with SessionLocal() as db:
                portfolios = (
                    db.query(Portfolio)
                    .order_by(Portfolio.created_at.desc())
                    .all()
                )
                return [
                    {
                        "id": p.id,
                        "name": p.name,
                        "strategy": p.strategy,
                        "risk_level": p.risk_level,
                        "total_allocation": p.total_allocation,
                        "position_count": len(p.positions),
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                    }
                    for p in portfolios
                ]
        except Exception as exc:
            logger.error(f"Error listing portfolios: {exc}")
            return []

    @staticmethod
    def get_portfolio(portfolio_id: int) -> dict | None:
        """Get a single portfolio with all positions."""
        try:
            with SessionLocal() as db:
                p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
                if not p:
                    return None
                return {
                    "id": p.id,
                    "name": p.name,
                    "strategy": p.strategy,
                    "risk_level": p.risk_level,
                    "total_allocation": p.total_allocation,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "positions": [
                        {
                            "ticker": pos.ticker,
                            "target_weight": pos.target_weight,
                            "role": pos.role,
                            "sector": pos.sector,
                            "volatility_atr": pos.volatility_atr,
                        }
                        for pos in p.positions
                    ],
                }
        except Exception as exc:
            logger.error(f"Error getting portfolio {portfolio_id}: {exc}")
            return None

    @staticmethod
    def delete_portfolio(portfolio_id: int) -> bool:
        """Delete a portfolio and its positions. Returns True on success."""
        try:
            with SessionLocal() as db:
                p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
                if not p:
                    return False
                db.delete(p)
                db.commit()
                return True
        except Exception as exc:
            logger.error(f"Error deleting portfolio {portfolio_id}: {exc}")
            return False
