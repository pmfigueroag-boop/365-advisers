"""
src/data/providers/financials.py
──────────────────────────────────────────────────────────────────────────────
Provider: Financial statements and computed ratios from yfinance.

Produces a FinancialStatements contract with income/balance/cashflow data
and pre-computed profitability, valuation, leverage, and quality ratios.
"""

from __future__ import annotations

import logging
import threading
import pandas as pd
import yfinance as yf

from src.contracts.market_data import (
    FinancialStatements, FinancialRatios,
    ProfitabilityRatios, ValuationRatios,
    LeverageRatios, QualityRatios, CashFlowEntry,
)
from src.utils.helpers import sanitize_data
from src.config import get_settings

logger = logging.getLogger("365advisers.providers.financials")
_settings = get_settings()


def _safe_get(df: pd.DataFrame | None, index_keys: list[str], default=None):
    """Safely retrieve the first available row from a DataFrame."""
    if df is None or df.empty:
        return default
    for k in index_keys:
        if k in df.index:
            val = df.loc[k]
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            try:
                return float(val) if pd.notnull(val) else default
            except (TypeError, ValueError):
                continue
    return default


def _pct_or_none(num, denom):
    if num is not None and denom:
        return num / denom
    return "DATA_INCOMPLETE"


def fetch_financials(ticker: str) -> FinancialStatements:
    """
    Fetch fundamental financial data for a ticker.

    Returns a typed FinancialStatements contract with computed ratios
    and cashflow series.
    """
    symbol = ticker.upper()
    logger.info(f"Fetching financials for {symbol}")

    def _fetch() -> FinancialStatements:
        stock = yf.Ticker(symbol)
        info = stock.info or {}

        # ── Raw financial statements ──────────────────────────────────────
        try:
            is_ = stock.financials
            bs = stock.balance_sheet
            cf = stock.cashflow
        except Exception as exc:
            logger.warning(f"Statement fetch error: {exc}")
            is_, bs, cf = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # ── Derived values ────────────────────────────────────────────────
        total_rev = _safe_get(is_, ["Total Revenue"])
        gross_profit = _safe_get(is_, ["Gross Profit"])
        ebit = _safe_get(is_, ["EBIT", "Operating Income"])
        net_income = _safe_get(is_, ["Net Income"])
        total_assets = _safe_get(bs, ["Total Assets"])
        total_equity = _safe_get(bs, ["Stockholders Equity", "Total Stockholder Equity"])
        total_debt = _safe_get(bs, ["Total Debt", "Long Term Debt"], 0.0)
        free_cash_flow = _safe_get(cf, ["Free Cash Flow"])

        # ── Cashflow series (last 4 years) ────────────────────────────────
        cashflow_series: list[CashFlowEntry] = []
        try:
            latest_fcf = info.get("freeCashflow") or info.get("operatingCashflow")
            if is_ is not None and not is_.empty and "Total Revenue" in is_.index:
                is_cols = list(is_.columns)[:4]
                for i, col in enumerate(is_cols):
                    try:
                        rev = is_.loc["Total Revenue", col]
                        rev_val = float(rev) if pd.notnull(rev) else None
                        year_label = col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4]

                        fcf_val = None
                        if i == 0 and latest_fcf is not None:
                            fcf_val = float(latest_fcf)
                        else:
                            ni_key = [k for k in ["Net Income", "Net Income Common Stockholders"] if k in is_.index]
                            if ni_key:
                                ni = is_.loc[ni_key[0], col]
                                fcf_val = float(ni) if pd.notnull(ni) else None

                        if rev_val is not None or fcf_val is not None:
                            cashflow_series.append(CashFlowEntry(
                                year=year_label,
                                fcf=fcf_val or 0.0,
                                revenue=rev_val or 0.0,
                            ))
                    except Exception:
                        continue
                cashflow_series.sort(key=lambda x: x.year)
        except Exception as cf_exc:
            logger.warning(f"Cashflow series build error: {cf_exc}")

        # ── Compute ratios ────────────────────────────────────────────────
        profitability = ProfitabilityRatios(
            gross_margin=_pct_or_none(gross_profit, total_rev),
            ebit_margin=_pct_or_none(ebit, total_rev),
            net_margin=_pct_or_none(net_income, total_rev),
            roe=_pct_or_none(net_income, total_equity),
            roic=(ebit * 0.75 / (total_debt + total_equity))
                if ebit and (total_debt + (total_equity or 0)) else "DATA_INCOMPLETE",
        )

        valuation = ValuationRatios(
            pe_ratio=info.get("trailingPE") or info.get("forwardPE") or "DATA_INCOMPLETE",
            pb_ratio=info.get("priceToBook") or "DATA_INCOMPLETE",
            ev_ebitda=info.get("enterpriseToEbitda") or "DATA_INCOMPLETE",
            fcf_yield=_pct_or_none(free_cash_flow, info.get("marketCap")),
            market_cap=info.get("marketCap"),
        )

        leverage = LeverageRatios(
            debt_to_equity=_pct_or_none(total_debt, total_equity),
            interest_coverage=info.get("operatingCashflow") or "DATA_INCOMPLETE",
            current_ratio=info.get("currentRatio") or "DATA_INCOMPLETE",
            quick_ratio=info.get("quickRatio") or "DATA_INCOMPLETE",
        )

        quality = QualityRatios(
            revenue_growth_yoy=info.get("revenueGrowth") or "DATA_INCOMPLETE",
            earnings_growth_yoy=info.get("earningsGrowth") or "DATA_INCOMPLETE",
            dividend_yield=info.get("dividendYield") or 0.0,
            payout_ratio=info.get("payoutRatio") or 0.0,
            beta=info.get("beta") or "DATA_INCOMPLETE",
        )

        return FinancialStatements(
            ticker=symbol,
            name=info.get("shortName") or info.get("longName") or symbol,
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            description=info.get("longBusinessSummary", ""),
            ratios=FinancialRatios(
                profitability=profitability,
                valuation=valuation,
                leverage=leverage,
                quality=quality,
            ),
            cashflow_series=cashflow_series,
            info=info,
        )

    # ── Execute with timeout ──────────────────────────────────────────────
    result_container: dict = {}

    def _thread_target():
        try:
            result_container["data"] = _fetch()
        except Exception as e:
            result_container["error"] = e

    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    t.join(timeout=_settings.YFINANCE_TIMEOUT)

    if t.is_alive():
        logger.error(f"Financials for {symbol} timed out after {_settings.YFINANCE_TIMEOUT}s")
        return FinancialStatements(ticker=symbol, name=symbol)

    if "error" in result_container:
        logger.error(f"Financials error for {symbol}: {result_container['error']}")
        return FinancialStatements(ticker=symbol, name=symbol)

    return result_container.get("data", FinancialStatements(ticker=symbol, name=symbol))
