"""
src/engines/validation/run_institutional_backtest.py
──────────────────────────────────────────────────────────────────────────────
Runner for the institutional-grade Alpha Validation System (AVS V2).

Usage:
    python -m src.engines.validation.run_institutional_backtest

Configuration:
    Adjust UNIVERSE_SIZE, YEARS, TRAIN_YEARS, TEST_MONTHS below.
    Default: 50 stocks, 5Y history, 2Y train / 6M test windows.
    Full: 150 stocks, 10Y history, 3Y train / 6M test windows.
"""

from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("365advisers.validation.institutional")

# ── Configuration ────────────────────────────────────────────────────────────
# Adjust these for your run. Start small, scale up.

# "QUICK" for fast validation (~20 min), "FULL" for institutional (~2-4 hours)
MODE = os.environ.get("AVS_MODE", "QUICK")

if MODE == "FULL":
    UNIVERSE_SIZE = 150
    YEARS = 10
    TRAIN_YEARS = 3
    TEST_MONTHS = 6
    EVAL_FREQ = 5  # every 5 trading days
else:
    UNIVERSE_SIZE = 50
    YEARS = 5
    TRAIN_YEARS = 2
    TEST_MONTHS = 6
    EVAL_FREQ = 5


def main():
    from src.engines.validation.sharadar_loader import SharadarDataLoader, SharadarUniverse
    from src.engines.validation.institutional_backtest import InstitutionalBacktest
    from src.engines.validation.statistical_validator import StatisticalValidator
    from src.engines.validation.institutional_report import generate_report

    report_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "reports",
    )
    os.makedirs(report_dir, exist_ok=True)

    print("=" * 80)
    print(f"AVS V2 — INSTITUTIONAL BACKTEST ({MODE} mode)")
    print("=" * 80)
    print(f"  Universe: {UNIVERSE_SIZE} stocks")
    print(f"  History:  {YEARS} years")
    print(f"  Windows:  {TRAIN_YEARS}Y train / {TEST_MONTHS}M test (rolling)")
    print(f"  Eval freq: every {EVAL_FREQ} trading days")
    print()

    t0 = time.time()

    # ── 1. Build universe ────────────────────────────────────────────────
    print("Step 1/4: Building universe from SHARADAR/TICKERS...")

    # First try to use dynamic Sharadar universe
    try:
        universe_data = SharadarUniverse.build(
            min_market_cap=2e9,
            max_tickers=UNIVERSE_SIZE,
            include_delisted=False,  # start without delisted for speed
            sector_balance=True,
        )
        tickers = [t["ticker"] for t in universe_data]
    except Exception as e:
        logger.warning(f"Sharadar universe failed ({e}), using SYSTEMATIC_50 fallback")
        from src.engines.validation.universes import SYSTEMATIC_50
        tickers = SYSTEMATIC_50[:UNIVERSE_SIZE]

    print(f"  Universe: {len(tickers)} tickers")
    print(f"  Sample: {tickers[:10]}...")
    print()

    # ── 2. Run walk-forward backtest ─────────────────────────────────────
    print("Step 2/4: Running walk-forward backtest...")
    print("  (This may take 10-60 minutes depending on universe size)")
    print()

    loader = SharadarDataLoader()
    bt = InstitutionalBacktest(
        data_loader=loader,
        eval_frequency_days=EVAL_FREQ,
        commission_per_share=0.005,
        slippage_bps=10,
    )

    backtest_report = bt.run(
        tickers=tickers,
        years=YEARS,
        train_years=TRAIN_YEARS,
        test_months=TEST_MONTHS,
    )

    t1 = time.time()

    print(f"\n  Backtest complete in {(t1-t0)/60:.1f} minutes")
    print(f"  Total evaluations: {backtest_report.total_evals:,}")
    print(f"  Total BUY trades:  {backtest_report.total_buy_trades:,}")
    print(f"  OOS BUY trades:    {backtest_report.agg_oos_trades:,}")
    print()

    # ── 3. Statistical validation ────────────────────────────────────────
    print("Step 3/4: Running statistical validation...")

    validator = StatisticalValidator()
    stat_report = validator.validate(backtest_report)

    print(f"  Verdict: {stat_report.verdict}")
    if stat_report.excess_significance:
        sig = stat_report.excess_significance
        print(f"  t-stat:  {sig.t_stat:.2f}")
        print(f"  p-value: {sig.p_value:.4f}")
    print()

    # ── 4. Generate report ───────────────────────────────────────────────
    print("Step 4/4: Generating institutional report...")

    report_text = generate_report(
        backtest_report, stat_report, output_dir=report_dir,
    )

    filepath = os.path.join(report_dir, "institutional_report.md")
    print(f"  Report saved to: {filepath}")
    print()

    t2 = time.time()

    # ── Summary ──────────────────────────────────────────────────────────
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Total time:        {(t2-t0)/60:.1f} minutes")
    print(f"  Universe:          {len(tickers)} stocks")
    print(f"  Evaluations:       {backtest_report.total_evals:,}")
    print(f"  OOS Trades:        {backtest_report.agg_oos_trades:,}")
    print(f"  OOS Avg T+20d:     {backtest_report.agg_oos_avg_return_20d:+.2%}")
    print(f"  OOS Hit Rate:      {backtest_report.agg_oos_hit_rate_20d:.1%}")
    print(f"  OOS Sharpe:        {backtest_report.agg_oos_sharpe_20d:.2f}")
    print(f"  Excess Return:     {backtest_report.agg_oos_excess_return:+.2%}")
    print(f"  Net Alpha:         {backtest_report.net_alpha:+.2%}")
    if stat_report.excess_significance:
        print(f"  t-stat:            {stat_report.excess_significance.t_stat:.2f}")
        print(f"  p-value:           {stat_report.excess_significance.p_value:.4f}")
    print(f"  Verdict:           {stat_report.verdict}")
    print("=" * 80)


if __name__ == "__main__":
    main()
