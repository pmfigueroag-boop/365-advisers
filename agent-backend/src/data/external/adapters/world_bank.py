"""
src/data/external/adapters/world_bank.py
──────────────────────────────────────────────────────────────────────────────
World Bank Open Data Adapter — global macro economic indicators.

Provides:
  - GDP (current, per capita, growth)
  - Inflation (CPI, GDP deflator)
  - Unemployment rate
  - Trade (imports, exports)
  - Population, FDI, government debt

Auth: None required — fully open API.
Rate limiting: Generous, undocumented. Respectful usage advised.

Docs: https://datahelpdesk.worldbank.org/knowledgebase/topics/125589
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config import get_settings
from src.data.external.base import (
    DataDomain,
    HealthStatus,
    ProviderAdapter,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from src.data.external.contracts.economic_indicator import (
    EconomicIndicatorData,
    EconomicSeries,
    EconomicObservation,
)

logger = logging.getLogger("365advisers.external.world_bank")

_WB_BASE = "https://api.worldbank.org/v2"

# Common indicator codes
_WB_INDICATORS = {
    "GDP": "NY.GDP.MKTP.CD",
    "GDP_GROWTH": "NY.GDP.MKTP.KD.ZG",
    "GDP_PER_CAPITA": "NY.GDP.PCAP.CD",
    "INFLATION_CPI": "FP.CPI.TOTL.ZG",
    "UNEMPLOYMENT": "SL.UEM.TOTL.ZS",
    "POPULATION": "SP.POP.TOTL",
    "TRADE_PCT_GDP": "NE.TRD.GNFS.ZS",
    "FDI_NET": "BX.KLT.DINV.CD.WD",
    "GOV_DEBT_PCT_GDP": "GC.DOD.TOTL.GD.ZS",
    "CURRENT_ACCOUNT": "BN.CAB.XOKA.CD",
}


class WorldBankAdapter(ProviderAdapter):
    """
    Adapter for the World Bank Open Data API.

    Fetches macro-level country indicators. No authentication required.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.EDPL_WB_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=_WB_BASE,
            timeout=self._timeout,
        )

    @property
    def name(self) -> str:
        return "world_bank"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.MACRO

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.GDP_DATA,
            ProviderCapability.INFLATION_DATA,
            ProviderCapability.LABOR_DATA,
            ProviderCapability.ECONOMIC_INDICATORS,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Fetch economic indicator from World Bank.

        Expected request.params:
          - indicator: str — World Bank indicator code or shorthand key
                              (e.g. "GDP", "INFLATION_CPI", "NY.GDP.MKTP.CD")
                              Default: "GDP"
          - country: str — ISO2 country code. Default: "US"
          - years: int — number of years of data. Default: 20
        """
        indicator_key = request.params.get("indicator", "GDP")
        # Resolve shorthand to full indicator code
        indicator = _WB_INDICATORS.get(indicator_key.upper(), indicator_key)
        country = request.params.get("country", "US")
        years = request.params.get("years", 20)
        t0 = time.perf_counter()

        try:
            url = f"/country/{country}/indicator/{indicator}"
            resp = await self._client.get(
                url,
                params={
                    "format": "json",
                    "per_page": years,
                    "mrv": years,
                },
            )
            resp.raise_for_status()
            raw = resp.json()

            # World Bank returns [metadata, data] — data is at index 1
            if not isinstance(raw, list) or len(raw) < 2:
                elapsed = (time.perf_counter() - t0) * 1000
                return self._error_response("Unexpected response format", latency_ms=elapsed)

            data_items = raw[1] or []
            observations = self._parse_observations(data_items)

            # Build series metadata from first item
            meta = data_items[0] if data_items else {}
            series = EconomicSeries(
                series_id=indicator,
                name=meta.get("indicator", {}).get("value", indicator_key),
                country=meta.get("country", {}).get("value", country),
                source_agency="World Bank",
                frequency="annual",
            )

            latest = observations[0] if observations else None
            data = EconomicIndicatorData(
                series=series,
                observations=observations,
                latest_value=latest.value if latest else None,
                latest_date=latest.date if latest else "",
                source="world_bank",
                fetched_at=datetime.now(timezone.utc),
            )
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(f"Timeout after {self._timeout}s", latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"World Bank error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get(
                "/country/US/indicator/NY.GDP.MKTP.CD",
                params={"format": "json", "per_page": 1, "mrv": 1},
            )
            if resp.status_code == 200:
                return HealthStatus(
                    provider_name=self.name, domain=self.domain,
                    status=ProviderStatus.ACTIVE, message="connected",
                )
            return HealthStatus(
                provider_name=self.name, domain=self.domain,
                status=ProviderStatus.DEGRADED, message=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name, domain=self.domain,
                status=ProviderStatus.DISABLED, message=str(exc),
            )

    def _parse_observations(self, items: list[dict]) -> list[EconomicObservation]:
        obs: list[EconomicObservation] = []
        prev_val: float | None = None
        for item in items:
            val = item.get("value")
            if val is None:
                continue
            try:
                value = float(val)
            except (ValueError, TypeError):
                continue
            date = item.get("date", "")
            change = (value - prev_val) if prev_val is not None else None
            change_pct = (change / abs(prev_val) * 100) if change is not None and prev_val else None
            obs.append(EconomicObservation(
                date=date,
                value=value,
                previous=prev_val,
                change=round(change, 4) if change is not None else None,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
            ))
            prev_val = value
        return obs
