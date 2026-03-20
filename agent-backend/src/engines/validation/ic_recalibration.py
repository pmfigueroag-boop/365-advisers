"""
src/engines/validation/ic_recalibration.py
──────────────────────────────────────────────────────────────────────────────
#5 + #6: IC Recalibration Engine.

Runs SignalDiagnostics on configurable universes (tech, non-tech, full)
and produces updated IC weight tables. Can be run monthly as a cron job
to keep IC weights fresh.

Output: dict[signal_id → float] per sector bucket, ready to drop into
the combiner's _IC_WEIGHTS_TECH / _IC_WEIGHTS_NON_TECH tables.

Usage:
    engine = ICRecalibrationEngine()
    report = engine.recalibrate()
    engine.print_report(report)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from src.engines.validation.signal_diagnostics import SignalDiagnostics
from src.engines.validation.universes import (
    TECH_UNIVERSE,
    NON_TECH_UNIVERSE,
    SYSTEMATIC_50,
    SECTOR_MAP,
)

logger = logging.getLogger("365advisers.validation.ic_recalibration")


# Sectors considered "tech" for IC bucketing
_TECH_SECTORS = {
    "Technology", "Communication Services", "Consumer Cyclical",
}


@dataclass
class ICCalibrationResult:
    """Calibration result for a single signal."""
    signal_id: str
    ic_tech: float = 0.0
    ic_non_tech: float = 0.0
    ic_all: float = 0.0
    fire_rate_tech: float = 0.0
    fire_rate_non_tech: float = 0.0
    sign_flipped: bool = False       # IC flipped sign vs current weight
    current_weight_tech: float = 0.0
    current_weight_non_tech: float = 0.0
    recommended_weight_tech: float = 0.0
    recommended_weight_non_tech: float = 0.0


@dataclass
class RecalibrationReport:
    """Full recalibration report."""
    calibration_date: str = ""
    tech_universe: list[str] = field(default_factory=list)
    non_tech_universe: list[str] = field(default_factory=list)
    results: list[ICCalibrationResult] = field(default_factory=list)
    # Alerts
    sign_flips: list[str] = field(default_factory=list)  # signals that flipped
    new_signals: list[str] = field(default_factory=list)  # signals with no prior weight
    dead_signals: list[str] = field(default_factory=list) # signals with IC ~0 everywhere


class ICRecalibrationEngine:
    """
    #5 + #6: Monthly IC recalibration.

    Steps:
      1. Run SignalDiagnostics on tech universe
      2. Run SignalDiagnostics on non-tech universe
      3. Compare fresh IC values vs current combiner weights
      4. Flag sign flips, dead signals, new discoveries
      5. Output recommended updated weight tables
    """

    def __init__(
        self,
        damping: float = 0.5,      # blend old and new: new_weight = damp * new_ic + (1-damp) * old_weight
        dead_threshold: float = 0.005,  # |IC| < 0.005 → dead
    ):
        self.damping = damping
        self.dead_threshold = dead_threshold
        self._diag = SignalDiagnostics()

    def recalibrate(
        self,
        tech_tickers: list[str] | None = None,
        non_tech_tickers: list[str] | None = None,
        years: int = 2,
    ) -> RecalibrationReport:
        """Run full recalibration across tech and non-tech universes."""
        from src.engines.alpha_signals.combiner import _IC_WEIGHTS_TECH, _IC_WEIGHTS_NON_TECH

        tech = tech_tickers or TECH_UNIVERSE
        non_tech = non_tech_tickers or NON_TECH_UNIVERSE

        report = RecalibrationReport(
            calibration_date=date.today().isoformat(),
            tech_universe=tech,
            non_tech_universe=non_tech,
        )

        logger.info(f"IC RECAL: Running tech universe ({len(tech)} tickers)...")
        tech_report = self._diag.run(tickers=tech, years=years)

        logger.info(f"IC RECAL: Running non-tech universe ({len(non_tech)} tickers)...")
        non_tech_report = self._diag.run(tickers=non_tech, years=years)

        # Extract IC at T+20 for each signal
        tech_ic: dict[str, float] = {}
        for dc in tech_report.decay_curves:
            ic_20 = dc.ic_by_horizon.get(20, 0.0)
            tech_ic[dc.signal_id] = ic_20

        non_tech_ic: dict[str, float] = {}
        for dc in non_tech_report.decay_curves:
            ic_20 = dc.ic_by_horizon.get(20, 0.0)
            non_tech_ic[dc.signal_id] = ic_20

        # Merge all signal IDs
        all_signals = sorted(set(tech_ic.keys()) | set(non_tech_ic.keys()))

        for sid in all_signals:
            ic_t = tech_ic.get(sid, 0.0)
            ic_nt = non_tech_ic.get(sid, 0.0)
            ic_all = (ic_t + ic_nt) / 2

            current_t = _IC_WEIGHTS_TECH.get(sid, 0.0)
            current_nt = _IC_WEIGHTS_NON_TECH.get(sid, 0.0)

            # Damped update: blend old weight with fresh IC
            rec_t = round(self.damping * ic_t + (1 - self.damping) * current_t, 4)
            rec_nt = round(self.damping * ic_nt + (1 - self.damping) * current_nt, 4)

            # Check for sign flip
            sign_flipped = False
            if current_t != 0 and ic_t != 0:
                sign_flipped = (current_t > 0) != (ic_t > 0)
            elif current_nt != 0 and ic_nt != 0:
                sign_flipped = (current_nt > 0) != (ic_nt > 0)

            result = ICCalibrationResult(
                signal_id=sid,
                ic_tech=round(ic_t, 4),
                ic_non_tech=round(ic_nt, 4),
                ic_all=round(ic_all, 4),
                current_weight_tech=current_t,
                current_weight_non_tech=current_nt,
                recommended_weight_tech=rec_t,
                recommended_weight_non_tech=rec_nt,
                sign_flipped=sign_flipped,
            )
            report.results.append(result)

            if sign_flipped:
                report.sign_flips.append(sid)
            if abs(ic_t) < self.dead_threshold and abs(ic_nt) < self.dead_threshold:
                report.dead_signals.append(sid)
            if current_t == 0 and current_nt == 0 and (abs(ic_t) > 0.01 or abs(ic_nt) > 0.01):
                report.new_signals.append(sid)

        return report

    @staticmethod
    def print_report(report: RecalibrationReport) -> str:
        """Format recalibration report."""
        lines = [
            "=" * 90,
            f"IC RECALIBRATION REPORT — {report.calibration_date}",
            "=" * 90,
            f"Tech universe: {', '.join(report.tech_universe)}",
            f"Non-tech universe: {', '.join(report.non_tech_universe)}",
            "",
        ]

        # Alerts
        if report.sign_flips:
            lines.append(f"⚠️  SIGN FLIPS ({len(report.sign_flips)}): {', '.join(report.sign_flips)}")
        if report.dead_signals:
            lines.append(f"💀 DEAD SIGNALS ({len(report.dead_signals)}): {', '.join(report.dead_signals[:10])}")
        if report.new_signals:
            lines.append(f"🆕 NEW DISCOVERIES ({len(report.new_signals)}): {', '.join(report.new_signals)}")

        lines.extend([
            "",
            f"  {'Signal':<45} {'IC_T':>7} {'IC_NT':>7} {'Cur_T':>7} {'Rec_T':>7} {'Cur_NT':>7} {'Rec_NT':>7} {'Flip':>5}",
            "  " + "-" * 95,
        ])

        # Sort by absolute IC (all)
        for r in sorted(report.results, key=lambda x: abs(x.ic_all), reverse=True):
            flip = " ⚠️" if r.sign_flipped else ""
            lines.append(
                f"  {r.signal_id:<45} "
                f"{r.ic_tech:>+.4f} "
                f"{r.ic_non_tech:>+.4f} "
                f"{r.current_weight_tech:>+.4f} "
                f"{r.recommended_weight_tech:>+.4f} "
                f"{r.current_weight_non_tech:>+.4f} "
                f"{r.recommended_weight_non_tech:>+.4f}"
                f"{flip}"
            )

        lines.extend([
            "",
            "=" * 90,
            "To apply: copy 'Rec_T' and 'Rec_NT' columns to _IC_WEIGHTS_TECH / _IC_WEIGHTS_NON_TECH",
            "=" * 90,
        ])

        text = "\n".join(lines)
        print(text)
        return text
