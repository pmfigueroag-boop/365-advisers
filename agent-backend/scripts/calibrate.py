"""
scripts/calibrate.py
--------------------------------------------------------------------------
Adaptive Signal Calibration Orchestrator.

Executes the full calibration loop:
  1. Run backtest (rolling window)
  2. Analyze signal performance
  3. Detect current market regime
  4. Compute regime-conditional weights
  5. Run through governor (validate changes)
  6. Save new version
  7. Optionally apply to registry (--apply flag)
  8. Print diff report

Usage:
    cd agent-backend

    # Dry-run calibration (test universe)
    python scripts/calibrate.py

    # With larger universe, apply changes
    python scripts/calibrate.py --universe mega_cap --apply

    # Full calibration
    python scripts/calibrate.py --universe sp500_100 --fundamental --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Force UTF-8 on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Auto-register signals
import src.engines.alpha_signals  # noqa: F401
from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.models import BacktestConfig
from src.engines.backtesting.universes import get_universe
from src.engines.backtesting.regime_detector import RegimeDetector
from src.engines.backtesting.adaptive_calibrator import AdaptiveCalibrator
from src.engines.backtesting.calibration_governor import CalibrationGovernor
from src.engines.backtesting.calibration_store import CalibrationStore
from src.engines.backtesting.calibration_models import (
    CalibrationConfig,
    CalibrationVersion,
    GovernanceAction,
    GovernanceDecision,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("calibrate")


def parse_args():
    parser = argparse.ArgumentParser(description="Adaptive Signal Calibration")
    parser.add_argument("--universe", default="test", help="Universe name")
    parser.add_argument("--lookback", type=int, default=250, help="Rolling window (trading days)")
    parser.add_argument("--fundamental", action="store_true", help="Include fundamentals")
    parser.add_argument("--apply", action="store_true", help="Apply APPROVED changes to registry")
    parser.add_argument("--approve-flagged", action="store_true", help="Also apply FLAGGED changes (requires review)")
    parser.add_argument("--benchmark", default="SPY", help="Benchmark ticker")
    parser.add_argument("--max-change", type=float, default=0.20, help="Max change %%")
    return parser.parse_args()


def format_calibration_report(
    version, decisions, approved_changes, rejected, flagged,
    calibrated_configs=None,
) -> str:
    """Format calibration results for console output with percentage diff table."""
    lines = []
    lines.append("=" * 90)
    lines.append("  ADAPTIVE SIGNAL CALIBRATION REPORT (Hardened v2)")
    lines.append("=" * 90)
    lines.append(f"  Version      : {version.version}")
    lines.append(f"  Universe     : {version.universe_name} ({version.universe_size} tickers)")
    lines.append(f"  Lookback     : {version.lookback_days} days")
    lines.append(f"  Signals Cal. : {version.signals_calibrated}")
    lines.append(f"  Changes      : {len(approved_changes)} approved, {len(rejected)} rejected, {len(flagged)} flagged")
    lines.append(f"  Formula      : Bayesian shrinkage w' = base * [alpha * (1+IC) + (1-alpha) * prior]")
    lines.append("=" * 90)

    # ── FULL PERCENTAGE DIFF TABLE ──
    if calibrated_configs:
        lines.append("\n-- SIGNAL CALIBRATION DIFF (all signals) ---------------------------------")
        lines.append(f"  {'Signal':<38} {'Old':>6} {'New':>6} {'Chg%':>7} {'Conf':>6} {'Sharpe':>7} {'Action':>10}")
        lines.append(f"  {'-'*38} {'-'*6} {'-'*6} {'-'*7} {'-'*6} {'-'*7} {'-'*10}")

        # Build lookup of decisions and original weights
        decision_map = {}
        for d in decisions:
            key = (d.change.signal_id, d.change.parameter)
            decision_map[key] = d

        for cfg in sorted(calibrated_configs, key=lambda c: c.weight, reverse=True):
            # Find original weight from registry
            from src.engines.alpha_signals.registry import registry
            sig_def = registry.get(cfg.signal_id)
            old_w = sig_def.weight if sig_def else 1.0

            chg_pct = ((cfg.weight - old_w) / old_w * 100) if old_w > 0 else 0.0
            chg_str = f"{chg_pct:+.1f}%"

            # Find governance action
            d = decision_map.get((cfg.signal_id, "weight"))
            if d is not None:
                action = d.action.value.upper()
            elif abs(chg_pct) < 1.0:
                action = "NO_CHANGE"
            else:
                action = "N/A"

            # Find Sharpe from the version's performance data
            sharpe = "N/A"
            for rt in version.regime_weights:
                if cfg.signal_id in rt.sharpe_by_signal:
                    sharpe = f"{rt.sharpe_by_signal[cfg.signal_id]:+.2f}"
                    break

            short_id = cfg.signal_id.split(".")[-1] if "." in cfg.signal_id else cfg.signal_id
            lines.append(
                f"  {short_id:<38} {old_w:6.3f} {cfg.weight:6.4f} {chg_str:>7} "
                f"{cfg.confidence_score:6.3f} {sharpe:>7} {action:>10}"
            )

    # ── APPROVED CHANGES (detailed) ──
    if approved_changes:
        lines.append("\n-- APPROVED CHANGES (with evidence) --------------------------------------")
        for ch in approved_changes:
            direction = "+" if ch.new_value > ch.old_value else "-"
            lines.append(
                f"  {ch.signal_id:<38} | {ch.parameter:>10}: "
                f"{ch.old_value:.4f} -> {ch.new_value:.4f} ({direction}{ch.change_pct:.0%}) "
                f"| {ch.evidence}"
            )

    if rejected:
        lines.append("\n-- REJECTED CHANGES (governance) -----------------------------------------")
        for d in rejected:
            lines.append(
                f"  {d.change.signal_id:<38} | {d.change.parameter:>10}: "
                f"{d.change.old_value:.4f} -> {d.change.new_value:.4f} "
                f"| REASON: {d.reason}"
            )

    if flagged:
        lines.append("\n-- FLAGGED FOR REVIEW (use --approve-flagged to apply) -------------------")
        for ch in flagged:
            lines.append(
                f"  {ch.signal_id:<38} | {ch.parameter:>10}: "
                f"{ch.old_value:.4f} -> {ch.new_value:.4f} "
                f"| {ch.evidence}"
            )

    # ── REGIME WEIGHTS ──
    if version.regime_weights:
        lines.append("\n-- REGIME-CONDITIONAL WEIGHTS (top 5 per regime) -------------------------")
        for rt in version.regime_weights:
            if rt.sample_size == 0:
                continue
            sorted_w = sorted(rt.weights.items(), key=lambda x: x[1], reverse=True)[:5]
            weights_str = ", ".join(f"{s.split('.')[-1]}={w:.2f}" for s, w in sorted_w)
            lines.append(f"  {rt.regime:<12} ({rt.sample_size:>4} days) | {weights_str}")

    # ── PERFORMANCE ──
    if version.performance_snapshot:
        lines.append("\n-- PERFORMANCE SNAPSHOT ---------------------------------------------------")
        for k, v in sorted(version.performance_snapshot.items()):
            lines.append(f"  {k:<30}: {v:.4f}")

    lines.append("\n" + "=" * 90)
    return "\n".join(lines)


async def main():
    args = parse_args()
    t0 = time.monotonic()

    logger.info("=" * 60)
    logger.info("ADAPTIVE SIGNAL CALIBRATION")
    logger.info("=" * 60)

    universe = get_universe(args.universe)

    # Rolling window: need lookback (trading) + 200 warmup + 60 fwd ≈ 500+ calendar days
    end_date = date.today()
    calendar_days = int(args.lookback * 2.0) + 360  # 2x for weekends + 360 for warmup/fwd
    start_date = end_date - timedelta(days=calendar_days)

    logger.info(f"Universe: {args.universe} ({len(universe)} tickers)")
    logger.info(f"Rolling window: {start_date} -> {end_date} (~{args.lookback} trading days)")
    logger.info(f"Fundamentals: {args.fundamental}")

    # Step 1: Run backtest
    logger.info("\n>>> Step 1: Running backtest...")
    config = BacktestConfig(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        forward_windows=[1, 5, 10, 20, 60],
        benchmark_ticker=args.benchmark,
        min_observations=10,
        cooldown_factor=0.5,
        include_fundamentals=args.fundamental,
    )

    engine = BacktestEngine()
    report = await engine.run(config)

    if report.error_message:
        logger.error(f"Backtest failed: {report.error_message}")
        return

    logger.info(
        f"Backtest complete: {len(report.signal_results)} signals, "
        f"{report.execution_time_seconds:.1f}s"
    )

    # Step 2: Detect market regimes
    logger.info("\n>>> Step 2: Detecting market regimes...")
    regime_detector = RegimeDetector()

    # Fetch benchmark data for regime detection
    benchmark_data = await BacktestEngine._fetch_historical_data(
        [args.benchmark], start_date, end_date,
    )
    benchmark_ohlcv = benchmark_data.get(args.benchmark)
    regime_map = {}
    if benchmark_ohlcv is not None and not benchmark_ohlcv.empty:
        regime_map = regime_detector.classify(benchmark_ohlcv)

    # Step 3: Calibrate
    logger.info("\n>>> Step 3: Running adaptive calibration...")
    cal_config = CalibrationConfig(
        lookback_days=args.lookback,
        max_change_pct=args.max_change,
    )
    calibrator = AdaptiveCalibrator(cal_config)
    proposed_changes, calibrated_configs, regime_tables = calibrator.calibrate(
        report, regime_map,
    )

    # Step 4: Governance
    logger.info("\n>>> Step 4: Running governance review...")
    governor = CalibrationGovernor(cal_config)
    records_map = {r.signal_id: r for r in report.signal_results}
    decisions = governor.review(proposed_changes, records_map)

    approved_changes = governor.get_approved(decisions)
    flagged_changes = governor.get_flagged(decisions)
    rejected = governor.get_rejected(decisions)

    # Determine what gets applied
    applied_changes = list(approved_changes)
    if args.approve_flagged:
        applied_changes.extend(flagged_changes)
        logger.info(f"--approve-flagged: Including {len(flagged_changes)} flagged changes")

    # Step 5: Build version
    logger.info("\n>>> Step 5: Building calibration version...")
    store = CalibrationStore()
    version_tag = store.get_next_version_tag()

    # Performance snapshot
    perf_snapshot = {}
    if report.signal_results:
        sharpes = [r.sharpe_ratio.get(20, 0.0) for r in report.signal_results]
        hit_rates = [r.hit_rate.get(20, 0.0) for r in report.signal_results]
        perf_snapshot = {
            "avg_sharpe_20d": sum(sharpes) / len(sharpes),
            "avg_hit_rate_20d": sum(hit_rates) / len(hit_rates),
            "total_signals": len(report.signal_results),
            "total_events": sum(r.total_firings for r in report.signal_results),
        }

    version = CalibrationVersion(
        version=version_tag,
        lookback_days=args.lookback,
        universe_name=args.universe,
        universe_size=len(universe),
        signals_calibrated=len(calibrated_configs),
        changes_applied=applied_changes,
        changes_rejected=rejected,
        changes_flagged=[GovernanceDecision(change=c, action=GovernanceAction.FLAGGED) for c in flagged_changes],
        signal_configs=calibrated_configs,
        regime_weights=regime_tables,
        performance_snapshot=perf_snapshot,
    )

    # Step 6: Save
    path = store.save_version(version)
    logger.info(f"Saved calibration {version_tag} to {path}")

    # Step 7: Apply (if requested)
    if args.apply:
        if not applied_changes:
            logger.warning("\n>>> Step 7: No approved changes to apply")
        else:
            logger.info(f"\n>>> Step 7: Applying {len(applied_changes)} changes to registry...")
            updated = store.apply_to_registry(version, signal_registry)
            logger.info(f"Applied {version_tag} -- {updated} signals updated")
        if flagged_changes and not args.approve_flagged:
            logger.info(
                f"    {len(flagged_changes)} flagged changes held for review. "
                f"Use --approve-flagged to include them."
            )
    else:
        logger.info("\n>>> Step 7: DRY RUN -- use --apply to apply changes")

    # Step 8: Print report
    report_str = format_calibration_report(
        version, decisions, applied_changes, rejected, flagged_changes,
        calibrated_configs=calibrated_configs,
    )
    print("\n" + report_str)

    elapsed = time.monotonic() - t0
    logger.info(f"\nCalibration complete in {elapsed:.1f}s")

    # Save report to results
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    report_path = results_dir / "calibration_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(version.model_dump(mode="json"), f, indent=2, default=str)
    logger.info(f"Report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
