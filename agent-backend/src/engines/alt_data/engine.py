"""
src/engines/alt_data/engine.py — Alternative Data Engine.
"""
from __future__ import annotations
import logging
from src.engines.alt_data.models import AltDataType, AltDataSignal, AltDataReport
from src.engines.alt_data.adapters import ALL_ADAPTERS

logger = logging.getLogger("365advisers.alt_data.engine")


class AltDataEngine:
    """Unified alternative data aggregation."""

    @classmethod
    def analyse(cls, ticker: str, seed: int | None = None) -> AltDataReport:
        """Fetch all alt data sources and produce composite signal."""
        signals = []
        for adapter in ALL_ADAPTERS:
            try:
                sig = adapter.fetch(ticker, seed)
                signals.append(sig)
            except Exception as e:
                logger.warning("Adapter %s failed: %s", adapter.data_type, e)

        if not signals:
            return AltDataReport(ticker=ticker)

        # Composite: confidence-weighted average
        total_weight = sum(s.confidence for s in signals)
        if total_weight > 0:
            composite = sum(s.signal * s.confidence for s in signals) / total_weight
            comp_conf = total_weight / len(signals)
        else:
            composite = 0.0
            comp_conf = 0.0

        return AltDataReport(
            ticker=ticker, signals=signals,
            composite_signal=round(composite, 4),
            composite_confidence=round(min(comp_conf, 1.0), 4),
            sources_available=len(ALL_ADAPTERS),
            sources_used=len(signals),
        )

    @classmethod
    def batch_analyse(cls, tickers: list[str], seed: int | None = None) -> dict[str, AltDataReport]:
        return {t: cls.analyse(t, seed) for t in tickers}

    @classmethod
    def get_source_signal(cls, ticker: str, source_type: AltDataType, seed: int | None = None) -> AltDataSignal | None:
        for adapter in ALL_ADAPTERS:
            if adapter.data_type == source_type:
                return adapter.fetch(ticker, seed)
        return None
