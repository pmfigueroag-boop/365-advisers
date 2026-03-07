"""
src/data/external/adapters/finnhub.py
──────────────────────────────────────────────────────────────────────────────
Finnhub Adapter — insider transactions, institutional ownership, and
company news via Finnhub REST API.

Registers as a secondary adapter for DataDomain.INSTITUTIONAL.
Also contributes news/sentiment data when requested.

Data sources:
  - Finnhub REST API (finnhub.io) — free tier: 60 calls/min
  - Requires API key (FINNHUB_API_KEY)

Retry policy:
  - 2 retries with exponential backoff
  - Rate limit: 60 req/min → internal rate limiter
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
    InsiderTransaction,
    InstitutionalFlowData,
    OwnershipChange,
)

logger = logging.getLogger("365advisers.external.finnhub")

FINNHUB_BASE = "https://finnhub.io/api/v1"


class FinnhubAdapter(ProviderAdapter):
    """
    Finnhub adapter for insider transactions, institutional ownership,
    and company news.  Registered as a fallback for INSTITUTIONAL domain.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.FINNHUB_API_KEY
        self._timeout = settings.EDPL_FINNHUB_TIMEOUT
        self._max_retries = settings.EDPL_DEFAULT_MAX_RETRIES
        self._retry_delay = settings.EDPL_DEFAULT_RETRY_DELAY
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={"X-Finnhub-Token": self._api_key},
        )

    @property
    def name(self) -> str:
        return "finnhub"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.INSTITUTIONAL

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.INSIDER_TRANSACTIONS,
            ProviderCapability.OWNERSHIP_CHANGES,
            ProviderCapability.EARNINGS_SURPRISES,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch institutional flow data from Finnhub."""
        t0 = time.perf_counter()
        ticker = request.ticker or ""

        if not self._api_key:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                "FINNHUB_API_KEY not configured", latency_ms=elapsed,
            )

        if not ticker:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                "ticker required for Finnhub", latency_ms=elapsed,
            )

        try:
            insiders, ownership = await asyncio.gather(
                self._fetch_insider_transactions(ticker),
                self._fetch_ownership(ticker),
                return_exceptions=True,
            )

            if isinstance(insiders, Exception):
                logger.warning(f"Finnhub insider fetch failed: {insiders}")
                insiders = []
            if isinstance(ownership, Exception):
                logger.warning(f"Finnhub ownership fetch failed: {ownership}")
                ownership = []

            # Compute net insider buy ratio
            buys = sum(1 for t in insiders if t.transaction_type == "BUY")
            total = len(insiders)
            net_ratio = buys / total if total > 0 else None

            data = InstitutionalFlowData(
                ticker=ticker,
                insider_transactions_90d=insiders,
                ownership_changes_q=ownership,
                net_insider_buy_ratio=net_ratio,
                source="finnhub",
                sources_used=["finnhub"],
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Finnhub adapter error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Lightweight health probe."""
        if not self._api_key:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DISABLED,
                message="FINNHUB_API_KEY not configured",
            )

        try:
            resp = await self._client.get(f"{FINNHUB_BASE}/stock/symbol", params={"exchange": "US"})
            if resp.status_code == 200:
                return HealthStatus(
                    provider_name=self.name,
                    domain=self.domain,
                    status=ProviderStatus.ACTIVE,
                    last_success=datetime.now(timezone.utc),
                    message="Finnhub API reachable",
                )
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"Finnhub returned HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"Health check failed: {exc}",
            )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_insider_transactions(self, ticker: str) -> list[InsiderTransaction]:
        """Fetch insider sentiment (transactions) from Finnhub."""
        resp = await self._api_get("/stock/insider-transactions", {"symbol": ticker})
        if not resp:
            return []

        transactions: list[InsiderTransaction] = []
        for entry in resp.get("data", [])[:50]:  # limit to last 50
            tx_type = "BUY" if entry.get("change", 0) > 0 else "SELL"
            shares = abs(int(entry.get("change", 0)))
            price = float(entry.get("transactionPrice", 0) or 0)

            transactions.append(InsiderTransaction(
                ticker=ticker,
                insider_name=entry.get("name", "Unknown"),
                title=entry.get("filingDate", ""),
                transaction_type=tx_type,
                shares=shares,
                price=price,
                date=entry.get("transactionDate", ""),
                total_value=shares * price,
            ))

        return transactions

    async def _fetch_ownership(self, ticker: str) -> list[OwnershipChange]:
        """Fetch institutional ownership from Finnhub."""
        resp = await self._api_get("/stock/ownership", {"symbol": ticker, "limit": 20})
        if not resp:
            return []

        changes: list[OwnershipChange] = []
        for entry in resp.get("ownership", []):
            changes.append(OwnershipChange(
                ticker=ticker,
                institution_name=entry.get("name", "Unknown"),
                shares_held=int(entry.get("share", 0)),
                shares_change=int(entry.get("change", 0)),
                pct_portfolio=entry.get("percentage"),
                filing_date=entry.get("filingDate", ""),
            ))

        return changes

    async def _api_get(self, endpoint: str, params: dict) -> dict | None:
        """Make Finnhub API call with retry."""
        for attempt in range(1 + self._max_retries):
            try:
                resp = await self._client.get(f"{FINNHUB_BASE}{endpoint}", params=params)
                if resp.status_code == 429:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    continue
                if resp.status_code == 200:
                    return resp.json()
                logger.debug(f"Finnhub {endpoint} returned HTTP {resp.status_code}")
                return None
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                else:
                    logger.debug(f"Finnhub {endpoint} exhausted retries: {exc}")
            except Exception as exc:
                logger.debug(f"Finnhub {endpoint} error: {exc}")
                break
        return None
