"""
scripts/case_snapshot_scheduler.py
──────────────────────────────────────────────────────────────────────────────
T4: Point-in-Time CASE Snapshot Scheduler

Records daily CASE score snapshots for a universe of tickers,
enabling proper forward-return validation over time.

Usage:
    # Manual run (records one snapshot for today):
    python scripts/case_snapshot_scheduler.py

    # Schedule with Windows Task Scheduler or cron:
    # Run once per market day at 16:30 ET (after market close)

Storage:
    results/case_snapshots.jsonl  — one JSON line per ticker per day
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.market_data import fetch_fundamental_data, fetch_technical_data
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.composite_alpha.engine import CompositeAlphaEngine
from src.engines.idea_generation.engine import IdeaGenerationEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("case_snapshot")

# Universe — same as backtest runner
SNAPSHOT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ADBE", "CRM", "CSCO", "INTC",
    "JPM", "V", "MA", "BAC", "GS", "BLK",
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
    "AMZN", "TSLA", "HD", "NKE", "SBUX",
    "CAT", "GE", "HON", "UPS", "BA",
    "XOM", "CVX", "COP", "SLB",
    "PG", "KO", "PEP", "COST",
    "DIS", "NFLX", "CMCSA",
    "NEE", "DUK",
    "LIN", "APD",
    "PLD", "AMT",
]


def record_snapshots():
    """Record CASE snapshots for all tickers in the universe."""
    evaluator = SignalEvaluator()
    case_engine = CompositeAlphaEngine()
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    snapshot_file = results_dir / "case_snapshots.jsonl"

    recorded = 0

    for i, ticker in enumerate(SNAPSHOT_UNIVERSE):
        logger.info(f"[{i+1}/{len(SNAPSHOT_UNIVERSE)}] {ticker}")
        try:
            fund_raw = fetch_fundamental_data(ticker)
            tech_raw = fetch_technical_data(ticker)

            fund_features = IdeaGenerationEngine._build_fundamental_features(ticker, fund_raw) if fund_raw and "error" not in fund_raw else None
            tech_features = IdeaGenerationEngine._build_technical_features(ticker, tech_raw) if tech_raw and "error" not in tech_raw else None

            if fund_features is None and tech_features is None:
                continue

            profile = evaluator.evaluate(
                ticker=ticker,
                fundamental=fund_features,
                technical=tech_features,
            )

            case_result = case_engine.compute(profile)

            # Record snapshot as JSONL
            snapshot = {
                "date": snapshot_date,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "case_score": case_result.composite_alpha_score,
                "environment": case_result.signal_environment.value,
                "fired_signals": profile.fired_signals,
                "total_signals": profile.total_signals,
                "sector": fund_raw.get("sector", "") if fund_raw else "",
                "current_price": tech_raw.get("current_price", 0) if tech_raw else 0,
                "subscores": {k: v.score for k, v in case_result.subscores.items()},
                "convergence_bonus": case_result.convergence_bonus,
                "conflicts": case_result.cross_category_conflicts,
            }

            with open(snapshot_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(snapshot, default=str) + "\n")

            recorded += 1
            logger.info(f"  ✓ CASE={case_result.composite_alpha_score}")

        except Exception as e:
            logger.error(f"  ✗ {ticker}: {e}")

        time.sleep(0.5)

    logger.info(f"\n📸 {recorded} snapshots recorded to {snapshot_file}")
    logger.info(f"📅 Date: {snapshot_date}")
    return recorded


if __name__ == "__main__":
    record_snapshots()
