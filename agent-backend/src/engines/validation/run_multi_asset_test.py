"""
P3.5: Multi-asset robustness test runner.

Runs the composite backtest on the multi-asset ETF universe to validate
that the signal combiner generalizes beyond individual equities.

Usage:
    python -m src.engines.validation.run_multi_asset_test
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from src.engines.validation.composite_backtest import CompositeBacktest
from src.engines.validation.universes import (
    SYSTEMATIC_50,
    MULTI_ASSET,
    TECH_UNIVERSE,
    NON_TECH_UNIVERSE,
)


def main():
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    bt = CompositeBacktest()

    # ── P1.1: Systematic 50-stock backtest ────────────────────────────────
    print("\n" + "=" * 80)
    print("P1.1 — SYSTEMATIC BACKTEST (50 stocks, 2Y)")
    print("=" * 80)

    try:
        sys50_report = bt.run(tickers=SYSTEMATIC_50, years=2, buy_threshold=0.20)
        sys50_out = bt.print_report(sys50_report)
        with open(os.path.join(report_dir, "systematic_50_backtest.txt"), "w") as f:
            f.write(sys50_out)
    except Exception as exc:
        print(f"  ⚠️  Systematic 50 failed: {exc}")
        sys50_report = None

    # ── P3.5: Multi-asset robustness ──────────────────────────────────────
    print("\n" + "=" * 80)
    print("P3.5 — MULTI-ASSET ROBUSTNESS (ETFs, 2Y)")
    print("=" * 80)

    try:
        multi_report = bt.run(tickers=MULTI_ASSET, years=2, buy_threshold=0.20)
        multi_out = bt.print_report(multi_report)
        with open(os.path.join(report_dir, "multi_asset_backtest.txt"), "w") as f:
            f.write(multi_out)
    except Exception as exc:
        print(f"  ⚠️  Multi-asset failed: {exc}")
        multi_report = None

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("CROSS-UNIVERSE SUMMARY")
    print("=" * 80)
    print(f"\n  {'Universe':<25} {'Trades':>7} {'Avg 20d':>8} {'HR 20d':>7} {'Excess':>8}")
    print("  " + "-" * 55)

    for name, rpt in [
        ("Tech (6)", None),           # reference from previous runs
        ("Non-Tech (10)", None),
        ("Systematic (50)", sys50_report),
        ("Multi-Asset (ETFs)", multi_report),
    ]:
        if rpt is None:
            continue
        n = rpt.strong_buy_count + rpt.buy_only_count
        excess = rpt.is_avg_return_20d - rpt.benchmark_return_20d
        print(
            f"  {name:<25} {n:>7} "
            f"{rpt.is_avg_return_20d:>7.2%} "
            f"{rpt.is_hit_rate_20d:>6.1%} "
            f"{excess:>+7.2%}"
        )


if __name__ == "__main__":
    main()
