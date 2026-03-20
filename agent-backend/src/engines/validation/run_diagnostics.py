"""
Run AVS Phase 2: Signal Diagnostics.

Usage:
    python -m src.engines.validation.run_diagnostics
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from src.engines.validation.signal_diagnostics import SignalDiagnostics


def main():
    tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]

    print("\n" + "=" * 80)
    print("ALPHA VALIDATION SYSTEM — Phase 2: Signal Diagnostics")
    print(f"Universe: {', '.join(tickers)}")
    print("=" * 80 + "\n")

    diag = SignalDiagnostics()
    report = diag.run(tickers=tickers, years=2)

    output = diag.print_report(report)

    import os
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    txt_path = os.path.join(report_dir, "diagnostics_report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"\nReport saved to: {txt_path}")

    return report


if __name__ == "__main__":
    main()
