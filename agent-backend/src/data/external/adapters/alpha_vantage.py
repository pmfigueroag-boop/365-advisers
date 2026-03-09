"""
src/data/external/adapters/alpha_vantage.py
──────────────────────────────────────────────────────────────────────────────
Alpha Vantage Adapter — market data + fundamentals provider.

Provides:
  - Daily / weekly / monthly OHLCV via TIME_SERIES endpoints
  - Company overview (profile, ratios)
  - Income statement, balance sheet, cash flow
  - Analyst estimates (earnings calendar)

Rate limiting: Free = 5 req/min, 500 req/day.
               Premium = 75 req/min (from $49.99/mo).

Docs: https://www.alphavantage.co/documentation/
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
from src.data.external.contracts.enhanced_market import (
    EnhancedMarketData,
    IntradayBar,
)
from src.data.external.contracts.asset_profile import AssetProfile
from src.data.external.contracts.financial_statement import (
    FinancialStatementData,
    IncomeStatement,
    BalanceSheet,
    CashFlowStatement,
)

logger = logging.getLogger("365advisers.external.alpha_vantage")

_AV_BASE = "https://www.alphavantage.co/query"


class AlphaVantageAdapter(ProviderAdapter):
    """
    Adapter for the Alpha Vantage REST API.

    Serves as a secondary market data source and a fundamental data source.
    Transforms responses into EnhancedMarketData or FinancialStatementData
    contracts depending on the request params.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.ALPHA_VANTAGE_API_KEY
        self._timeout = settings.EDPL_AV_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "alpha_vantage"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.MARKET_DATA

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.DAILY_BARS,
            ProviderCapability.FINANCIAL_STATEMENTS,
            ProviderCapability.COMPANY_PROFILE,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Fetch data from Alpha Vantage.

        Expected request.params:
          - function: str — "TIME_SERIES_DAILY", "OVERVIEW",
                           "INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"
                           Default: "TIME_SERIES_DAILY"
        """
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")
        if not self._api_key:
            return self._error_response("ALPHA_VANTAGE_API_KEY not configured")

        function = request.params.get("function", "TIME_SERIES_DAILY")
        t0 = time.perf_counter()

        try:
            params: dict[str, Any] = {
                "function": function,
                "symbol": ticker,
                "apikey": self._api_key,
            }
            if function == "TIME_SERIES_DAILY":
                params["outputsize"] = request.params.get("outputsize", "compact")

            resp = await self._client.get(_AV_BASE, params=params)
            resp.raise_for_status()
            raw = resp.json()

            # Check for API error messages
            if "Error Message" in raw:
                elapsed = (time.perf_counter() - t0) * 1000
                return self._error_response(raw["Error Message"], latency_ms=elapsed)
            if "Note" in raw:  # Rate limit notice
                elapsed = (time.perf_counter() - t0) * 1000
                return self._error_response(f"Rate limited: {raw['Note']}", latency_ms=elapsed)

            data = self._transform(function, ticker, raw)
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(f"Timeout after {self._timeout}s", latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Alpha Vantage error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get(
                _AV_BASE,
                params={"function": "TIME_SERIES_DAILY", "symbol": "IBM", "apikey": self._api_key},
            )
            if resp.status_code == 200 and "Error" not in resp.text:
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

    # ── Transformers ──────────────────────────────────────────────────────

    def _transform(self, function: str, ticker: str, raw: dict) -> Any:
        if function == "TIME_SERIES_DAILY":
            return self._transform_daily(ticker, raw)
        elif function == "OVERVIEW":
            return self._transform_profile(ticker, raw)
        elif function in ("INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW"):
            return self._transform_financials(function, ticker, raw)
        return raw

    def _transform_daily(self, ticker: str, raw: dict) -> EnhancedMarketData:
        ts_key = "Time Series (Daily)"
        series = raw.get(ts_key, {})
        bars: list[IntradayBar] = []
        for date_str, vals in list(series.items())[:90]:
            try:
                bars.append(IntradayBar(
                    timestamp=datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                    open=float(vals.get("1. open", 0)),
                    high=float(vals.get("2. high", 0)),
                    low=float(vals.get("3. low", 0)),
                    close=float(vals.get("4. close", 0)),
                    volume=int(float(vals.get("5. volume", 0))),
                ))
            except (ValueError, TypeError):
                continue
        return EnhancedMarketData(
            ticker=ticker,
            intraday_bars=bars,
            last_trade_price=bars[0].close if bars else None,
            source="alpha_vantage",
            fetched_at=datetime.now(timezone.utc),
        )

    def _transform_profile(self, ticker: str, raw: dict) -> AssetProfile:
        return AssetProfile(
            ticker=ticker,
            name=raw.get("Name", ""),
            exchange=raw.get("Exchange", ""),
            currency=raw.get("Currency", "USD"),
            country=raw.get("Country", ""),
            sector=raw.get("Sector", ""),
            industry=raw.get("Industry", ""),
            description=raw.get("Description", ""),
            market_cap=_safe_float(raw.get("MarketCapitalization")),
            shares_outstanding=_safe_float(raw.get("SharesOutstanding")),
            employees=_safe_int(raw.get("FullTimeEmployees")),
            fiscal_year_end=raw.get("FiscalYearEnd"),
            asset_type=raw.get("AssetType", "equity").lower(),
            source="alpha_vantage",
            fetched_at=datetime.now(timezone.utc),
        )

    def _transform_financials(self, function: str, ticker: str, raw: dict) -> FinancialStatementData:
        data = FinancialStatementData(
            ticker=ticker,
            source="alpha_vantage",
            fetched_at=datetime.now(timezone.utc),
        )
        reports = raw.get("annualReports", []) + raw.get("quarterlyReports", [])

        for r in reports[:12]:
            period = r.get("fiscalDateEnding", "")
            if function == "INCOME_STATEMENT":
                data.income_statements.append(IncomeStatement(
                    period=period, fiscal_date=period,
                    revenue=_safe_float(r.get("totalRevenue")),
                    gross_profit=_safe_float(r.get("grossProfit")),
                    operating_income=_safe_float(r.get("operatingIncome")),
                    ebitda=_safe_float(r.get("ebitda")),
                    net_income=_safe_float(r.get("netIncome")),
                    eps=_safe_float(r.get("reportedEPS")),
                ))
            elif function == "BALANCE_SHEET":
                data.balance_sheets.append(BalanceSheet(
                    period=period, fiscal_date=period,
                    total_assets=_safe_float(r.get("totalAssets")),
                    total_liabilities=_safe_float(r.get("totalLiabilities")),
                    total_equity=_safe_float(r.get("totalShareholderEquity")),
                    cash_and_equivalents=_safe_float(r.get("cashAndCashEquivalentsAtCarryingValue")),
                    total_debt=_safe_float(r.get("shortLongTermDebtTotal")),
                    total_current_assets=_safe_float(r.get("totalCurrentAssets")),
                    total_current_liabilities=_safe_float(r.get("totalCurrentLiabilities")),
                ))
            elif function == "CASH_FLOW":
                data.cash_flows.append(CashFlowStatement(
                    period=period, fiscal_date=period,
                    operating_cash_flow=_safe_float(r.get("operatingCashflow")),
                    capital_expenditure=_safe_float(r.get("capitalExpenditures")),
                    dividends_paid=_safe_float(r.get("dividendPayout")),
                    share_repurchases=_safe_float(r.get("commonStockRepurchased")),
                    net_change_in_cash=_safe_float(r.get("changeInCashAndCashEquivalents")),
                ))
                # Compute FCF
                if data.cash_flows[-1].operating_cash_flow is not None and \
                   data.cash_flows[-1].capital_expenditure is not None:
                    op = data.cash_flows[-1].operating_cash_flow
                    capex = abs(data.cash_flows[-1].capital_expenditure)
                    data.cash_flows[-1].free_cash_flow = op - capex
        return data


def _safe_float(val: Any) -> float | None:
    if val is None or val == "None" or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> int | None:
    if val is None or val == "None" or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
