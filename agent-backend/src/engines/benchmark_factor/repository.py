"""
src/engines/benchmark_factor/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for benchmark & factor evaluation results.

Stores per-signal profiles keyed by run ID.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.data.database import BenchmarkFactorProfileRecord, SessionLocal

logger = logging.getLogger("365advisers.benchmark_factor.repository")


class BenchmarkFactorRepository:
    """CRUD for benchmark & factor profiles."""

    # ── Write ─────────────────────────────────────────────────────────────

    def save_profiles(
        self,
        run_id: str,
        profiles: list,
    ) -> int:
        """
        Persist benchmark & factor profiles for a run.

        Parameters
        ----------
        run_id : str
            Associated run ID.
        profiles : list[SignalBenchmarkProfile]
            Profiles to save.

        Returns
        -------
        int
            Number of saved records.
        """
        with SessionLocal() as db:
            count = 0
            for p in profiles:
                # Extract primary benchmark (SPY) values at T+20
                market_br = next(
                    (br for br in p.benchmark_results if br.benchmark_ticker == "SPY"),
                    None,
                )
                sector_br = p.sector_result

                rec = BenchmarkFactorProfileRecord(
                    run_id=run_id,
                    signal_id=p.signal_id,
                    signal_name=p.signal_name,
                    excess_vs_market=market_br.excess_return.get(20) if market_br else None,
                    ir_vs_market=market_br.information_ratio.get(20) if market_br else None,
                    excess_vs_sector=sector_br.excess_return.get(20) if sector_br else None,
                    ir_vs_sector=sector_br.information_ratio.get(20) if sector_br else None,
                    factor_alpha=p.factor_exposure.factor_alpha if p.factor_exposure else None,
                    alpha_t_stat=p.factor_exposure.alpha_t_stat if p.factor_exposure else None,
                    alpha_significant=p.factor_exposure.alpha_significant if p.factor_exposure else False,
                    beta_market=p.factor_exposure.beta_market if p.factor_exposure else None,
                    beta_size=p.factor_exposure.beta_size if p.factor_exposure else None,
                    beta_value=p.factor_exposure.beta_value if p.factor_exposure else None,
                    beta_momentum=p.factor_exposure.beta_momentum if p.factor_exposure else None,
                    r_squared=p.factor_exposure.r_squared if p.factor_exposure else None,
                    factor_neutrality=p.factor_exposure.factor_neutrality if p.factor_exposure else None,
                    alpha_source=p.alpha_source.value,
                    n_observations=p.total_events,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("BF-REPO: Saved %d profiles for run %s", count, run_id)
            return count

    # ── Read ──────────────────────────────────────────────────────────────

    def get_profiles(self, run_id: str) -> list[dict]:
        """Get all benchmark/factor profiles for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(BenchmarkFactorProfileRecord)
                .filter(BenchmarkFactorProfileRecord.run_id == run_id)
                .order_by(BenchmarkFactorProfileRecord.factor_alpha.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_signal_profile(self, signal_id: str) -> dict | None:
        """Get the latest benchmark/factor profile for a signal."""
        with SessionLocal() as db:
            row = (
                db.query(BenchmarkFactorProfileRecord)
                .filter(BenchmarkFactorProfileRecord.signal_id == signal_id)
                .order_by(BenchmarkFactorProfileRecord.created_at.desc())
                .first()
            )
            if not row:
                return None
            return self._to_dict(row)

    @staticmethod
    def _to_dict(row: BenchmarkFactorProfileRecord) -> dict:
        return {
            "signal_id": row.signal_id,
            "signal_name": row.signal_name,
            "run_id": row.run_id,
            "excess_vs_market": row.excess_vs_market,
            "ir_vs_market": row.ir_vs_market,
            "excess_vs_sector": row.excess_vs_sector,
            "ir_vs_sector": row.ir_vs_sector,
            "factor_alpha": row.factor_alpha,
            "alpha_t_stat": row.alpha_t_stat,
            "alpha_significant": row.alpha_significant,
            "beta_market": row.beta_market,
            "beta_size": row.beta_size,
            "beta_value": row.beta_value,
            "beta_momentum": row.beta_momentum,
            "r_squared": row.r_squared,
            "factor_neutrality": row.factor_neutrality,
            "alpha_source": row.alpha_source,
            "n_observations": row.n_observations,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
