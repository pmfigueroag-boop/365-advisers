"""
src/data/market_data.py
─────────────────────────────────────────────────────────────────────────────
MarketDataFetcher — the single source of truth for all external data.

Provides two independent fetch paths:
  - fetch_fundamental_data(ticker) → fundamentals + company info
  - fetch_technical_data(ticker)   → OHLCV + computed indicators + TV data

Each path can be called independently, allowing the Fundamental Engine
and Technical Engine to operate without fetching each other's data.

Also provides:
  - fetch_company_info(ticker)  → lightweight name/price/exchange lookup
"""

from __future__ import annotations

import os
import logging
import pandas as pd
import yfinance as yf
from tradingview_ta import TA_Handler, Interval

from src.utils.helpers import sanitize_data
from src.utils.exchange_resolver import resolve_exchange, resolve_screener
from src.config import get_settings

import asyncio
from src.data.external.adapters.alpha_vantage import AlphaVantageAdapter
from src.data.external.adapters.fmp import FMPAdapter
from src.data.external.adapters.polygon import PolygonAdapter
from src.data.external.adapters.twelve_data import TwelveDataAdapter
from src.data.external.base import ProviderRequest, DataDomain
from src.data.cache import get_cache, TTL_FUNDAMENTAL, TTL_TECHNICAL

logger = logging.getLogger("365advisers.market_data")
_settings = get_settings()


# ─── Types (inline TypedDicts for clear contracts) ───────────────────────────

# These are documentary; full TypedDicts live in src/utils/types.py (Phase 3)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _resolve_exchange(exchange_code: str) -> str:
    """Legacy shim — delegates to centralized resolver."""
    return resolve_exchange(exchange_code)


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


def _get_tv_indicator(inds: dict, keys: str | list, default: float = 0.0) -> float:
    """Extract a float indicator from a TradingView indicators dict."""
    if isinstance(keys, str):
        keys = [keys]
    for k in keys:
        if k in inds and inds[k] is not None:
            try:
                return float(inds[k])
            except (TypeError, ValueError):
                continue
    return default


# ─── Company Info (lightweight, used by /ticker-info) ────────────────────────

def fetch_company_info(ticker: str) -> dict:
    """
    Fast lookup: name, price, exchange, sector.
    Used by /ticker-info endpoint and watchlist population.
    """
    try:
        info = yf.Ticker(ticker.upper()).info or {}
        return sanitize_data({
            "ticker": ticker.upper(),
            "name": info.get("shortName") or info.get("longName") or ticker,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "exchange": info.get("exchange", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
        })
    except Exception as exc:
        logger.warning(f"fetch_company_info error for {ticker}: {exc}")
        return {"ticker": ticker.upper(), "name": ticker, "price": None}


# ─── Fallback Helpers ─────────────────────────────────────────────────────────

def _fallback_fundamental(symbol: str) -> dict | None:
    """Fallback to EDPL: Alpha Vantage -> FMP."""
    adapters = [
        ("alpha_vantage", AlphaVantageAdapter, DataDomain.MARKET_DATA, {"function": "OVERVIEW"}),
        ("fmp", FMPAdapter, DataDomain.FUNDAMENTAL, {"endpoint": "profile"})
    ]
    for name, adapter_cls, domain, params in adapters:
        try:
            adapter = adapter_cls()
            req = ProviderRequest(ticker=symbol, domain=domain, params=params)
            resp = asyncio.run(adapter.fetch(req))
            if resp.ok and resp.data:
                prof = resp.data
                return sanitize_data({
                    "ticker": symbol,
                    "name": getattr(prof, "name", symbol) or symbol,
                    "info": {"longBusinessSummary": getattr(prof, "description", ""), "marketCap": getattr(prof, "market_cap", None)},
                    "ratios": {
                        "valuation": {"market_cap": getattr(prof, "market_cap", None)},
                        "profitability": {}, "leverage": {}, "quality": {}
                    },
                    "cashflow_series": [],
                    "description": getattr(prof, "description", "") or "",
                    "sector": getattr(prof, "sector", "") or "",
                    "industry": getattr(prof, "industry", "") or "",
                    "_fallback": name,
                })
        except Exception as e:
            logger.debug(f"{name} fundamental fallback failed for {symbol}: {e}")
    return None

def _fallback_technical_ohlcv(symbol: str) -> tuple[dict, pd.DataFrame]:
    """Fallback to EDPL: Polygon -> Alpha Vantage -> Twelve Data."""
    adapters = [
        ("polygon", PolygonAdapter, DataDomain.MARKET_DATA, {"resolution": "day", "days_back": 180}),
        ("alpha_vantage", AlphaVantageAdapter, DataDomain.MARKET_DATA, {"function": "TIME_SERIES_DAILY", "outputsize": "compact"}),
        ("twelve_data", TwelveDataAdapter, DataDomain.MARKET_DATA, {"interval": "1day", "outputsize": 180})
    ]
    for name, adapter_cls, domain, params in adapters:
        try:
            adapter = adapter_cls()
            req = ProviderRequest(ticker=symbol, domain=domain, params=params)
            resp = asyncio.run(adapter.fetch(req))
            if resp.ok and resp.data and hasattr(resp.data, 'intraday_bars'):
                bars = resp.data.intraday_bars
                if bars:
                    df = pd.DataFrame([
                        {"Open": b.open, "High": b.high, "Low": b.low, "Close": b.close, "Volume": b.volume}
                        for b in bars
                    ], index=[b.timestamp for b in bars])
                    df = df.sort_index()
                    return {"_fallback": name}, df
        except Exception as e:
            logger.debug(f"{name} technical fallback failed for {symbol}: {e}")
    return {}, pd.DataFrame()


# ─── Fundamental Data ─────────────────────────────────────────────────────────

def fetch_fundamental_data(ticker: str, force_refresh: bool = False) -> dict:
    """
    Fetch data required by the Fundamental Engine.
    Uses TTL cache (30 min) to avoid redundant yfinance calls.

    Parameters
    ----------
    ticker : str
        Stock symbol.
    force_refresh : bool
        If True, bypass cache and fetch fresh data.
    """
    symbol = ticker.upper()
    cache = get_cache()

    # Check cache first
    if not force_refresh:
        entry = cache.get(symbol, "fundamental")
        if entry is not None:
            logger.info(f"CACHE HIT: fundamental data for {symbol} (age={entry.age_seconds}s)")
            result = dict(entry.data)  # shallow copy
            result["_data_freshness"] = entry.freshness.to_dict()
            return result

    logger.info(f"Fetching fundamental data for {symbol} (force_refresh={force_refresh})")

    def _fetch():
        stock = yf.Ticker(symbol)
        info = stock.info or {}

        # ── Raw financial statements ──────────────────────────────────────────
        try:
            is_ = stock.financials         # Income statement (annual)
            bs = stock.balance_sheet       # Balance sheet (annual)
            cf = stock.cashflow            # Cash flow statement (annual)
        except Exception as exc:
            logger.warning(f"Statement fetch error: {exc}")
            is_, bs, cf = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # ── Derived values ────────────────────────────────────────────────────
        total_rev    = _safe_get(is_, ["Total Revenue"])
        gross_profit = _safe_get(is_, ["Gross Profit"])
        ebit         = _safe_get(is_, ["EBIT", "Operating Income"])
        net_income   = _safe_get(is_, ["Net Income"])
        total_assets = _safe_get(bs, ["Total Assets"])
        total_equity = _safe_get(bs, ["Stockholders Equity", "Total Stockholder Equity"])
        total_debt   = _safe_get(bs, ["Total Debt", "Long Term Debt"], 0.0)
        free_cash_flow = _safe_get(cf, ["Free Cash Flow"])
        interest_expense = _safe_get(is_, ["Interest Expense", "Interest Expense Non Operating"])
        capex        = _safe_get(cf, ["Capital Expenditure", "CapitalExpenditure"])
        repurchase   = _safe_get(cf, ["Repurchase Of Capital Stock", "RepurchaseOfCapitalStock", "Repurchase Of Stock"])

        # ── Clean cashflow series for chart (last 4 years) ───────────────────
        # Strategy: Build from income statement columns (reliable) + info for FCF.
        # stock.cashflow is known to return (0,0) in yfinance>=0.2.x for many tickers.
        cashflow_series = []
        try:
            # Latest FCF from info dict (most reliable single-point source)
            latest_fcf = info.get("freeCashflow") or info.get("operatingCashflow")

            if is_ is not None and not is_.empty and "Total Revenue" in is_.index:
                is_cols = list(is_.columns)[:4]  # Most recent 4 years
                for i, col in enumerate(is_cols):
                    try:
                        rev = is_.loc["Total Revenue", col]
                        rev_val = float(rev) if pd.notnull(rev) else None
                        year_label = col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4]

                        # FCF: use info value for latest year, net income proxy for older years
                        fcf_val = None
                        if i == 0 and latest_fcf is not None:
                            fcf_val = float(latest_fcf)
                        else:
                            # Estimate FCF ≈ net income as proxy for older years
                            ni_key = [k for k in ["Net Income", "Net Income Common Stockholders"] if k in is_.index]
                            if ni_key:
                                ni = is_.loc[ni_key[0], col]
                                fcf_val = float(ni) if pd.notnull(ni) else None

                        # Extract net_income for earnings stability
                        ni_val = 0.0
                        ni_keys = [k for k in ["Net Income", "Net Income Common Stockholders"] if k in is_.index]
                        if ni_keys:
                            _ni = is_.loc[ni_keys[0], col]
                            ni_val = float(_ni) if pd.notnull(_ni) else 0.0

                        # Extract EBIT for debt coverage
                        ebit_val = 0.0
                        ebit_keys = [k for k in ["EBIT", "Operating Income"] if k in is_.index]
                        if ebit_keys:
                            _eb = is_.loc[ebit_keys[0], col]
                            ebit_val = float(_eb) if pd.notnull(_eb) else 0.0

                        # Extract operating cashflow
                        ocf_val = 0.0
                        if cf is not None and not cf.empty:
                            ocf_keys = [k for k in ["Total Cash From Operating Activities",
                                                      "Operating Cash Flow",
                                                      "Cash Flow From Continuing Operating Activities"] if k in cf.index]
                            if ocf_keys and col in cf.columns:
                                _ocf = cf.loc[ocf_keys[0], col]
                                ocf_val = float(_ocf) if pd.notnull(_ocf) else 0.0

                        if rev_val is not None or fcf_val is not None:
                            cashflow_series.append({
                                "year": year_label,
                                "fcf": fcf_val or 0.0,
                                "revenue": rev_val or 0.0,
                                "net_income": ni_val,
                                "ebit": ebit_val,
                                "operating_cashflow": ocf_val,
                            })
                    except Exception:
                        continue
                # Sort ascending (oldest → newest)
                cashflow_series.sort(key=lambda x: x["year"])
        except Exception as cf_exc:
            logger.warning(f"cashflow_series build error: {cf_exc}")

        def pct_or_none(num, denom):
            if num is not None and denom:
                return num / denom
            return "DATA_INCOMPLETE"

        ratios = {
            "profitability": {
                "gross_margin":  pct_or_none(gross_profit, total_rev),
                "ebit_margin":   pct_or_none(ebit, total_rev),
                "net_margin":    pct_or_none(net_income, total_rev),
                "roe":           pct_or_none(net_income, total_equity),
                "roic":          (ebit * 0.75 / (total_debt + total_equity))
                                 if ebit and (total_debt + (total_equity or 0)) else "DATA_INCOMPLETE",
            },
            "valuation": {
                "pe_ratio":      info.get("trailingPE") or info.get("forwardPE") or "DATA_INCOMPLETE",
                "pb_ratio":      info.get("priceToBook") or "DATA_INCOMPLETE",
                "ev_ebitda":     info.get("enterpriseToEbitda") or "DATA_INCOMPLETE",
                "fcf_yield":     pct_or_none(free_cash_flow, info.get("marketCap")),
                "market_cap":    info.get("marketCap"),
            },
            "leverage": {
                "debt_to_equity":     pct_or_none(total_debt, total_equity),
                "interest_coverage":  (ebit / abs(interest_expense))
                                     if ebit and interest_expense and abs(interest_expense) > 0
                                     else "DATA_INCOMPLETE",
                "current_ratio":      info.get("currentRatio") or "DATA_INCOMPLETE",
                "quick_ratio":        info.get("quickRatio") or "DATA_INCOMPLETE",
            },
            "quality": {
                "revenue_growth_yoy": info.get("revenueGrowth") if info.get("revenueGrowth") is not None else "DATA_INCOMPLETE",
                "earnings_growth_yoy": info.get("earningsGrowth") if info.get("earningsGrowth") is not None else "DATA_INCOMPLETE",
                "dividend_yield":     info.get("dividendYield") if info.get("dividendYield") is not None else 0.0,
                "payout_ratio":       info.get("payoutRatio") if info.get("payoutRatio") is not None else 0.0,
                "beta":               info.get("beta") if info.get("beta") is not None else "DATA_INCOMPLETE",
                "capex_to_revenue":   pct_or_none(abs(capex) if capex is not None else None, total_rev),
                "buyback_yield":      pct_or_none(abs(repurchase) if repurchase is not None else None, info.get("marketCap")),
            },
        }

        return sanitize_data({
            "ticker": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "info": info,
            "ratios": ratios,
            "cashflow_series": cashflow_series,
            "description": info.get("longBusinessSummary", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
        })

    try:
        import threading
        result_container = {}
        def _thread_target():
            try:
                result_container['data'] = _fetch()
            except Exception as e:
                result_container['error'] = e

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()
        t.join(timeout=_settings.YFINANCE_TIMEOUT)

        if t.is_alive():
            logger.error(f"fetch_fundamental_data for {symbol} timed out after {_settings.YFINANCE_TIMEOUT}s")
            fb = _fallback_fundamental(symbol)
            if fb: return fb
            return sanitize_data({
                "ticker": symbol,
                "name": symbol,
                "info": {},
                "ratios": {},
                "cashflow_series": [],
                "error": "Timeout fetching market data from source",
            })
            
        if 'error' in result_container:
            logger.error(f"fetch_fundamental_data error for {symbol}: {result_container['error']}")
            fb = _fallback_fundamental(symbol)
            if fb: return fb
            raise result_container['error']
            
        data = result_container.get('data')
        # P1: Store in cache and add freshness metadata
        if data and "error" not in data:
            cache.set(symbol, "fundamental", data, ttl_seconds=TTL_FUNDAMENTAL)
        freshness = cache.make_live_freshness("fundamental", TTL_FUNDAMENTAL)
        if data:
            data["_data_freshness"] = freshness.to_dict()
        return data

    except Exception as exc:
        logger.error(f"fetch_fundamental_data for {symbol}: {exc}")
        fb = _fallback_fundamental(symbol)
        if fb: return fb
        return sanitize_data({
            "ticker": symbol,
            "name": symbol,
            "info": {},
            "ratios": {},
            "cashflow_series": [],
            "error": str(exc),
        })


# ─── Technical Data ───────────────────────────────────────────────────────────

def fetch_technical_data(ticker: str, force_refresh: bool = False) -> dict:
    """
    Fetch data required by the Technical Engine.
    Uses TTL cache (5 min) to avoid redundant yfinance/TV calls.

    Parameters
    ----------
    ticker : str
        Stock symbol.
    force_refresh : bool
        If True, bypass cache and fetch fresh data.
    """
    symbol = ticker.upper()
    cache = get_cache()

    # Check cache first
    if not force_refresh:
        entry = cache.get(symbol, "technical")
        if entry is not None:
            logger.info(f"CACHE HIT: technical data for {symbol} (age={entry.age_seconds}s)")
            result = dict(entry.data)  # shallow copy
            result["_data_freshness"] = entry.freshness.to_dict()
            return result

    logger.info(f"Fetching technical data for {symbol} (force_refresh={force_refresh})")

    def _fetch_yf():
        stock = yf.Ticker(symbol)
        info = stock.info or {}
        history = stock.history(period="1y")
        return info, history

    ohlcv: list[dict] = []
    history = pd.DataFrame()
    info: dict = {}

    # ── 1. yfinance OHLCV ────────────────────────────────────────────────────
    try:
        import threading
        result_container = {}
        def _thread_target_tech():
            try:
                result_container['data'] = _fetch_yf()
            except Exception as e:
                result_container['error'] = e

        t = threading.Thread(target=_thread_target_tech, daemon=True)
        t.start()
        t.join(timeout=_settings.YFINANCE_TIMEOUT)

        if t.is_alive():
            logger.error(f"fetch_technical_data yfinance for {symbol} timed out.")
            info, history = _fallback_technical_ohlcv(symbol)
        elif 'error' in result_container:
            logger.warning(f"yfinance technical error: {result_container['error']}")
            info, history = _fallback_technical_ohlcv(symbol)
        else:
            info, history = result_container.get('data', ({}, pd.DataFrame()))
            if history.empty:
                logger.warning(f"yfinance returned empty history for {symbol}, trying fallback.")
                info, history = _fallback_technical_ohlcv(symbol)
            
        if not history.empty:
            for idx, row in history.iterrows():
                ohlcv.append({
                    "time":   idx.strftime("%Y-%m-%d"),
                    "open":   float(row["Open"]),
                    "high":   float(row["High"]),
                    "low":    float(row["Low"]),
                    "close":  float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
    except Exception as exc:
        logger.error(f"OHLCV fetch error for {symbol}: {exc}")

    last_price = float(history["Close"].iloc[-1]) if not history.empty else 0.0
    exchange = _resolve_exchange(info.get("exchange", ""))

    # ── 2. TradingView indicators ─────────────────────────────────────────────
    raw_indicators: dict = {}
    tv_summary: dict = {"RECOMMENDATION": "UNKNOWN"}
    tv_oscillators: dict = {}
    tv_moving_averages: dict = {}

    try:
        handler = TA_Handler(
            symbol=symbol,
            screener=resolve_screener(exchange),
            exchange=exchange,
            interval=Interval.INTERVAL_1_DAY,
        )
        import time
        analysis = None
        for attempt in range(3):
            try:
                analysis = handler.get_analysis()
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2 * (attempt + 1))
        inds = analysis.indicators

        raw_indicators = {
            # Trend
            "close":      _get_tv_indicator(inds, ["close", "Close"], last_price),
            "sma20":      _get_tv_indicator(inds, ["SMA20", "EMA20"]),
            "sma50":      _get_tv_indicator(inds, ["SMA50", "EMA50"]),
            "sma200":     _get_tv_indicator(inds, ["SMA200", "EMA200"]),
            "ema20":      _get_tv_indicator(inds, ["EMA20", "SMA20"]),
            # Momentum
            "rsi":        _get_tv_indicator(inds, ["RSI", "RSI[1]"], 50.0),
            "stoch_k":    _get_tv_indicator(inds, ["Stoch.K", "Stoch.K[1]"], 50.0),
            "stoch_d":    _get_tv_indicator(inds, ["Stoch.D", "Stoch.D[1]"], 50.0),
            # MACD
            "macd":       _get_tv_indicator(inds, "MACD.macd"),
            "macd_signal":_get_tv_indicator(inds, "MACD.signal"),
            "macd_hist":  _get_tv_indicator(inds, "MACD.hist"),
            # Volatility
            "bb_upper":   _get_tv_indicator(inds, "BB.upper"),
            "bb_lower":   _get_tv_indicator(inds, "BB.lower"),
            "bb_basis":   _get_tv_indicator(inds, ["BB.basis", "SMA20"]),
            "atr":        _get_tv_indicator(inds, ["ATR", "Average True Range(14)"]),
            # Volume
            "volume":     _get_tv_indicator(inds, "volume"),
            "obv":        _get_tv_indicator(inds, "OBV"),
            # Regime detection (ADX + Directional)
            "adx":        _get_tv_indicator(inds, ["ADX", "ADX+DI[14]"], 20.0),
            "plus_di":    _get_tv_indicator(inds, ["ADX+DI", "DI.plus"], 20.0),
            "minus_di":   _get_tv_indicator(inds, ["ADX-DI", "DI.minus"], 20.0),
            # Extra oscillators
            "cci":        _get_tv_indicator(inds, ["CCI20", "CCI"], 0.0),
            "williams_r": _get_tv_indicator(inds, ["W.R", "W%R"], -50.0),
            # TV recommendation
            "tv_recommendation": analysis.summary.get("RECOMMENDATION", "UNKNOWN"),
        }

        tv_summary        = analysis.summary
        tv_oscillators    = analysis.oscillators
        tv_moving_averages = analysis.moving_averages

    except Exception as exc:
        logger.warning(f"TradingView fetch error for {symbol}: {exc}")
        # Minimal fallback so the Technical Engine can still run
        raw_indicators = {
            "close": last_price, "rsi": 50.0,
            "sma50": 0.0, "sma200": 0.0,
            "macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
            "bb_upper": 0.0, "bb_lower": 0.0, "bb_basis": 0.0,
            "atr": 0.0, "obv": 0.0, "volume": 0.0,
            "stoch_k": 50.0, "stoch_d": 50.0,
            "adx": 20.0, "plus_di": 20.0, "minus_di": 20.0,
            "cci": 0.0, "williams_r": -50.0,
            "tv_recommendation": "UNKNOWN",
            "_tv_error": str(exc),
        }

    data = sanitize_data({
        "ticker":            symbol,
        "current_price":     raw_indicators.get("close", last_price),
        "exchange":          exchange,
        "ohlcv":             ohlcv,
        "indicators":        raw_indicators,
        "tv_summary":        tv_summary,
        "tv_oscillators":    tv_oscillators,
        "tv_moving_averages": tv_moving_averages,
    })

    # P1: Store in cache and add freshness metadata
    cache.set(symbol, "technical", data, ttl_seconds=TTL_TECHNICAL)
    freshness = cache.make_live_freshness("technical", TTL_TECHNICAL)
    data["_data_freshness"] = freshness.to_dict()
    return data


# ─── Legacy compatibility shim ────────────────────────────────────────────────
# Kept so the original graph.py can import this without changes during migration.

def fetch_financial_data(ticker_symbol: str) -> dict:
    """
    Legacy combined fetcher — calls both fundamental and technical fetchers
    and merges their outputs to preserve backwards compatibility with graph.py.

    DEPRECATED: will be removed once graph.py is split into separate engines.
    """
    fund = fetch_fundamental_data(ticker_symbol)
    tech = fetch_technical_data(ticker_symbol)

    return sanitize_data({
        "ticker":            ticker_symbol.upper(),
        "name":              fund.get("name", ticker_symbol),
        "info":              fund.get("info", {}),
        "chart_data":        {"prices": tech.get("ohlcv", [])},
        "tech_indicators":   tech.get("indicators", {}),
        "fundamental_engine": fund.get("ratios", {}),
        "tradingview": {
            "summary":          tech.get("tv_summary", {}),
            "oscillators":      tech.get("tv_oscillators", {}),
            "moving_averages":  tech.get("tv_moving_averages", {}),
        },
        "sector":            fund.get("sector", ""),
        "industry":          fund.get("industry", ""),
    })
