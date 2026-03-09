"""
src/engines/pilot/alerts.py
─────────────────────────────────────────────────────────────────────────────
PilotAlertEvaluator — evaluates 9 pilot-specific alert conditions
and produces PilotAlert instances with recommended actions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from .config import AlertThresholds
from .models import (
    PilotAlert,
    PilotAlertSeverity,
    PilotAlertType,
    PilotDailySnapshot,
)

logger = logging.getLogger("365advisers.pilot.alerts")


class PilotAlertEvaluator:
    """
    Evaluates pilot-specific alert conditions against current metrics
    and snapshots.  Returns a list of PilotAlert instances.
    """

    def __init__(self, pilot_id: str):
        self.pilot_id = pilot_id
        self.thresholds = AlertThresholds()

    # ── Public API ──────────────────────────────────────────────────────

    def evaluate_all(
        self,
        signal_hit_rates: dict[str, float],
        strategy_drawdowns: dict[str, float],
        portfolio_volatilities: dict[str, float],
        data_last_updated: datetime | None,
        case_expired_ratio: float,
        portfolio_correlations: dict[str, float],
        current_regime: str,
        previous_regime: str | None = None,
    ) -> list[PilotAlert]:
        """
        Run all 9 alert checks and return any alerts that fire.

        Args:
            signal_hit_rates: {category: hit_rate_20d} for each signal category
            strategy_drawdowns: {strategy_id: current_drawdown} (negative values)
            portfolio_volatilities: {portfolio_id: annualised_vol_5d}
            data_last_updated: timestamp of last data refresh
            case_expired_ratio: fraction of signals in "Expired" state
            portfolio_correlations: {portfolio_id: intra_portfolio_corr}
            current_regime: current detected regime ("bull", "bear", "range")
            previous_regime: previous regime for change detection
        """
        alerts: list[PilotAlert] = []

        alerts.extend(self._check_signal_degradation(signal_hit_rates))
        alerts.extend(self._check_strategy_drawdown(strategy_drawdowns))
        alerts.extend(self._check_portfolio_volatility(portfolio_volatilities))
        alerts.extend(self._check_data_staleness(data_last_updated))
        alerts.extend(self._check_case_collapse(case_expired_ratio))
        alerts.extend(self._check_correlation_spike(portfolio_correlations))
        alerts.extend(self._check_regime_change(current_regime, previous_regime))

        if alerts:
            logger.info(
                "Pilot alert evaluation produced %d alerts (%d critical)",
                len(alerts),
                sum(1 for a in alerts if a.severity == PilotAlertSeverity.CRITICAL),
            )

        return alerts

    # ── Individual Checks ───────────────────────────────────────────────

    def _check_signal_degradation(
        self, hit_rates: dict[str, float]
    ) -> list[PilotAlert]:
        alerts = []
        for category, hr in hit_rates.items():
            if hr < self.thresholds.SIGNAL_HR_WARNING:
                alerts.append(PilotAlert(
                    pilot_id=self.pilot_id,
                    alert_type=PilotAlertType.SIGNAL_DEGRADATION,
                    severity=PilotAlertSeverity.WARNING,
                    title=f"Signal degradation: {category}",
                    message=(
                        f"Hit rate for category '{category}' dropped to "
                        f"{hr:.1%} (threshold: {self.thresholds.SIGNAL_HR_WARNING:.1%})"
                    ),
                    metric_name="hit_rate_20d",
                    current_value=hr,
                    threshold_value=self.thresholds.SIGNAL_HR_WARNING,
                    auto_action="reduce_category_weight_50",
                ))
        return alerts

    def _check_strategy_drawdown(
        self, drawdowns: dict[str, float]
    ) -> list[PilotAlert]:
        alerts = []
        for strategy_id, dd in drawdowns.items():
            abs_dd = abs(dd)
            if abs_dd > self.thresholds.STRATEGY_DD_CRITICAL:
                alerts.append(PilotAlert(
                    pilot_id=self.pilot_id,
                    alert_type=PilotAlertType.STRATEGY_DRAWDOWN_CRITICAL,
                    severity=PilotAlertSeverity.CRITICAL,
                    portfolio_id=strategy_id,
                    title=f"CRITICAL drawdown: {strategy_id}",
                    message=(
                        f"Strategy '{strategy_id}' drawdown reached "
                        f"{abs_dd:.1%} (limit: {self.thresholds.STRATEGY_DD_CRITICAL:.1%})"
                    ),
                    metric_name="max_drawdown",
                    current_value=abs_dd,
                    threshold_value=self.thresholds.STRATEGY_DD_CRITICAL,
                    auto_action="pause_strategy",
                ))
            elif abs_dd > self.thresholds.STRATEGY_DD_WARNING:
                alerts.append(PilotAlert(
                    pilot_id=self.pilot_id,
                    alert_type=PilotAlertType.STRATEGY_DRAWDOWN,
                    severity=PilotAlertSeverity.WARNING,
                    portfolio_id=strategy_id,
                    title=f"Strategy drawdown warning: {strategy_id}",
                    message=(
                        f"Strategy '{strategy_id}' drawdown at "
                        f"{abs_dd:.1%} (warning: {self.thresholds.STRATEGY_DD_WARNING:.1%})"
                    ),
                    metric_name="max_drawdown",
                    current_value=abs_dd,
                    threshold_value=self.thresholds.STRATEGY_DD_WARNING,
                    auto_action="evaluate_pause",
                ))
        return alerts

    def _check_portfolio_volatility(
        self, volatilities: dict[str, float]
    ) -> list[PilotAlert]:
        alerts = []
        for portfolio_id, vol in volatilities.items():
            if vol > self.thresholds.PORTFOLIO_VOL_CRITICAL:
                alerts.append(PilotAlert(
                    pilot_id=self.pilot_id,
                    alert_type=PilotAlertType.PORTFOLIO_VOLATILITY_CRITICAL,
                    severity=PilotAlertSeverity.CRITICAL,
                    portfolio_id=portfolio_id,
                    title=f"CRITICAL volatility: {portfolio_id}",
                    message=(
                        f"Portfolio '{portfolio_id}' volatility spiked to "
                        f"{vol:.1%} (limit: {self.thresholds.PORTFOLIO_VOL_CRITICAL:.1%})"
                    ),
                    metric_name="annualized_volatility",
                    current_value=vol,
                    threshold_value=self.thresholds.PORTFOLIO_VOL_CRITICAL,
                    auto_action="emergency_derisk_50_cash",
                ))
            elif vol > self.thresholds.PORTFOLIO_VOL_WARNING:
                alerts.append(PilotAlert(
                    pilot_id=self.pilot_id,
                    alert_type=PilotAlertType.PORTFOLIO_VOLATILITY_SPIKE,
                    severity=PilotAlertSeverity.WARNING,
                    portfolio_id=portfolio_id,
                    title=f"Volatility spike: {portfolio_id}",
                    message=(
                        f"Portfolio '{portfolio_id}' volatility at "
                        f"{vol:.1%} (warning: {self.thresholds.PORTFOLIO_VOL_WARNING:.1%})"
                    ),
                    metric_name="annualized_volatility",
                    current_value=vol,
                    threshold_value=self.thresholds.PORTFOLIO_VOL_WARNING,
                    auto_action="reduce_exposure_25",
                ))
        return alerts

    def _check_data_staleness(
        self, last_updated: datetime | None
    ) -> list[PilotAlert]:
        if last_updated is None:
            return [PilotAlert(
                pilot_id=self.pilot_id,
                alert_type=PilotAlertType.DATA_STALENESS,
                severity=PilotAlertSeverity.WARNING,
                title="Data staleness: no data timestamp",
                message="No data update timestamp available — cannot verify freshness",
                auto_action="skip_daily_run",
            )]

        now = datetime.now(timezone.utc)
        hours_stale = (now - last_updated).total_seconds() / 3600

        if hours_stale > self.thresholds.DATA_STALENESS_HOURS:
            return [PilotAlert(
                pilot_id=self.pilot_id,
                alert_type=PilotAlertType.DATA_STALENESS,
                severity=PilotAlertSeverity.WARNING,
                title="Data staleness detected",
                message=(
                    f"Market data last updated {hours_stale:.1f}h ago "
                    f"(threshold: {self.thresholds.DATA_STALENESS_HOURS}h)"
                ),
                metric_name="data_staleness_hours",
                current_value=hours_stale,
                threshold_value=self.thresholds.DATA_STALENESS_HOURS,
                auto_action="skip_daily_run",
            )]
        return []

    def _check_case_collapse(self, expired_ratio: float) -> list[PilotAlert]:
        if expired_ratio >= self.thresholds.CASE_EXPIRED_RATIO:
            return [PilotAlert(
                pilot_id=self.pilot_id,
                alert_type=PilotAlertType.CASE_SCORE_COLLAPSE,
                severity=PilotAlertSeverity.WARNING,
                title="CASE score collapse",
                message=(
                    f"{expired_ratio:.0%} of signals are in 'Expired' state "
                    f"(threshold: {self.thresholds.CASE_EXPIRED_RATIO:.0%})"
                ),
                metric_name="case_expired_ratio",
                current_value=expired_ratio,
                threshold_value=self.thresholds.CASE_EXPIRED_RATIO,
                auto_action="freeze_new_entries",
            )]
        return []

    def _check_correlation_spike(
        self, correlations: dict[str, float]
    ) -> list[PilotAlert]:
        alerts = []
        for portfolio_id, corr in correlations.items():
            if corr > self.thresholds.CORRELATION_WARNING:
                alerts.append(PilotAlert(
                    pilot_id=self.pilot_id,
                    alert_type=PilotAlertType.CORRELATION_SPIKE,
                    severity=PilotAlertSeverity.WARNING,
                    portfolio_id=portfolio_id,
                    title=f"Correlation spike: {portfolio_id}",
                    message=(
                        f"Intra-portfolio correlation for '{portfolio_id}' "
                        f"reached {corr:.2f} (threshold: {self.thresholds.CORRELATION_WARNING})"
                    ),
                    metric_name="intra_portfolio_correlation",
                    current_value=corr,
                    threshold_value=self.thresholds.CORRELATION_WARNING,
                    auto_action="evaluate_diversification",
                ))
        return alerts

    def _check_regime_change(
        self, current: str, previous: str | None
    ) -> list[PilotAlert]:
        if previous and current != previous and current == "bear":
            return [PilotAlert(
                pilot_id=self.pilot_id,
                alert_type=PilotAlertType.REGIME_CHANGE,
                severity=PilotAlertSeverity.INFO,
                title=f"Regime change: {previous} -> {current}",
                message=(
                    f"Market regime shifted from '{previous}' to '{current}'. "
                    "Regime rules will be applied to all active strategies."
                ),
                auto_action="apply_regime_rules",
            )]
        return []
