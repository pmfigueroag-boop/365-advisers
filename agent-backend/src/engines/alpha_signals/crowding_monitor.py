"""
src/engines/alpha_signals/crowding_monitor.py
──────────────────────────────────────────────────────────────────────────────
#9: Signal Capacity & Crowding Monitor.

Monitors signal crowding risk and estimates capacity constraints:
  - How many tickers fire the same signal simultaneously?
  - Is volume sufficient to execute signal-generated trades?
  - Are signals becoming crowded (everyone uses the same factor)?

Architecture:
  - Tracks signal fire rates across the universe
  - Estimates execution capacity from historical volume
  - Alerts when signals become too crowded (>60% fire rate)
  - Computes capacity decay curves for each signal

Usage:
    monitor = CrowdingMonitor()
    report = monitor.analyze(signal_profiles, volume_data)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.alpha_signals.crowding_monitor")


@dataclass
class SignalCrowding:
    """Crowding analysis for a single signal."""
    signal_id: str
    fire_rate: float              # % of universe where signal fires
    avg_confidence_when_fired: float
    concurrent_fire_count: int    # number of tickers firing simultaneously
    universe_size: int
    # Capacity
    estimated_capacity_usd: float = 0.0   # max $ before alpha decay
    volume_impact_pct: float = 0.0        # trade volume / ADV
    # Risk
    crowding_level: str = "LOW"           # LOW, MODERATE, HIGH, EXTREME
    alpha_decay_risk: float = 0.0         # 0-1 probability of alpha decay


@dataclass
class CrowdingReport:
    """Complete crowding analysis report."""
    universe_size: int = 0
    total_signals_monitored: int = 0
    crowded_signals: list[SignalCrowding] = field(default_factory=list)
    # Summary
    avg_fire_rate: float = 0.0
    max_fire_rate: float = 0.0
    signals_at_risk: int = 0      # signals with crowding ≥ HIGH
    total_capacity_usd: float = 0.0


class CrowdingMonitor:
    """
    #9: Monitor signal crowding and capacity constraints.

    Key metrics:
      - Fire Rate: what % of the universe fires this signal?
        - < 10% = niche (good alpha, low capacity)
        - 10-30% = balanced
        - 30-60% = getting crowded
        - > 60% = extremely crowded (alpha likely decayed)

      - Capacity: how much $ can we deploy before moving the market?
        - Based on historical ADV and assumed max impact of 1% of ADV

      - Alpha Decay Risk: P(signal loses predictive power)
        - Driven by fire_rate, volume_impact, and signal age
    """

    def __init__(
        self,
        crowding_threshold: float = 0.30,     # 30% fire rate → "moderate"
        high_crowding_threshold: float = 0.60, # 60% fire rate → "high"
        max_volume_impact: float = 0.01,       # max 1% of ADV per trade
        target_position_usd: float = 100_000,  # typical position size
    ):
        self.crowding_threshold = crowding_threshold
        self.high_crowding_threshold = high_crowding_threshold
        self.max_volume_impact = max_volume_impact
        self.target_position_usd = target_position_usd

    def analyze(
        self,
        signal_profiles: list[dict[str, bool | float]],
        volume_data: dict[str, float] | None = None,
        prices: dict[str, float] | None = None,
    ) -> CrowdingReport:
        """
        Analyze crowding across signal profiles for the entire universe.

        Parameters
        ----------
        signal_profiles : list[dict]
            One dict per ticker: {signal_id: confidence_if_fired (0 if not)}
        volume_data : dict[str, float] | None
            {ticker: average_daily_volume_usd}
        prices : dict[str, float] | None
            {ticker: current_price}
        """
        universe_size = len(signal_profiles)
        if universe_size == 0:
            return CrowdingReport()

        volume_data = volume_data or {}
        prices = prices or {}

        # Aggregate fire rates per signal
        signal_fires: dict[str, list[float]] = {}  # signal_id → [confidence_values]

        for profile in signal_profiles:
            for signal_id, confidence in profile.items():
                if confidence > 0:
                    signal_fires.setdefault(signal_id, []).append(confidence)

        # Compute per-signal crowding
        crowding_results: list[SignalCrowding] = []

        for signal_id, confidences in signal_fires.items():
            fire_count = len(confidences)
            fire_rate = fire_count / universe_size

            avg_conf = sum(confidences) / len(confidences) if confidences else 0

            # Estimate capacity
            # Assume we trade all tickers where signal fires
            # Max capacity = sum(ADV * max_impact) for all fired tickers
            total_capacity = 0.0
            avg_volume_impact = 0.0

            if volume_data:
                for ticker, adv in volume_data.items():
                    capacity = adv * self.max_volume_impact
                    total_capacity += capacity

                if total_capacity > 0 and fire_count > 0:
                    avg_volume_impact = self.target_position_usd / (total_capacity / fire_count)

            # Crowding level classification
            if fire_rate >= self.high_crowding_threshold:
                level = "EXTREME"
            elif fire_rate >= self.crowding_threshold:
                level = "HIGH"
            elif fire_rate >= 0.15:
                level = "MODERATE"
            else:
                level = "LOW"

            # Alpha decay risk model
            # Higher fire rate + higher volume impact → more decay risk
            fire_rate_risk = min(1.0, fire_rate / self.high_crowding_threshold)
            volume_risk = min(1.0, avg_volume_impact / 0.05)  # 5% impact = max risk
            alpha_decay_risk = 0.4 * fire_rate_risk + 0.3 * volume_risk + 0.3 * (1 - avg_conf)

            crowding_results.append(SignalCrowding(
                signal_id=signal_id,
                fire_rate=round(fire_rate, 4),
                avg_confidence_when_fired=round(avg_conf, 4),
                concurrent_fire_count=fire_count,
                universe_size=universe_size,
                estimated_capacity_usd=round(total_capacity, 0),
                volume_impact_pct=round(avg_volume_impact * 100, 2),
                crowding_level=level,
                alpha_decay_risk=round(alpha_decay_risk, 4),
            ))

        # Sort by crowding level (worst first)
        level_order = {"EXTREME": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
        crowding_results.sort(key=lambda c: (level_order.get(c.crowding_level, 4), -c.fire_rate))

        # Summary
        fire_rates = [c.fire_rate for c in crowding_results]
        at_risk = sum(1 for c in crowding_results if c.crowding_level in ("HIGH", "EXTREME"))

        return CrowdingReport(
            universe_size=universe_size,
            total_signals_monitored=len(crowding_results),
            crowded_signals=crowding_results,
            avg_fire_rate=round(sum(fire_rates) / len(fire_rates), 4) if fire_rates else 0,
            max_fire_rate=max(fire_rates) if fire_rates else 0,
            signals_at_risk=at_risk,
            total_capacity_usd=sum(c.estimated_capacity_usd for c in crowding_results),
        )

    @staticmethod
    def print_report(report: CrowdingReport) -> str:
        """Format crowding report."""
        lines = [
            "=" * 90,
            "SIGNAL CROWDING & CAPACITY MONITOR (#9)",
            "=" * 90,
            f"Universe size: {report.universe_size}",
            f"Signals monitored: {report.total_signals_monitored}",
            f"Signals at risk (HIGH/EXTREME): {report.signals_at_risk}",
            f"Avg fire rate: {report.avg_fire_rate:.1%}",
            f"Max fire rate: {report.max_fire_rate:.1%}",
            "",
            f"  {'Signal':<45} {'Fire%':>6} {'#Fire':>6} {'Level':>8} {'Decay':>6} {'Conf':>6}",
            "  " + "-" * 80,
        ]

        for c in report.crowded_signals:
            emoji = {"EXTREME": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(c.crowding_level, "⚪")
            lines.append(
                f"  {c.signal_id:<45} "
                f"{c.fire_rate:>5.1%} "
                f"{c.concurrent_fire_count:>6} "
                f"{emoji} {c.crowding_level:<7} "
                f"{c.alpha_decay_risk:>5.1%} "
                f"{c.avg_confidence_when_fired:>5.2f}"
            )

        lines.extend([
            "",
            "─── Crowding Legend ────────────────────────────────────────",
            "  🟢 LOW    (<15%):  Niche signal — strong alpha potential",
            "  🟡 MODERATE (15-30%): Balanced — monitor regularly",
            "  🟠 HIGH   (30-60%): Getting crowded — alpha may decay",
            "  🔴 EXTREME (>60%):  Very crowded — likely commoditized",
            "=" * 90,
        ])

        text = "\n".join(lines)
        print(text)
        return text
