"""
src/research/alpha_tests/quintile_spread_test.py
──────────────────────────────────────────────────────────────────────────────
Alpha Discrimination Test — Quintile Spread.

Evaluates whether the Opportunity Score (and component scores) can rank
assets by future return.  The core hypothesis is:

    E[R_future | score_high] > E[R_future | score_low]

The test splits observations into quintiles by score, computes forward
return metrics per bucket, and evaluates:
  • Alpha spread (Q5 − Q1)
  • Statistical significance (Welch t-test, Spearman, bootstrap CI)
  • Monotonicity (Kendall tau-b)
  • Alpha decay curve across multiple horizons

Enhanced statistical safeguards:
  • Observation deduplication per ticker/window
  • Concentration warnings
  • Strict acceptance criteria requiring p < 0.05
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from src.research.alpha_tests.models import (
    AlphaDecayPoint,
    AlphaSpreadResult,
    BucketMetrics,
    ScoreTestComparison,
    SignificanceResult,
)

logger = logging.getLogger("365advisers.research.alpha_tests.quintile_spread")

# ── Data Loading ──────────────────────────────────────────────────────────────

_SCORE_COLUMNS = [
    "opportunity_score",
    "case_score",
    "fundamental_score",
    "technical_score",
]

_RETURN_COLUMNS = {
    "return_1d": 1,
    "return_5d": 5,
    "return_20d": 20,
    "return_60d": 60,
}


def load_tracker_data(min_age_days: int = 20) -> pd.DataFrame:
    """
    Load all OpportunityTracker records with complete 20d returns.

    Returns a DataFrame with columns:
        ticker, generated_at, opportunity_score, case_score,
        fundamental_score, technical_score, return_1d, return_5d,
        return_20d, return_60d
    """
    from src.engines.opportunity_tracking.repository import OpportunityRepository

    records = OpportunityRepository.get_all_complete(min_age_days=min_age_days)

    if not records:
        logger.warning("ALPHA-TEST: No complete records found in OpportunityTracker")
        return pd.DataFrame()

    rows = []
    for r in records:
        rows.append({
            "ticker": r.ticker,
            "generated_at": r.generated_at,
            "opportunity_score": r.opportunity_score,
            "case_score": getattr(r, "case_score", None),
            "fundamental_score": getattr(r, "fundamental_score", None),
            "technical_score": getattr(r, "technical_score", None),
            "return_1d": r.return_1d,
            "return_5d": r.return_5d,
            "return_20d": r.return_20d,
            "return_60d": r.return_60d,
        })

    df = pd.DataFrame(rows)
    logger.info("ALPHA-TEST: Loaded %d observations from tracker", len(df))
    return df


# ── Deduplication ─────────────────────────────────────────────────────────────


def deduplicate_observations(
    df: pd.DataFrame,
    window_days: int = 5,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Remove duplicate observations of the same ticker within a rolling window.

    Keeps the first observation per ticker per N-day window to ensure
    statistical independence.  Also checks for concentration risk.

    Returns
    -------
    tuple[pd.DataFrame, list[str]]
        Deduplicated DataFrame and list of warning messages.
    """
    warnings: list[str] = []

    if df.empty:
        return df, warnings

    df = df.sort_values(["ticker", "generated_at"]).reset_index(drop=True)

    keep_mask = pd.Series([True] * len(df), index=df.index)
    prev_dates: dict[str, pd.Timestamp] = {}

    for idx, row in df.iterrows():
        ticker = row["ticker"]
        gen_at = pd.Timestamp(row["generated_at"])
        if ticker in prev_dates:
            delta = (gen_at - prev_dates[ticker]).days
            if delta < window_days:
                keep_mask.iloc[idx] = False  # type: ignore[index]
                continue
        prev_dates[ticker] = gen_at

    deduped = df[keep_mask].reset_index(drop=True)
    removed = len(df) - len(deduped)
    if removed > 0:
        warnings.append(
            f"Deduplication removed {removed} observations "
            f"(same ticker within {window_days}-day window)"
        )

    # Concentration check
    if len(deduped) > 0:
        counts = deduped["ticker"].value_counts()
        max_pct = counts.iloc[0] / len(deduped) if len(counts) > 0 else 0
        if max_pct > 0.10:
            top_ticker = counts.index[0]
            warnings.append(
                f"Concentration warning: {top_ticker} represents "
                f"{max_pct:.0%} of observations (>{10}% threshold)"
            )

    logger.info(
        "ALPHA-TEST: Dedup %d → %d observations (%d removed)",
        len(df), len(deduped), removed,
    )
    return deduped, warnings


# ── Bucket Construction ───────────────────────────────────────────────────────


def build_quintile_buckets(
    df: pd.DataFrame,
    score_col: str,
    n_buckets: int = 5,
) -> dict[str, pd.DataFrame]:
    """
    Sort observations by score and split into N equal-sized buckets.

    Auto-falls back to terciles (3) if N < 200.

    Returns dict mapping bucket label (Q1…Q5 or T1…T3) to sub-DataFrame.
    """
    valid = df.dropna(subset=[score_col]).copy()

    if len(valid) < 30:
        logger.warning(
            "ALPHA-TEST: Only %d valid observations for %s — too few for buckets",
            len(valid), score_col,
        )
        return {}

    # Auto-fallback
    if len(valid) < 200 and n_buckets > 3:
        n_buckets = 3
        logger.info("ALPHA-TEST: N=%d < 200, falling back to terciles", len(valid))

    valid = valid.sort_values(score_col).reset_index(drop=True)

    # Use pd.qcut for quantile-based splitting
    try:
        valid["_bucket"] = pd.qcut(
            valid[score_col],
            q=n_buckets,
            labels=False,
            duplicates="drop",
        )
    except ValueError:
        # Not enough unique values for the requested number of buckets
        n_buckets = min(n_buckets, valid[score_col].nunique())
        if n_buckets < 2:
            return {}
        valid["_bucket"] = pd.qcut(
            valid[score_col],
            q=n_buckets,
            labels=False,
            duplicates="drop",
        )

    actual_buckets = int(valid["_bucket"].max()) + 1
    prefix = "Q" if actual_buckets >= 5 else "T"

    result: dict[str, pd.DataFrame] = {}
    for i in range(actual_buckets):
        label = f"{prefix}{i + 1}"
        result[label] = valid[valid["_bucket"] == i].drop(columns=["_bucket"])

    return result


# ── Bucket Metrics ────────────────────────────────────────────────────────────


def calculate_bucket_metrics(
    buckets: dict[str, pd.DataFrame],
) -> list[BucketMetrics]:
    """Compute descriptive statistics per bucket for 5d and 20d horizons."""
    metrics: list[BucketMetrics] = []

    for label, bdf in sorted(buckets.items()):
        score_cols_in_df = [c for c in _SCORE_COLUMNS if c in bdf.columns]
        score_col = score_cols_in_df[0] if score_cols_in_df else None

        m = BucketMetrics(
            bucket_label=label,
            score_min=float(bdf[score_col].min()) if score_col and not bdf.empty else 0.0,
            score_max=float(bdf[score_col].max()) if score_col and not bdf.empty else 0.0,
            count=len(bdf),
        )

        # 5-day returns
        r5 = bdf["return_5d"].dropna()
        if len(r5) > 0:
            m.mean_return_5d = round(float(r5.mean()), 6)
            m.median_return_5d = round(float(r5.median()), 6)
            m.std_return_5d = round(float(r5.std(ddof=1)) if len(r5) > 1 else 0.0, 6)
            m.hit_rate_5d = round(float((r5 > 0).mean()), 4)

        # 20-day returns
        r20 = bdf["return_20d"].dropna()
        if len(r20) > 0:
            m.mean_return_20d = round(float(r20.mean()), 6)
            m.median_return_20d = round(float(r20.median()), 6)
            m.std_return_20d = round(float(r20.std(ddof=1)) if len(r20) > 1 else 0.0, 6)
            m.hit_rate_20d = round(float((r20 > 0).mean()), 4)

        metrics.append(m)

    return metrics


# ── Alpha Spread ──────────────────────────────────────────────────────────────


def compute_alpha_spread(
    bucket_metrics: list[BucketMetrics],
) -> dict[str, float]:
    """
    Compute alpha spread: top bucket − bottom bucket.

    Works for both quintiles (Q5 − Q1) and terciles (T3 − T1).
    """
    if len(bucket_metrics) < 2:
        return {"alpha_spread_5d": 0.0, "alpha_spread_20d": 0.0}

    bottom = bucket_metrics[0]
    top = bucket_metrics[-1]

    return {
        "alpha_spread_5d": round(top.mean_return_5d - bottom.mean_return_5d, 6),
        "alpha_spread_20d": round(top.mean_return_20d - bottom.mean_return_20d, 6),
    }


# ── Statistical Significance ─────────────────────────────────────────────────


def compute_significance(
    df: pd.DataFrame,
    score_col: str,
    buckets: dict[str, pd.DataFrame],
    n_bootstrap: int = 1000,
) -> SignificanceResult:
    """
    Compute statistical significance of the alpha spread.

    • Welch t-test: top vs bottom bucket returns (20d)
    • Spearman rank correlation: score vs forward return
    • Bootstrap 95% CI on the alpha spread
    • Kendall tau-b for monotonicity
    """
    result = SignificanceResult()
    bucket_labels = sorted(buckets.keys())

    if len(bucket_labels) < 2:
        return result

    bottom_key = bucket_labels[0]
    top_key = bucket_labels[-1]

    bottom_returns = buckets[bottom_key]["return_20d"].dropna().values
    top_returns = buckets[top_key]["return_20d"].dropna().values

    # ── Welch t-test ──────────────────────────────────────────────────────
    if len(bottom_returns) >= 5 and len(top_returns) >= 5:
        t_stat, p_val = sp_stats.ttest_ind(
            top_returns, bottom_returns, equal_var=False,
        )
        result.welch_t_statistic = round(float(t_stat), 4)
        result.welch_p_value = round(float(p_val), 6)

    # ── Spearman rank correlation ─────────────────────────────────────────
    valid = df.dropna(subset=[score_col, "return_20d"])
    if len(valid) >= 10:
        rho, p = sp_stats.spearmanr(valid[score_col], valid["return_20d"])
        result.spearman_correlation = round(float(rho), 4)
        result.spearman_p_value = round(float(p), 6)

    # ── Bootstrap CI on alpha spread ──────────────────────────────────────
    if len(bottom_returns) >= 5 and len(top_returns) >= 5:
        rng = np.random.default_rng(42)
        spreads = []
        for _ in range(n_bootstrap):
            top_sample = rng.choice(top_returns, size=len(top_returns), replace=True)
            bot_sample = rng.choice(bottom_returns, size=len(bottom_returns), replace=True)
            spreads.append(float(np.mean(top_sample) - np.mean(bot_sample)))
        result.bootstrap_ci_lower = round(float(np.percentile(spreads, 2.5)), 6)
        result.bootstrap_ci_upper = round(float(np.percentile(spreads, 97.5)), 6)

    # ── Kendall tau-b (monotonicity) ──────────────────────────────────────
    bucket_ranks = []
    bucket_means = []
    for i, label in enumerate(bucket_labels):
        bdf = buckets[label]
        r20 = bdf["return_20d"].dropna()
        if len(r20) > 0:
            bucket_ranks.append(i)
            bucket_means.append(float(r20.mean()))

    if len(bucket_ranks) >= 3:
        tau, _ = sp_stats.kendalltau(bucket_ranks, bucket_means)
        result.kendall_tau = round(float(tau), 4)

    return result


# ── Alpha Decay Curve ─────────────────────────────────────────────────────────


def compute_alpha_decay_curve(
    df: pd.DataFrame,
    score_col: str,
    n_buckets: int = 5,
) -> list[AlphaDecayPoint]:
    """
    Compute the alpha spread at multiple horizons to diagnose persistence.

    Uses [1d, 5d, 20d, 60d] horizons.
    """
    horizons = [
        ("1d", "return_1d", 1),
        ("5d", "return_5d", 5),
        ("20d", "return_20d", 20),
        ("60d", "return_60d", 60),
    ]

    curve: list[AlphaDecayPoint] = []
    for label, col, days in horizons:
        point = AlphaDecayPoint(horizon_label=label, horizon_days=days)

        if col not in df.columns:
            curve.append(point)
            continue

        valid = df.dropna(subset=[score_col, col])
        if len(valid) < 30:
            curve.append(point)
            continue

        buckets = build_quintile_buckets(valid, score_col, n_buckets)
        if len(buckets) < 2:
            curve.append(point)
            continue

        bucket_labels = sorted(buckets.keys())
        bottom = buckets[bucket_labels[0]][col].dropna()
        top = buckets[bucket_labels[-1]][col].dropna()

        if len(bottom) > 0 and len(top) > 0:
            point.alpha_spread = round(
                float(top.mean()) - float(bottom.mean()), 6,
            )

        curve.append(point)

    return curve


# ── Monotonicity Check ────────────────────────────────────────────────────────


def check_monotonicity(
    bucket_metrics: list[BucketMetrics],
) -> dict[str, Any]:
    """
    Verify if returns increase monotonically with score.

    Returns dict with is_monotonic flag and violations list.
    """
    if len(bucket_metrics) < 2:
        return {"is_monotonic": False, "violations": ["Insufficient buckets"]}

    means = [bm.mean_return_20d for bm in bucket_metrics]
    violations: list[str] = []

    for i in range(1, len(means)):
        if means[i] < means[i - 1]:
            violations.append(
                f"{bucket_metrics[i].bucket_label} ({means[i]:.4f}) < "
                f"{bucket_metrics[i - 1].bucket_label} ({means[i - 1]:.4f})"
            )

    return {
        "is_monotonic": len(violations) == 0,
        "violations": violations,
    }


# ── Report Generation ────────────────────────────────────────────────────────


def _evaluate_acceptance(
    spread: dict[str, float],
    significance: SignificanceResult,
    bucket_metrics: list[BucketMetrics],
) -> tuple[str, dict]:
    """
    Evaluate acceptance criteria with enhanced rigor.

    Criteria:
    1. alpha_spread_20d > 0  AND  p_value < 0.05
    2. hit_rate_Q5 > hit_rate_Q1
    3. spearman_correlation > 0  AND  spearman_p_value < 0.10
    """
    details: dict[str, Any] = {}

    alpha_20d = spread.get("alpha_spread_20d", 0.0)
    p_val = significance.welch_p_value
    spearman = significance.spearman_correlation
    spearman_p = significance.spearman_p_value

    # Criterion 1: Spread positive + significant
    spread_positive = alpha_20d > 0
    spread_significant = p_val is not None and p_val < 0.05
    details["spread_positive"] = spread_positive
    details["spread_significant"] = spread_significant

    # Criterion 2: Hit rate Q5 > Q1
    if len(bucket_metrics) >= 2:
        hr_top = bucket_metrics[-1].hit_rate_20d
        hr_bottom = bucket_metrics[0].hit_rate_20d
        hr_pass = hr_top > hr_bottom
    else:
        hr_pass = False
        hr_top = hr_bottom = 0.0
    details["hit_rate_top"] = hr_top
    details["hit_rate_bottom"] = hr_bottom
    details["hit_rate_pass"] = hr_pass

    # Criterion 3: Spearman positive + meaningful
    spearman_positive = spearman > 0
    spearman_significant = spearman_p is not None and spearman_p < 0.10
    details["spearman_positive"] = spearman_positive
    details["spearman_significant"] = spearman_significant

    # Decision
    if spread_positive and spread_significant and hr_pass and spearman_positive and spearman_significant:
        signal = "Predictive ranking detected"
    elif spread_positive and hr_pass:
        if not spread_significant:
            signal = "Weak signal — insufficient statistical significance"
        elif not spearman_significant:
            signal = "Weak signal — low rank correlation significance"
        else:
            signal = "Weak signal — partial criteria met"
    else:
        signal = "No clear alpha signal"

    return signal, details


def generate_report(
    score_col: str,
    raw_count: int,
    df: pd.DataFrame,
    buckets: dict[str, pd.DataFrame],
    bucket_metrics: list[BucketMetrics],
    spread: dict[str, float],
    significance: SignificanceResult,
    decay_curve: list[AlphaDecayPoint],
    warnings: list[str],
) -> AlphaSpreadResult:
    """Assemble all computed metrics into a single report."""
    signal, acceptance = _evaluate_acceptance(spread, significance, bucket_metrics)

    return AlphaSpreadResult(
        score_column=score_col,
        observations=raw_count,
        observations_after_dedup=len(df),
        n_buckets=len(buckets),
        buckets=bucket_metrics,
        alpha_spread_5d=spread.get("alpha_spread_5d", 0.0),
        alpha_spread_20d=spread.get("alpha_spread_20d", 0.0),
        significance=significance,
        alpha_decay_curve=decay_curve,
        signal=signal,
        acceptance_details=acceptance,
        warnings=warnings,
    )


# ── Orchestrators ─────────────────────────────────────────────────────────────


def run_full_test(
    score_col: str = "opportunity_score",
    df: pd.DataFrame | None = None,
    dedup_window: int = 5,
    n_buckets: int = 5,
) -> AlphaSpreadResult:
    """
    End-to-end quintile spread test for a single score column.

    Parameters
    ----------
    score_col : str
        Column name to test (opportunity_score, case_score, etc.).
    df : pd.DataFrame | None
        Pre-loaded data.  If None, loads from OpportunityRepository.
    dedup_window : int
        Days for deduplication window (default 5).
    n_buckets : int
        Number of buckets (default 5, auto-fallback to 3 if N < 200).
    """
    # Load
    if df is None:
        df = load_tracker_data()

    if df.empty:
        return AlphaSpreadResult(
            score_column=score_col,
            signal="No data — tracker has no complete records",
        )

    raw_count = len(df)

    # Validate score column exists
    if score_col not in df.columns:
        return AlphaSpreadResult(
            score_column=score_col,
            observations=raw_count,
            signal=f"Score column '{score_col}' not found in data",
        )

    # Deduplicate
    df, warnings = deduplicate_observations(df, window_days=dedup_window)

    if len(df) < 30:
        return AlphaSpreadResult(
            score_column=score_col,
            observations=raw_count,
            observations_after_dedup=len(df),
            signal="Insufficient observations after deduplication (need ≥ 30)",
            warnings=warnings,
        )

    # Build buckets
    buckets = build_quintile_buckets(df, score_col, n_buckets)
    if len(buckets) < 2:
        return AlphaSpreadResult(
            score_column=score_col,
            observations=raw_count,
            observations_after_dedup=len(df),
            signal="Could not construct meaningful buckets",
            warnings=warnings,
        )

    # Metrics
    bucket_metrics = calculate_bucket_metrics(buckets)
    spread = compute_alpha_spread(bucket_metrics)
    significance = compute_significance(df, score_col, buckets)
    decay_curve = compute_alpha_decay_curve(df, score_col, n_buckets)

    return generate_report(
        score_col=score_col,
        raw_count=raw_count,
        df=df,
        buckets=buckets,
        bucket_metrics=bucket_metrics,
        spread=spread,
        significance=significance,
        decay_curve=decay_curve,
        warnings=warnings,
    )


def run_multi_score_comparison(
    df: pd.DataFrame | None = None,
) -> ScoreTestComparison:
    """
    Run the quintile spread test for all 4 score dimensions and compare.

    Returns a ScoreTestComparison identifying which score has the strongest
    predictive power.
    """
    if df is None:
        df = load_tracker_data()

    results: dict[str, AlphaSpreadResult] = {}
    best_score = ""
    best_spread = -float("inf")

    for col in _SCORE_COLUMNS:
        if col in df.columns and df[col].notna().sum() >= 30:
            result = run_full_test(score_col=col, df=df.copy())
            results[col] = result

            if result.alpha_spread_20d > best_spread:
                best_spread = result.alpha_spread_20d
                best_score = col
        else:
            results[col] = AlphaSpreadResult(
                score_column=col,
                signal=f"Insufficient data for {col}",
            )

    return ScoreTestComparison(
        results=results,
        best_score=best_score,
        best_alpha_spread_20d=round(best_spread, 6) if best_spread > -float("inf") else 0.0,
    )
