"""
src/engines/crowding/engine.py
──────────────────────────────────────────────────────────────────────────────
Signal Crowding Detection Engine.

Aggregates 4 crowding indicators into a Crowding Risk Score (CRS)
and produces a penalty factor for the Composite Alpha Score Engine.

Pipeline:
  1. Compute individual indicators (VAS, EFC, IOH, VC)
  2. Weight and combine into CRS
  3. Classify severity
  4. Compute CASE penalty factor
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from src.engines.crowding.indicators import (
    compute_etf_flow_concentration,
    compute_institutional_herding,
    compute_volatility_compression,
    compute_volume_anomaly,
)
from src.engines.crowding.models import (
    CrowdingConfig,
    CrowdingIndicators,
    CrowdingResult,
    CrowdingSeverity,
)

logger = logging.getLogger("365advisers.crowding.engine")


class CrowdingEngine:
    """
    Detects signal crowding and produces a risk-adjusted penalty.

    Usage
    -----
    engine = CrowdingEngine()
    result = engine.assess("AAPL", ohlcv=df)
    penalty = result.penalty_factor  # Apply to CASE
    """

    def __init__(self, config: CrowdingConfig | None = None) -> None:
        self.config = config or CrowdingConfig()
        # In-memory cache for batch operations
        self._cache: dict[str, CrowdingResult] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def assess(
        self,
        ticker: str,
        ohlcv: pd.DataFrame | None = None,
        net_flows_5d: float = 0.0,
        mean_flow_60d: float = 0.0,
        std_flow_60d: float = 1.0,
        inst_ownership_change: float = 0.0,
        sector_avg_change: float = 0.0,
        realized_vol_20d: float | None = None,
        implied_vol_30d: float | None = None,
    ) -> CrowdingResult:
        """
        Full crowding assessment for a single ticker.

        Parameters
        ----------
        ticker : str
            Ticker symbol.
        ohlcv : pd.DataFrame | None
            Historical OHLCV data for volume and vol calculations.
        net_flows_5d, mean_flow_60d, std_flow_60d : float
            ETF flow data for EFC calculation.
        inst_ownership_change, sector_avg_change : float
            13F data for IOH calculation.
        realized_vol_20d, implied_vol_30d : float | None
            Volatility data for VC calculation.
        """
        cfg = self.config
        data_available = {
            "volume": False,
            "etf_flow": False,
            "institutional": False,
            "volatility": False,
        }

        # 1. Compute individual indicators
        vas = 0.0
        if ohlcv is not None and not ohlcv.empty and "Volume" in ohlcv.columns:
            vas = compute_volume_anomaly(ohlcv, cfg.volume_short_window, cfg.volume_long_window)
            data_available["volume"] = True

        efc = 0.0
        if std_flow_60d > 0 and net_flows_5d != 0:
            efc = compute_etf_flow_concentration(net_flows_5d, mean_flow_60d, std_flow_60d)
            data_available["etf_flow"] = True

        ioh = 0.0
        if sector_avg_change > 0 and inst_ownership_change != 0:
            ioh = compute_institutional_herding(inst_ownership_change, sector_avg_change)
            data_available["institutional"] = True

        vc = 0.0
        if implied_vol_30d is not None and implied_vol_30d > 0:
            vc = compute_volatility_compression(ohlcv, realized_vol_20d, implied_vol_30d)
            data_available["volatility"] = True

        indicators = CrowdingIndicators(
            volume_anomaly=round(vas, 4),
            etf_flow_conc=round(efc, 4),
            inst_herding=round(ioh, 4),
            vol_compression=round(vc, 4),
        )

        # 2. Weighted CRS
        crs = (
            cfg.w_volume * vas
            + cfg.w_etf_flow * efc
            + cfg.w_institutional * ioh
            + cfg.w_volatility * vc
        )
        crs = round(max(0.0, min(1.0, crs)), 4)

        # 3. Severity
        severity = self._classify_severity(crs)

        # 4. Penalty factor
        penalty = round(1.0 - (cfg.max_penalty * crs), 4)

        result = CrowdingResult(
            ticker=ticker,
            crowding_risk_score=crs,
            severity=severity,
            indicators=indicators,
            penalty_factor=penalty,
            data_available=data_available,
        )

        # Cache for batch / CASE lookup
        self._cache[ticker] = result

        logger.info(
            f"CROWDING: {ticker} CRS={crs:.3f} ({severity.value}), "
            f"penalty={penalty:.3f}"
        )

        return result

    def assess_batch(
        self,
        tickers: list[str],
        ohlcv_data: dict[str, pd.DataFrame] | None = None,
        flow_data: dict[str, dict] | None = None,
        inst_data: dict[str, dict] | None = None,
        vol_data: dict[str, dict] | None = None,
    ) -> dict[str, CrowdingResult]:
        """
        Batch crowding assessment for multiple tickers.

        Parameters
        ----------
        tickers : list[str]
            List of ticker symbols.
        ohlcv_data : dict | None
            {ticker: DataFrame}.
        flow_data : dict | None
            {ticker: {net_flows_5d, mean_flow_60d, std_flow_60d}}.
        inst_data : dict | None
            {ticker: {inst_ownership_change, sector_avg_change}}.
        vol_data : dict | None
            {ticker: {realized_vol_20d, implied_vol_30d}}.
        """
        ohlcv_data = ohlcv_data or {}
        flow_data = flow_data or {}
        inst_data = inst_data or {}
        vol_data = vol_data or {}

        results: dict[str, CrowdingResult] = {}

        for ticker in tickers:
            flow = flow_data.get(ticker, {})
            inst = inst_data.get(ticker, {})
            vol = vol_data.get(ticker, {})

            results[ticker] = self.assess(
                ticker=ticker,
                ohlcv=ohlcv_data.get(ticker),
                net_flows_5d=flow.get("net_flows_5d", 0.0),
                mean_flow_60d=flow.get("mean_flow_60d", 0.0),
                std_flow_60d=flow.get("std_flow_60d", 1.0),
                inst_ownership_change=inst.get("inst_ownership_change", 0.0),
                sector_avg_change=inst.get("sector_avg_change", 0.0),
                realized_vol_20d=vol.get("realized_vol_20d"),
                implied_vol_30d=vol.get("implied_vol_30d"),
            )

        return results

    def get_penalty(self, ticker: str) -> float:
        """
        Get cached penalty factor for a ticker.

        Returns 1.0 (no penalty) if no assessment exists.
        """
        result = self._cache.get(ticker)
        return result.penalty_factor if result else 1.0

    def get_all_penalties(self) -> dict[str, float]:
        """Get all cached penalties as {ticker: penalty_factor}."""
        return {t: r.penalty_factor for t, r in self._cache.items()}

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _classify_severity(crs: float) -> CrowdingSeverity:
        """Classify CRS into a severity level."""
        if crs >= 0.8:
            return CrowdingSeverity.EXTREME
        elif crs >= 0.6:
            return CrowdingSeverity.HIGH
        elif crs >= 0.4:
            return CrowdingSeverity.MODERATE
        elif crs >= 0.2:
            return CrowdingSeverity.LOW
        return CrowdingSeverity.NONE
