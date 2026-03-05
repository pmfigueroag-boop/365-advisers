"""
src/engines/idea_generation/engine.py
──────────────────────────────────────────────────────────────────────────────
IdeaGenerationEngine — orchestrates all detectors across a universe of
tickers and produces a ranked list of investment ideas.

Usage:
    engine = IdeaGenerationEngine()
    result = await engine.scan(tickers=["AAPL", "MSFT", "NVDA"])
"""

from __future__ import annotations

import asyncio
import logging
import time as _time

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.contracts.market_data import (
    FinancialStatements, FinancialRatios,
    ProfitabilityRatios, ValuationRatios, LeverageRatios, QualityRatios,
    CashFlowEntry, PriceHistory, OHLCVBar, MarketMetrics, RawIndicators,
)
from src.data.market_data import fetch_fundamental_data, fetch_technical_data
from src.features.fundamental_features import extract_fundamental_features
from src.features.technical_features import extract_technical_features

from src.engines.idea_generation.models import (
    IdeaCandidate,
    IdeaScanResult,
    DetectorResult,
)
from src.engines.idea_generation.detectors.base import BaseDetector
from src.engines.idea_generation.detectors.value_detector import ValueDetector
from src.engines.idea_generation.detectors.quality_detector import QualityDetector
from src.engines.idea_generation.detectors.momentum_detector import MomentumDetector
from src.engines.idea_generation.detectors.reversal_detector import ReversalDetector
from src.engines.idea_generation.detectors.event_detector import EventDetector
from src.engines.idea_generation.ranker import rank_ideas


logger = logging.getLogger("365advisers.idea_generation.engine")

# Max concurrency for yfinance fetches to respect rate limits
_MAX_CONCURRENT = 5


class IdeaGenerationEngine:
    """
    Orchestrates opportunity detection across a set of tickers.

    Workflow:
      1. Fetch fundamental + technical data for each ticker (parallel, throttled)
      2. Extract normalised feature sets
      3. Run all detectors on each ticker
      4. Collect results, deduplicate, rank
      5. Return IdeaScanResult
    """

    def __init__(self) -> None:
        self.detectors: list[BaseDetector] = [
            ValueDetector(),
            QualityDetector(),
            MomentumDetector(),
            ReversalDetector(),
        ]
        self.event_detector = EventDetector()

    async def scan(
        self,
        tickers: list[str],
        score_history: dict[str, float] | None = None,
        current_scores: dict[str, float] | None = None,
    ) -> IdeaScanResult:
        """
        Scan a list of tickers and return prioritised ideas.

        Parameters
        ----------
        tickers : list[str]
            Universe of ticker symbols to scan.
        score_history : dict | None
            Previous opportunity scores keyed by ticker (for event detection).
        current_scores : dict | None
            Current opportunity scores keyed by ticker.
        """
        start = _time.monotonic_ns()
        score_hist = score_history or {}
        curr_scores = current_scores or {}

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        raw_ideas: list[IdeaCandidate] = []

        async def _scan_ticker(ticker: str) -> list[IdeaCandidate]:
            async with semaphore:
                return await self._scan_single(
                    ticker,
                    previous_score=score_hist.get(ticker.upper()),
                    current_score=curr_scores.get(ticker.upper()),
                )

        tasks = [_scan_ticker(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        detector_stats: dict[str, int] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"IDEA-ENGINE: Scan error: {result}")
                continue
            for idea in result:
                raw_ideas.append(idea)
                key = idea.idea_type.value
                detector_stats[key] = detector_stats.get(key, 0) + 1

        # Rank and deduplicate
        ranked = rank_ideas(raw_ideas)

        elapsed_ms = (_time.monotonic_ns() - start) / 1e6

        return IdeaScanResult(
            universe_size=len(tickers),
            ideas=ranked,
            scan_duration_ms=round(elapsed_ms, 1),
            detector_stats=detector_stats,
        )

    async def _scan_single(
        self,
        ticker: str,
        previous_score: float | None = None,
        current_score: float | None = None,
    ) -> list[IdeaCandidate]:
        """Fetch data, extract features, and run all detectors for one ticker."""
        symbol = ticker.upper().strip()
        ideas: list[IdeaCandidate] = []

        fundamental_features: FundamentalFeatureSet | None = None
        technical_features: TechnicalFeatureSet | None = None

        # ── Fetch + extract fundamental features ─────────────────────────
        try:
            fund_raw = await asyncio.to_thread(fetch_fundamental_data, symbol)
            if fund_raw and "error" not in fund_raw:
                fundamental_features = self._build_fundamental_features(symbol, fund_raw)
        except Exception as exc:
            logger.debug(f"IDEA-ENGINE: Fundamental fetch failed for {symbol}: {exc}")

        # ── Fetch + extract technical features ───────────────────────────
        try:
            tech_raw = await asyncio.to_thread(fetch_technical_data, symbol)
            if tech_raw and "error" not in tech_raw:
                technical_features = self._build_technical_features(symbol, tech_raw)
        except Exception as exc:
            logger.debug(f"IDEA-ENGINE: Technical fetch failed for {symbol}: {exc}")

        if fundamental_features is None and technical_features is None:
            logger.info(f"IDEA-ENGINE: No data available for {symbol}, skipping")
            return ideas

        # ── Run detectors ────────────────────────────────────────────────
        for detector in self.detectors:
            try:
                result = detector.scan(fundamental_features, technical_features)
                if result is not None:
                    ideas.append(self._result_to_candidate(
                        symbol, result, fundamental_features
                    ))
            except Exception as exc:
                logger.warning(
                    f"IDEA-ENGINE: {detector.name} detector error on {symbol}: {exc}"
                )

        # Event detector (needs score history)
        try:
            event_result = self.event_detector.scan(
                fundamental_features,
                technical_features,
                previous_score=previous_score,
                current_score=current_score,
            )
            if event_result is not None:
                ideas.append(self._result_to_candidate(
                    symbol, event_result, fundamental_features
                ))
        except Exception as exc:
            logger.warning(f"IDEA-ENGINE: event detector error on {symbol}: {exc}")

        return ideas

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _build_fundamental_features(
        symbol: str, fund_raw: dict
    ) -> FundamentalFeatureSet:
        """
        Convert raw dict from fetch_fundamental_data() into a
        FinancialStatements contract, then extract features.
        """
        ratios_raw = fund_raw.get("ratios", {})
        cashflow_raw = fund_raw.get("cashflow_series", [])

        fs = FinancialStatements(
            ticker=symbol,
            name=fund_raw.get("name", ""),
            sector=fund_raw.get("sector", ""),
            industry=fund_raw.get("industry", ""),
            description=fund_raw.get("description", ""),
            ratios=FinancialRatios(
                profitability=ProfitabilityRatios(**ratios_raw.get("profitability", {})),
                valuation=ValuationRatios(**ratios_raw.get("valuation", {})),
                leverage=LeverageRatios(**ratios_raw.get("leverage", {})),
                quality=QualityRatios(**ratios_raw.get("quality", {})),
            ),
            cashflow_series=[
                CashFlowEntry(**entry)
                for entry in cashflow_raw
                if isinstance(entry, dict)
            ],
        )
        return extract_fundamental_features(fs)

    @staticmethod
    def _build_technical_features(
        symbol: str, tech_raw: dict
    ) -> TechnicalFeatureSet:
        """
        Convert raw dict from fetch_technical_data() into PriceHistory +
        MarketMetrics contracts, then extract features.
        """
        ohlcv_raw = tech_raw.get("ohlcv", [])
        indicators_raw = tech_raw.get("indicators", {})

        price_history = PriceHistory(
            ticker=symbol,
            current_price=tech_raw.get("current_price", 0),
            ohlcv=[OHLCVBar(**bar) for bar in ohlcv_raw if isinstance(bar, dict)],
        )
        market_metrics = MarketMetrics(
            ticker=symbol,
            exchange=tech_raw.get("exchange", ""),
            indicators=RawIndicators(**{
                k: v for k, v in indicators_raw.items()
                if k in RawIndicators.model_fields
            }),
        )
        return extract_technical_features(price_history, market_metrics)

    @staticmethod
    def _result_to_candidate(
        ticker: str,
        result: DetectorResult,
        fundamental: FundamentalFeatureSet | None,
    ) -> IdeaCandidate:
        """Convert a DetectorResult into a full IdeaCandidate."""
        return IdeaCandidate(
            ticker=ticker,
            name=fundamental.name if fundamental else "",
            sector=fundamental.sector if fundamental else "",
            idea_type=result.idea_type,
            confidence=result.confidence,
            signal_strength=result.signal_strength,
            signals=result.signals,
            metadata=result.metadata,
        )
