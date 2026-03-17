"""
scripts/signal_backtest_runner.py
--------------------------------------------------------------------------
Signal Backtest Runner - runs the BacktestEngine against configurable
universes and prints formatted reports of per-signal performance.

Usage:
    cd agent-backend

    # Basic test (10 tickers, technical only)
    python scripts/signal_backtest_runner.py

    # With fundamentals
    python scripts/signal_backtest_runner.py --fundamental

    # Larger universe
    python scripts/signal_backtest_runner.py --universe sp500_100 --fundamental

    # Cross-sectional ranking
    python scripts/signal_backtest_runner.py --universe mega_cap --cross-sectional

    # Full institutional run
    python scripts/signal_backtest_runner.py --universe sp500_100 --fundamental --cross-sectional --start 2021-01-01
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
from src.engines.backtesting.universes import get_universe, list_universes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("signal_backtest")


# =============================================================================
# Report Formatters
# =============================================================================

def format_signal_report(report) -> str:
    """Format BacktestReport into a readable console string."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("  SIGNAL BACKTEST REPORT")
    lines.append("=" * 80)
    lines.append(f"  Run ID       : {report.run_id}")
    lines.append(f"  Status       : {report.status.value}")
    lines.append(f"  Universe     : {len(report.config.universe)} tickers")
    lines.append(f"  Date Range   : {report.config.start_date} -> {report.config.end_date}")
    lines.append(f"  Fundamentals : {report.config.include_fundamentals}")
    lines.append(f"  Benchmark    : {report.config.benchmark_ticker}")
    lines.append(f"  Signals Eval : {len(report.signal_results)}")
    lines.append(f"  Execution    : {report.execution_time_seconds:.1f}s")
    lines.append("=" * 80)

    if report.error_message:
        lines.append(f"\n  ERROR: {report.error_message}\n")
        return "\n".join(lines)

    # Per-Signal Results
    lines.append("\n-- PER-SIGNAL PERFORMANCE ---------------------------------------------")
    hdr = f"{'Signal':<40} {'Cat':>8} {'N':>5} {'HR@5d':>7} {'HR@20d':>7} {'AvgR@20d':>10} {'Sharpe20':>9} {'Conf':>6}"
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for r in report.signal_results:
        hr5 = r.hit_rate.get(5, 0.0)
        hr20 = r.hit_rate.get(20, 0.0)
        avg20 = r.avg_return.get(20, 0.0)
        sh20 = r.sharpe_ratio.get(20, 0.0)

        hr5_str = f"{hr5:.1%}"
        hr20_str = f"{hr20:.1%}"
        avg20_str = f"{avg20:+.4f}"
        sh20_str = f"{sh20:+.2f}"
        tag = "[+]" if hr20 >= 0.55 else "[~]" if hr20 >= 0.45 else "[-]"

        lines.append(
            f"  {r.signal_name:<38} {r.category.value:>8} {r.total_firings:>5} "
            f"{tag}{hr5_str:>6} {hr20_str:>7} {avg20_str:>10} "
            f"{sh20_str:>9} {r.confidence_level:>6}"
        )

    # Category Summaries
    if report.category_summaries:
        lines.append("\n-- CATEGORY SUMMARIES -------------------------------------------------")
        for cs in report.category_summaries:
            lines.append(
                f"  {cs.category.value:<14} | "
                f"Signals: {cs.signal_count:>2} | "
                f"HitRate: {cs.avg_hit_rate:.1%} | "
                f"Sharpe: {cs.avg_sharpe:+.2f} | "
                f"Alpha: {cs.category_alpha:+.4f}"
            )

    if report.top_signals:
        lines.append(f"\n  [TOP] Top signals: {', '.join(report.top_signals[:5])}")
    if report.underperforming_signals:
        lines.append(f"  [!] Underperformers: {', '.join(report.underperforming_signals[:5])}")

    if report.calibration_suggestions:
        lines.append("\n-- CALIBRATION SUGGESTIONS --------------------------------------------")
        for s in report.calibration_suggestions[:10]:
            lines.append(
                f"  {s.signal_id:<35} | {s.parameter:>10}: "
                f"{s.current_value:.3f} -> {s.suggested_value:.3f} | {s.evidence}"
            )

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


def format_cross_sectional_report(report) -> str:
    """Format CrossSectionalReport for console."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("  CROSS-SECTIONAL RANKING REPORT")
    lines.append("=" * 80)
    lines.append(f"  Universe     : {len(report.config.universe)} tickers")
    lines.append(f"  Periods      : {report.total_periods}")
    lines.append(f"  Execution    : {report.execution_time_seconds:.1f}s")
    lines.append("=" * 80)

    # Quintile returns
    lines.append("\n-- QUINTILE AVERAGE RETURNS -------------------------------------------")
    for w in report.config.forward_windows:
        lines.append(f"\n  T+{w} days:")
        for p in report.periods[:1]:  # Show first period as example
            if p.quintiles:
                for q in p.quintiles:
                    ret = q.avg_return.get(w, 0.0)
                    exc = q.avg_excess_return.get(w, 0.0)
                    tag = "[+]" if ret > 0 else "[-]"
                    lines.append(
                        f"    Q{q.quintile} ({q.n_tickers:>3} tickers) | "
                        f"Score: {q.avg_score:.4f} | "
                        f"Return: {tag} {ret:+.4f} | "
                        f"Excess: {exc:+.4f}"
                    )

    # Aggregate spread
    lines.append("\n-- AGGREGATE SPREAD (Q1 - Q5) -----------------------------------------")
    for w in report.config.forward_windows:
        spread = report.avg_spread.get(w, 0.0)
        t_stat = report.spread_t_stat.get(w, 0.0)
        p_val = report.spread_p_value.get(w, 1.0)
        mono = report.is_monotonic.get(w, 0.0)

        sig_str = "***" if p_val < 0.01 else "**" if p_val < 0.05 else "*" if p_val < 0.1 else ""
        lines.append(
            f"  T+{w:>2}d | Spread: {spread:+.4f} | "
            f"t-stat: {t_stat:+.2f}{sig_str} | "
            f"p-value: {p_val:.4f} | "
            f"Monotonicity: {mono:.2f}"
        )

    lines.append(f"\n  Q1 Turnover: {report.avg_turnover:.1%}")
    lines.append(f"  Avg Q1 Return@20d: {report.avg_q1_return.get(20, 0):+.4f}")
    lines.append(f"  Avg Q5 Return@20d: {report.avg_q5_return.get(20, 0):+.4f}")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Signal Backtest Runner")
    parser.add_argument(
        "--universe", type=str, default="test",
        help=f"Universe name: {', '.join(list_universes().keys())}",
    )
    parser.add_argument("--max-tickers", type=int, default=None, help="Limit universe size")
    parser.add_argument("--start", type=str, default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--fundamental", action="store_true", help="Include fundamental signals")
    parser.add_argument("--cross-sectional", action="store_true", help="Run cross-sectional ranking")
    parser.add_argument("--benchmark", type=str, default="SPY", help="Benchmark ticker")
    return parser.parse_args()


async def main():
    args = parse_args()
    start = time.monotonic()

    logger.info("=" * 60)
    logger.info("SIGNAL BACKTEST RUNNER")
    logger.info("=" * 60)

    # Show registered signals
    summary = signal_registry.summary()
    total_signals = sum(summary.values())
    logger.info(f"Registered signals: {total_signals} across {len(summary)} categories")
    for cat, count in sorted(summary.items()):
        logger.info(f"  {cat}: {count}")

    # Universe
    universe = get_universe(args.universe, args.max_tickers)
    logger.info(f"\nUniverse: {args.universe} ({len(universe)} tickers)")
    if len(universe) <= 20:
        logger.info(f"  Tickers: {', '.join(universe)}")

    # Config
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end) if args.end else date.today()

    logger.info(f"Period: {start_date} -> {end_date}")
    logger.info(f"Fundamentals: {args.fundamental}")
    logger.info(f"Cross-sectional: {args.cross_sectional}")
    logger.info(f"Benchmark: {args.benchmark}")

    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)

    # --- Signal Backtest ---
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

    logger.info("\n>>> Starting signal backtest engine...")
    engine = BacktestEngine()
    report = await engine.run(config)

    print("\n" + format_signal_report(report))

    # Save signal results
    json_data = {
        "run_id": report.run_id,
        "status": report.status.value,
        "error_message": report.error_message,
        "execution_time_s": report.execution_time_seconds,
        "universe": universe,
        "universe_name": args.universe,
        "universe_size": len(universe),
        "date_range": f"{config.start_date} to {config.end_date}",
        "include_fundamentals": args.fundamental,
        "total_signals_evaluated": len(report.signal_results),
        "top_signals": report.top_signals[:5],
        "underperformers": report.underperforming_signals[:5],
        "signal_results": [
            {
                "signal_id": r.signal_id,
                "signal_name": r.signal_name,
                "category": r.category.value,
                "total_firings": r.total_firings,
                "hit_rate": {str(k): v for k, v in r.hit_rate.items()},
                "avg_return": {str(k): v for k, v in r.avg_return.items()},
                "avg_excess_return": {str(k): v for k, v in r.avg_excess_return.items()},
                "sharpe_ratio": {str(k): v for k, v in r.sharpe_ratio.items()},
                "confidence_level": r.confidence_level,
                "optimal_hold_period": r.optimal_hold_period,
            }
            for r in report.signal_results
        ],
        "category_summaries": [
            {
                "category": cs.category.value,
                "signal_count": cs.signal_count,
                "avg_hit_rate": cs.avg_hit_rate,
                "avg_sharpe": cs.avg_sharpe,
                "category_alpha": cs.category_alpha,
            }
            for cs in (report.category_summaries or [])
        ],
    }

    json_path = results_dir / "signal_backtest_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)
    logger.info(f"Signal results saved to {json_path}")

    # --- Cross-Sectional Ranking ---
    if args.cross_sectional:
        from src.engines.backtesting.cross_sectional import CrossSectionalRanker
        from src.engines.backtesting.cross_sectional_models import CrossSectionalConfig
        from src.engines.backtesting.fundamental_provider import FundamentalProvider

        cs_config = CrossSectionalConfig(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            rebalance_frequency_days=21,
            forward_windows=[20, 60],
            benchmark_ticker=args.benchmark,
            include_fundamentals=args.fundamental,
        )

        logger.info("\n>>> Starting cross-sectional ranking analysis...")

        # Reuse OHLCV data from the engine's cache or re-fetch
        ohlcv_data = await BacktestEngine._fetch_historical_data(
            universe + [args.benchmark], start_date, end_date,
        )

        # Fetch fundamental data if enabled
        fund_data = None
        if args.fundamental:
            fund_provider = FundamentalProvider()
            fund_data = {}
            for ticker in universe:
                ticker_ohlcv = ohlcv_data.get(ticker)
                fund_data[ticker] = fund_provider.get_snapshots(
                    ticker, start_date, end_date, ticker_ohlcv,
                )

        ranker = CrossSectionalRanker()
        cs_report = ranker.run(cs_config, ohlcv_data, fund_data)

        print("\n" + format_cross_sectional_report(cs_report))

        # Save cross-sectional results
        cs_json = {
            "total_periods": cs_report.total_periods,
            "avg_q1_return": cs_report.avg_q1_return,
            "avg_q5_return": cs_report.avg_q5_return,
            "avg_spread": cs_report.avg_spread,
            "spread_t_stat": cs_report.spread_t_stat,
            "spread_p_value": cs_report.spread_p_value,
            "is_monotonic": cs_report.is_monotonic,
            "avg_turnover": cs_report.avg_turnover,
            "execution_time_s": cs_report.execution_time_seconds,
        }
        cs_path = results_dir / "cross_sectional_results.json"
        with open(cs_path, "w", encoding="utf-8") as f:
            json.dump(cs_json, f, indent=2, default=str)
        logger.info(f"Cross-sectional results saved to {cs_path}")

    elapsed = time.monotonic() - start
    logger.info(f"\n{'=' * 60}")
    logger.info(f"ALL BACKTEST RUNS COMPLETE in {elapsed:.1f}s")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
