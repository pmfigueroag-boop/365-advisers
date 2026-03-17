"""
scripts/run_signal_attribution.py
--------------------------------------------------------------------------
Signal Attribution Runner — computes marginal alpha contribution per signal
using leave-one-out analysis on completed backtest data.

Usage:
    cd agent-backend

    # Run attribution on a test universe
    python scripts/run_signal_attribution.py

    # Larger universe with longer lookback
    python scripts/run_signal_attribution.py --universe mega_cap --start 2023-01-01

    # Include fundamental signals
    python scripts/run_signal_attribution.py --universe sp500_100 --fundamental

    # Custom output path
    python scripts/run_signal_attribution.py --output results/my_attribution.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -- Project root -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# -- Auto-register all alpha signals ------------------------------------------
import src.engines.alpha_signals  # noqa: F401  - triggers registry
from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.models import BacktestConfig
from src.engines.backtesting.signal_attribution import (
    SignalAttributionEngine,
    AttributionReport,
)
from src.engines.backtesting.universes import get_universe, list_universes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("signal_attribution")


# =============================================================================
# Report Formatter
# =============================================================================

def format_attribution_report(report: AttributionReport) -> str:
    """Format an AttributionReport into a readable console table."""
    lines: list[str] = []
    lines.append("=" * 90)
    lines.append("  SIGNAL ALPHA ATTRIBUTION REPORT")
    lines.append("=" * 90)
    lines.append(f"  System Sharpe@20d: {report.system_sharpe:+.4f}")
    lines.append(f"  Total Signals:     {report.total_signals}")
    lines.append(f"  Effective:         {report.effective_signal_count}")
    lines.append(f"  Dilutive:          {report.total_dilutive}")
    lines.append(f"  Avg IC:            {report.avg_ic:+.4f}")
    lines.append(f"  BAIR:              {report.bair:+.4f}  (IC × √BR_eff)")
    lines.append(f"  Computed At:       {report.computed_at.isoformat()}")
    lines.append("=" * 90)

    # Table header
    hdr = (
        f"  {'Rank':>4}  {'Signal':<35} {'N':>5} "
        f"{'Sharpe':>8} {'Contrib':>9} {'Redund':>7} {'Status':>8}"
    )
    lines.append(f"\n{hdr}")
    lines.append("  " + "-" * 84)

    for c in report.signal_contributions:
        status = "DILUTV" if c.is_dilutive else "  OK  "
        tag = "[-]" if c.is_dilutive else "[+]"
        redund = f"{c.redundancy_score:.2f}" if c.redundancy_score > 0 else "  --"

        lines.append(
            f"  {c.contribution_rank:>4}  "
            f"{(c.signal_name or c.signal_id):<35} "
            f"{c.individual_firings:>5} "
            f"{c.individual_sharpe:>+8.2f} "
            f"{c.marginal_contribution:>+9.4f} "
            f"{redund:>7} "
            f"{tag}{status}"
        )

    # Summary
    if report.total_dilutive > 0:
        lines.append(f"\n  ⚠  {report.total_dilutive} dilutive signal(s) detected.")
        dilutive = [
            c for c in report.signal_contributions if c.is_dilutive
        ]
        for c in dilutive:
            lines.append(
                f"     → {c.signal_name or c.signal_id}: "
                f"contribution={c.marginal_contribution:+.4f}"
            )

    redundant = [
        c for c in report.signal_contributions if c.redundancy_score > 0.7
    ]
    if redundant:
        lines.append(f"\n  ⚠  {len(redundant)} highly redundant signal(s):")
        for c in redundant:
            lines.append(
                f"     → {c.signal_name or c.signal_id}: "
                f"redundancy={c.redundancy_score:.2f}"
            )

    lines.append("\n" + "=" * 90)
    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Signal Alpha Attribution Runner")
    parser.add_argument(
        "--universe", type=str, default="test",
        help=f"Universe name: {', '.join(list_universes().keys())}",
    )
    parser.add_argument("--max-tickers", type=int, default=None, help="Limit universe size")
    parser.add_argument("--start", type=str, default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--fundamental", action="store_true", help="Include fundamental signals")
    parser.add_argument("--benchmark", type=str, default="SPY", help="Benchmark ticker")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON path (default: results/signal_attribution.json)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    start = time.monotonic()

    logger.info("=" * 60)
    logger.info("SIGNAL ALPHA ATTRIBUTION RUNNER")
    logger.info("=" * 60)

    # Show registered signals
    summary = signal_registry.summary()
    total_signals = sum(summary.values())
    logger.info(f"Registered signals: {total_signals} across {len(summary)} categories")

    # Universe
    universe = get_universe(args.universe, args.max_tickers)
    logger.info(f"Universe: {args.universe} ({len(universe)} tickers)")

    # Config
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end) if args.end else date.today()

    logger.info(f"Period: {start_date} -> {end_date}")
    logger.info(f"Fundamentals: {args.fundamental}")
    logger.info(f"Benchmark: {args.benchmark}")

    # ── Step 1: Run backtest to collect events ───────────────────────────
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

    logger.info("\n>>> Step 1: Running backtest to collect signal events...")
    engine = BacktestEngine()

    # We need the raw events — use the internal pipeline
    signals = engine._get_signals(config.signal_ids)
    if not signals:
        logger.error("No enabled signals found. Cannot run attribution.")
        return

    ohlcv_data = await engine._fetch_historical_data(
        config.universe + [config.benchmark_ticker],
        config.start_date,
        config.end_date,
    )

    from src.engines.backtesting.return_tracker import ReturnTracker
    import pandas as pd

    benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
    return_tracker = ReturnTracker(benchmark_ohlcv)

    all_events = []
    for ticker in config.universe:
        ticker_ohlcv = ohlcv_data.get(ticker)
        if ticker_ohlcv is None or ticker_ohlcv.empty:
            continue
        events = engine._evaluator.evaluate(
            ticker=ticker, ohlcv=ticker_ohlcv,
            signals=signals, forward_windows=config.forward_windows,
        )
        events = return_tracker.enrich(events, config.forward_windows)
        all_events.extend(events)

    logger.info(f"Collected {len(all_events)} events across {len(signals)} signals")

    # ── Step 2: Run attribution ──────────────────────────────────────────
    logger.info("\n>>> Step 2: Running leave-one-out attribution...")
    signal_meta = {
        s.id: (s.name, s.category) for s in signals
    }
    attr_engine = SignalAttributionEngine()
    report = attr_engine.compute(all_events, signal_meta)

    # ── Step 3: Print report ─────────────────────────────────────────────
    print("\n" + format_attribution_report(report))

    # ── Step 4: Persist ──────────────────────────────────────────────────
    results_dir = PROJECT_ROOT / "results"
    output_path = Path(args.output) if args.output else results_dir / "signal_attribution.json"
    attr_engine.save_report(report, output_path)

    elapsed = time.monotonic() - start
    logger.info(f"\n{'=' * 60}")
    logger.info(f"ATTRIBUTION COMPLETE in {elapsed:.1f}s")
    logger.info(f"Results: {output_path}")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
