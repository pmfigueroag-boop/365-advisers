"""
src/engines/super_alpha/engine.py
──────────────────────────────────────────────────────────────────────────────
Super Alpha Engine — orchestrates all 8 quantitative factors into a single
Composite Alpha Score (CAS) with full explainability.

Architecture:
  4 new factors  → ValueFactor, MomentumFactor, QualityFactor, SizeFactor
  4 delegated    → AlphaVolatilityEngine, AlphaSentimentEngine,
                   AlphaMacroEngine, AlphaEventEngine

Composite Alpha Score (CAS) formula:
  CAS = Σ wᵢ·Fᵢ + volatility_adjustment + convergence_bonus

  Default Weights:
    Value=0.20, Momentum=0.15, Quality=0.20, Size=0.10,
    Sentiment=0.10, Macro=0.10, Event=0.10, Volatility=0.05

  Volatility adjustment: -5 per regime tier above Normal
  Convergence bonus: +5 when ≥6 factors score > 60
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.super_alpha.factors.value import ValueFactor
from src.engines.super_alpha.factors.momentum import MomentumFactor
from src.engines.super_alpha.factors.quality import QualityFactor
from src.engines.super_alpha.factors.size import SizeFactor
from src.engines.super_alpha.models import (
    AlphaTier,
    CompositeAlphaProfile,
    FactorExposure,
    FactorName,
    FactorScore,
    SuperAlphaRanking,
    VariableContribution,
)

# Delegate engines (existing)
from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
from src.engines.alpha_macro.engine import AlphaMacroEngine
from src.engines.alpha_event.engine import AlphaEventEngine

logger = logging.getLogger("365advisers.super_alpha.engine")

# ── Default factor weights (sum to 1.0 before vol adjustment) ─────────────────

DEFAULT_WEIGHTS = {
    FactorName.VALUE: 0.20,
    FactorName.MOMENTUM: 0.15,
    FactorName.QUALITY: 0.20,
    FactorName.SIZE: 0.10,
    FactorName.SENTIMENT: 0.10,
    FactorName.MACRO: 0.10,
    FactorName.EVENT: 0.10,
    FactorName.VOLATILITY: 0.05,
}
# NOTE: Weights intentionally sum to 0.95+0.05=1.0.
# The engine normalises weights at L256 to handle custom profiles
# that may not sum to 1.0.  Keeping VOL at 0.05 is intentional —
# volatility is an adjustment layer, not a directional alpha source.

_VOL_PENALTY_PER_TIER = 5.0
_CONVERGENCE_THRESHOLD = 60.0
_CONVERGENCE_MIN_FACTORS = 6
_CONVERGENCE_BONUS = 5.0


class SuperAlphaEngine:
    """
    8-factor Composite Alpha Score engine.

    Usage::

        engine = SuperAlphaEngine()
        profile = engine.score_asset("AAPL", asset_data)
        ranking = engine.rank_universe([("AAPL", data1), ("MSFT", data2)])
    """

    def __init__(
        self,
        weights: dict[FactorName, float] | None = None,
    ) -> None:
        self._weights = weights or DEFAULT_WEIGHTS.copy()

        # New factor engines
        self._value = ValueFactor()
        self._momentum = MomentumFactor()
        self._quality = QualityFactor()
        self._size = SizeFactor()

        # Delegate engines (existing)
        self._volatility = AlphaVolatilityEngine()
        self._sentiment = AlphaSentimentEngine()
        self._macro = AlphaMacroEngine()
        self._event = AlphaEventEngine()

    # ── Public API ────────────────────────────────────────────────────────

    def score_asset(self, ticker: str, data: dict) -> CompositeAlphaProfile:
        """
        Compute full 8-factor profile for a single asset.

        Parameters
        ----------
        ticker : str
        data : dict
            Combined data dict with keys for all factors:
            - Value: pe_ratio, ev_to_ebitda, pb_ratio, fcf_yield
            - Momentum: return_3m, return_6m, return_12m, price_to_sma200
            - Quality: roic, operating_margin, earnings_stability, debt_to_equity
            - Size: market_cap, avg_daily_volume_usd
            - Volatility: vix_current, iv_rank, realized_vol, iv_current, ...
            - Sentiment: bullish_pct, bearish_pct, message_volume_24h, ...
            - Macro: gdp_growth, inflation, unemployment, ...
            - Event: events (list[dict])
        """
        # Score all 8 factors
        value_score = self._value.score(data)
        momentum_score = self._momentum.score(data)
        quality_score = self._quality.score(data)
        size_score = self._size.score(data)
        volatility_score = self._score_volatility(data)
        sentiment_score = self._score_sentiment(ticker, data)
        macro_score = self._score_macro(data)
        event_score = self._score_event(ticker, data)

        factor_scores = {
            FactorName.VALUE: value_score,
            FactorName.MOMENTUM: momentum_score,
            FactorName.QUALITY: quality_score,
            FactorName.SIZE: size_score,
            FactorName.VOLATILITY: volatility_score,
            FactorName.SENTIMENT: sentiment_score,
            FactorName.MACRO: macro_score,
            FactorName.EVENT: event_score,
        }

        # Compute Composite Alpha Score
        cas, vol_adj, conv_bonus, agreement = self._compute_composite(factor_scores)

        # Classify tier
        tier = self._classify_tier(cas)

        # Top drivers
        top_drivers = self._identify_top_drivers(factor_scores)

        return CompositeAlphaProfile(
            ticker=ticker,
            composite_alpha_score=round(cas, 1),
            tier=tier,
            value=value_score,
            momentum=momentum_score,
            quality=quality_score,
            size=size_score,
            volatility=volatility_score,
            sentiment=sentiment_score,
            macro=macro_score,
            event=event_score,
            convergence_bonus=round(conv_bonus, 1),
            volatility_adjustment=round(vol_adj, 1),
            factor_agreement=agreement,
            top_drivers=top_drivers,
        )

    def rank_universe(
        self,
        assets: list[tuple[str, dict]],
    ) -> SuperAlphaRanking:
        """
        Score and rank multiple assets.

        Parameters
        ----------
        assets : list[tuple[str, dict]]
            List of (ticker, data_dict) tuples.
        """
        profiles = [self.score_asset(ticker, data) for ticker, data in assets]

        # Sort by CAS descending
        profiles.sort(key=lambda p: p.composite_alpha_score, reverse=True)

        # Assign ranks and percentiles
        n = len(profiles)
        for i, p in enumerate(profiles):
            p.rank = i + 1
            p.percentile = round((1 - i / max(n, 1)) * 100, 1) if n > 0 else 50.0

        top = [p.ticker for p in profiles if p.tier in (AlphaTier.ALPHA_ELITE, AlphaTier.STRONG_ALPHA)][:10]
        bottom = [p.ticker for p in profiles if p.tier in (AlphaTier.WEAK, AlphaTier.AVOID)][:5]

        # Determine market regime from macro
        regime = "unknown"
        if profiles:
            macro_scores = [p.macro.score for p in profiles]
            avg_macro = sum(macro_scores) / len(macro_scores) if macro_scores else 50
            if avg_macro > 65:
                regime = "expansion"
            elif avg_macro > 45:
                regime = "neutral"
            elif avg_macro > 30:
                regime = "slowdown"
            else:
                regime = "contraction"

        return SuperAlphaRanking(
            rankings=profiles,
            universe_size=n,
            top_alpha=top,
            bottom_alpha=bottom,
            market_regime=regime,
        )

    def get_factor_exposures(
        self,
        profiles: list[CompositeAlphaProfile],
    ) -> list[FactorExposure]:
        """Build radar-chart-ready factor exposure data."""
        return [
            FactorExposure(
                ticker=p.ticker,
                exposures={
                    "Value": p.value.score,
                    "Momentum": p.momentum.score,
                    "Quality": p.quality.score,
                    "Size": p.size.score,
                    "Volatility": p.volatility.score,
                    "Sentiment": p.sentiment.score,
                    "Macro": p.macro.score,
                    "Event": p.event.score,
                },
            )
            for p in profiles
        ]

    # ── Composite Calculation ─────────────────────────────────────────────

    def _compute_composite(
        self,
        factors: dict[FactorName, FactorScore],
    ) -> tuple[float, float, float, int]:
        """
        CAS = Σ wᵢ·Fᵢ + vol_adjustment + convergence_bonus

        Returns: (cas, vol_adjustment, convergence_bonus, factor_agreement)
        """
        weighted_sum = 0.0
        total_weight = 0.0

        for name, score in factors.items():
            w = self._weights.get(name, 0.0)
            weighted_sum += w * score.score
            total_weight += w

        # Normalize if weights don't exactly sum to 1
        if total_weight > 0 and abs(total_weight - 1.0) > 0.01:
            weighted_sum = weighted_sum / total_weight

        # Volatility adjustment
        vol_score = factors.get(FactorName.VOLATILITY)
        vol_adjustment = 0.0
        if vol_score:
            # Higher vol score = lower risk (already inverted in adapter)
            # Penalize when vol score is very low (high risk)
            if vol_score.score < 30:
                vol_adjustment = -_VOL_PENALTY_PER_TIER * 2
            elif vol_score.score < 40:
                vol_adjustment = -_VOL_PENALTY_PER_TIER

        # Convergence bonus
        agreement = sum(1 for s in factors.values() if s.score >= _CONVERGENCE_THRESHOLD)
        convergence_bonus = _CONVERGENCE_BONUS if agreement >= _CONVERGENCE_MIN_FACTORS else 0.0

        cas = min(max(weighted_sum + vol_adjustment + convergence_bonus, 0), 100)
        return cas, vol_adjustment, convergence_bonus, agreement

    # ── Delegated Factor Adapters ─────────────────────────────────────────

    def _score_volatility(self, data: dict) -> FactorScore:
        """Adapt AlphaVolatilityEngine output to FactorScore."""
        try:
            dashboard = self._volatility.analyze(data)
            # composite_risk is 0–100 where higher = more risk
            # Invert: 100 - risk = "stability score"
            stability = 100.0 - dashboard.score.composite_risk
            signals = dashboard.score.signals or []
            variables = [
                VariableContribution(
                    name="VIX Level", raw_value=dashboard.score.vix_level,
                    weight=0.4,
                ),
                VariableContribution(
                    name="IV Rank", raw_value=dashboard.score.iv_rank,
                    weight=0.3,
                ),
                VariableContribution(
                    name="Regime", raw_value=None,
                    weight=0.3,
                ),
            ]
        except Exception as exc:
            logger.warning(f"Volatility engine error: {exc}")
            stability = 50.0
            signals = []
            variables = []

        return FactorScore(
            factor=FactorName.VOLATILITY,
            score=round(min(max(stability, 0), 100), 1),
            variables=variables,
            signals=signals[:3],
        )

    def _score_sentiment(self, ticker: str, data: dict) -> FactorScore:
        """Adapt AlphaSentimentEngine output to FactorScore."""
        try:
            result = self._sentiment.analyze(ticker, data)
            # composite_score is -100 to +100 → rescale to 0–100
            score_0_100 = (result.composite_score + 100) / 2.0
            variables = [
                VariableContribution(
                    name="Polarity", raw_value=result.polarity, weight=0.4,
                ),
                VariableContribution(
                    name="Mention Volume", raw_value=float(result.mention_volume),
                    weight=0.3,
                ),
                VariableContribution(
                    name="Momentum of Attention",
                    raw_value=result.momentum_of_attention, weight=0.3,
                ),
            ]
            signals = result.signals or []
        except Exception as exc:
            logger.warning(f"Sentiment engine error: {exc}")
            score_0_100 = 50.0
            variables = []
            signals = []

        return FactorScore(
            factor=FactorName.SENTIMENT,
            score=round(min(max(score_0_100, 0), 100), 1),
            variables=variables,
            signals=signals[:3],
        )

    def _score_macro(self, data: dict) -> FactorScore:
        """Adapt AlphaMacroEngine output to FactorScore."""
        try:
            dashboard = self._macro.analyze(data)
            score = dashboard.score.composite_score
            signals = dashboard.score.signals or []
            variables = [
                VariableContribution(
                    name="Regime",
                    raw_value=None,
                    weight=0.5,
                ),
                VariableContribution(
                    name="Composite Score",
                    raw_value=score,
                    weight=0.5,
                ),
            ]
        except Exception as exc:
            logger.warning(f"Macro engine error: {exc}")
            score = 50.0
            variables = []
            signals = []

        return FactorScore(
            factor=FactorName.MACRO,
            score=round(min(max(score, 0), 100), 1),
            variables=variables,
            signals=signals[:3],
        )

    def _score_event(self, ticker: str, data: dict) -> FactorScore:
        """Adapt AlphaEventEngine output to FactorScore."""
        try:
            raw_events = data.get("events", [])
            detected = self._event.detect_events(ticker, raw_events)
            event_score = self._event.score_ticker(ticker, detected)
            # composite_score is -100 to +100 → rescale to 0–100
            score_0_100 = (event_score.composite_score + 100) / 2.0
            signals = event_score.signals or []
            variables = [
                VariableContribution(
                    name="Event Count",
                    raw_value=float(event_score.event_count),
                    weight=0.3,
                ),
                VariableContribution(
                    name="Bullish Events",
                    raw_value=float(event_score.bullish_events),
                    weight=0.35,
                ),
                VariableContribution(
                    name="Bearish Events",
                    raw_value=float(event_score.bearish_events),
                    weight=0.35,
                ),
            ]
        except Exception as exc:
            logger.warning(f"Event engine error: {exc}")
            score_0_100 = 50.0
            variables = []
            signals = []

        return FactorScore(
            factor=FactorName.EVENT,
            score=round(min(max(score_0_100, 0), 100), 1),
            variables=variables,
            signals=signals[:3],
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _classify_tier(cas: float) -> AlphaTier:
        if cas >= 85:
            return AlphaTier.ALPHA_ELITE
        if cas >= 70:
            return AlphaTier.STRONG_ALPHA
        if cas >= 55:
            return AlphaTier.MODERATE_ALPHA
        if cas >= 40:
            return AlphaTier.NEUTRAL
        if cas >= 25:
            return AlphaTier.WEAK
        return AlphaTier.AVOID

    @staticmethod
    def _identify_top_drivers(
        factors: dict[FactorName, FactorScore],
    ) -> list[str]:
        """Identify the top 3 factor contributors."""
        # Sort by score descending
        sorted_factors = sorted(
            factors.items(), key=lambda kv: kv[1].score, reverse=True,
        )
        drivers = []
        for name, score in sorted_factors[:3]:
            label = name.value.capitalize()
            if score.score >= 70:
                drivers.append(f"Strong {label} ({score.score:.0f})")
            elif score.score >= 50:
                drivers.append(f"Positive {label} ({score.score:.0f})")
            else:
                drivers.append(f"{label} ({score.score:.0f})")
        return drivers
