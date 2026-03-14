"""
scripts/case_backtest_runner.py
──────────────────────────────────────────────────────────────────────────────
CASE Predictive Validation Backtest Runner

Evaluates whether the Composite Alpha Score (CASE) has predictive power by:
  1. Computing CASE scores for ~50 S&P 500 tickers (current features)
  2. Using 1-year OHLCV history to measure realized returns at 5D/20D/60D
     horizons from multiple lookback dates
  3. Analyzing hit rates, average returns, and calibration by CASE bucket

Usage:
    cd agent-backend
    python scripts/case_backtest_runner.py

Output:
    results/case_backtest_results.json  — raw data
    docs/case_validation_report.md      — formatted report
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean, median

# ── Add project root to path ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Imports from the engine stack ────────────────────────────────────────────
from src.data.market_data import fetch_fundamental_data, fetch_technical_data
from src.features.fundamental_features import extract_fundamental_features
from src.features.technical_features import extract_technical_features
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.composite_alpha.engine import CompositeAlphaEngine
from src.engines.idea_generation.engine import IdeaGenerationEngine
from src.contracts.market_data import (
    FinancialStatements, FinancialRatios,
    ProfitabilityRatios, ValuationRatios, LeverageRatios, QualityRatios,
    CashFlowEntry, PriceHistory, OHLCVBar, MarketMetrics, RawIndicators,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("case_backtest")

# ── Universe: ~50 S&P 500 tickers, diversified by sector ────────────────────
UNIVERSE = [
    # Technology (10)
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ADBE", "CRM", "CSCO", "INTC",
    # Financial Services (6)
    "JPM", "V", "MA", "BAC", "GS", "BLK",
    # Healthcare (6)
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
    # Consumer Discretionary (5)
    "AMZN", "TSLA", "HD", "NKE", "SBUX",
    # Industrials (5)
    "CAT", "GE", "HON", "UPS", "BA",
    # Energy (4)
    "XOM", "CVX", "COP", "SLB",
    # Consumer Staples (4)
    "PG", "KO", "PEP", "COST",
    # Communication (3)
    "DIS", "NFLX", "CMCSA",
    # Utilities (2)
    "NEE", "DUK",
    # Materials (2)
    "LIN", "APD",
    # REITs (2)
    "PLD", "AMT",
]

HORIZONS_DAYS = [5, 20, 60]  # Calendar days to look back
BENCHMARK = "SPY"


# ═════════════════════════════════════════════════════════════════════════════
# Data Collection
# ═════════════════════════════════════════════════════════════════════════════

def fetch_ohlcv_map(tickers: list[str]) -> dict[str, list[dict]]:
    """Fetch 1yr OHLCV for all tickers + benchmark. Returns {ticker: [{time,close}]}."""
    all_tickers = list(set(tickers + [BENCHMARK]))
    ohlcv_map: dict[str, list[dict]] = {}

    for i, ticker in enumerate(all_tickers):
        logger.info(f"  [{i+1}/{len(all_tickers)}] Fetching OHLCV: {ticker}")
        try:
            tech = fetch_technical_data(ticker)
            bars = tech.get("ohlcv", [])
            ohlcv_map[ticker] = bars
        except Exception as e:
            logger.warning(f"  ⚠  OHLCV error for {ticker}: {e}")
            ohlcv_map[ticker] = []
        time.sleep(0.3)  # Rate limit

    return ohlcv_map


def compute_case_scores(tickers: list[str]) -> dict[str, dict]:
    """Compute CASE score + metadata for each ticker. Returns {ticker: {...}}."""
    evaluator = SignalEvaluator()
    case_engine = CompositeAlphaEngine()
    results: dict[str, dict] = {}

    for i, ticker in enumerate(tickers):
        logger.info(f"  [{i+1}/{len(tickers)}] Computing CASE: {ticker}")
        try:
            # Fetch data
            fund_raw = fetch_fundamental_data(ticker)
            tech_raw = fetch_technical_data(ticker)

            # Extract features
            fund_features = IdeaGenerationEngine._build_fundamental_features(ticker, fund_raw) if fund_raw and "error" not in fund_raw else None
            tech_features = IdeaGenerationEngine._build_technical_features(ticker, tech_raw) if tech_raw and "error" not in tech_raw else None

            if fund_features is None and tech_features is None:
                logger.warning(f"  ⚠  No features for {ticker}, skipping")
                continue

            # Run signal evaluator
            profile = evaluator.evaluate(
                ticker=ticker,
                fundamental=fund_features,
                technical=tech_features,
            )

            # Compute CASE score
            case_result = case_engine.compute(profile)

            results[ticker] = {
                "ticker": ticker,
                "case_score": case_result.composite_alpha_score,
                "environment": case_result.signal_environment.value,
                "active_categories": case_result.active_categories,
                "fired_signals": profile.fired_signals,
                "total_signals": profile.total_signals,
                "sector": fund_raw.get("sector", "") if fund_raw else "",
                "name": fund_raw.get("name", ticker) if fund_raw else ticker,
                "subscores": {
                    k: v.score for k, v in case_result.subscores.items()
                },
                "convergence_bonus": case_result.convergence_bonus,
                "conflicts": case_result.cross_category_conflicts,
            }
            logger.info(
                f"  ✓  {ticker}: CASE={case_result.composite_alpha_score}, "
                f"env={case_result.signal_environment.value}, "
                f"signals={profile.fired_signals}/{profile.total_signals}"
            )

        except Exception as e:
            logger.error(f"  ✗  CASE error for {ticker}: {e}")

        time.sleep(0.5)  # Rate limit

    return results


# ═════════════════════════════════════════════════════════════════════════════
# Outcome Evaluation (using historical OHLCV)
# ═════════════════════════════════════════════════════════════════════════════

def evaluate_outcomes(
    case_scores: dict[str, dict],
    ohlcv_map: dict[str, list[dict]],
) -> list[dict]:
    """
    Evaluate forward returns using historical OHLCV data.

    Strategy: For each ticker, we simulate "what if we computed CASE N days ago?"
    - Take the price on date T-N (signal date)
    - Take the price on date T (outcome date = today)
    - Compute raw return and excess return vs SPY
    - Repeat for each horizon (5D, 20D, 60D)
    """
    outcomes: list[dict] = []
    spy_bars = {b["time"]: b["close"] for b in ohlcv_map.get(BENCHMARK, [])}
    spy_dates = sorted(spy_bars.keys())

    for ticker, case_data in case_scores.items():
        bars = ohlcv_map.get(ticker, [])
        if len(bars) < 70:
            logger.warning(f"  ⚠  {ticker}: only {len(bars)} bars, skipping")
            continue

        price_map = {b["time"]: b["close"] for b in bars}
        dates = sorted(price_map.keys())
        latest_date = dates[-1]
        latest_price = price_map[latest_date]

        for horizon in HORIZONS_DAYS:
            # Find the signal date (approximately N calendar days back)
            signal_idx = max(0, len(dates) - 1 - horizon)
            signal_date = dates[signal_idx]
            signal_price = price_map[signal_date]

            if signal_price <= 0:
                continue

            # Raw return
            raw_return = (latest_price - signal_price) / signal_price

            # Excess return vs SPY
            excess_return = None
            if signal_date in spy_bars and latest_date in spy_bars:
                spy_signal = spy_bars[signal_date]
                spy_latest = spy_bars[latest_date]
                if spy_signal > 0:
                    spy_return = (spy_latest - spy_signal) / spy_signal
                    excess_return = raw_return - spy_return

            # Classify
            if raw_return > 0.005:
                outcome = "win"
            elif raw_return < -0.005:
                outcome = "loss"
            else:
                outcome = "neutral"

            outcomes.append({
                "ticker": ticker,
                "case_score": case_data["case_score"],
                "environment": case_data["environment"],
                "sector": case_data["sector"],
                "horizon": f"{horizon}D",
                "signal_date": signal_date,
                "outcome_date": latest_date,
                "signal_price": round(signal_price, 2),
                "outcome_price": round(latest_price, 2),
                "raw_return": round(raw_return, 6),
                "excess_return": round(excess_return, 6) if excess_return is not None else None,
                "outcome": outcome,
                "is_hit": outcome == "win",
            })

    return outcomes


# ═════════════════════════════════════════════════════════════════════════════
# Analytics
# ═════════════════════════════════════════════════════════════════════════════

CASE_BUCKETS = [
    (0, 20, "0–20 (Negative)"),
    (20, 40, "20–40 (Weak)"),
    (40, 60, "40–60 (Neutral)"),
    (60, 80, "60–80 (Strong)"),
    (80, 101, "80–100 (Very Strong)"),
]


def assign_bucket(score: float) -> str:
    for low, high, label in CASE_BUCKETS:
        if low <= score < high:
            return label
    return "Unknown"


def compute_analytics(outcomes: list[dict]) -> dict:
    """Compute analytics by CASE bucket, horizon, and sector."""
    analytics: dict = {
        "by_bucket_and_horizon": {},
        "by_sector": {},
        "overall": {},
        "monotonicity": {},
    }

    # ── By CASE bucket × horizon ──────────────────────────────────────────
    for horizon in ["5D", "20D", "60D"]:
        h_outcomes = [o for o in outcomes if o["horizon"] == horizon]
        if not h_outcomes:
            continue

        bucket_data: dict[str, list[dict]] = {}
        for o in h_outcomes:
            bucket = assign_bucket(o["case_score"])
            bucket_data.setdefault(bucket, []).append(o)

        horizon_analytics = {}
        for label, items in sorted(bucket_data.items()):
            returns = [o["raw_return"] for o in items]
            excess = [o["excess_return"] for o in items if o["excess_return"] is not None]
            hits = sum(1 for o in items if o["is_hit"])

            horizon_analytics[label] = {
                "count": len(items),
                "hit_rate": round(hits / len(items), 4) if items else 0,
                "avg_return": round(mean(returns), 6) if returns else 0,
                "median_return": round(median(returns), 6) if returns else 0,
                "avg_excess_return": round(mean(excess), 6) if excess else 0,
                "win_count": hits,
                "loss_count": sum(1 for o in items if o["outcome"] == "loss"),
            }

        analytics["by_bucket_and_horizon"][horizon] = horizon_analytics

        # Monotonicity check
        bucket_labels = [b[2] for b in CASE_BUCKETS]
        populated = [(l, horizon_analytics[l]) for l in bucket_labels if l in horizon_analytics and horizon_analytics[l]["count"] > 0]
        violations = []
        for i in range(len(populated) - 1):
            curr_label, curr = populated[i]
            next_label, nxt = populated[i + 1]
            if nxt["avg_return"] < curr["avg_return"]:
                violations.append(f"{next_label} (avg={nxt['avg_return']:.4f}) < {curr_label} (avg={curr['avg_return']:.4f})")

        analytics["monotonicity"][horizon] = {
            "is_monotonic": len(violations) == 0,
            "violations": violations,
        }

    # ── Overall by horizon ────────────────────────────────────────────────
    for horizon in ["5D", "20D", "60D"]:
        h_outcomes = [o for o in outcomes if o["horizon"] == horizon]
        if not h_outcomes:
            continue
        returns = [o["raw_return"] for o in h_outcomes]
        excess = [o["excess_return"] for o in h_outcomes if o["excess_return"] is not None]
        hits = sum(1 for o in h_outcomes if o["is_hit"])
        analytics["overall"][horizon] = {
            "count": len(h_outcomes),
            "hit_rate": round(hits / len(h_outcomes), 4),
            "avg_return": round(mean(returns), 6),
            "avg_excess": round(mean(excess), 6) if excess else 0,
        }

    # ── By sector (20D only) ──────────────────────────────────────────────
    h20 = [o for o in outcomes if o["horizon"] == "20D"]
    sector_data: dict[str, list[dict]] = {}
    for o in h20:
        sector_data.setdefault(o["sector"] or "Unknown", []).append(o)

    for sector, items in sorted(sector_data.items()):
        returns = [o["raw_return"] for o in items]
        hits = sum(1 for o in items if o["is_hit"])
        avg_case = mean([o["case_score"] for o in items])
        analytics["by_sector"][sector] = {
            "count": len(items),
            "avg_case": round(avg_case, 1),
            "hit_rate": round(hits / len(items), 4) if items else 0,
            "avg_return": round(mean(returns), 6) if returns else 0,
        }

    return analytics


# ═════════════════════════════════════════════════════════════════════════════
# Report Generation
# ═════════════════════════════════════════════════════════════════════════════

def generate_report(
    case_scores: dict[str, dict],
    outcomes: list[dict],
    analytics: dict,
    elapsed_s: float,
) -> str:
    """Generate a markdown validation report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# CASE Predictive Validation Report",
        f"",
        f"**Generated:** {now}  ",
        f"**Universe:** {len(case_scores)} tickers · **Outcomes:** {len(outcomes)} data points  ",
        f"**Horizons:** 5D, 20D, 60D · **Benchmark:** SPY  ",
        f"**Execution Time:** {elapsed_s:.1f}s",
        f"",
        f"---",
        f"",
    ]

    # ── CASE Score Distribution ──────────────────────────────────────────
    lines.append("## 1. CASE Score Distribution\n")
    lines.append("| Ticker | CASE | Environment | Signals | Sector |")
    lines.append("|:--|--:|:--|--:|:--|")
    for t, d in sorted(case_scores.items(), key=lambda x: x[1]["case_score"], reverse=True):
        lines.append(
            f"| **{t}** | {d['case_score']} | {d['environment']} | "
            f"{d['fired_signals']}/{d['total_signals']} | {d['sector']} |"
        )
    lines.append("")

    # Stats
    scores = [d["case_score"] for d in case_scores.values()]
    if scores:
        lines.append(f"**Stats:** Mean={mean(scores):.1f}, Median={median(scores):.1f}, "
                      f"Min={min(scores):.1f}, Max={max(scores):.1f}\n")

    # ── Hit Rate by CASE Bucket × Horizon ─────────────────────────────────
    lines.append("---\n")
    lines.append("## 2. Hit Rate by CASE Bucket\n")

    for horizon in ["5D", "20D", "60D"]:
        h_data = analytics["by_bucket_and_horizon"].get(horizon, {})
        if not h_data:
            continue
        lines.append(f"### {horizon} Horizon\n")
        lines.append("| CASE Bucket | N | Hit Rate | Avg Return | Median Return | Excess Return |")
        lines.append("|:--|--:|--:|--:|--:|--:|")
        for label in [b[2] for b in CASE_BUCKETS]:
            d = h_data.get(label)
            if d and d["count"] > 0:
                hr_emoji = "🟢" if d["hit_rate"] >= 0.55 else "🟡" if d["hit_rate"] >= 0.45 else "🔴"
                lines.append(
                    f"| {label} | {d['count']} | {hr_emoji} {d['hit_rate']:.1%} | "
                    f"{d['avg_return']:+.2%} | {d['median_return']:+.2%} | "
                    f"{d['avg_excess_return']:+.2%} |"
                )
        lines.append("")

    # ── Monotonicity ──────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 3. Monotonicity Analysis\n")
    lines.append("_Does higher CASE → higher returns?_\n")

    for horizon in ["5D", "20D", "60D"]:
        mono = analytics["monotonicity"].get(horizon, {})
        if not mono:
            continue
        status = "✅ Monotonic" if mono["is_monotonic"] else f"⚠️ {len(mono['violations'])} violation(s)"
        lines.append(f"**{horizon}:** {status}")
        for v in mono.get("violations", []):
            lines.append(f"  - {v}")
        lines.append("")

    # ── Sector Performance (20D) ──────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 4. Sector Analysis (20D Horizon)\n")
    lines.append("| Sector | N | Avg CASE | Hit Rate | Avg Return |")
    lines.append("|:--|--:|--:|--:|--:|")
    for sector, d in sorted(analytics["by_sector"].items(), key=lambda x: x[1]["avg_return"], reverse=True):
        lines.append(
            f"| {sector} | {d['count']} | {d['avg_case']} | "
            f"{d['hit_rate']:.1%} | {d['avg_return']:+.2%} |"
        )
    lines.append("")

    # ── Overall Summary ──────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 5. Overall Summary\n")
    lines.append("| Horizon | N | Hit Rate | Avg Return | Avg Excess |")
    lines.append("|:--|--:|--:|--:|--:|")
    for horizon in ["5D", "20D", "60D"]:
        ov = analytics["overall"].get(horizon)
        if ov:
            lines.append(
                f"| {horizon} | {ov['count']} | {ov['hit_rate']:.1%} | "
                f"{ov['avg_return']:+.2%} | {ov['avg_excess']:+.2%} |"
            )
    lines.append("")

    # ── Verdict ──────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 6. Verdict\n")

    # Compute verdict
    h20_buckets = analytics["by_bucket_and_horizon"].get("20D", {})
    high_bucket = None
    low_bucket = None
    for label in [b[2] for b in CASE_BUCKETS]:
        d = h20_buckets.get(label)
        if d and d["count"] > 0:
            if "Strong" in label or "Very" in label:
                if high_bucket is None:
                    high_bucket = d
                else:
                    # Merge
                    total = high_bucket["count"] + d["count"]
                    high_bucket = {
                        "count": total,
                        "hit_rate": (high_bucket["hit_rate"] * high_bucket["count"] + d["hit_rate"] * d["count"]) / total,
                        "avg_return": (high_bucket["avg_return"] * high_bucket["count"] + d["avg_return"] * d["count"]) / total,
                    }
            elif "Negative" in label or "Weak" in label:
                if low_bucket is None:
                    low_bucket = d
                else:
                    total = low_bucket["count"] + d["count"]
                    low_bucket = {
                        "count": total,
                        "hit_rate": (low_bucket["hit_rate"] * low_bucket["count"] + d["hit_rate"] * d["count"]) / total,
                        "avg_return": (low_bucket["avg_return"] * low_bucket["count"] + d["avg_return"] * d["count"]) / total,
                    }

    mono_20d = analytics["monotonicity"].get("20D", {})

    verdicts = []
    if high_bucket and high_bucket["hit_rate"] > 0.55:
        verdicts.append(f"✅ High CASE (≥60) hit rate: {high_bucket['hit_rate']:.1%} > 55% threshold")
    elif high_bucket:
        verdicts.append(f"❌ High CASE (≥60) hit rate: {high_bucket['hit_rate']:.1%} ≤ 55% threshold")

    if high_bucket and low_bucket:
        diff = high_bucket["avg_return"] - low_bucket["avg_return"]
        if diff > 0.02:
            verdicts.append(f"✅ Return spread (high vs low CASE): {diff:+.2%} > 2% threshold")
        else:
            verdicts.append(f"❌ Return spread (high vs low CASE): {diff:+.2%} ≤ 2% threshold")

    if mono_20d.get("is_monotonic"):
        verdicts.append("✅ 20D returns are monotonic across CASE buckets")
    elif mono_20d:
        verdicts.append(f"⚠️ 20D monotonicity violated ({len(mono_20d.get('violations', []))} violations)")

    for v in verdicts:
        lines.append(f"- {v}")

    lines.append("")
    passed = sum(1 for v in verdicts if v.startswith("✅"))
    total = len(verdicts)
    if total > 0:
        lines.append(f"\n**Score: {passed}/{total} criteria passed.**\n")
        if passed == total:
            lines.append("> [!TIP]\n> CASE shows **predictive signal**. Consider production deployment.\n")
        elif passed >= total / 2:
            lines.append("> [!NOTE]\n> CASE shows **partial predictive signal**. Calibration recommended.\n")
        else:
            lines.append("> [!WARNING]\n> CASE shows **weak/no predictive signal**. Thresholds and weights need recalibration.\n")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

async def main():
    start = time.monotonic()

    logger.info("=" * 60)
    logger.info("CASE Predictive Validation Backtest")
    logger.info(f"Universe: {len(UNIVERSE)} tickers")
    logger.info(f"Horizons: {HORIZONS_DAYS}")
    logger.info(f"Benchmark: {BENCHMARK}")
    logger.info("=" * 60)

    # Step 1: Compute CASE scores
    logger.info("\n📊 Step 1/4: Computing CASE scores...")
    case_scores = compute_case_scores(UNIVERSE)
    logger.info(f"  ✓ {len(case_scores)} CASE scores computed")

    # Step 2: Fetch OHLCV history
    logger.info("\n📈 Step 2/4: Fetching OHLCV history...")
    ohlcv_map = fetch_ohlcv_map(list(case_scores.keys()))
    logger.info(f"  ✓ {len(ohlcv_map)} OHLCV series fetched")

    # Step 3: Evaluate outcomes
    logger.info("\n🎯 Step 3/4: Evaluating outcomes...")
    outcomes = evaluate_outcomes(case_scores, ohlcv_map)
    logger.info(f"  ✓ {len(outcomes)} outcomes evaluated")

    # Step 4: Analytics & Report
    logger.info("\n📋 Step 4/4: Computing analytics...")
    analytics = compute_analytics(outcomes)

    elapsed = time.monotonic() - start
    report = generate_report(case_scores, outcomes, analytics, elapsed)

    # ── Save results ─────────────────────────────────────────────────────
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)

    results_path = results_dir / "case_backtest_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "universe_size": len(case_scores),
            "outcome_count": len(outcomes),
            "elapsed_seconds": round(elapsed, 1),
            "case_scores": case_scores,
            "outcomes": outcomes,
            "analytics": analytics,
        }, f, indent=2, default=str)
    logger.info(f"\n💾 Results saved: {results_path}")

    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "case_validation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"📝 Report saved: {report_path}")

    # ── Print summary ────────────────────────────────────────────────────
    logger.info(f"\n{'=' * 60}")
    logger.info(f"BACKTEST COMPLETE in {elapsed:.1f}s")
    logger.info(f"{'=' * 60}")

    for horizon in ["5D", "20D", "60D"]:
        ov = analytics["overall"].get(horizon)
        if ov:
            logger.info(f"  {horizon}: N={ov['count']}, HitRate={ov['hit_rate']:.1%}, AvgReturn={ov['avg_return']:+.2%}")

    return report_path


if __name__ == "__main__":
    asyncio.run(main())
