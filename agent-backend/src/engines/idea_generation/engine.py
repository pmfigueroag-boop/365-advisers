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

from src.engines.idea_generation.metrics import get_collector

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
from src.engines.idea_generation.detectors.base import BaseDetector, ScanContext
from src.engines.idea_generation.detector_registry import (
    build_active_detectors,
    default_registry,
)
from src.engines.idea_generation.ranker import rank_ideas
from src.engines.idea_generation.strategy_profiles import StrategyProfile

# ── Alpha Signals Library integration ─────────────────────────────────────
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.alpha_signals.models import SignalProfile

# ── Composite Alpha Score Engine ──────────────────────────────────────────
from src.engines.composite_alpha.engine import CompositeAlphaEngine
from src.engines.composite_alpha.models import CompositeAlphaResult

# ── Alpha Decay Engine ────────────────────────────────────────────
from src.engines.alpha_decay import DecayEngine, ActivationTracker, DecayConfig

# ── Opportunity Performance Tracking ─────────────────────────────────────
from src.engines.opportunity_tracking.tracker import OpportunityTracker


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

    def __init__(
        self,
        detector_keys: set[str] | None = None,
        disabled_keys: set[str] | None = None,
        strategy_profile: StrategyProfile | None = None,
    ) -> None:
        self._strategy_profile = strategy_profile

        # Resolve detectors from profile or explicit keys
        _enabled = detector_keys
        _disabled = disabled_keys
        if strategy_profile is not None:
            if strategy_profile.enabled_detectors:
                _enabled = set(strategy_profile.enabled_detectors)
            if strategy_profile.disabled_detectors:
                _disabled = set(strategy_profile.disabled_detectors)

        self.detectors: list[BaseDetector] = build_active_detectors(
            enabled_keys=_enabled,
            disabled_keys=_disabled,
        )
        self._signal_evaluator = SignalEvaluator()
        self._composite_alpha_engine = CompositeAlphaEngine()
        # Alpha Decay
        _decay_config = DecayConfig()
        self._decay_engine = DecayEngine(
            tracker=ActivationTracker(config=_decay_config),
            config=_decay_config,
        )
        # Opportunity Performance Tracking
        self._opportunity_tracker = OpportunityTracker()

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
                logger.warning(
                    "scan_ticker_error",
                    extra={"error": str(result)},
                )
                continue
            for idea in result:
                raw_ideas.append(idea)
                key = idea.idea_type.value
                detector_stats[key] = detector_stats.get(key, 0) + 1

        # ── Apply profile minimum thresholds ───────────────────────
        if self._strategy_profile is not None:
            min_conf = self._strategy_profile.minimum_confidence
            min_sig = self._strategy_profile.minimum_signal_strength
            if min_conf > 0.0 or min_sig > 0.0:
                before = len(raw_ideas)
                raw_ideas = [
                    idea for idea in raw_ideas
                    if idea.confidence_score >= min_conf
                    and idea.signal_strength >= min_sig
                ]
                filtered = before - len(raw_ideas)
                if filtered > 0:
                    logger.info(
                        "profile_filtered",
                        extra={
                            "profile": self._strategy_profile.key,
                            "filtered_count": filtered,
                            "min_confidence": min_conf,
                            "min_signal_strength": min_sig,
                        },
                    )

        # Rank and deduplicate (with profile weights if available)
        _ranking_weights = None
        if self._strategy_profile is not None:
            _ranking_weights = self._strategy_profile.ranking_weights
        ranked = rank_ideas(raw_ideas, ranking_weights=_ranking_weights)

        # ── Store profile key in idea metadata ────────────────────────
        if self._strategy_profile is not None:
            for idea in ranked:
                idea.metadata["strategy_profile"] = self._strategy_profile.key

        # ── Auto-register ideas for opportunity tracking ──────────────
        for idea in ranked:
            try:
                cas = idea.metadata.get("composite_alpha_score")
                self._opportunity_tracker.register_idea(
                    idea,
                    opp_score=float(cas) if cas is not None else None,
                )
            except Exception as exc:
                logger.debug(
                    "IDEA-ENGINE: Failed to register idea %s for tracking: %s",
                    idea.id, exc,
                )

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

        # ── Evaluate Alpha Signals ────────────────────────────────────────
        signal_profile: SignalProfile | None = None
        composite_alpha: CompositeAlphaResult | None = None
        try:
            signal_profile = self._signal_evaluator.evaluate(
                ticker=symbol,
                fundamental=fundamental_features,
                technical=technical_features,
            )
            logger.debug(
                f"IDEA-ENGINE: Signal profile for {symbol}: "
                f"{signal_profile.fired_signals}/{signal_profile.total_signals} signals fired"
            )
        except Exception as exc:
            logger.warning(f"IDEA-ENGINE: Signal evaluation failed for {symbol}: {exc}")

        # ── Compute Composite Alpha Score ─────────────────────────────────
        if signal_profile is not None:
            try:
                composite_alpha = self._composite_alpha_engine.compute(
                    signal_profile, decay_engine=self._decay_engine
                )
                logger.debug(
                    f"IDEA-ENGINE: CASE for {symbol}: "
                    f"score={composite_alpha.composite_alpha_score}, "
                    f"env={composite_alpha.signal_environment.value}"
                )
            except Exception as exc:
                logger.warning(f"IDEA-ENGINE: CASE computation failed for {symbol}: {exc}")

        # ── Run detectors (uniform loop, ScanContext carries event data) ──
        scan_context = ScanContext(
            previous_score=previous_score,
            current_score=current_score,
        )

        for detector in self.detectors:
            try:
                result = None
                # Try Alpha Signals profile first, fall back to legacy
                if signal_profile is not None:
                    result = detector.scan_from_profile(signal_profile)
                if result is None:
                    result = detector.scan(
                        fundamental_features, technical_features,
                        context=scan_context,
                    )
                if result is not None:
                    result.detector = detector.name
                    # ── Compute confidence_score if detector didn't set it ──
                    if result.confidence_score == 0.0 and result.signals:
                        result.confidence_score = self._compute_confidence(
                            result
                        )
                    ideas.append(self._result_to_candidate(
                        symbol, result, fundamental_features,
                        composite_alpha=composite_alpha,
                    ))
                    _m = get_collector()
                    _m.increment("ideas_generated_total", tags={
                        "detector": detector.name,
                        "idea_type": result.idea_type.value,
                    })
                    logger.info(
                        "idea_generated",
                        extra={
                            "ticker": symbol,
                            "detector": detector.name,
                            "idea_type": result.idea_type.value,
                            "signal_strength": result.signal_strength,
                            "confidence_score": result.confidence_score,
                        },
                    )
            except Exception as exc:
                get_collector().increment("detector_errors_total", tags={
                    "detector": detector.name,
                    "error_type": type(exc).__name__,
                })
                logger.warning(
                    "detector_error",
                    extra={
                        "ticker": symbol,
                        "detector": detector.name,
                        "error": str(exc),
                    },
                )

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
        composite_alpha: CompositeAlphaResult | None = None,
    ) -> IdeaCandidate:
        """Convert a DetectorResult into a full IdeaCandidate."""
        metadata = dict(result.metadata)

        # Enrich with CASE data if available
        if composite_alpha is not None:
            metadata["composite_alpha_score"] = composite_alpha.composite_alpha_score
            metadata["signal_environment"] = composite_alpha.signal_environment.value
            metadata["active_categories"] = composite_alpha.active_categories

        return IdeaCandidate(
            ticker=ticker,
            name=fundamental.name if fundamental else "",
            sector=fundamental.sector if fundamental else "",
            idea_type=result.idea_type,
            confidence=result.confidence,
            signal_strength=result.signal_strength,
            confidence_score=result.confidence_score,
            signals=result.signals,
            detector=result.detector,
            metadata=metadata,
        )

    @staticmethod
    def _compute_confidence(result: DetectorResult) -> float:
        """Heuristic confidence score from signal confirmation quality.

        Formula
        -------
        base = fired_strong / total_signals
        quality_bonus = strong_ratio * 0.2
        consistency_penalty = -0.1 if any weak signals present

        confidence = clamp(base + quality_bonus + consistency_penalty, 0, 1)
        """
        total = len(result.signals)
        if total == 0:
            return 0.0

        strong = sum(1 for s in result.signals if s.strength.value == "strong")
        moderate = sum(1 for s in result.signals if s.strength.value == "moderate")
        weak = sum(1 for s in result.signals if s.strength.value == "weak")

        # Base: ratio of confirming signals (strong + moderate weighted)
        base = (strong + moderate * 0.6) / total

        # Quality bonus for high strong ratio
        quality_bonus = (strong / total) * 0.2 if total > 0 else 0.0

        # Penalty for weak/conflicting signals
        consistency_penalty = -0.1 if weak > 0 else 0.0

        return max(0.0, min(1.0, base + quality_bonus + consistency_penalty))
