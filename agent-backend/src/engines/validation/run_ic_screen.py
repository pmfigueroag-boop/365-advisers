"""
Run the AVS Phase 0: Signal IC Screen.

Usage:
    python -m src.engines.validation.run_ic_screen
"""
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from src.engines.validation.ic_screen import ICScreen


def main():
    """Run IC screen on the target universe."""
    tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]

    print("\n" + "=" * 80)
    print("ALPHA VALIDATION SYSTEM — Phase 0: Signal IC Screen")
    print(f"Universe: {', '.join(tickers)}")
    print(f"Period: 2 years")
    print(f"Eval frequency: weekly (every 5 trading days)")
    print("=" * 80 + "\n")

    screen = ICScreen()
    report = screen.run(tickers=tickers, years=2, eval_frequency_days=5)

    # Print report
    output = screen.print_report(report)

    # Save JSON report
    import os
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)
    json_path = os.path.join(report_dir, "ic_screen_report.json")
    with open(json_path, "w") as f:
        f.write(screen.to_json(report))
    print(f"\nJSON report saved to: {json_path}")

    # Save text report
    txt_path = os.path.join(report_dir, "ic_screen_report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Text report saved to: {txt_path}")

    # Summary statistics
    print("\n\n" + "=" * 50)
    print("QUICK SUMMARY")
    print("=" * 50)
    if report.results:
        top_5 = [r for r in report.results[:5]]
        bottom_5 = [r for r in report.results[-5:]]
        print("\nTOP 5 signals by IC_20d:")
        for r in top_5:
            print(f"  {r.signal_id:<40} IC={r.ic_20d:+.4f}  HR={r.hit_rate_20d:.1%}")
        print("\nBOTTOM 5 signals by IC_20d:")
        for r in bottom_5:
            print(f"  {r.signal_id:<40} IC={r.ic_20d:+.4f}  HR={r.hit_rate_20d:.1%}")

    return report


if __name__ == "__main__":
    main()
