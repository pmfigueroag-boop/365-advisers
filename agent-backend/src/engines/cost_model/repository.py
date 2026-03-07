"""
src/engines/cost_model/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for transaction cost analysis results.

Stores per-signal cost profiles keyed by backtest run ID.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.data.database import CostModelProfileRecord, SessionLocal

logger = logging.getLogger("365advisers.cost_model.repository")


class CostModelRepository:
    """CRUD for cost model profiles."""

    # ── Write ─────────────────────────────────────────────────────────────

    def save_profiles(
        self,
        run_id: str,
        profiles: list,
    ) -> int:
        """
        Persist cost profiles for a backtest run.

        Parameters
        ----------
        run_id : str
            Associated backtest run ID.
        profiles : list[SignalCostProfile]
            Cost profiles to save.

        Returns
        -------
        int
            Number of saved records.
        """
        with SessionLocal() as db:
            count = 0
            for p in profiles:
                rec = CostModelProfileRecord(
                    run_id=run_id,
                    signal_id=p.signal_id,
                    signal_name=p.signal_name,
                    raw_sharpe_20=p.raw_sharpe.get(20),
                    adjusted_sharpe_20=p.adjusted_sharpe.get(20),
                    raw_alpha_20=p.raw_alpha.get(20),
                    net_alpha_20=p.net_alpha.get(20),
                    avg_total_cost=p.avg_total_cost,
                    cost_drag_bps=p.total_cost_drag_bps,
                    breakeven_cost_bps=p.breakeven_cost_bps,
                    cost_resilience=p.cost_resilience_score,
                    cost_adjusted_tier=p.cost_adjusted_tier,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("COST-REPO: Saved %d profiles for run %s", count, run_id)
            return count

    # ── Read ──────────────────────────────────────────────────────────────

    def get_profiles(self, run_id: str) -> list[dict]:
        """Get all cost profiles for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(CostModelProfileRecord)
                .filter(CostModelProfileRecord.run_id == run_id)
                .order_by(CostModelProfileRecord.cost_resilience.desc())
                .all()
            )
            return [
                {
                    "signal_id": r.signal_id,
                    "signal_name": r.signal_name,
                    "raw_sharpe_20": r.raw_sharpe_20,
                    "adjusted_sharpe_20": r.adjusted_sharpe_20,
                    "raw_alpha_20": r.raw_alpha_20,
                    "net_alpha_20": r.net_alpha_20,
                    "avg_total_cost": r.avg_total_cost,
                    "cost_drag_bps": r.cost_drag_bps,
                    "breakeven_cost_bps": r.breakeven_cost_bps,
                    "cost_resilience": r.cost_resilience,
                    "cost_adjusted_tier": r.cost_adjusted_tier,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def get_signal_profile(self, signal_id: str) -> dict | None:
        """Get the latest cost profile for a signal from the most recent run."""
        with SessionLocal() as db:
            row = (
                db.query(CostModelProfileRecord)
                .filter(CostModelProfileRecord.signal_id == signal_id)
                .order_by(CostModelProfileRecord.created_at.desc())
                .first()
            )
            if not row:
                return None
            return {
                "signal_id": row.signal_id,
                "signal_name": row.signal_name,
                "run_id": row.run_id,
                "raw_sharpe_20": row.raw_sharpe_20,
                "adjusted_sharpe_20": row.adjusted_sharpe_20,
                "raw_alpha_20": row.raw_alpha_20,
                "net_alpha_20": row.net_alpha_20,
                "avg_total_cost": row.avg_total_cost,
                "cost_drag_bps": row.cost_drag_bps,
                "breakeven_cost_bps": row.breakeven_cost_bps,
                "cost_resilience": row.cost_resilience,
                "cost_adjusted_tier": row.cost_adjusted_tier,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
