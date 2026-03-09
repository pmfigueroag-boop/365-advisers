"""
src/engines/stat_arb/scanner.py
──────────────────────────────────────────────────────────────────────────────
Universe-level pair scanner.

Pre-filters by sector (same-sector pairs) and correlation, then runs
cointegration tests on the filtered candidates. Returns top-N pairs
ranked by quality score (half-life + cointegration strength).
"""

from __future__ import annotations

import logging
import time
from itertools import combinations

import numpy as np

from src.engines.stat_arb.models import (
    PairCandidate,
    PairScanResult,
    PairStatus,
    ZScoreSignal,
)
from src.engines.stat_arb.cointegration import engle_granger_test
from src.engines.stat_arb.zscore import compute_spread, compute_zscore, current_signal_from_zscore

logger = logging.getLogger("365advisers.stat_arb.scanner")


class PairScanner:
    """
    Scans a universe of equities for cointegrated pairs.

    Pipeline:
        1. Group tickers by sector (same-sector pairs only for relevance)
        2. Filter by rolling correlation > min_correlation
        3. Run Engle-Granger cointegration test on qualifying pairs
        4. Compute z-score and half-life for cointegrated pairs
        5. Rank by quality score and return top-N
    """

    DEFAULT_MIN_CORRELATION = 0.60
    DEFAULT_MAX_PVALUE = 0.05
    DEFAULT_MAX_HALF_LIFE = 60.0   # days
    DEFAULT_TOP_N = 20

    @classmethod
    def scan(
        cls,
        universe_prices: dict[str, list[float]],
        sector_map: dict[str, str] | None = None,
        *,
        min_correlation: float = DEFAULT_MIN_CORRELATION,
        max_pvalue: float = DEFAULT_MAX_PVALUE,
        max_half_life: float = DEFAULT_MAX_HALF_LIFE,
        top_n: int = DEFAULT_TOP_N,
        lookback_days: int = 252,
    ) -> PairScanResult:
        """
        Scan for cointegrated pairs.

        Args:
            universe_prices: Dict mapping ticker → list of daily close prices.
            sector_map: Dict mapping ticker → sector string.
            min_correlation: Minimum correlation to consider a pair.
            max_pvalue: Maximum ADF p-value for cointegration.
            max_half_life: Reject pairs with half-life > this (too slow).
            top_n: Return this many top pairs.
            lookback_days: Number of trailing days to use.

        Returns:
            PairScanResult with ranked pairs and scan statistics.
        """
        start_time = time.time()
        sector_map = sector_map or {}

        # Trim to lookback
        tickers = list(universe_prices.keys())
        prices = {}
        for t in tickers:
            p = universe_prices[t]
            prices[t] = p[-lookback_days:] if len(p) > lookback_days else p

        # Group by sector for same-sector pairing
        sector_groups: dict[str, list[str]] = {}
        for t in tickers:
            sec = sector_map.get(t, "Unknown")
            sector_groups.setdefault(sec, []).append(t)

        pairs_tested = 0
        cointegrated_pairs: list[PairCandidate] = []

        for sector, group_tickers in sector_groups.items():
            if len(group_tickers) < 2:
                continue

            for t_a, t_b in combinations(group_tickers, 2):
                p_a = prices.get(t_a, [])
                p_b = prices.get(t_b, [])
                min_len = min(len(p_a), len(p_b))
                if min_len < 60:
                    continue

                a = np.array(p_a[:min_len])
                b = np.array(p_b[:min_len])

                # Correlation filter
                corr = float(np.corrcoef(a, b)[0, 1])
                if abs(corr) < min_correlation:
                    continue

                pairs_tested += 1

                # Cointegration test
                coint = engle_granger_test(a, b)
                coint.ticker_a = t_a
                coint.ticker_b = t_b

                if not coint.is_cointegrated:
                    continue

                hl = coint.half_life or 999
                if hl > max_half_life:
                    continue

                # Compute current z-score
                spread = compute_spread(a, b, hedge_ratio=coint.hedge_ratio)
                z_scores = compute_zscore(spread, lookback=min(60, min_len // 2))
                current_z = float(z_scores[-1]) if len(z_scores) > 0 else 0.0
                signal = current_signal_from_zscore(current_z)

                # Quality score: prioritise short half-life + low p-value
                quality = cls._quality_score(hl, coint.p_value, abs(corr))

                pair = PairCandidate(
                    ticker_a=t_a,
                    ticker_b=t_b,
                    sector=sector,
                    correlation=round(corr, 4),
                    cointegration=coint,
                    half_life=round(hl, 2),
                    current_z_score=round(current_z, 4),
                    current_signal=signal,
                    spread_mean=round(float(np.mean(spread)), 4),
                    spread_std=round(float(np.std(spread)), 4),
                    status=PairStatus.ACTIVE,
                    quality_score=round(quality, 2),
                )
                cointegrated_pairs.append(pair)

        # Sort by quality (higher is better), take top-N
        cointegrated_pairs.sort(key=lambda p: p.quality_score, reverse=True)
        top_pairs = cointegrated_pairs[:top_n]

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "Pair scan complete: %d tickers → %d pairs tested → %d cointegrated → %d returned (%.0f ms)",
            len(tickers), pairs_tested, len(cointegrated_pairs), len(top_pairs), duration_ms,
        )

        return PairScanResult(
            pairs=top_pairs,
            universe_size=len(tickers),
            pairs_tested=pairs_tested,
            pairs_cointegrated=len(cointegrated_pairs),
            scan_duration_ms=round(duration_ms, 1),
            filters_applied={
                "min_correlation": min_correlation,
                "max_pvalue": max_pvalue,
                "max_half_life": max_half_life,
            },
        )

    @staticmethod
    def _quality_score(half_life: float, p_value: float, correlation: float) -> float:
        """
        Composite pair quality score (0–100).

        Components:
            - Half-life (40%):  shorter is better, max 60 days
            - Cointegration (40%): lower p-value is better
            - Correlation (20%):   higher absolute correlation is better
        """
        # Half-life: 0 days → 100, 60 days → 0
        hl_score = max(0, 100 * (1 - half_life / 60.0))

        # P-value: 0.001 → 100, 0.05 → 0
        pv_score = max(0, 100 * (1 - p_value / 0.05))

        # Correlation: 0.6 → 0, 1.0 → 100
        corr_score = max(0, 100 * (correlation - 0.6) / 0.4)

        return 0.40 * hl_score + 0.40 * pv_score + 0.20 * corr_score
