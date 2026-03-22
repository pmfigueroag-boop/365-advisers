"""
Run V3 composite backtest on full 16-stock universe.

Usage:
    python -m src.engines.validation.run_v3_full_backtest
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


def main():
    tech = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]
    non_tech = ["JNJ", "UNH", "JPM", "GS", "WMT", "KO", "XOM", "CVX", "CAT", "HON"]
    full = tech + non_tech

    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    bt = CompositeBacktest()

    # ── Tech only ─────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("V3 BACKTEST — Tech Universe (6 stocks)")
    print("=" * 80)
    tech_report = bt.run(tickers=tech, years=2, buy_threshold=0.35)
    tech_out = bt.print_report(tech_report)
    with open(os.path.join(report_dir, "v3_backtest_tech.txt"), "w", encoding="utf-8") as f:
        f.write(tech_out)

    # ── Non-Tech only ─────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("V3 BACKTEST — Non-Tech Universe (10 stocks)")
    print("=" * 80)
    nontech_report = bt.run(tickers=non_tech, years=2, buy_threshold=0.35)
    nontech_out = bt.print_report(nontech_report)
    with open(os.path.join(report_dir, "v3_backtest_nontech.txt"), "w", encoding="utf-8") as f:
        f.write(nontech_out)

    # ── Full 16-Stock ─────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("V3 BACKTEST — Full Universe (16 stocks)")
    print("=" * 80)
    full_report = bt.run(tickers=full, years=2, buy_threshold=0.35)
    full_out = bt.print_report(full_report)
    with open(os.path.join(report_dir, "v3_backtest_full.txt"), "w", encoding="utf-8") as f:
        f.write(full_out)

    # ── Cross-Universe Summary ────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("CROSS-UNIVERSE COMPARISON (Combiner V3, Sector-Adaptive)")
    print("=" * 80)
    print(f"\n  {'Universe':<20} {'Trades':>7} {'Avg 20d':>8} {'HR 20d':>7} {'Sharpe':>7} {'Excess':>8}")
    print("  " + "-" * 60)

    for name, rpt in [("Tech (6)", tech_report),
                       ("Non-Tech (10)", nontech_report),
                       ("Full (16)", full_report)]:
        excess = rpt.is_avg_return_20d - rpt.benchmark_return_20d
        sh = rpt.is_metrics_20d.sharpe if rpt.is_metrics_20d else 0
        n = rpt.strong_buy_count + rpt.buy_only_count
        print(f"  {name:<20} {n:>7} {rpt.is_avg_return_20d:>7.2%} {rpt.is_hit_rate_20d:>6.1%} {sh:>7.1f} {excess:>+7.2%}")


if __name__ == "__main__":
    main()
