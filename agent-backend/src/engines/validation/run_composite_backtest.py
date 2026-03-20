"""
Run the AVS Phase 1: Composite Backtest.

Usage:
    python -m src.engines.validation.run_composite_backtest
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from src.engines.validation.composite_backtest import CompositeBacktest


def main():
    tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]

    print("\n" + "=" * 80)
    print("ALPHA VALIDATION SYSTEM — Phase 1: Composite Backtest")
    print(f"Universe: {', '.join(tickers)}")
    print("=" * 80 + "\n")

    bt = CompositeBacktest()
    report = bt.run(
        tickers=tickers,
        years=2,
        eval_frequency_days=5,
        buy_threshold=0.20,
        oos_months=3,
    )

    output = bt.print_report(report)

    # Save reports
    import os
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    txt_path = os.path.join(report_dir, "composite_backtest_report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"\nReport saved to: {txt_path}")

    return report


if __name__ == "__main__":
    main()
