"""
src/engines/investment_brain/risk_detector.py
──────────────────────────────────────────────────────────────────────────────
Risk Detector — synthesises risk signals from all engines into prioritised
alerts with full traceability.

Detects: bubble signals, systemic risk, sector overheating, liquidity stress,
         drawdown warnings, correlation spikes.

Consumes: volatility data, macro data, alpha rankings, sentiment scores.
Output:   list[RiskAlert] ordered by severity.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.investment_brain.models import (
    RiskAlert,
    RiskAlertSeverity,
    RiskAlertType,
)

logger = logging.getLogger("365advisers.investment_brain.risk_detector")


class RiskDetector:
    """
    Synthesises cross-engine data into prioritised risk alerts.

    Usage::

        detector = RiskDetector()
        alerts = detector.detect(vol_data, macro_data, alpha_profiles, sentiment_scores)
    """

    def detect(
        self,
        vol_data: dict | None = None,
        macro_data: dict | None = None,
        alpha_profiles: list[dict] | None = None,
        sentiment_scores: list[dict] | None = None,
    ) -> list[RiskAlert]:
        """
        Detect market risks from cross-engine signals.

        Parameters
        ----------
        vol_data : dict | None
            Volatility data: vix_current, iv_rank, term_structure_slope,
            put_call_ratio, realized_vol
        macro_data : dict | None
            Macro indicators: gdp_growth, inflation, unemployment,
            interest_rate, credit_spread, yield_curve_spread
        alpha_profiles : list[dict] | None
            SuperAlpha profiles with composite scores and sectors
        sentiment_scores : list[dict] | None
            Sentiment data with composite_score, regime, polarity
        """
        vol = vol_data or {}
        macro = macro_data or {}
        profiles = alpha_profiles or []
        sentiments = sentiment_scores or []

        alerts: list[RiskAlert] = []

        alerts.extend(self._detect_volatility_risks(vol))
        alerts.extend(self._detect_macro_stress(macro))
        alerts.extend(self._detect_bubble_signals(profiles, sentiments))
        alerts.extend(self._detect_sector_overheating(profiles))
        alerts.extend(self._detect_liquidity_stress(macro, vol))
        alerts.extend(self._detect_correlation_risks(profiles))

        # Sort by severity (critical first)
        severity_order = {
            RiskAlertSeverity.CRITICAL: 0,
            RiskAlertSeverity.HIGH: 1,
            RiskAlertSeverity.MODERATE: 2,
            RiskAlertSeverity.LOW: 3,
        }
        alerts.sort(key=lambda a: severity_order.get(a.severity, 4))

        return alerts

    # ── Volatility risks ─────────────────────────────────────────────────

    def _detect_volatility_risks(self, vol: dict) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        vix = _f(vol.get("vix_current"))
        iv_rank = _f(vol.get("iv_rank"))
        slope = _f(vol.get("term_structure_slope"))
        pcr = _f(vol.get("put_call_ratio"))

        if vix is not None and vix > 35:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.SYSTEMIC_RISK,
                severity=RiskAlertSeverity.CRITICAL,
                title="Extreme Volatility Regime",
                description=f"VIX at {vix:.1f} indicates extreme market stress. Historical drawdowns of 15-30% are common at these levels.",
                metrics={"vix": vix},
                source_signals=[f"VIX={vix:.1f}", "Extreme regime"],
            ))
        elif vix is not None and vix > 25:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.DRAWDOWN_WARNING,
                severity=RiskAlertSeverity.HIGH,
                title="Elevated Volatility Warning",
                description=f"VIX at {vix:.1f} signals elevated risk. Consider reducing exposure or hedging.",
                metrics={"vix": vix},
                source_signals=[f"VIX={vix:.1f}"],
            ))

        if slope is not None and slope < -0.5:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.SYSTEMIC_RISK,
                severity=RiskAlertSeverity.HIGH,
                title="Volatility Term Structure Inversion",
                description="The VIX term structure is inverted, indicating near-term stress expectations exceeding long-term levels.",
                metrics={"term_structure_slope": slope},
                source_signals=["Term structure inversion"],
            ))

        if pcr is not None and pcr > 1.5:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.DRAWDOWN_WARNING,
                severity=RiskAlertSeverity.MODERATE,
                title="Elevated Put/Call Ratio",
                description=f"Put/Call ratio at {pcr:.2f} suggests heavy hedging activity or bearish positioning.",
                metrics={"put_call_ratio": pcr},
                source_signals=[f"PCR={pcr:.2f}"],
            ))

        return alerts

    # ── Macro stress ─────────────────────────────────────────────────────

    def _detect_macro_stress(self, macro: dict) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        gdp = _f(macro.get("gdp_growth"))
        inflation = _f(macro.get("inflation"))
        unemployment = _f(macro.get("unemployment"))
        credit_spread = _f(macro.get("credit_spread"))
        yield_curve = _f(macro.get("yield_curve_spread"))

        # Stagflation risk
        if gdp is not None and inflation is not None:
            if gdp < 1.0 and inflation > 4.0:
                alerts.append(RiskAlert(
                    alert_type=RiskAlertType.SYSTEMIC_RISK,
                    severity=RiskAlertSeverity.CRITICAL,
                    title="Stagflation Risk",
                    description=f"GDP growth at {gdp:.1f}% with inflation at {inflation:.1f}% — stagflation conditions.",
                    metrics={"gdp_growth": gdp, "inflation": inflation},
                    source_signals=["Low GDP + High CPI"],
                ))

        # Yield curve inversion
        if yield_curve is not None and yield_curve < -0.5:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.SYSTEMIC_RISK,
                severity=RiskAlertSeverity.HIGH,
                title="Yield Curve Inversion",
                description=f"Yield curve spread at {yield_curve:.2f}% — historically precedes recessions by 6-18 months.",
                metrics={"yield_curve_spread": yield_curve},
                source_signals=["Inverted yield curve"],
            ))

        # Credit stress
        if credit_spread is not None and credit_spread > 4.0:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.LIQUIDITY_STRESS,
                severity=RiskAlertSeverity.HIGH,
                title="Credit Spread Widening",
                description=f"Credit spreads at {credit_spread:.1f}% indicate deteriorating credit conditions.",
                metrics={"credit_spread": credit_spread},
                source_signals=[f"Credit spread={credit_spread:.1f}%"],
            ))

        # Rising unemployment
        if unemployment is not None and unemployment > 6.0:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.SYSTEMIC_RISK,
                severity=RiskAlertSeverity.MODERATE,
                title="Rising Unemployment",
                description=f"Unemployment at {unemployment:.1f}% signals labor market deterioration.",
                metrics={"unemployment": unemployment},
                source_signals=[f"Unemployment={unemployment:.1f}%"],
            ))

        return alerts

    # ── Bubble signals ───────────────────────────────────────────────────

    def _detect_bubble_signals(
        self,
        profiles: list[dict],
        sentiments: list[dict],
    ) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        if not profiles:
            return alerts

        # Extreme alpha concentration — too many assets at very high scores
        high_alpha = [p for p in profiles if (_f(p.get("composite_alpha_score")) or 0) > 80]
        if len(high_alpha) > len(profiles) * 0.4 and len(profiles) > 5:
            tickers = [p.get("ticker", "") for p in high_alpha[:5]]
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.BUBBLE_SIGNAL,
                severity=RiskAlertSeverity.HIGH,
                title="Alpha Concentration Warning",
                description=f"{len(high_alpha)} of {len(profiles)} assets ({len(high_alpha)/len(profiles)*100:.0f}%) have alpha scores >80. This level of concentration often precedes mean-reversion.",
                affected_tickers=tickers,
                metrics={"high_alpha_count": len(high_alpha), "universe_size": len(profiles)},
                source_signals=["Extreme alpha score clustering"],
            ))

        # Euphoric sentiment across multiple assets
        sentiment_map = {s.get("ticker", ""): s for s in sentiments}
        euphoric = [
            s for s in sentiments
            if (_f(s.get("composite_score")) or 0) > 60
        ]
        if len(euphoric) > len(sentiments) * 0.5 and len(sentiments) > 3:
            tickers = [s.get("ticker", "") for s in euphoric[:5]]
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.BUBBLE_SIGNAL,
                severity=RiskAlertSeverity.MODERATE,
                title="Broad Euphoric Sentiment",
                description=f"{len(euphoric)} assets showing euphoric sentiment — contrarian caution warranted.",
                affected_tickers=tickers,
                metrics={"euphoric_count": len(euphoric)},
                source_signals=["Broad euphoria detection"],
            ))

        return alerts

    # ── Sector overheating ───────────────────────────────────────────────

    def _detect_sector_overheating(self, profiles: list[dict]) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        if not profiles:
            return alerts

        # Group by sector
        sector_scores: dict[str, list[float]] = {}
        sector_tickers: dict[str, list[str]] = {}
        for p in profiles:
            sector = p.get("sector", "Unknown")
            score = _f(p.get("composite_alpha_score")) or 0
            ticker = p.get("ticker", "")
            sector_scores.setdefault(sector, []).append(score)
            sector_tickers.setdefault(sector, []).append(ticker)

        for sector, scores in sector_scores.items():
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            count_high = sum(1 for s in scores if s > 70)

            if avg > 70 and count_high >= 3:
                alerts.append(RiskAlert(
                    alert_type=RiskAlertType.SECTOR_OVERHEATING,
                    severity=RiskAlertSeverity.MODERATE,
                    title=f"{sector} Sector Overheating",
                    description=f"{sector} has {count_high} high-alpha assets (avg score {avg:.0f}). Concentrated momentum increases sector-specific drawdown risk.",
                    affected_tickers=sector_tickers.get(sector, [])[:5],
                    metrics={"sector_avg_alpha": round(avg, 1), "high_alpha_count": count_high},
                    source_signals=[f"{sector} concentration"],
                ))

        return alerts

    # ── Liquidity stress ─────────────────────────────────────────────────

    def _detect_liquidity_stress(self, macro: dict, vol: dict) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        credit_spread = _f(macro.get("credit_spread"))
        m2_growth = _f(macro.get("m2_growth"))
        vix = _f(vol.get("vix_current"))

        stress_count = 0
        metrics: dict[str, float] = {}
        signals: list[str] = []

        if credit_spread is not None and credit_spread > 3.0:
            stress_count += 1
            metrics["credit_spread"] = credit_spread
            signals.append(f"Credit spread={credit_spread:.1f}%")

        if m2_growth is not None and m2_growth < -2.0:
            stress_count += 1
            metrics["m2_growth"] = m2_growth
            signals.append(f"M2 contraction={m2_growth:.1f}%")

        if vix is not None and vix > 25:
            stress_count += 1
            metrics["vix"] = vix
            signals.append(f"VIX={vix:.1f}")

        if stress_count >= 2:
            severity = RiskAlertSeverity.HIGH if stress_count >= 3 else RiskAlertSeverity.MODERATE
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.LIQUIDITY_STRESS,
                severity=severity,
                title="Liquidity Stress Detected",
                description=f"Multiple liquidity stress indicators detected ({stress_count}/3). Market liquidity may be deteriorating.",
                metrics=metrics,
                source_signals=signals,
            ))

        return alerts

    # ── Correlation risks ────────────────────────────────────────────────

    def _detect_correlation_risks(self, profiles: list[dict]) -> list[RiskAlert]:
        """Detect when too many assets are moving in sync (high correlation proxy)."""
        alerts: list[RiskAlert] = []
        if len(profiles) < 5:
            return alerts

        scores = [_f(p.get("composite_alpha_score")) or 50 for p in profiles]
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)

        # Low variance = highly correlated moves
        if variance < 50 and len(profiles) > 8:
            alerts.append(RiskAlert(
                alert_type=RiskAlertType.CORRELATION_SPIKE,
                severity=RiskAlertSeverity.MODERATE,
                title="Cross-Asset Correlation Spike",
                description=f"Alpha scores showing low dispersion (variance={variance:.1f}). Assets moving in sync reduces diversification benefits.",
                metrics={"score_variance": round(variance, 1), "asset_count": len(profiles)},
                source_signals=["Low alpha score dispersion"],
            ))

        return alerts


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
