"""
Run per-sector IC screens to compute sector-adaptive IC weights for Combiner v3.

Usage:
    python -m src.engines.validation.run_sector_ic_screen
"""
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

from src.engines.validation.ic_screen import ICScreen


def main():
    tech = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]
    non_tech = ["JNJ", "UNH", "JPM", "GS", "WMT", "KO", "XOM", "CVX", "CAT", "HON"]

    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")
    os.makedirs(report_dir, exist_ok=True)

    screen = ICScreen()

    # ── Tech IC Screen ──────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SECTOR IC SCREEN — Tech Universe")
    print(f"Universe: {', '.join(tech)}")
    print("=" * 80 + "\n")

    tech_report = screen.run(tickers=tech, years=2)
    tech_output = screen.print_report(tech_report)

    with open(os.path.join(report_dir, "ic_screen_tech.txt"), "w", encoding="utf-8") as f:
        f.write(tech_output)

    # ── Non-Tech IC Screen ──────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SECTOR IC SCREEN — Non-Tech Universe")
    print(f"Universe: {', '.join(non_tech)}")
    print("=" * 80 + "\n")

    nontech_report = screen.run(tickers=non_tech, years=2)
    nontech_output = screen.print_report(nontech_report)

    with open(os.path.join(report_dir, "ic_screen_nontech.txt"), "w", encoding="utf-8") as f:
        f.write(nontech_output)

    # ── Extract IC tables ───────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("SECTOR IC COMPARISON")
    print("=" * 80)
    print(f"\n  {'Signal':<45} {'IC_Tech':>8} {'IC_NonTech':>10} {'Delta':>8}")
    print("  " + "-" * 75)

    ic_tech = {}
    ic_nontech = {}

    for sig in tech_report.results:
        ic_tech[sig.signal_id] = sig.ic_20d

    for sig in nontech_report.results:
        ic_nontech[sig.signal_id] = sig.ic_20d

    all_ids = sorted(set(ic_tech.keys()) | set(ic_nontech.keys()))
    divergent = []

    for sid in all_ids:
        t = ic_tech.get(sid, 0.0)
        nt = ic_nontech.get(sid, 0.0)
        delta = nt - t
        # Flag signals where sign flips or delta > 0.05
        flag = ""
        if t * nt < 0 and (abs(t) > 0.02 or abs(nt) > 0.02):
            flag = "  ⚡ SIGN FLIP"
            divergent.append(sid)
        elif abs(delta) > 0.08:
            flag = "  ⚠️ DIVERGENT"
            divergent.append(sid)
        print(f"  {sid:<45} {t:>+7.4f} {nt:>+9.4f} {delta:>+7.4f}{flag}")

    print(f"\n  Divergent signals: {len(divergent)}")
    for sid in divergent:
        print(f"    → {sid}: tech={ic_tech.get(sid, 0):.4f}, nontech={ic_nontech.get(sid, 0):.4f}")

    # ── Save JSON IC tables for combiner v3 ─────────────────────────────
    ic_tables = {
        "tech": {sid: round(ic, 4) for sid, ic in ic_tech.items()},
        "non_tech": {sid: round(ic, 4) for sid, ic in ic_nontech.items()},
    }
    json_path = os.path.join(report_dir, "sector_ic_tables.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ic_tables, f, indent=2)
    print(f"\n  IC tables saved to: {json_path}")


if __name__ == "__main__":
    main()
