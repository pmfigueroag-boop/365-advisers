"""
src/routes/portfolio.py
─────────────────────────────────────────────────────────────────────────────
Portfolio construction and database CRUD endpoints.
Extracted from main.py as part of audit finding #1 (APIRouter decomposition).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from src.schemas import BuildPortfolioRequest, SavePortfolioRequest
from src.engines.portfolio.portfolio_builder import PortfolioConstructionModel
from src.data.database import SessionLocal, Portfolio, PortfolioPosition

logger = logging.getLogger("365advisers.routes.portfolio")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/portfolio", tags=["Portfolio"], dependencies=[Depends(get_current_user)])


@router.post("/build")
async def build_portfolio(request: BuildPortfolioRequest):
    """
    Constructs a Core-Satellite Risk-Adjusted Portfolio from a list of positions.
    Uses Volatility Parity for risk-equalized weighting.
    """
    try:
        positions = [p.model_dump() for p in request.positions]
        result = PortfolioConstructionModel.build_portfolio(positions)
        return result
    except Exception as exc:
        logger.error(f"Portfolio build error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("")
async def save_portfolio(request: SavePortfolioRequest):
    """Saves a built portfolio to the database."""
    try:
        with SessionLocal() as db:
            new_port = Portfolio(
                name=request.name,
                strategy=request.strategy,
                risk_level=request.risk_level,
                total_allocation=request.total_allocation,
            )
            db.add(new_port)
            db.flush()

            for p in request.positions:
                pos = PortfolioPosition(
                    portfolio_id=new_port.id,
                    ticker=p.ticker,
                    target_weight=p.target_weight,
                    role=p.role,
                    sector=p.sector,
                    volatility_atr=p.volatility_atr,
                )
                db.add(pos)

            db.commit()
            logger.info(f"Saved portfolio '{request.name}' with ID {new_port.id}")
            return {"status": "success", "portfolio_id": new_port.id}
    except Exception as exc:
        logger.error(f"Portfolio save error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("")
async def list_portfolios():
    """Lists all saved portfolios."""
    with SessionLocal() as db:
        ports = db.query(Portfolio).order_by(Portfolio.created_at.desc()).all()
        return [{
            "id": p.id,
            "name": p.name,
            "strategy": p.strategy,
            "risk_level": p.risk_level,
            "total_allocation": p.total_allocation,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        } for p in ports]


@router.get("/{portfolio_id}")
async def get_portfolio(portfolio_id: int):
    """Gets details of a specific portfolio."""
    with SessionLocal() as db:
        port = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        positions = [{
            "ticker": pos.ticker,
            "target_weight": pos.target_weight,
            "role": pos.role,
            "sector": pos.sector,
            "volatility_atr": pos.volatility_atr,
        } for pos in port.positions]

        return {
            "id": port.id,
            "name": port.name,
            "strategy": port.strategy,
            "risk_level": port.risk_level,
            "total_allocation": port.total_allocation,
            "created_at": port.created_at.isoformat() if port.created_at else None,
            "positions": positions,
        }


@router.delete("/{portfolio_id}")
async def delete_portfolio(portfolio_id: int):
    """Deletes a portfolio."""
    with SessionLocal() as db:
        port = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        db.delete(port)
        db.commit()
        logger.info(f"Deleted portfolio ID {portfolio_id}")
        return {"status": "success", "deleted_id": portfolio_id}
