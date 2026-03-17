"""
src/engines/backtesting/fundamental_provider.py
--------------------------------------------------------------------------
Fetches historical quarterly financials from yfinance and builds
date-keyed fundamental snapshots for the walk-forward evaluator.

Each snapshot maps FundamentalFeatureSet attribute names to float values,
forward-filled from the quarterly release date until the next release.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
import yfinance as yf

logger = logging.getLogger("365advisers.backtesting.fundamental_provider")


# ---------------------------------------------------------------------------
# yfinance field name mappings
# ---------------------------------------------------------------------------

# Income Statement fields
_IS_TOTAL_REVENUE = "Total Revenue"
_IS_GROSS_PROFIT = "Gross Profit"
_IS_OPERATING_INCOME = "Operating Income"
_IS_EBIT = "EBIT"
_IS_EBITDA = "EBITDA"
_IS_NET_INCOME = "Net Income"
_IS_DILUTED_EPS = "Diluted EPS"

# Balance Sheet fields
_BS_TOTAL_ASSETS = "Total Assets"
_BS_TOTAL_DEBT = "Total Debt"
_BS_STOCKHOLDERS_EQUITY = "Stockholders Equity"
_BS_INVESTED_CAPITAL = "Invested Capital"
_BS_CURRENT_ASSETS = "Current Assets"
_BS_CURRENT_LIABILITIES = "Current Liabilities"
_BS_COMMON_STOCK_EQUITY = "Common Stock Equity"

# Cash Flow fields
_CF_FREE_CASH_FLOW = "Free Cash Flow"
_CF_OPERATING_CASH_FLOW = "Operating Cash Flow"
_CF_CAPITAL_EXPENDITURE = "Capital Expenditure"
_CF_DIVIDENDS_PAID = "Cash Dividends Paid"
_CF_BUYBACKS = "Repurchase Of Capital Stock"
_CF_DEBT_REPAYMENT = "Repayment Of Debt"


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Safe division returning None if inputs are invalid."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0 or math.isnan(denominator) or math.isnan(numerator):
        return None
    return numerator / denominator


def _get_field(frame: pd.DataFrame, field: str, col) -> float | None:
    """Safely extract a value from a yfinance statement DataFrame."""
    try:
        if field in frame.index:
            val = frame.loc[field, col]
            if pd.notna(val):
                return float(val)
    except Exception:
        pass
    return None


class FundamentalProvider:
    """
    Builds historical fundamental snapshots from yfinance quarterly data.

    Usage::

        provider = FundamentalProvider()
        snapshots = provider.get_snapshots("AAPL", start_date, end_date)
        # snapshots = {"2024-03-28": {"pe_ratio": 28.5, "roic": 0.32, ...}, ...}
    """

    def __init__(self, cache_enabled: bool = True) -> None:
        self._cache: dict[str, dict[str, dict[str, float]]] = {}
        self._cache_enabled = cache_enabled

    def get_snapshots(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        ohlcv: pd.DataFrame | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Fetch quarterly financials and build date-keyed snapshots.

        Parameters
        ----------
        ticker : str
            Stock symbol.
        start_date, end_date : date
            Period for which to generate daily snapshots.
        ohlcv : pd.DataFrame | None
            Optional OHLCV data for price-derived metrics (PE, PB, etc.).

        Returns
        -------
        dict[str, dict[str, float]]
            Mapping of "YYYY-MM-DD" -> {attr_name: value}.
            Forward-filled daily from quarterly release dates.
        """
        if self._cache_enabled and ticker in self._cache:
            return self._cache[ticker]

        try:
            snapshots = self._build_snapshots(ticker, start_date, end_date, ohlcv)
        except Exception as exc:
            logger.warning(f"FUNDAMENTAL: Failed to fetch {ticker} -- {exc}")
            snapshots = {}

        if self._cache_enabled:
            self._cache[ticker] = snapshots

        return snapshots

    def _build_snapshots(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        ohlcv: pd.DataFrame | None,
    ) -> dict[str, dict[str, float]]:
        """Build quarterly snapshots and forward-fill to daily."""
        t = yf.Ticker(ticker)

        # Fetch all statement types
        income_stmt = t.quarterly_financials
        balance_sheet = t.quarterly_balance_sheet
        cashflow = t.quarterly_cashflow

        if income_stmt is None or income_stmt.empty:
            logger.debug(f"FUNDAMENTAL: No income statement data for {ticker}")
            return {}

        # Get market cap history from OHLCV + shares outstanding
        shares_outstanding = None
        info = t.info or {}
        shares_outstanding = info.get("sharesOutstanding")

        # Build one snapshot per quarterly date
        quarterly_dates = sorted(income_stmt.columns, reverse=False)
        quarterly_snapshots: list[tuple[date, dict[str, float]]] = []

        for q_date in quarterly_dates:
            snap = self._extract_quarter(
                q_date, income_stmt, balance_sheet, cashflow,
                ohlcv, shares_outstanding, info,
            )
            if snap:
                q_d = q_date.date() if hasattr(q_date, "date") else q_date
                quarterly_snapshots.append((q_d, snap))

        if not quarterly_snapshots:
            return {}

        # Sort by date
        quarterly_snapshots.sort(key=lambda x: x[0])

        # Forward-fill to daily
        daily_snapshots: dict[str, dict[str, float]] = {}
        current_snap: dict[str, float] = {}

        # Create date range
        all_days = pd.bdate_range(start=start_date, end=end_date)

        q_idx = 0
        for day in all_days:
            day_d = day.date()

            # Advance to the latest quarterly snapshot available
            while (
                q_idx < len(quarterly_snapshots)
                and quarterly_snapshots[q_idx][0] <= day_d
            ):
                current_snap = quarterly_snapshots[q_idx][1].copy()

                # Compute price-dependent metrics if we have OHLCV
                if ohlcv is not None and not ohlcv.empty:
                    day_str_for_price = day_d.isoformat()
                    self._enrich_with_price(current_snap, ohlcv, day_d, shares_outstanding)

                q_idx += 1

            if current_snap:
                daily_snapshots[day_d.isoformat()] = current_snap.copy()

        logger.info(
            f"FUNDAMENTAL: {ticker} -- {len(quarterly_snapshots)} quarters, "
            f"{len(daily_snapshots)} daily snapshots"
        )
        return daily_snapshots

    def _extract_quarter(
        self,
        q_date,
        income_stmt: pd.DataFrame,
        balance_sheet: pd.DataFrame | None,
        cashflow: pd.DataFrame | None,
        ohlcv: pd.DataFrame | None,
        shares_outstanding: float | None,
        info: dict,
    ) -> dict[str, float]:
        """Extract fundamental metrics from a single quarter's data."""
        snap: dict[str, float] = {}

        # --- Income Statement ---
        revenue = _get_field(income_stmt, _IS_TOTAL_REVENUE, q_date)
        gross_profit = _get_field(income_stmt, _IS_GROSS_PROFIT, q_date)
        operating_income = _get_field(income_stmt, _IS_OPERATING_INCOME, q_date)
        ebit = _get_field(income_stmt, _IS_EBIT, q_date)
        ebitda = _get_field(income_stmt, _IS_EBITDA, q_date)
        net_income = _get_field(income_stmt, _IS_NET_INCOME, q_date)

        # Margins (quarterly, annualized later if needed)
        if revenue and revenue > 0:
            if gross_profit is not None:
                snap["gross_margin"] = gross_profit / revenue
            if operating_income is not None:
                snap["ebit_margin"] = operating_income / revenue
            if net_income is not None:
                snap["net_margin"] = net_income / revenue

        # --- Balance Sheet ---
        bs = balance_sheet
        if bs is not None and not bs.empty:
            total_assets = _get_field(bs, _BS_TOTAL_ASSETS, q_date)
            total_debt = _get_field(bs, _BS_TOTAL_DEBT, q_date)
            equity = _get_field(bs, _BS_STOCKHOLDERS_EQUITY, q_date)
            invested_capital = _get_field(bs, _BS_INVESTED_CAPITAL, q_date)
            current_assets = _get_field(bs, _BS_CURRENT_ASSETS, q_date)
            current_liab = _get_field(bs, _BS_CURRENT_LIABILITIES, q_date)

            # Leverage
            dte = _safe_div(total_debt, equity)
            if dte is not None:
                snap["debt_to_equity"] = dte

            if ebitda and ebitda > 0 and total_debt is not None:
                snap["debt_to_ebitda"] = total_debt / (ebitda * 4)  # annualise

            # Liquidity
            cr = _safe_div(current_assets, current_liab)
            if cr is not None:
                snap["current_ratio"] = cr

            # Profitability
            # ROIC = NOPAT / Invested Capital (annualised)
            if invested_capital and invested_capital > 0 and ebit is not None:
                nopat = ebit * 0.75  # rough 25% tax estimate
                snap["roic"] = (nopat * 4) / invested_capital  # annualise

            # ROE = Net Income / Equity (annualised)
            roe = _safe_div(net_income, equity)
            if roe is not None:
                snap["roe"] = roe * 4  # annualise

            # Asset Turnover = Revenue / Total Assets (annualised)
            at = _safe_div(revenue, total_assets)
            if at is not None:
                snap["asset_turnover"] = at * 4  # annualise

        # --- Cash Flow ---
        if cashflow is not None and not cashflow.empty:
            fcf = _get_field(cashflow, _CF_FREE_CASH_FLOW, q_date)
            ocf = _get_field(cashflow, _CF_OPERATING_CASH_FLOW, q_date)
            capex = _get_field(cashflow, _CF_CAPITAL_EXPENDITURE, q_date)
            dividends_paid = _get_field(cashflow, _CF_DIVIDENDS_PAID, q_date)
            buybacks = _get_field(cashflow, _CF_BUYBACKS, q_date)
            debt_repayment = _get_field(cashflow, _CF_DEBT_REPAYMENT, q_date)

            # Store annualised FCF for yield calculation later
            if fcf is not None:
                snap["_fcf_annual"] = fcf * 4  # annualise quarterly

            # Shareholder yield components (annualised)
            # dividends_paid and buybacks are typically negative in yfinance
            div_yield_abs = abs(dividends_paid) if dividends_paid else 0
            buyback_abs = abs(buybacks) if buybacks else 0
            debt_repay_abs = abs(debt_repayment) if debt_repayment else 0
            snap["_shareholder_return_annual"] = (
                div_yield_abs + buyback_abs + debt_repay_abs
            ) * 4  # annualise

        # Store raw fields for price-based calcs
        if net_income is not None:
            snap["_net_income_annual"] = net_income * 4
        if ebit is not None:
            snap["_ebit_annual"] = ebit * 4
        if ebitda is not None:
            snap["_ebitda_annual"] = ebitda * 4
        if revenue is not None:
            snap["_revenue_annual"] = revenue * 4

        return snap

    def _enrich_with_price(
        self,
        snap: dict[str, float],
        ohlcv: pd.DataFrame,
        target_date: date,
        shares_outstanding: float | None,
    ) -> None:
        """Add price-dependent metrics (PE, PB, FCF Yield, EV/EBITDA, etc.)."""
        # Find closest price
        close_col = "Close"
        if close_col not in ohlcv.columns:
            return

        close_series = ohlcv[close_col]
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]

        # Find nearest available date
        target_ts = pd.Timestamp(target_date)
        idx = close_series.index.get_indexer([target_ts], method="ffill")
        if idx[0] < 0:
            idx = close_series.index.get_indexer([target_ts], method="bfill")
        if idx[0] < 0 or idx[0] >= len(close_series):
            return

        price = float(close_series.iloc[idx[0]])
        if price <= 0:
            return

        if shares_outstanding and shares_outstanding > 0:
            market_cap = price * shares_outstanding
            snap["market_cap"] = market_cap

            # PE Ratio
            net_inc = snap.get("_net_income_annual")
            if net_inc and net_inc > 0:
                eps = net_inc / shares_outstanding
                snap["pe_ratio"] = price / eps

            # PB Ratio (requires equity from balance sheet)
            # We can approximate: PB = Market Cap / Equity
            # but equity is not directly in snap — we'd need it from _extract
            # For now, skip PB if not computable

            # FCF Yield = FCF / Market Cap
            fcf_annual = snap.get("_fcf_annual")
            if fcf_annual is not None:
                snap["fcf_yield"] = fcf_annual / market_cap

            # EV = Market Cap + Total Debt - Cash
            # Simplified: use market cap as proxy
            ebitda_annual = snap.get("_ebitda_annual")
            if ebitda_annual and ebitda_annual > 0:
                ev = market_cap  # simplified, no debt/cash adjustment
                snap["ev_ebitda"] = ev / ebitda_annual

            # EV/Revenue
            revenue_annual = snap.get("_revenue_annual")
            if revenue_annual and revenue_annual > 0:
                snap["ev_revenue"] = market_cap / revenue_annual

            # EBIT/EV (Greenblatt earnings yield)
            ebit_annual = snap.get("_ebit_annual")
            if ebit_annual and market_cap > 0:
                snap["ebit_ev"] = ebit_annual / market_cap

            # Dividend Yield
            shareholder_return = snap.get("_shareholder_return_annual", 0)
            if shareholder_return > 0:
                snap["shareholder_yield"] = shareholder_return / market_cap

            # Dividend yield alone (rough: from total dividends paid)
            # We use the component if available
            if "_shareholder_return_annual" in snap:
                # Very rough approximation
                snap["dividend_yield"] = snap.get("shareholder_yield", 0) * 0.5

        # Clean up internal fields
        for key in list(snap.keys()):
            if key.startswith("_"):
                del snap[key]

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
