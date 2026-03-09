"""
src/data/external/adapters/imf.py
──────────────────────────────────────────────────────────────────────────────
IMF Adapter — International Monetary Fund data.

Provides: WEO indicators (GDP forecasts, debt/GDP, inflation projections).
Auth: None required. API docs are sparse but functional.
Docs: https://datahelp.imf.org/knowledgebase/articles/667681
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from src.config import get_settings
from src.data.external.base import (
    DataDomain, HealthStatus, ProviderAdapter, ProviderCapability,
    ProviderRequest, ProviderResponse, ProviderStatus,
)
from src.data.external.contracts.economic_indicator import (
    EconomicIndicatorData, EconomicSeries, EconomicObservation,
)

logger = logging.getLogger("365advisers.external.imf")
_IMF_BASE = "http://dataservices.imf.org/REST/SDMX_JSON.svc"


class IMFAdapter(ProviderAdapter):
    """Adapter for the IMF CompactData/SDMX JSON API."""

    def __init__(self) -> None:
        s = get_settings()
        self._timeout = s.EDPL_IMF_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "imf"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.MACRO

    def get_capabilities(self) -> set[ProviderCapability]:
        return {ProviderCapability.GDP_DATA, ProviderCapability.INFLATION_DATA, ProviderCapability.ECONOMIC_INDICATORS}

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Fetch from IMF. request.params:
          - indicator: str — IFS indicator code, default "NGDP_RPCH" (real GDP growth)
          - country: str — ISO2 code, default "US"
        """
        indicator = request.params.get("indicator", "NGDP_RPCH")
        country = request.params.get("country", "US")
        t0 = time.perf_counter()
        try:
            url = f"{_IMF_BASE}/CompactData/IFS/A.{country}.{indicator}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            raw = resp.json()
            series_data = (raw.get("CompactData", {}).get("DataSet", {}).get("Series", {}))
            obs_raw = series_data.get("Obs", [])
            if isinstance(obs_raw, dict):
                obs_raw = [obs_raw]
            observations = []
            for o in obs_raw:
                val = o.get("@OBS_VALUE")
                if val is None:
                    continue
                try:
                    observations.append(EconomicObservation(date=o.get("@TIME_PERIOD", ""), value=float(val)))
                except (ValueError, TypeError):
                    continue
            series = EconomicSeries(series_id=indicator, name=indicator, country=country, source_agency="IMF", frequency="annual")
            latest = observations[-1] if observations else None
            data = EconomicIndicatorData(
                series=series, observations=observations,
                latest_value=latest.value if latest else None,
                latest_date=latest.date if latest else "",
                source="imf", fetched_at=datetime.now(timezone.utc),
            )
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"IMF error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get(f"{_IMF_BASE}/Dataflow")
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(provider_name=self.name, domain=self.domain, status=status, message="ok")
        except Exception as exc:
            return HealthStatus(provider_name=self.name, domain=self.domain, status=ProviderStatus.DISABLED, message=str(exc))
