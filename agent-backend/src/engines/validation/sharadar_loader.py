"""
src/engines/validation/sharadar_loader.py
──────────────────────────────────────────────────────────────────────────────
Sharadar-backed data loader for the institutional-grade Alpha Validation
System (AVS V2).

Replaces yfinance-based ValidationDataLoader with:
  - SHARADAR/SEP  → OHLCV daily prices (adjusted, 20+ years, incl. delisted)
  - SHARADAR/SF1  → Point-in-time quarterly fundamentals (20+ years)
  - SHARADAR/TICKERS → Dynamic universe (sector, market cap, delisted flags)
  - Computed technical indicators from raw OHLCV (reuses existing math)

Key advantages over yfinance:
  - 20+ year history (vs ~5 quarters of fundamentals)
  - Delisted stocks (no survivorship bias)
  - No rate limits (bulk download supported)
  - Consistent, clean data
"""

from __future__ import annotations

import logging
import math
import os
from datetime import date, timedelta
from typing import Any

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("365advisers.validation.sharadar")


def _get_api():
    """Lazy-import and configure nasdaqdatalink."""
    import nasdaqdatalink
    key = os.getenv("NASDAQ_DATA_LINK_API_KEY", "")
    if key:
        nasdaqdatalink.ApiConfig.api_key = key
    return nasdaqdatalink


# ═════════════════════════════════════════════════════════════════════════════
# UNIVERSE BUILDER
# ═════════════════════════════════════════════════════════════════════════════

class SharadarUniverse:
    """Build a diversified equity universe from SHARADAR/TICKERS."""

    @staticmethod
    def build(
        min_market_cap: float = 2e9,      # $2B minimum (large + mid cap)
        max_tickers: int = 200,
        include_delisted: bool = True,     # survivorship-bias free
        sector_balance: bool = True,       # ensure sector diversity
    ) -> list[dict]:
        """
        Fetch tickers from SHARADAR/TICKERS with filters.

        Returns list of dicts: {ticker, name, sector, industry, isdelisted, category}.
        """
        ndl = _get_api()

        logger.info(
            f"SharadarUniverse: building universe "
            f"(min_cap=${min_market_cap/1e9:.0f}B, max={max_tickers}, "
            f"delisted={include_delisted})"
        )

        # Fetch all SEP-table tickers (equities with daily prices)
        df = ndl.get_table(
            "SHARADAR/TICKERS",
            table="SEP",
            paginate=True,
            qopts={
                "columns": [
                    "ticker", "name", "sector", "industry",
                    "isdelisted", "category", "siccode",
                    "scalemarketcap",
                ],
            },
        )

        if df.empty:
            logger.warning("SharadarUniverse: no tickers returned")
            return []

        # Filter: only Domestic Common Stock (excludes ADRs, ETFs, warrants)
        if "category" in df.columns:
            df = df[df["category"].str.contains("Domestic Common Stock", na=False)]

        # Filter: market cap
        if "scalemarketcap" in df.columns:
            # scalemarketcap is a text field like "5 - Large", "4 - Mid"
            valid_scales = {"6 - Mega", "5 - Large", "4 - Mid"}
            df = df[df["scalemarketcap"].isin(valid_scales)]

        # Filter: delisted
        if not include_delisted and "isdelisted" in df.columns:
            df = df[df["isdelisted"] != "Y"]

        # Sector balance: cap per sector
        if sector_balance and "sector" in df.columns:
            sectors = df["sector"].dropna().unique()
            n_sectors = max(len(sectors), 1)
            per_sector = max(max_tickers // n_sectors, 5)
            balanced = []
            for sec in sectors:
                sec_df = df[df["sector"] == sec].head(per_sector)
                balanced.append(sec_df)
            df = pd.concat(balanced, ignore_index=True)

        df = df.head(max_tickers)

        tickers = df.to_dict("records")
        logger.info(
            f"SharadarUniverse: built {len(tickers)} tickers "
            f"across {df['sector'].nunique() if 'sector' in df.columns else '?'} sectors"
        )
        return tickers


# ═════════════════════════════════════════════════════════════════════════════
# DATA LOADER
# ═════════════════════════════════════════════════════════════════════════════

class SharadarDataLoader:
    """
    Loads OHLCV, fundamentals, and technical indicators from Sharadar.

    Usage::

        loader = SharadarDataLoader()
        data = loader.load("AAPL", years=10)
        # data = {
        #   "ohlcv": pd.DataFrame (daily OHLCV),
        #   "fundamentals": {date_str: {field: value}},
        #   "indicators": {date_str: {indicator: value}},
        # }

    Output format is identical to ValidationDataLoader for
    drop-in compatibility with CompositeBacktest.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    def load(
        self,
        ticker: str,
        years: int = 10,
        end_date: date | None = None,
    ) -> dict:
        """Load all data for a single ticker."""
        cache_key = f"{ticker}_{years}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        end = end_date or date.today()
        # Extra 250 bars for indicator warm-up (SMA200)
        start = end - timedelta(days=int(years * 365) + 250)

        logger.info(f"SHARADAR: Loading {ticker} from {start} to {end}")

        # 1. OHLCV from SHARADAR/SEP
        ohlcv = self._fetch_ohlcv(ticker, start, end)
        if ohlcv.empty:
            logger.warning(f"SHARADAR: No price data for {ticker}")
            return {"ohlcv": ohlcv, "fundamentals": {}, "indicators": {}}

        # 2. Fundamentals from SHARADAR/SF1 (point-in-time)
        eval_start = end - timedelta(days=int(years * 365))
        fundamentals = self._fetch_fundamentals(ticker, start, end)

        # 3. Technical indicators (computed from OHLCV)
        indicators = self._compute_rolling_indicators(ohlcv, eval_start, end)

        n_quarters = len(fundamentals) if fundamentals else 0
        n_days = len(indicators) if indicators else 0
        logger.info(
            f"SHARADAR: {ticker} -- {n_quarters} quarters, "
            f"{n_days} daily snapshots"
        )

        result = {
            "ohlcv": ohlcv,
            "fundamentals": fundamentals,
            "indicators": indicators,
        }
        self._cache[cache_key] = result
        return result

    # ── OHLCV ────────────────────────────────────────────────────────────────

    def _fetch_ohlcv(
        self, ticker: str, start: date, end: date,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV — hybrid approach.

        Strategy:
          1. Try SHARADAR/SEP first (adjusted, includes delisted)
          2. If insufficient data (< 201 rows for SMA200), fall back to yfinance
             which provides 10+ years of free OHLCV data
        """
        # Try Sharadar first
        df = self._fetch_ohlcv_sharadar(ticker, start, end)
        if len(df) >= 201:
            logger.info(f"  {ticker}: {len(df)} rows from SHARADAR/SEP")
            return df

        # Fallback to yfinance
        logger.info(f"  {ticker}: SEP has {len(df)} rows, falling back to yfinance")
        return self._fetch_ohlcv_yfinance(ticker, start, end)

    def _fetch_ohlcv_sharadar(
        self, ticker: str, start: date, end: date,
    ) -> pd.DataFrame:
        """Fetch from SHARADAR/SEP."""
        ndl = _get_api()
        try:
            df = ndl.get_table(
                "SHARADAR/SEP",
                ticker=ticker,
                paginate=True,
                qopts={
                    "columns": [
                        "date", "open", "high", "low", "close", "volume",
                    ],
                },
            )
            if df.empty:
                return pd.DataFrame()

            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").set_index("date")
            df.columns = ["Open", "High", "Low", "Close", "Volume"]
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)
            df = df[(df.index >= start_ts) & (df.index <= end_ts)]
            return df
        except Exception as exc:
            logger.error(f"SHARADAR SEP error for {ticker}: {exc}")
            return pd.DataFrame()

    @staticmethod
    def _fetch_ohlcv_yfinance(
        ticker: str, start: date, end: date,
    ) -> pd.DataFrame:
        """Fallback: fetch from yfinance (10+ years free)."""
        try:
            import yfinance as yf
            df = yf.download(
                ticker, start=start.isoformat(), end=end.isoformat(),
                progress=False, auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            logger.info(f"  {ticker}: {len(df)} rows from yfinance")
            return df
        except Exception as exc:
            logger.error(f"yfinance error for {ticker}: {exc}")
            return pd.DataFrame()

    # ── FUNDAMENTALS ─────────────────────────────────────────────────────────

    def _fetch_fundamentals(
        self, ticker: str, start: date, end: date,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch quarterly fundamentals from SHARADAR/SF1.

        Returns {date_str: {field: value}} in point-in-time format,
        keyed by calendardate for compatibility with CompositeBacktest.
        """
        ndl = _get_api()
        try:
            df = ndl.get_table(
                "SHARADAR/SF1",
                ticker=ticker,
                dimension="MRQ",  # Most Recent Quarterly
                paginate=True,
            )
            if df.empty:
                return {}

            # Filter by date range in Python
            df["calendardate"] = pd.to_datetime(df["calendardate"])
            start_ts = pd.Timestamp(start)
            end_ts = pd.Timestamp(end)
            df = df[(df["calendardate"] >= start_ts) & (df["calendardate"] <= end_ts)]

            df = df.sort_values("calendardate")
            result: dict[str, dict[str, Any]] = {}

            for _, row in df.iterrows():
                cal_date = str(row.get("calendardate", ""))[:10]
                if not cal_date:
                    continue

                # Map SF1 columns → FundamentalFeatureSet field names
                snapshot = self._map_sf1_to_features(row)
                result[cal_date] = snapshot

            return result

        except Exception as exc:
            logger.error(f"SHARADAR SF1 error for {ticker}: {exc}")
            return {}

    @staticmethod
    def _map_sf1_to_features(row: pd.Series) -> dict[str, Any]:
        """Map a SHARADAR/SF1 row to FundamentalFeatureSet-compatible dict."""

        def _safe(val, default=None):
            """Convert NaN/None to default."""
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return default
            return float(val)

        revenue = _safe(row.get("revenue"), 0)
        marketcap = _safe(row.get("marketcap"), 0)
        ev = _safe(row.get("ev"), 0)
        ebit = _safe(row.get("ebit"), 0)
        ebitda = _safe(row.get("ebitda"), 0)
        fcf = _safe(row.get("fcf"), 0)
        total_assets = _safe(row.get("assets"), 0)
        net_income = _safe(row.get("netinc"), 0)
        interest_expense = _safe(row.get("intexp"), 0)
        equity = _safe(row.get("equity"), 0)

        # Computed ratios (fill gaps Sharadar might not have)
        fcf_yield = None
        if marketcap and marketcap > 0 and fcf:
            fcf_yield = (fcf * 4) / marketcap  # annualize quarterly FCF

        ebit_ev = None
        if ev and ev > 0 and ebit:
            ebit_ev = (ebit * 4) / ev  # annualized

        ev_revenue = None
        if revenue and revenue > 0 and ev:
            ev_revenue = ev / (revenue * 4)  # annualized

        asset_turnover = None
        if total_assets and total_assets > 0 and revenue:
            asset_turnover = (revenue * 4) / total_assets

        interest_coverage = None
        if interest_expense and abs(interest_expense) > 0 and ebit:
            interest_coverage = (ebit * 4) / abs(interest_expense)

        debt_to_ebitda = None
        debt = _safe(row.get("debt"), 0)
        if ebitda and ebitda > 0 and debt:
            debt_to_ebitda = debt / (ebitda * 4)

        operating_leverage = None
        rev_growth = _safe(row.get("revenuegrowth"))
        eps_growth = _safe(row.get("epsgrowth"))
        if rev_growth and rev_growth != 0 and eps_growth:
            operating_leverage = eps_growth / rev_growth

        rule_of_40 = None
        fcf_margin = None
        if revenue and revenue > 0 and fcf:
            fcf_margin = fcf / revenue
        if rev_growth is not None and fcf_margin is not None:
            rule_of_40 = (rev_growth * 100) + (fcf_margin * 100)

        # Shareholder yield (div yield + buyback yield)
        div_yield = _safe(row.get("divyield"), 0)
        buyback_yield = 0.0
        ncfcommon = _safe(row.get("ncfcommon"), 0)  # net cash from equity issuance
        if marketcap and marketcap > 0 and ncfcommon:
            buyback_yield = max(0, -ncfcommon * 4 / marketcap)  # negative ncf = buyback
        shareholder_yield = div_yield + buyback_yield

        # PEG ratio
        peg = None
        pe = _safe(row.get("pe"))
        if pe and pe > 0 and eps_growth and eps_growth > 0:
            peg = pe / (eps_growth * 100)

        # Margin trend (approximation from current margin)
        gross_margin = _safe(row.get("grossmargin"))
        net_margin = _safe(row.get("netmargin"))
        margin_trend = None  # Would need prior quarter to compute

        return {
            # Direct mappings
            "roic": _safe(row.get("roic")),
            "roe": _safe(row.get("roe")),
            "gross_margin": gross_margin,
            "ebit_margin": _safe(row.get("ebitdamargin")),  # closest proxy
            "net_margin": net_margin,
            "fcf_yield": fcf_yield,
            "debt_to_equity": _safe(row.get("de")),
            "debt_to_ebitda": debt_to_ebitda,
            "current_ratio": _safe(row.get("currentratio")),
            "quick_ratio": None,  # SF1 doesn't have quick ratio directly
            "revenue_growth_yoy": rev_growth,
            "earnings_growth_yoy": eps_growth,
            "pe_ratio": pe,
            "pb_ratio": _safe(row.get("pb")),
            "ev_ebitda": _safe(row.get("evebitda")),
            "dividend_yield": div_yield or 0.0,
            "payout_ratio": _safe(row.get("payoutratio"), 0.0),
            "beta": None,  # not in SF1, would need SEP+benchmark
            "interest_coverage": interest_coverage,
            "f_score": None,  # Piotroski — would need multi-quarter calc
            "asset_turnover": asset_turnover,
            "shareholder_yield": shareholder_yield,
            "peg_ratio": peg,
            "ev_revenue": ev_revenue,
            "ebit_ev": ebit_ev,
            "ncav_ratio": None,  # would need current assets - total liabilities
            "margin_trend": margin_trend,
            "earnings_stability": None,
            "operating_leverage": operating_leverage,
            "rule_of_40": rule_of_40,
            "revenue_acceleration": None,  # need multi-quarter series
            "sector": str(row.get("sector", "")),
            "industry": str(row.get("industry", "")),
            "market_cap": marketcap,
            "name": str(row.get("ticker", "")),

            # Metadata
            "calendardate": str(row.get("calendardate", ""))[:10],
            "datekey": str(row.get("datekey", ""))[:10],  # filing date (PIT)
        }

    # ── TECHNICAL INDICATORS ─────────────────────────────────────────────────

    def _compute_rolling_indicators(
        self,
        ohlcv: pd.DataFrame,
        eval_start: date,
        eval_end: date,
    ) -> dict[str, dict[str, float]]:
        """
        Compute all technical indicators per day from OHLCV.

        Identical output format to ValidationDataLoader._compute_rolling_indicators.
        """
        result: dict[str, dict[str, float]] = {}

        if ohlcv.empty or len(ohlcv) < 201:
            return result

        closes = ohlcv["Close"].values.tolist()
        highs = ohlcv["High"].values.tolist()
        lows = ohlcv["Low"].values.tolist()
        volumes = ohlcv["Volume"].values.tolist()
        dates = ohlcv.index.tolist()

        for i in range(200, len(closes)):
            dt = dates[i]
            day = dt.date() if hasattr(dt, "date") else dt
            if day < eval_start or day > eval_end:
                continue

            price = closes[i]
            if price <= 0:
                continue

            # SMA
            sma_50 = sum(closes[i-49:i+1]) / 50
            sma_200 = sum(closes[i-199:i+1]) / 200

            # EMA 20
            ema_20 = self._compute_ema(closes[:i+1], 20)

            # RSI 14
            rsi = self._compute_rsi(closes[:i+1], 14)

            # MACD (12, 26, 9)
            macd, macd_signal, macd_hist = self._compute_macd(closes[:i+1])

            # Bollinger Bands (20, 2)
            bb_basis, bb_upper, bb_lower = self._compute_bb(closes[:i+1], 20, 2.0)

            # ATR 14
            atr = self._compute_atr(highs[:i+1], lows[:i+1], closes[:i+1], 14)

            # Stochastic (14, 3)
            stoch_k, stoch_d = self._compute_stochastic(
                highs[:i+1], lows[:i+1], closes[:i+1], 14, 3,
            )

            # Volume features
            vol_avg_20 = sum(volumes[max(0, i-19):i+1]) / min(20, i+1)
            vol_current = volumes[i]
            volume_surprise = 0.0
            relative_volume = 1.0
            if i >= 20:
                recent_vols = volumes[i-19:i+1]
                mean_v = sum(recent_vols) / len(recent_vols)
                std_v = (sum((v - mean_v)**2 for v in recent_vols) / len(recent_vols)) ** 0.5
                if std_v > 0 and vol_current > 0:
                    volume_surprise = (vol_current - mean_v) / std_v
                if mean_v > 0 and vol_current > 0:
                    relative_volume = vol_current / mean_v

            # OBV (simplified — use incremental from last 252 bars to avoid O(n²))
            obv = 0.0
            obv_start = max(1, i - 251)
            for j in range(obv_start, i + 1):
                if closes[j] > closes[j-1]:
                    obv += volumes[j]
                elif closes[j] < closes[j-1]:
                    obv -= volumes[j]

            # SMA spread
            sma_spread = (sma_50 / sma_200 - 1.0) if sma_200 > 0 else 0.0

            # % from 52w high
            lookback = min(252, i + 1)
            high_52w = max(highs[i-lookback+1:i+1])
            pct_52w = (price - high_52w) / high_52w if high_52w > 0 else 0.0

            # Mean reversion z
            log_closes = [math.log(c) for c in closes[max(0, i-251):i+1] if c > 0]
            mr_z = None
            if len(log_closes) >= 50:
                avg_lp = sum(log_closes) / len(log_closes)
                std_lp = (sum((lp - avg_lp)**2 for lp in log_closes) / len(log_closes)) ** 0.5
                if std_lp > 0:
                    mr_z = (math.log(price) - avg_lp) / std_lp

            # ADX proxy
            adx = min(50, abs(sma_spread) * 200 + 15)

            # OHLCV bars (last 60 for structure analysis)
            ohlcv_bars = []
            for j in range(max(0, i-59), i+1):
                ohlcv_bars.append({
                    "open": ohlcv.iloc[j]["Open"] if "Open" in ohlcv.columns else closes[j],
                    "high": highs[j],
                    "low": lows[j],
                    "close": closes[j],
                    "volume": volumes[j],
                })

            # Realized vol 20d (annualized)
            realized_vol_20d = 0.0
            if i >= 20:
                log_rets = [
                    math.log(closes[j] / closes[j-1])
                    for j in range(i - 19, i + 1)
                    if closes[j-1] > 0 and closes[j] > 0
                ]
                if len(log_rets) >= 10:
                    mean_lr = sum(log_rets) / len(log_rets)
                    var_lr = sum((r - mean_lr)**2 for r in log_rets) / len(log_rets)
                    realized_vol_20d = (var_lr ** 0.5) * (252 ** 0.5)

            # BB width
            bb_width = (bb_upper - bb_lower) / bb_basis if bb_basis > 0 else 0.0

            # MFI 14
            mfi = 50.0
            if i >= 14:
                pos_flow = neg_flow = 0.0
                for j in range(i - 13, i + 1):
                    tp_curr = (highs[j] + lows[j] + closes[j]) / 3
                    tp_prev = (highs[j-1] + lows[j-1] + closes[j-1]) / 3
                    mf = tp_curr * volumes[j]
                    if tp_curr > tp_prev:
                        pos_flow += mf
                    else:
                        neg_flow += mf
                if neg_flow > 0:
                    mfi = 100 - (100 / (1 + pos_flow / neg_flow))

            # Effort-result ratio
            effort_result = 0.0
            if i >= 1 and closes[i-1] > 0 and vol_current > 0:
                pct_change = abs(closes[i] - closes[i-1]) / closes[i-1]
                if pct_change > 0.0001:
                    effort_result = vol_current / (pct_change * 100)

            result[day.isoformat()] = {
                "current_price": price,
                "sma_50": round(sma_50, 4),
                "sma_200": round(sma_200, 4),
                "ema_20": round(ema_20, 4),
                "rsi": round(rsi, 2),
                "stoch_k": round(stoch_k, 2),
                "stoch_d": round(stoch_d, 2),
                "macd": round(macd, 4),
                "macd_signal": round(macd_signal, 4),
                "macd_hist": round(macd_hist, 4),
                "bb_upper": round(bb_upper, 4),
                "bb_lower": round(bb_lower, 4),
                "bb_basis": round(bb_basis, 4),
                "atr": round(atr, 4),
                "volume": vol_current,
                "obv": round(obv, 2),
                "volume_avg_20": round(vol_avg_20, 2),
                "volume_surprise": round(volume_surprise, 4),
                "relative_volume": round(relative_volume, 4),
                "sma_50_200_spread": round(sma_spread, 6),
                "pct_from_52w_high": round(pct_52w, 6),
                "mean_reversion_z": round(mr_z, 4) if mr_z is not None else None,
                "adx": round(adx, 2),
                "plus_di": 25.0 if sma_spread > 0 else 15.0,
                "minus_di": 15.0 if sma_spread > 0 else 25.0,
                "tv_recommendation": "UNKNOWN",
                "ohlcv_bars": ohlcv_bars,
                "realized_vol_20d": round(realized_vol_20d, 6),
                "bb_width": round(bb_width, 6),
                "mfi": round(mfi, 2),
                "effort_result_ratio": round(effort_result, 2),
            }

        logger.info(f"SHARADAR: Computed indicators for {len(result)} days")
        return result

    # ── Indicator math (identical to ValidationDataLoader) ───────────────────

    @staticmethod
    def _compute_ema(prices: list[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        mult = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = p * mult + ema * (1 - mult)
        return ema

    @staticmethod
    def _compute_rsi(prices: list[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        if len(gains) < period:
            return 50.0
        avg_g = sum(gains[:period]) / period
        avg_l = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_g = (avg_g * (period - 1) + gains[i]) / period
            avg_l = (avg_l * (period - 1) + losses[i]) / period
        if avg_l == 0:
            return 100.0
        return 100 - (100 / (1 + avg_g / avg_l))

    @staticmethod
    def _compute_macd(prices: list[float]) -> tuple[float, float, float]:
        def ema_series(data, period):
            if not data:
                return []
            result = [sum(data[:period]) / period if len(data) >= period else data[0]]
            mult = 2.0 / (period + 1)
            for i in range(period if len(data) >= period else 1, len(data)):
                result.append(data[i] * mult + result[-1] * (1 - mult))
            return result
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        ema12 = ema_series(prices, 12)
        ema26 = ema_series(prices, 26)
        ml = min(len(ema12), len(ema26))
        macd_line = [ema12[-(ml-i)] - ema26[-(ml-i)] for i in range(ml)]
        if not macd_line:
            return 0.0, 0.0, 0.0
        signal = ema_series(macd_line, 9)
        return macd_line[-1], signal[-1] if signal else 0.0, macd_line[-1] - (signal[-1] if signal else 0.0)

    @staticmethod
    def _compute_bb(prices, period=20, std_mult=2.0):
        if len(prices) < period:
            p = prices[-1] if prices else 0.0
            return p, p, p
        window = prices[-period:]
        basis = sum(window) / period
        std = (sum((x - basis)**2 for x in window) / period) ** 0.5
        return basis, basis + std_mult * std, basis - std_mult * std

    @staticmethod
    def _compute_atr(highs, lows, closes, period=14):
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            trs.append(tr)
        return sum(trs[-period:]) / period if len(trs) >= period else (sum(trs) / len(trs) if trs else 0.0)

    @staticmethod
    def _compute_stochastic(highs, lows, closes, k_period=14, d_period=3):
        if len(closes) < k_period:
            return 50.0, 50.0
        k_values = []
        for i in range(k_period - 1, len(closes)):
            hh = max(highs[i - k_period + 1:i + 1])
            ll = min(lows[i - k_period + 1:i + 1])
            k_values.append(100 * (closes[i] - ll) / (hh - ll) if hh - ll > 0 else 50.0)
        if not k_values:
            return 50.0, 50.0
        return k_values[-1], sum(k_values[-d_period:]) / min(d_period, len(k_values))
