"""
src/engines/scorecard/attribution.py
─────────────────────────────────────────────────────────────────────────────
AttributionEngine — Decomposes total alpha into signal-level contributions.
Answers: "What % of the system's alpha came from each signal?"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.scorecard.attribution")


class AttributionEngine:
    """Attribute total alpha to individual signals and categories."""

    def compute_signal_attribution(self, horizon: str = "20d") -> dict:
        """Compute per-signal alpha attribution.

        For each signal, calculate its proportional contribution to
        total system alpha based on firing frequency and excess returns.

        Returns:
            Dict with total_alpha, signal_contributions list, and
            category_contributions dict.
        """
        from src.data.database import LiveSignalTrackingRecord

        horizon_col = self._horizon_column(horizon)
        if not horizon_col:
            return {"error": f"Unknown horizon: {horizon}"}

        with SessionLocal() as db:
            records = (
                db.query(LiveSignalTrackingRecord)
                .filter(
                    getattr(LiveSignalTrackingRecord, horizon_col).isnot(None)
                )
                .all()
            )

        if not records:
            return {
                "horizon": horizon,
                "total_alpha_bps": 0.0,
                "signal_contributions": [],
                "category_contributions": {},
            }

        # Group by signal
        signal_groups: dict[str, list[float]] = {}
        signal_names: dict[str, str] = {}
        signal_categories: dict[str, str] = {}

        for r in records:
            sid = r.signal_id
            ret = getattr(r, horizon_col, 0.0) or 0.0
            benchmark = getattr(r, f"benchmark_{horizon_col}", 0.0) or 0.0
            excess = ret - benchmark

            signal_groups.setdefault(sid, []).append(excess)
            signal_names[sid] = r.signal_name or sid
            signal_categories[sid] = r.category or "unknown"

        # Total alpha = sum of all excess returns (volume-weighted)
        all_excess = [e for returns in signal_groups.values() for e in returns]
        total_alpha = sum(all_excess)

        # Per-signal contribution
        contributions = []
        for sid, excess_list in signal_groups.items():
            signal_alpha = sum(excess_list)
            pct = (signal_alpha / total_alpha * 100) if total_alpha != 0 else 0.0

            contributions.append({
                "signal_id": sid,
                "signal_name": signal_names.get(sid, sid),
                "category": signal_categories.get(sid, "unknown"),
                "firings": len(excess_list),
                "total_excess": round(signal_alpha, 6),
                "contribution_pct": round(pct, 2),
                "avg_excess": round(signal_alpha / len(excess_list), 6) if excess_list else 0.0,
            })

        # Sort by absolute contribution
        contributions.sort(key=lambda c: abs(c["contribution_pct"]), reverse=True)

        # Category roll-up
        cat_contrib: dict[str, float] = {}
        for c in contributions:
            cat = c["category"]
            cat_contrib[cat] = cat_contrib.get(cat, 0.0) + c["contribution_pct"]

        return {
            "horizon": horizon,
            "total_alpha_bps": round(total_alpha * 10000, 2),
            "signal_contributions": contributions,
            "category_contributions": {
                k: round(v, 2) for k, v in sorted(
                    cat_contrib.items(), key=lambda x: abs(x[1]), reverse=True
                )
            },
        }

    def compute_idea_attribution(self, horizon: str = "20d") -> dict:
        """Compute per-idea-type alpha attribution using OpportunityPerformanceRecord."""
        from src.data.database import OpportunityPerformanceRecord

        horizon_col = self._opp_horizon_column(horizon)
        if not horizon_col:
            return {"error": f"Unknown horizon: {horizon}"}

        with SessionLocal() as db:
            records = (
                db.query(OpportunityPerformanceRecord)
                .filter(
                    getattr(OpportunityPerformanceRecord, horizon_col).isnot(None)
                )
                .all()
            )

        if not records:
            return {"horizon": horizon, "idea_contributions": []}

        # Group by idea type
        type_groups: dict[str, list[dict]] = {}
        for r in records:
            ret = getattr(r, horizon_col, 0.0) or 0.0
            benchmark = r.benchmark_return_20d or 0.0
            excess = ret - benchmark

            type_groups.setdefault(r.idea_type, []).append({
                "return": ret,
                "excess": excess,
                "confidence": r.confidence,
            })

        contributions = []
        for idea_type, items in type_groups.items():
            n = len(items)
            avg_excess = sum(i["excess"] for i in items) / n if n > 0 else 0.0
            hit_rate = sum(1 for i in items if i["return"] > 0) / n if n > 0 else 0.0

            contributions.append({
                "idea_type": idea_type,
                "count": n,
                "hit_rate": round(hit_rate, 4),
                "avg_excess_return": round(avg_excess, 6),
                "alpha_bps": round(avg_excess * 10000, 2),
            })

        contributions.sort(key=lambda c: c["alpha_bps"], reverse=True)

        return {
            "horizon": horizon,
            "idea_contributions": contributions,
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _horizon_column(horizon: str) -> str | None:
        return {
            "1d": "return_1d",
            "5d": "return_5d",
            "20d": "return_20d",
            "60d": "return_60d",
        }.get(horizon)

    @staticmethod
    def _opp_horizon_column(horizon: str) -> str | None:
        return {
            "1d": "return_1d",
            "5d": "return_5d",
            "20d": "return_20d",
            "60d": "return_60d",
        }.get(horizon)
