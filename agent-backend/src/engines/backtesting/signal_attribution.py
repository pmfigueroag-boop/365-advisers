"""
src/engines/backtesting/signal_attribution.py
--------------------------------------------------------------------------
Signal Attribution Engine — Leave-One-Out Marginal Alpha Contribution.

Measures each signal's marginal contribution to the system's aggregate
alpha.  Works on cached SignalEvent lists from a completed backtest —
no additional backtests required.

Method: Leave-One-Out (LOO)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. Compute full-system composite performance (weighted Sharpe@20d)
2. For each signal_i: recompute composite performance excluding signal_i
3. marginal_contribution_i = full_system_sharpe - system_without_i_sharpe
4. Positive = signal adds alpha; Negative = signal dilutes alpha

Redundancy Detection
~~~~~~~~~~~~~~~~~~~~
For each signal, compute the Pearson correlation between its per-event
excess returns and the system's composite excess returns (averaged across
all other signals' events at the same ticker+date).  High correlation
(> 0.7) indicates the signal is largely redundant.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from src.engines.alpha_signals.models import SignalCategory
from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.attribution")


# ── Contracts ────────────────────────────────────────────────────────────────

class SignalContribution(BaseModel):
    """Attribution result for a single signal."""
    signal_id: str
    signal_name: str = ""
    category: SignalCategory | None = None

    # Per-signal standalone metrics
    individual_sharpe: float = Field(
        0.0, description="Signal's standalone Sharpe@20d",
    )
    individual_firings: int = Field(
        0, ge=0, description="Number of events for this signal",
    )
    individual_avg_excess: float = Field(
        0.0, description="Signal's standalone avg excess return@20d",
    )

    # System-level context
    system_sharpe: float = Field(
        0.0, description="Full system composite Sharpe@20d",
    )
    system_without_sharpe: float = Field(
        0.0, description="System Sharpe@20d with this signal removed",
    )

    # Attribution metrics
    marginal_contribution: float = Field(
        0.0,
        description="system_sharpe - system_without_sharpe. "
        "Positive = adds alpha, negative = dilutes alpha.",
    )
    is_dilutive: bool = Field(
        False,
        description="True if marginal_contribution < 0",
    )
    contribution_rank: int = Field(
        0, ge=0,
        description="Ordinal rank by marginal_contribution (1 = top)",
    )
    redundancy_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Correlation with system composite (0=unique, 1=redundant)",
    )
    ic: float = Field(
        0.0,
        description="Information Coefficient — Spearman rank correlation "
        "between signal confidence and forward excess return@20d. "
        "Range [-1, 1]. >0.05 is institutionally valuable.",
    )


class AttributionReport(BaseModel):
    """Full attribution analysis output."""
    signal_contributions: list[SignalContribution] = Field(default_factory=list)
    system_sharpe: float = Field(
        0.0, description="Full system composite Sharpe@20d",
    )
    effective_signal_count: int = Field(
        0, ge=0, description="Non-dilutive signals",
    )
    total_dilutive: int = Field(
        0, ge=0, description="Signals with negative marginal contribution",
    )
    total_signals: int = Field(0, ge=0)

    # Breadth-Adjusted Information Ratio (Grinold's Fundamental Law)
    # BAIR = avg_IC × √BR_effective
    avg_ic: float = Field(
        0.0, description="Average Information Coefficient across effective signals",
    )
    bair: float = Field(
        0.0,
        description="Breadth-Adjusted Information Ratio: avg_IC × sqrt(BR_effective). "
        "Higher = better risk-adjusted alpha capacity.",
    )

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

# Reference forward window for attribution metrics
_REF_WINDOW = 20


class SignalAttributionEngine:
    """
    Computes marginal alpha contribution per signal using leave-one-out.

    Usage::

        engine = SignalAttributionEngine()
        report = engine.compute(events, signal_meta)
    """

    def compute(
        self,
        events: list[SignalEvent],
        signal_meta: dict[str, tuple[str, SignalCategory | None]] | None = None,
    ) -> AttributionReport:
        """
        Run leave-one-out attribution on cached backtest events.

        Parameters
        ----------
        events : list[SignalEvent]
            All signal events from a completed backtest run.
        signal_meta : dict[str, tuple[str, SignalCategory | None]] | None
            Optional mapping signal_id → (signal_name, category).

        Returns
        -------
        AttributionReport
        """
        if not events:
            return AttributionReport()

        signal_meta = signal_meta or {}

        # Group events by signal_id
        by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in events:
            by_signal[e.signal_id].append(e)

        signal_ids = sorted(by_signal.keys())
        if not signal_ids:
            return AttributionReport()

        # Step 1: Full system composite Sharpe
        full_sharpe = self._composite_sharpe(events)

        # Step 2: Per-signal standalone metrics + leave-one-out
        contributions: list[SignalContribution] = []

        for sig_id in signal_ids:
            sig_events = by_signal[sig_id]

            # Standalone metrics
            ind_sharpe = self._signal_sharpe(sig_events)
            ind_excess = self._signal_avg_excess(sig_events)

            # LOO: system without this signal
            without_events = [e for e in events if e.signal_id != sig_id]
            without_sharpe = self._composite_sharpe(without_events)

            marginal = full_sharpe - without_sharpe

            # Redundancy: correlation with "rest of system"
            redundancy = self._compute_redundancy(sig_events, without_events)

            # IC: Spearman rank correlation(confidence, excess_return)
            ic = self._compute_ic(sig_events)

            # Metadata
            name, category = signal_meta.get(sig_id, (sig_id, None))

            contributions.append(SignalContribution(
                signal_id=sig_id,
                signal_name=name,
                category=category,
                individual_sharpe=round(ind_sharpe, 4),
                individual_firings=len(sig_events),
                individual_avg_excess=round(ind_excess, 6),
                system_sharpe=round(full_sharpe, 4),
                system_without_sharpe=round(without_sharpe, 4),
                marginal_contribution=round(marginal, 4),
                is_dilutive=marginal < 0,
                redundancy_score=round(redundancy, 4),
                ic=round(ic, 4),
            ))

        # Rank by marginal contribution (descending)
        contributions.sort(key=lambda c: c.marginal_contribution, reverse=True)
        for rank, c in enumerate(contributions, 1):
            c.contribution_rank = rank

        total_dilutive = sum(1 for c in contributions if c.is_dilutive)

        effective_count = len(contributions) - total_dilutive

        # BAIR: avg_IC × √BR_effective (Grinold's Fundamental Law)
        # Uses formal Spearman IC (not Sharpe proxy)
        effective_ics = [
            c.ic for c in contributions if not c.is_dilutive
        ]
        avg_ic = (
            sum(effective_ics) / len(effective_ics)
            if effective_ics else 0.0
        )
        bair = avg_ic * math.sqrt(effective_count) if effective_count > 0 else 0.0

        report = AttributionReport(
            signal_contributions=contributions,
            system_sharpe=round(full_sharpe, 4),
            effective_signal_count=effective_count,
            total_dilutive=total_dilutive,
            total_signals=len(contributions),
            avg_ic=round(avg_ic, 4),
            bair=round(bair, 4),
        )

        logger.info(
            "ATTRIBUTION: %d signals analyzed — %d effective, %d dilutive, "
            "system Sharpe=%.2f",
            report.total_signals, report.effective_signal_count,
            report.total_dilutive, report.system_sharpe,
        )

        return report

    # ── Internal Computations ────────────────────────────────────────────

    @staticmethod
    def _signal_sharpe(events: list[SignalEvent]) -> float:
        """Compute Sharpe@REF_WINDOW for a single signal's events."""
        returns = [
            e.excess_returns.get(_REF_WINDOW, 0.0)
            for e in events
            if _REF_WINDOW in e.excess_returns
        ]
        if len(returns) < 5:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(var) if var > 0 else 1e-9
        return mean / std

    @staticmethod
    def _signal_avg_excess(events: list[SignalEvent]) -> float:
        """Average excess return@REF_WINDOW."""
        returns = [
            e.excess_returns.get(_REF_WINDOW, 0.0)
            for e in events
            if _REF_WINDOW in e.excess_returns
        ]
        if not returns:
            return 0.0
        return sum(returns) / len(returns)

    @staticmethod
    def _composite_sharpe(events: list[SignalEvent]) -> float:
        """
        Composite Sharpe@REF_WINDOW across all signals.

        Each event contributes its excess return equally.
        This is the system's aggregate risk-adjusted performance
        treating every signal firing as an independent bet.
        """
        returns = [
            e.excess_returns.get(_REF_WINDOW, 0.0)
            for e in events
            if _REF_WINDOW in e.excess_returns
        ]
        if len(returns) < 5:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(var) if var > 0 else 1e-9
        return mean / std

    @staticmethod
    def _compute_ic(events: list[SignalEvent]) -> float:
        """
        Formal Information Coefficient: Spearman rank correlation
        between signal confidence and forward excess return@20d.

        Spearman = Pearson correlation of rank-transformed variables.
        """
        pairs = [
            (e.confidence, e.excess_returns.get(_REF_WINDOW, 0.0))
            for e in events
            if _REF_WINDOW in e.excess_returns
        ]
        if len(pairs) < 5:
            return 0.0

        confidences = [p[0] for p in pairs]
        returns = [p[1] for p in pairs]

        return SignalAttributionEngine._spearman_rank_corr(confidences, returns)

    @staticmethod
    def _compute_redundancy(
        signal_events: list[SignalEvent],
        system_events: list[SignalEvent],
    ) -> float:
        """
        Compute return-based redundancy (Pearson correlation).

        Joins events on (ticker, fired_date) and correlates the signal's
        excess returns with the system's average excess returns.
        High correlation means the signal mostly agrees with others.
        """
        # Index system events by (ticker, date) → avg excess return
        system_by_key: dict[tuple[str, object], list[float]] = defaultdict(list)
        for e in system_events:
            ret = e.excess_returns.get(_REF_WINDOW)
            if ret is not None:
                system_by_key[(e.ticker, e.fired_date)].append(ret)

        system_avg: dict[tuple[str, object], float] = {
            k: sum(v) / len(v) for k, v in system_by_key.items() if v
        }

        # Pair up signal returns with system returns at same (ticker, date)
        sig_vals: list[float] = []
        sys_vals: list[float] = []

        for e in signal_events:
            sig_ret = e.excess_returns.get(_REF_WINDOW)
            if sig_ret is None:
                continue
            key = (e.ticker, e.fired_date)
            if key in system_avg:
                sig_vals.append(sig_ret)
                sys_vals.append(system_avg[key])

        if len(sig_vals) < 5:
            return 0.0

        # Pearson correlation
        n = len(sig_vals)
        mean_s = sum(sig_vals) / n
        mean_y = sum(sys_vals) / n

        cov = sum((sig_vals[i] - mean_s) * (sys_vals[i] - mean_y) for i in range(n))
        var_s = sum((v - mean_s) ** 2 for v in sig_vals)
        var_y = sum((v - mean_y) ** 2 for v in sys_vals)

        denom = math.sqrt(var_s * var_y)
        if denom < 1e-12:
            return 0.0

        corr = cov / denom
        # Clamp to [0, 1] — negative correlation is not "redundancy"
        return max(0.0, min(1.0, corr))

    @staticmethod
    def _spearman_rank_corr(x: list[float], y: list[float]) -> float:
        """
        Spearman rank correlation (no scipy dependency).

        Converts both lists to ranks, then computes Pearson correlation
        on the ranks.
        """
        if len(x) != len(y) or len(x) < 3:
            return 0.0

        def _rank(vals: list[float]) -> list[float]:
            """Average-rank with tie handling."""
            n = len(vals)
            indexed = sorted(range(n), key=lambda i: vals[i])
            ranks = [0.0] * n
            i = 0
            while i < n:
                j = i
                while j < n - 1 and vals[indexed[j + 1]] == vals[indexed[j]]:
                    j += 1
                avg_rank = (i + j) / 2.0 + 1.0  # 1-indexed average
                for k in range(i, j + 1):
                    ranks[indexed[k]] = avg_rank
                i = j + 1
            return ranks

        rx = _rank(x)
        ry = _rank(y)

        n = len(rx)
        mean_rx = sum(rx) / n
        mean_ry = sum(ry) / n

        cov = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
        var_rx = sum((r - mean_rx) ** 2 for r in rx)
        var_ry = sum((r - mean_ry) ** 2 for r in ry)

        denom = math.sqrt(var_rx * var_ry)
        if denom < 1e-12:
            return 0.0

        return cov / denom

    # ── Persistence ──────────────────────────────────────────────────────

    @staticmethod
    def save_report(report: AttributionReport, path: Path) -> Path:
        """
        Persist an AttributionReport as JSON for audit trail.

        Parameters
        ----------
        report : AttributionReport
        path : Path
            File path to write (e.g., results/signal_attribution.json).

        Returns
        -------
        Path
            The written file path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "computed_at": report.computed_at.isoformat(),
            "system_sharpe": report.system_sharpe,
            "total_signals": report.total_signals,
            "effective_signal_count": report.effective_signal_count,
            "total_dilutive": report.total_dilutive,
            "avg_ic": report.avg_ic,
            "bair": report.bair,
            "signal_contributions": [
                {
                    "signal_id": c.signal_id,
                    "signal_name": c.signal_name,
                    "category": c.category.value if c.category else None,
                    "individual_firings": c.individual_firings,
                    "individual_sharpe": c.individual_sharpe,
                    "individual_avg_excess": c.individual_avg_excess,
                    "system_sharpe": c.system_sharpe,
                    "system_without_sharpe": c.system_without_sharpe,
                    "marginal_contribution": c.marginal_contribution,
                    "is_dilutive": c.is_dilutive,
                    "contribution_rank": c.contribution_rank,
                    "redundancy_score": c.redundancy_score,
                    "ic": c.ic,
                }
                for c in report.signal_contributions
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("ATTRIBUTION: Report saved to %s", path)
        return path

    @staticmethod
    def load_report(path: Path) -> AttributionReport | None:
        """Load a previously saved AttributionReport from JSON."""
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        contributions = [
            SignalContribution(
                signal_id=c["signal_id"],
                signal_name=c.get("signal_name", ""),
                category=c.get("category"),
                individual_firings=c.get("individual_firings", 0),
                individual_sharpe=c.get("individual_sharpe", 0.0),
                individual_avg_excess=c.get("individual_avg_excess", 0.0),
                system_sharpe=c.get("system_sharpe", 0.0),
                system_without_sharpe=c.get("system_without_sharpe", 0.0),
                marginal_contribution=c.get("marginal_contribution", 0.0),
                is_dilutive=c.get("is_dilutive", False),
                contribution_rank=c.get("contribution_rank", 0),
                redundancy_score=c.get("redundancy_score", 0.0),
                ic=c.get("ic", 0.0),
            )
            for c in data.get("signal_contributions", [])
        ]

        return AttributionReport(
            signal_contributions=contributions,
            system_sharpe=data.get("system_sharpe", 0.0),
            effective_signal_count=data.get("effective_signal_count", 0),
            total_dilutive=data.get("total_dilutive", 0),
            total_signals=data.get("total_signals", 0),
            avg_ic=data.get("avg_ic", 0.0),
            bair=data.get("bair", 0.0),
            computed_at=datetime.fromisoformat(data["computed_at"])
                if "computed_at" in data else datetime.now(timezone.utc),
        )

