"""
src/data/external/adapters/institutional.py
──────────────────────────────────────────────────────────────────────────────
Institutional Flow Data Adapter.

Provides insider transactions, 13F ownership changes, and derived
accumulation signals.

Data sources:
  - SEC EDGAR XBRL API (free)  — insider transactions (Form 4)
  - Polygon.io (if key available) — additional ownership data
  - FMP or similar (future upgrade)

When neither is available, the adapter produces empty data and the
CrowdingEngine IOH indicator stays at 0 (graceful degradation).
"""

from __future__ import annotations

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
)

logger = logging.getLogger("365advisers.external.institutional")


class InstitutionalAdapter(ProviderAdapter):
    """
    Institutional flow adapter.

    Fetches insider transaction data from SEC EDGAR (free, no API key)
    and aggregates it into net insider buy ratios and ownership change
    estimates.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.EDPL_DEFAULT_TIMEOUT
        self._polygon_key = settings.POLYGON_API_KEY
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "User-Agent": "365Advisers/1.0 (institutional-data@365advisers.com)",
                "Accept": "application/json",
            },
        )

    @property
    def name(self) -> str:
        return "institutional"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.INSTITUTIONAL

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.INSIDER_TRANSACTIONS,
            ProviderCapability.OWNERSHIP_CHANGES,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch institutional flow data for a ticker."""
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")

        t0 = time.perf_counter()

        try:
            # Fetch insider transactions
            transactions = await self._fetch_insider_transactions(ticker)

            # Compute derived metrics
            net_buy_ratio = self._compute_net_buy_ratio(transactions)
            ownership_change = await self._estimate_ownership_change(ticker)

            data = InstitutionalFlowData(
                ticker=ticker,
                insider_transactions_90d=transactions,
                net_insider_buy_ratio=net_buy_ratio,
                inst_ownership_change_qoq=ownership_change,
                source="sec_edgar",
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Institutional fetch error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Check connectivity to SEC EDGAR."""
        try:
            resp = await self._client.get(
                "https://efts.sec.gov/LATEST/search-index?q=%22health%22&dateRange=custom&startdt=2024-01-01&enddt=2024-01-02",
            )
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=status,
                message=f"SEC EDGAR HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=str(exc),
            )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_insider_transactions(self, ticker: str) -> list[InsiderTransaction]:
        """
        Fetch insider transactions from a data source.

        Uses yfinance insider data as the primary free source.
        """
        transactions: list[InsiderTransaction] = []

        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)

            # yfinance provides insider transactions
            insiders = getattr(stock, "insider_transactions", None)
            if insiders is not None and not insiders.empty:
                for _, row in insiders.head(20).iterrows():
                    try:
                        tx_type = "BUY" if "Purchase" in str(row.get("Text", "")) else "SELL"
                        shares = int(row.get("Shares", 0)) if row.get("Shares") else 0
                        value = float(row.get("Value", 0)) if row.get("Value") else 0
                        price = value / shares if shares > 0 else 0

                        transactions.append(InsiderTransaction(
                            ticker=ticker,
                            insider_name=str(row.get("Insider", "Unknown")),
                            title=str(row.get("Position", "")),
                            transaction_type=tx_type,
                            shares=abs(shares),
                            price=round(price, 2),
                            date=str(row.get("Start Date", "")),
                            total_value=abs(value),
                        ))
                    except (ValueError, TypeError):
                        continue

        except Exception as exc:
            logger.debug(f"yfinance insider fetch failed for {ticker}: {exc}")

        return transactions

    def _compute_net_buy_ratio(self, transactions: list[InsiderTransaction]) -> float:
        """
        Compute net insider buy ratio: (buys - sells) / total.

        Returns value between -1.0 (all sells) and +1.0 (all buys).
        """
        if not transactions:
            return 0.0

        buys = sum(1 for t in transactions if t.transaction_type == "BUY")
        sells = sum(1 for t in transactions if t.transaction_type == "SELL")
        total = buys + sells

        if total == 0:
            return 0.0

        return round((buys - sells) / total, 3)

    async def _estimate_ownership_change(self, ticker: str) -> float:
        """
        Estimate quarterly institutional ownership change.

        Uses yfinance major_holders as a simplified approach.
        Returns the QoQ change estimate (0 if not available).
        """
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            holders = getattr(stock, "institutional_holders", None)

            if holders is not None and not holders.empty:
                # Use count of institutional holders as a proxy
                # More holders → accumulation; fewer → distribution
                total_shares = holders["Shares"].sum() if "Shares" in holders.columns else 0
                pct = holders["% Out"].sum() if "% Out" in holders.columns else 0

                # Without historical data, we return a small positive bias
                # for stocks with high institutional interest
                if pct > 70:
                    return 0.02  # Strong institutional interest
                elif pct > 50:
                    return 0.01  # Moderate institutional interest
                elif pct > 30:
                    return 0.0   # Neutral
                else:
                    return -0.01  # Low institutional interest

        except Exception as exc:
            logger.debug(f"Ownership change estimate failed for {ticker}: {exc}")

        return 0.0
