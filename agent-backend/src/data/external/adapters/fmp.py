"""
src/data/external/adapters/fmp.py
──────────────────────────────────────────────────────────────────────────────
Financial Modeling Prep (FMP) Adapter — comprehensive fundamental data.

Provides:
  - Company profile
  - Financial statements (income, balance sheet, cash flow)
  - Financial ratios and key metrics
  - Analyst estimates and recommendations
  - DCF valuation

Rate limiting: Free = 250 req/day.
               Starter = 300 req/min.

Docs: https://site.financialmodelingprep.com/developer/docs
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
from src.data.external.contracts.asset_profile import AssetProfile
from src.data.external.contracts.financial_statement import (
    FinancialStatementData,
    IncomeStatement,
    BalanceSheet,
    CashFlowStatement,
)
from src.data.external.contracts.financial_ratios import FinancialRatios
from src.data.external.contracts.analyst_estimate import (
    AnalystEstimateData,
    EarningsEstimate,
    RevenueEstimate,
    PriceTarget,
)

logger = logging.getLogger("365advisers.external.fmp")

_FMP_BASE = "https://financialmodelingprep.com/api/v3"


class FMPAdapter(ProviderAdapter):
    """
    Adapter for Financial Modeling Prep REST API.

    Primary fundamental data provider: profiles, financials, ratios,
    analyst estimates, and DCF.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.FMP_API_KEY
        self._timeout = settings.EDPL_FMP_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=_FMP_BASE,
            timeout=self._timeout,
        )

    @property
    def name(self) -> str:
        return "fmp"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.FUNDAMENTAL

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.FINANCIAL_STATEMENTS,
            ProviderCapability.FINANCIAL_RATIOS,
            ProviderCapability.ANALYST_ESTIMATES,
            ProviderCapability.COMPANY_PROFILE,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Fetch fundamental data from FMP.

        Expected request.params:
          - endpoint: str — "profile", "income-statement", "balance-sheet-statement",
                           "cash-flow-statement", "ratios-ttm", "analyst-estimates"
                           Default: "profile"
          - period: str — "annual" or "quarter" (for statements). Default: "annual"
          - limit: int — max results. Default: 8
        """
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")
        if not self._api_key:
            return self._error_response("FMP_API_KEY not configured")

        endpoint = request.params.get("endpoint", "profile")
        period = request.params.get("period", "annual")
        limit = request.params.get("limit", 8)
        t0 = time.perf_counter()

        try:
            url = f"/{endpoint}/{ticker}"
            params: dict[str, Any] = {"apikey": self._api_key}
            if endpoint in ("income-statement", "balance-sheet-statement", "cash-flow-statement"):
                params["period"] = period
                params["limit"] = limit

            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            raw = resp.json()

            if isinstance(raw, dict) and raw.get("Error Message"):
                elapsed = (time.perf_counter() - t0) * 1000
                return self._error_response(raw["Error Message"], latency_ms=elapsed)

            data = self._transform(endpoint, ticker, raw)
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(f"Timeout after {self._timeout}s", latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"FMP error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get(
                "/profile/AAPL", params={"apikey": self._api_key},
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

    # ── Transformers ──────────────────────────────────────────────────────

    def _transform(self, endpoint: str, ticker: str, raw: Any) -> Any:
        if endpoint == "profile":
            return self._transform_profile(ticker, raw)
        elif endpoint == "income-statement":
            return self._transform_income(ticker, raw)
        elif endpoint == "balance-sheet-statement":
            return self._transform_balance(ticker, raw)
        elif endpoint == "cash-flow-statement":
            return self._transform_cashflow(ticker, raw)
        elif endpoint in ("ratios-ttm", "ratios"):
            return self._transform_ratios(ticker, raw)
        elif endpoint == "analyst-estimates":
            return self._transform_estimates(ticker, raw)
        return raw

    def _transform_profile(self, ticker: str, raw: list | dict) -> AssetProfile:
        p = raw[0] if isinstance(raw, list) and raw else raw if isinstance(raw, dict) else {}
        return AssetProfile(
            ticker=ticker,
            name=p.get("companyName", ""),
            exchange=p.get("exchangeShortName", ""),
            currency=p.get("currency", "USD"),
            country=p.get("country", ""),
            sector=p.get("sector", ""),
            industry=p.get("industry", ""),
            description=p.get("description", ""),
            website=p.get("website", ""),
            logo_url=p.get("image"),
            market_cap=_sf(p.get("mktCap")),
            enterprise_value=_sf(p.get("enterpriseValue")),
            shares_outstanding=_sf(p.get("sharesOutstanding")),
            employees=_si(p.get("fullTimeEmployees")),
            ipo_date=p.get("ipoDate"),
            is_actively_traded=p.get("isActivelyTrading", True),
            source="fmp",
            fetched_at=datetime.now(timezone.utc),
        )

    def _transform_income(self, ticker: str, raw: list) -> FinancialStatementData:
        items = raw if isinstance(raw, list) else []
        stmts = []
        for r in items[:12]:
            stmts.append(IncomeStatement(
                period=r.get("period", "") + " " + r.get("calendarYear", ""),
                fiscal_date=r.get("date", ""),
                currency=r.get("reportedCurrency", "USD"),
                revenue=_sf(r.get("revenue")),
                cost_of_revenue=_sf(r.get("costOfRevenue")),
                gross_profit=_sf(r.get("grossProfit")),
                operating_expenses=_sf(r.get("operatingExpenses")),
                operating_income=_sf(r.get("operatingIncome")),
                ebitda=_sf(r.get("ebitda")),
                net_income=_sf(r.get("netIncome")),
                eps=_sf(r.get("eps")),
                eps_diluted=_sf(r.get("epsdiluted")),
                shares_outstanding=_sf(r.get("weightedAverageShsOut")),
                shares_diluted=_sf(r.get("weightedAverageShsOutDil")),
                revenue_growth=_sf(r.get("revenueGrowth")),
            ))
        return FinancialStatementData(
            ticker=ticker, income_statements=stmts,
            source="fmp", fetched_at=datetime.now(timezone.utc),
        )

    def _transform_balance(self, ticker: str, raw: list) -> FinancialStatementData:
        items = raw if isinstance(raw, list) else []
        sheets = []
        for r in items[:12]:
            sheets.append(BalanceSheet(
                period=r.get("period", "") + " " + r.get("calendarYear", ""),
                fiscal_date=r.get("date", ""),
                currency=r.get("reportedCurrency", "USD"),
                total_assets=_sf(r.get("totalAssets")),
                total_liabilities=_sf(r.get("totalLiabilities")),
                total_equity=_sf(r.get("totalStockholdersEquity")),
                cash_and_equivalents=_sf(r.get("cashAndCashEquivalents")),
                total_debt=_sf(r.get("totalDebt")),
                net_debt=_sf(r.get("netDebt")),
                total_current_assets=_sf(r.get("totalCurrentAssets")),
                total_current_liabilities=_sf(r.get("totalCurrentLiabilities")),
                inventory=_sf(r.get("inventory")),
                goodwill=_sf(r.get("goodwill")),
            ))
        return FinancialStatementData(
            ticker=ticker, balance_sheets=sheets,
            source="fmp", fetched_at=datetime.now(timezone.utc),
        )

    def _transform_cashflow(self, ticker: str, raw: list) -> FinancialStatementData:
        items = raw if isinstance(raw, list) else []
        cfs = []
        for r in items[:12]:
            op = _sf(r.get("operatingCashFlow"))
            capex = _sf(r.get("capitalExpenditure"))
            fcf = _sf(r.get("freeCashFlow"))
            if fcf is None and op is not None and capex is not None:
                fcf = op - abs(capex)
            cfs.append(CashFlowStatement(
                period=r.get("period", "") + " " + r.get("calendarYear", ""),
                fiscal_date=r.get("date", ""),
                currency=r.get("reportedCurrency", "USD"),
                operating_cash_flow=op,
                capital_expenditure=capex,
                free_cash_flow=fcf,
                dividends_paid=_sf(r.get("dividendsPaid")),
                share_repurchases=_sf(r.get("commonStockRepurchased")),
                net_change_in_cash=_sf(r.get("netChangeInCash")),
            ))
        return FinancialStatementData(
            ticker=ticker, cash_flows=cfs,
            source="fmp", fetched_at=datetime.now(timezone.utc),
        )

    def _transform_ratios(self, ticker: str, raw: list | dict) -> FinancialRatios:
        r = raw[0] if isinstance(raw, list) and raw else raw if isinstance(raw, dict) else {}
        return FinancialRatios(
            ticker=ticker,
            pe_ratio=_sf(r.get("peRatioTTM", r.get("priceEarningsRatio"))),
            pb_ratio=_sf(r.get("priceToBookRatioTTM", r.get("priceToBookRatio"))),
            ps_ratio=_sf(r.get("priceToSalesRatioTTM", r.get("priceToSalesRatio"))),
            ev_to_ebitda=_sf(r.get("enterpriseValueOverEBITDATTM")),
            peg_ratio=_sf(r.get("pegRatioTTM", r.get("pegRatio"))),
            price_to_fcf=_sf(r.get("priceToFreeCashFlowsRatioTTM")),
            gross_margin=_sf(r.get("grossProfitMarginTTM", r.get("grossProfitMargin"))),
            operating_margin=_sf(r.get("operatingProfitMarginTTM")),
            net_margin=_sf(r.get("netProfitMarginTTM", r.get("netProfitMargin"))),
            roe=_sf(r.get("returnOnEquityTTM", r.get("returnOnEquity"))),
            roa=_sf(r.get("returnOnAssetsTTM", r.get("returnOnAssets"))),
            roic=_sf(r.get("returnOnCapitalEmployedTTM")),
            current_ratio=_sf(r.get("currentRatioTTM", r.get("currentRatio"))),
            quick_ratio=_sf(r.get("quickRatioTTM", r.get("quickRatio"))),
            debt_to_equity=_sf(r.get("debtEquityRatioTTM", r.get("debtEquityRatio"))),
            dividend_yield=_sf(r.get("dividendYielTTM", r.get("dividendYield"))),
            payout_ratio=_sf(r.get("payoutRatioTTM", r.get("payoutRatio"))),
            source="fmp",
            fetched_at=datetime.now(timezone.utc),
        )

    def _transform_estimates(self, ticker: str, raw: list) -> AnalystEstimateData:
        items = raw if isinstance(raw, list) else []
        earnings = []
        revenues = []
        for r in items[:8]:
            date = r.get("date", "")
            earnings.append(EarningsEstimate(
                period=date,
                consensus_eps=_sf(r.get("estimatedEpsAvg")),
                high_eps=_sf(r.get("estimatedEpsHigh")),
                low_eps=_sf(r.get("estimatedEpsLow")),
                num_analysts=_si(r.get("numberAnalystEstimatedEps")),
            ))
            revenues.append(RevenueEstimate(
                period=date,
                consensus_revenue=_sf(r.get("estimatedRevenueAvg")),
                high_revenue=_sf(r.get("estimatedRevenueHigh")),
                low_revenue=_sf(r.get("estimatedRevenueLow")),
                num_analysts=_si(r.get("numberAnalystsEstimatedRevenue")),
            ))
        return AnalystEstimateData(
            ticker=ticker,
            earnings_estimates=earnings,
            revenue_estimates=revenues,
            source="fmp",
            fetched_at=datetime.now(timezone.utc),
        )


def _sf(val: Any) -> float | None:
    """Safe float conversion."""
    if val is None or val == "" or val == "None":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _si(val: Any) -> int | None:
    """Safe int conversion."""
    if val is None or val == "" or val == "None":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
