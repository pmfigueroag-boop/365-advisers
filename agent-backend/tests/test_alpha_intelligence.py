"""
tests/test_alpha_intelligence.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Alpha Decision Intelligence Platform.
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ALPHA FUNDAMENTAL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlphaFundamental:

    def test_analyze_with_strong_ratios(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        result = e.analyze("AAPL", ratios={
            "pe_ratio": 15, "roe": 0.25, "roic": 0.22,
            "gross_margin": 0.65, "operating_margin": 0.30,
            "current_ratio": 2.5, "debt_to_equity": 0.4,
        }, growth_data={"revenue_growth_yoy": 0.20, "earnings_growth_yoy": 0.18})
        assert result.ticker == "AAPL"
        assert result.composite_score > 50
        assert result.grade.value in ("A+", "A", "B")
        assert len(result.top_signals) > 0

    def test_analyze_with_weak_ratios(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        result = e.analyze("WEAK", ratios={
            "pe_ratio": 60, "roe": 0.02, "debt_to_equity": 3.0,
            "current_ratio": 0.7,
        })
        assert result.composite_score < 55
        assert result.grade.value in ("C", "D", "F")

    def test_analyze_empty_data(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        result = e.analyze("EMPTY")
        assert result.composite_score >= 0
        assert result.ticker == "EMPTY"

    def test_rank(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        s1 = e.analyze("HIGH", ratios={"roe": 0.30, "roic": 0.25, "gross_margin": 0.70}, growth_data={"revenue_growth_yoy": 0.35})
        s2 = e.analyze("LOW", ratios={"roe": 0.02})
        ranking = e.rank([s1, s2])
        assert ranking.rankings[0].ticker == "HIGH"
        assert ranking.total_analyzed == 2

    def test_score_range(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        r = e.analyze("TEST", ratios={"pe_ratio": 5, "roe": 0.5, "roic": 0.5, "gross_margin": 0.9, "operating_margin": 0.5, "current_ratio": 5, "debt_to_equity": 0.1}, growth_data={"revenue_growth_yoy": 0.5, "earnings_growth_yoy": 0.5, "fcf_growth_yoy": 0.3})
        assert 0 <= r.composite_score <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ALPHA MACRO ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlphaMacro:

    def test_expansion_regime(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        d = e.analyze({"gdp_growth": 4.0, "unemployment": 3.5, "pmi": 58, "yield_curve_spread": 1.5})
        assert d.score.regime.value == "expansion"
        assert d.allocation.equities_tilt > 0

    def test_recession_regime(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        d = e.analyze({"gdp_growth": -1.0, "unemployment": 8.0, "yield_curve_spread": -0.5, "pmi": 42})
        assert d.score.regime.value == "recession"
        assert d.allocation.equities_tilt < 0
        assert d.allocation.cash_tilt > 0

    def test_signals_generated(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        d = e.analyze({"gdp_growth": 3.0, "inflation": 2.5})
        assert len(d.score.signals) > 0

    def test_empty_indicators(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        d = e.analyze({})
        assert d.score.regime is not None

    def test_risk_identification(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        d = e.analyze({"inflation": 7.0, "yield_curve_spread": -0.3, "unemployment": 7.0})
        assert len(d.key_risks) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ALPHA SENTIMENT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlphaSentiment:

    def test_bullish_sentiment(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        r = e.analyze("AAPL", {"bullish_pct": 80, "bearish_pct": 20, "message_volume_24h": 500, "message_volume_7d": 2000})
        assert r.composite_score > 0
        assert r.polarity > 0

    def test_bearish_sentiment(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        r = e.analyze("BEAR", {"bullish_pct": 15, "bearish_pct": 85, "message_volume_24h": 300, "message_volume_7d": 1500})
        assert r.composite_score < 0
        assert r.polarity < 0

    def test_hype_detection(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        hype = e.detect_hype("MEME", {"bullish_pct": 85, "message_volume_24h": 5000, "avg_volume_30d": 500})
        assert hype is not None
        assert hype.severity in ("moderate", "high", "extreme")

    def test_panic_detection(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        panic = e.detect_panic("CRASH", {"bearish_pct": 90, "message_volume_24h": 3000, "avg_volume_30d": 400})
        assert panic is not None

    def test_dashboard(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        s1 = e.analyze("A", {"bullish_pct": 70, "bearish_pct": 30, "message_volume_24h": 100})
        s2 = e.analyze("B", {"bullish_pct": 40, "bearish_pct": 60, "message_volume_24h": 200})
        dash = e.build_dashboard([s1, s2])
        assert len(dash.scores) == 2
        assert len(dash.top_trending) <= 10

    def test_score_range(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        r = e.analyze("T", {"bullish_pct": 100, "bearish_pct": 0, "message_volume_24h": 10000, "avg_volume_30d": 100, "news_count": 50})
        assert -100 <= r.composite_score <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ALPHA VOLATILITY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlphaVolatility:

    def test_low_vol_regime(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 12.0, "iv_rank": 20})
        assert d.score.regime.value == "low"
        assert d.score.composite_risk < 40

    def test_extreme_vol_regime(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 35.0, "iv_rank": 95})
        assert d.score.regime.value == "extreme"
        assert d.score.composite_risk > 70
        assert any(s.signal_type == "regime_shift" for s in d.signals)

    def test_term_structure(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 25.0, "term_structure_slope": -1.0})
        assert d.score.term_structure == "backwardation"

    def test_iv_rv_spread(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 20.0, "iv_current": 30.0, "realized_vol": 15.0})
        assert d.score.iv_rv_spread == 15.0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ALPHA EVENT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlphaEvent:

    def test_detect_events(self):
        from src.engines.alpha_event.engine import AlphaEventEngine
        e = AlphaEventEngine()
        events = e.detect_events("AAPL", [
            {"event_type": "earnings_beat", "headline": "AAPL beats Q3", "severity": "high"},
            {"event_type": "insider_buy", "headline": "CEO buys 10K shares"},
        ])
        assert len(events) == 2
        assert events[0].ticker == "AAPL"

    def test_score_bullish_events(self):
        from src.engines.alpha_event.engine import AlphaEventEngine
        e = AlphaEventEngine()
        events = e.detect_events("AAPL", [
            {"event_type": "earnings_beat", "headline": "Beat", "severity": "high"},
            {"event_type": "buyback", "headline": "$5B buyback"},
        ])
        score = e.score_ticker("AAPL", events)
        assert score.composite_score > 0
        assert score.bullish_events == 2

    def test_score_bearish_events(self):
        from src.engines.alpha_event.engine import AlphaEventEngine
        e = AlphaEventEngine()
        events = e.detect_events("BAD", [
            {"event_type": "earnings_miss", "headline": "Miss", "severity": "critical"},
            {"event_type": "regulatory_action", "headline": "SEC investigation", "severity": "critical"},
        ])
        score = e.score_ticker("BAD", events)
        assert score.composite_score < 0
        assert score.bearish_events == 2

    def test_insider_clustering(self):
        from src.engines.alpha_event.engine import AlphaEventEngine
        e = AlphaEventEngine()
        events = e.detect_events("CLU", [
            {"event_type": "insider_buy", "headline": "Buy 1"},
            {"event_type": "insider_buy", "headline": "Buy 2"},
            {"event_type": "insider_buy", "headline": "Buy 3"},
        ])
        score = e.score_ticker("CLU", events)
        assert any("cluster" in s.lower() for s in score.signals)

    def test_empty_events(self):
        from src.engines.alpha_event.engine import AlphaEventEngine
        e = AlphaEventEngine()
        score = e.score_ticker("EMPTY", [])
        assert score.event_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. MULTI-STRATEGY ALPHA ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiStrategy:

    def test_rank_multiple_tickers(self):
        from src.engines.alpha_multi.engine import MultiStrategyAlphaEngine
        e = MultiStrategyAlphaEngine()
        result = e.rank([
            {"ticker": "GOOD", "fundamental": 85, "macro": 70, "sentiment": 60, "volatility_risk": 20, "event": 50},
            {"ticker": "BAD", "fundamental": 30, "macro": 40, "sentiment": -60, "volatility_risk": 80, "event": -40},
        ])
        assert result.rankings[0].ticker == "GOOD"
        assert result.rankings[0].composite_alpha > result.rankings[1].composite_alpha
        assert result.total_analyzed == 2

    def test_convergence_bonus(self):
        from src.engines.alpha_multi.engine import MultiStrategyAlphaEngine
        e = MultiStrategyAlphaEngine()
        result = e.rank([
            {"ticker": "CONV", "fundamental": 80, "macro": 75, "sentiment": 70, "volatility_risk": 15, "event": 65},
        ])
        assert result.rankings[0].engines_bullish >= 4
        assert result.rankings[0].convergence_bonus > 0

    def test_conviction_classification(self):
        from src.engines.alpha_multi.engine import MultiStrategyAlphaEngine
        e = MultiStrategyAlphaEngine()
        result = e.rank([
            {"ticker": "SB", "fundamental": 95, "macro": 85, "sentiment": 80, "volatility_risk": 10, "event": 75},
        ])
        assert result.rankings[0].conviction.value == "strong_buy"

    def test_heatmap_generated(self):
        from src.engines.alpha_multi.engine import MultiStrategyAlphaEngine
        e = MultiStrategyAlphaEngine()
        result = e.rank([{"ticker": "A", "fundamental": 50, "macro": 50, "sentiment": 0, "volatility_risk": 50, "event": 0}])
        assert len(result.heatmap) == 1
        assert result.heatmap[0].ticker == "A"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ALERT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlertEngine:

    def test_macro_recession_alert(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        from src.engines.alpha_macro.models import MacroScore, MacroRegime
        e = AlertEngine()
        ms = MacroScore(regime=MacroRegime.RECESSION, regime_confidence=0.7, composite_score=15)
        stream = e.evaluate(macro_score=ms)
        assert stream.total_critical >= 1
        assert any(a.alert_type.value == "regime_change" for a in stream.alerts)

    def test_vol_extreme_alert(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        from src.engines.alpha_volatility.models import VolScore, VolRegime
        e = AlertEngine()
        vs = VolScore(regime=VolRegime.EXTREME, vix_level=40, composite_risk=90)
        stream = e.evaluate(vol_score=vs)
        assert stream.total_critical >= 1

    def test_sentiment_panic_alert(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        from src.engines.alpha_sentiment.models import SentimentScoreResult, SentimentRegime
        e = AlertEngine()
        s = SentimentScoreResult(ticker="PANIC", composite_score=-80, regime=SentimentRegime.PANIC, polarity=-0.8)
        stream = e.evaluate(sentiments=[s])
        assert any(a.alert_type.value == "sentiment_panic" for a in stream.alerts)

    def test_fundamental_breakout_alert(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        from src.engines.alpha_fundamental.models import FundamentalScore, FundamentalGrade
        e = AlertEngine()
        fs = FundamentalScore(ticker="STAR", composite_score=90, grade=FundamentalGrade.A_PLUS)
        stream = e.evaluate(fundamentals=[fs])
        assert any(a.alert_type.value == "fundamental_breakout" for a in stream.alerts)

    def test_event_alert(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        from src.engines.alpha_event.models import EventScore, DetectedEvent, EventType, EventSeverity
        e = AlertEngine()
        ev = DetectedEvent(event_type=EventType.MERGER, ticker="TGT", headline="Major acquisition", impact_score=80)
        es = EventScore(ticker="TGT", composite_score=80, most_significant=ev)
        stream = e.evaluate(events=[es])
        assert any(a.alert_type.value == "event_signal" for a in stream.alerts)

    def test_empty_evaluation(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        e = AlertEngine()
        stream = e.evaluate()
        assert len(stream.alerts) == 0

    def test_alert_sorting(self):
        from src.engines.alpha_alerts.engine import AlertEngine
        from src.engines.alpha_volatility.models import VolScore, VolRegime
        from src.engines.alpha_macro.models import MacroScore, MacroRegime
        e = AlertEngine()
        ms = MacroScore(regime=MacroRegime.RECESSION, regime_confidence=0.8, composite_score=10)
        vs = VolScore(regime=VolRegime.ELEVATED, vix_level=25, composite_risk=60)
        stream = e.evaluate(macro_score=ms, vol_score=vs)
        # Critical alerts should come first
        if len(stream.alerts) >= 2:
            assert stream.alerts[0].severity.value in ("critical", "high")
