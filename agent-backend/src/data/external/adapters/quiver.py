"""
src/data/external/adapters/quiver.py
──────────────────────────────────────────────────────────────────────────────
Quiver Quantitative Adapter — congressional trading, lobbying, and
government contracts alternative data.

Registers as a tertiary adapter for DataDomain.INSTITUTIONAL.
Provides unique "smart money" signals not available from other sources.

Data sources:
  - Quiver Quantitative REST API (api.quiverquant.com)
  - Requires API key (QUIVER_API_KEY)

Retry policy:
  - 1 retry per dataset, 2s backoff
  - No fallback — Quiver data is unique
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

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
from src.data.external.contracts.institutional import (
    CongressionalTrade,
    InstitutionalFlowData,
)

logger = logging.getLogger("365advisers.external.quiver")

QUIVER_BASE = "https://api.quiverquant.com/beta"


class QuiverAdapter(ProviderAdapter):
    """
    Quiver Quantitative adapter for alternative institutional intelligence.

    Provides congressional trading disclosures, lobbying expenditure data,
    and government contract values -- unique "smart money" signals.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.QUIVER_API_KEY
        self._timeout = settings.EDPL_QUIVER_TIMEOUT
        self._retry_delay = settings.EDPL_DEFAULT_RETRY_DELAY
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    @property
    def name(self) -> str:
        return "quiver"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.INSTITUTIONAL

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.CONGRESSIONAL_TRADES,
            ProviderCapability.LOBBYING_DATA,
            ProviderCapability.GOV_CONTRACTS,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch alternative institutional intelligence from Quiver."""
        t0 = time.perf_counter()
        ticker = request.ticker or ""

        if not self._api_key:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                "QUIVER_API_KEY not configured", latency_ms=elapsed,
            )

        if not ticker:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                "ticker required for Quiver", latency_ms=elapsed,
            )

        try:
            congress, lobbying, contracts = await asyncio.gather(
                self._fetch_congressional_trades(ticker),
                self._fetch_lobbying(ticker),
                self._fetch_gov_contracts(ticker),
                return_exceptions=True,
            )

            if isinstance(congress, Exception):
                logger.warning(f"Quiver congress fetch failed: {congress}")
                congress = []
            if isinstance(lobbying, Exception):
                logger.warning(f"Quiver lobbying fetch failed: {lobbying}")
                lobbying = 0.0
            if isinstance(contracts, Exception):
                logger.warning(f"Quiver contracts fetch failed: {contracts}")
                contracts = 0.0

            # Compute smart money score (simplified)
            smart_score = self._compute_smart_money_score(congress, lobbying, contracts)

            data = InstitutionalFlowData(
                ticker=ticker,
                congressional_trades=congress,
                lobbying_spend_total=lobbying if isinstance(lobbying, (int, float)) else None,
                gov_contract_value=contracts if isinstance(contracts, (int, float)) else None,
                quiver_smart_money_score=smart_score,
                source="quiver",
                sources_used=["quiver"],
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Quiver adapter error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Lightweight health probe."""
        if not self._api_key:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DISABLED,
                message="QUIVER_API_KEY not configured",
            )

        try:
            resp = await self._client.get(f"{QUIVER_BASE}/historical/congresstrading/AAPL")
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=status,
                last_success=datetime.now(timezone.utc) if resp.status_code == 200 else None,
                message=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"Health check failed: {exc}",
            )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_congressional_trades(self, ticker: str) -> list[CongressionalTrade]:
        """Fetch congressional trading disclosures for a ticker."""
        data = await self._api_get(f"/historical/congresstrading/{ticker}")
        if not data or not isinstance(data, list):
            return []

        trades: list[CongressionalTrade] = []
        for entry in data[:30]:  # last 30 entries
            trades.append(CongressionalTrade(
                congress_member=entry.get("Representative", "Unknown"),
                ticker=ticker,
                tx_type=entry.get("Transaction", "UNKNOWN").upper(),
                amount_range=entry.get("Range", ""),
                date=entry.get("TransactionDate", ""),
                party=entry.get("Party", ""),
                chamber=entry.get("House", ""),
            ))

        return trades

    async def _fetch_lobbying(self, ticker: str) -> float:
        """Fetch total lobbying spend for a ticker."""
        data = await self._api_get(f"/historical/lobbying/{ticker}")
        if not data or not isinstance(data, list):
            return 0.0

        total = sum(entry.get("Amount", 0) for entry in data)
        return float(total)

    async def _fetch_gov_contracts(self, ticker: str) -> float:
        """Fetch recent government contract value."""
        data = await self._api_get(f"/historical/govcontracts/{ticker}")
        if not data or not isinstance(data, list):
            return 0.0

        total = sum(entry.get("Amount", 0) for entry in data[:10])
        return float(total)

    @staticmethod
    def _compute_smart_money_score(
        congress: list,
        lobbying: float | int,
        contracts: float | int,
    ) -> float | None:
        """
        Simplified smart money score (0–100).

        Components:
          - Congressional buy activity (40%)
          - Lobbying presence (30%)
          - Government contracts presence (30%)
        """
        score = 0.0
        components = 0

        if congress:
            buys = sum(1 for t in congress if t.tx_type == "BUY")
            total = len(congress)
            buy_ratio = buys / total if total > 0 else 0.5
            score += buy_ratio * 40
            components += 1

        if lobbying and isinstance(lobbying, (int, float)) and lobbying > 0:
            score += min(30, 30)  # binary: has lobbying presence
            components += 1

        if contracts and isinstance(contracts, (int, float)) and contracts > 0:
            score += min(30, 30)  # binary: has gov contracts
            components += 1

        return round(score, 1) if components > 0 else None

    async def _api_get(self, endpoint: str) -> list | dict | None:
        """Make Quiver API call with 1 retry."""
        for attempt in range(2):
            try:
                resp = await self._client.get(f"{QUIVER_BASE}{endpoint}")
                if resp.status_code == 429:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    continue
                if resp.status_code == 200:
                    return resp.json()
                return None
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == 0:
                    await asyncio.sleep(self._retry_delay)
            except Exception as exc:
                logger.debug(f"Quiver {endpoint} error: {exc}")
                break
        return None
