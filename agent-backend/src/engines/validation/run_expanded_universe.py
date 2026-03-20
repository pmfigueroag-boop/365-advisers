"""
Run AVS on expanded non-tech universe.

Usage:
    python -m src.engines.validation.run_expanded_universe
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from src.engines.validation.ic_screen import ICScreen
from src.engines.validation.composite_backtest import CompositeBacktest


def main():
    # Diversified non-tech universe
    non_tech = ["JNJ", "UNH", "JPM", "GS", "WMT", "KO", "XOM", "CVX", "CAT", "HON"]
    # Original tech universe
    tech = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]
    # Combined
    full = tech + non_tech

    import os
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    # ── 1. IC Screen on non-tech ─────────────────────────────────────────
    print("\n" + "=" * 80)
    print("PHASE A: IC SCREEN — Non-Tech Universe")
    print(f"Universe: {', '.join(non_tech)}")
    print("=" * 80 + "\n")

    screen = ICScreen()
    ic_report_nontec = screen.run(tickers=non_tech, years=2)
    output_ic = screen.print_report(ic_report_nontec)

    with open(os.path.join(report_dir, "ic_screen_nontech.txt"), "w", encoding="utf-8") as f:
        f.write(output_ic)

    # ── 2. Composite Backtest on non-tech ────────────────────────────────
    print("\n" + "=" * 80)
    print("PHASE B: COMPOSITE BACKTEST (V2) — Non-Tech Universe")
    print("=" * 80 + "\n")

    bt = CompositeBacktest()
    bt_report_nontec = bt.run(tickers=non_tech, years=2, buy_threshold=0.35)
    output_bt = bt.print_report(bt_report_nontec)

    with open(os.path.join(report_dir, "composite_backtest_nontech.txt"), "w", encoding="utf-8") as f:
        f.write(output_bt)

    # ── 3. Composite Backtest on FULL universe ───────────────────────────
    print("\n" + "=" * 80)
    print("PHASE C: COMPOSITE BACKTEST (V2) — Full 16-Stock Universe")
    print(f"Universe: {', '.join(full)}")
    print("=" * 80 + "\n")

    bt_full = CompositeBacktest()
    bt_report_full = bt_full.run(tickers=full, years=2, buy_threshold=0.35)
    output_full = bt_full.print_report(bt_report_full)

    with open(os.path.join(report_dir, "composite_backtest_full.txt"), "w", encoding="utf-8") as f:
        f.write(output_full)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("CROSS-UNIVERSE COMPARISON")
    print("=" * 70)
    print(f"  {'Universe':<20} {'BUY sigs':>8} {'Avg 20d':>8} {'HR 20d':>7} {'Excess':>8}")
    print("  " + "-" * 55)

    for name, rpt in [("Tech (6)", bt.run(tickers=tech, years=2, buy_threshold=0.35)),
                       ("Non-Tech (10)", bt_report_nontec),
                       ("Full (16)", bt_report_full)]:
        excess = rpt.is_avg_return_20d - rpt.benchmark_return_20d
        print(f"  {name:<20} {rpt.buy_signals:>8} {rpt.is_avg_return_20d:>7.2%} {rpt.is_hit_rate_20d:>6.1%} {excess:>+7.2%}")


if __name__ == "__main__":
    main()
