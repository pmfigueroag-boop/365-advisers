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
_CF_DEPRECIATION = "Depreciation And Amortization"

# Additional Income Statement fields (Tier 1)
_IS_INTEREST_EXPENSE = "Interest Expense"
_IS_DILUTED_EPS = "Diluted EPS"

# Additional Balance Sheet fields (Tier 1)
_BS_TOTAL_LIABILITIES = "Total Liabilities Net Minority Interest"
_BS_CASH_AND_EQUIVALENTS = "Cash And Cash Equivalents"


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

        # ── Tier 1: Multi-quarter lookback features ──────────────────────
        self._compute_multi_quarter_features(quarterly_snapshots)

        # ── Tier 1: Beta from OHLCV vs SPY ───────────────────────────────
        beta = self._compute_beta(ticker, ohlcv) if ohlcv is not None else None

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
                    self._enrich_with_price(current_snap, ohlcv, day_d, shares_outstanding)

                # Inject beta (constant across quarters — computed from price)
                if beta is not None:
                    current_snap["beta"] = beta

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
        interest_expense = _get_field(income_stmt, _IS_INTEREST_EXPENSE, q_date)
        diluted_eps = _get_field(income_stmt, _IS_DILUTED_EPS, q_date)

        # Margins (quarterly, annualized later if needed)
        if revenue and revenue > 0:
            if gross_profit is not None:
                snap["gross_margin"] = gross_profit / revenue
            if operating_income is not None:
                snap["ebit_margin"] = operating_income / revenue
            if net_income is not None:
                snap["net_margin"] = net_income / revenue

        # Interest Coverage = EBIT / Interest Expense (Tier 1)
        if ebit is not None and interest_expense is not None and abs(interest_expense) > 0:
            snap["interest_coverage"] = abs(ebit / interest_expense)

        # --- Balance Sheet ---
        bs = balance_sheet
        total_assets = None
        total_liab = None
        equity = None
        current_assets = None

        if bs is not None and not bs.empty:
            total_assets = _get_field(bs, _BS_TOTAL_ASSETS, q_date)
            total_debt = _get_field(bs, _BS_TOTAL_DEBT, q_date)
            equity = _get_field(bs, _BS_STOCKHOLDERS_EQUITY, q_date)
            invested_capital = _get_field(bs, _BS_INVESTED_CAPITAL, q_date)
            current_assets = _get_field(bs, _BS_CURRENT_ASSETS, q_date)
            current_liab = _get_field(bs, _BS_CURRENT_LIABILITIES, q_date)
            total_liab = _get_field(bs, _BS_TOTAL_LIABILITIES, q_date)
            cash = _get_field(bs, _BS_CASH_AND_EQUIVALENTS, q_date)

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

            # Store equity and total_liabilities for price-based calcs
            if equity is not None:
                snap["_equity"] = equity
            if total_liab is not None:
                snap["_total_liabilities"] = total_liab
            if current_assets is not None:
                snap["_current_assets"] = current_assets
            if cash is not None:
                snap["_cash"] = cash

        # --- Cash Flow ---
        depreciation = None
        capex = None
        fcf = None

        if cashflow is not None and not cashflow.empty:
            fcf = _get_field(cashflow, _CF_FREE_CASH_FLOW, q_date)
            ocf = _get_field(cashflow, _CF_OPERATING_CASH_FLOW, q_date)
            capex = _get_field(cashflow, _CF_CAPITAL_EXPENDITURE, q_date)
            dividends_paid = _get_field(cashflow, _CF_DIVIDENDS_PAID, q_date)
            buybacks = _get_field(cashflow, _CF_BUYBACKS, q_date)
            debt_repayment = _get_field(cashflow, _CF_DEBT_REPAYMENT, q_date)
            depreciation = _get_field(cashflow, _CF_DEPRECIATION, q_date)

            # Store annualised FCF for yield calculation later
            if fcf is not None:
                snap["_fcf_annual"] = fcf * 4  # annualise quarterly

            # Shareholder yield components (annualised)
            div_yield_abs = abs(dividends_paid) if dividends_paid else 0
            buyback_abs = abs(buybacks) if buybacks else 0
            debt_repay_abs = abs(debt_repayment) if debt_repayment else 0
            snap["_shareholder_return_annual"] = (
                div_yield_abs + buyback_abs + debt_repay_abs
            ) * 4  # annualise

            # Capex / Depreciation (Tier 1 — growth.capex_intensity)
            capex_abs = abs(capex) if capex else None
            if capex_abs and depreciation and abs(depreciation) > 0:
                snap["capex_to_depreciation"] = capex_abs / abs(depreciation)

            # Store OCF for F-score
            if ocf is not None:
                snap["_ocf"] = ocf

        # Store raw fields for price-based calcs AND multi-quarter lookback
        if net_income is not None:
            snap["_net_income_annual"] = net_income * 4
            snap["_net_income_q"] = net_income
        if ebit is not None:
            snap["_ebit_annual"] = ebit * 4
        if ebitda is not None:
            snap["_ebitda_annual"] = ebitda * 4
        if revenue is not None:
            snap["_revenue_annual"] = revenue * 4
            snap["_revenue_q"] = revenue
        if diluted_eps is not None:
            snap["_eps_q"] = diluted_eps
        if total_assets is not None:
            snap["_total_assets"] = total_assets
        if fcf is not None:
            snap["_fcf_q"] = fcf

        # ── Bonus 7.1: High-value signal fields ──────────────────────────
        # Short Interest Ratio (days to cover) — static from yfinance .info
        short_ratio = info.get("shortRatio")
        if short_ratio is not None:
            try:
                snap["short_ratio"] = float(short_ratio)
            except (TypeError, ValueError):
                pass

        # Analyst Recommendation Mean (1=Strong Buy, 5=Sell)
        rec_mean = info.get("recommendationMean")
        if rec_mean is not None:
            try:
                snap["analyst_recommendation"] = float(rec_mean)
            except (TypeError, ValueError):
                pass

        # Accruals Quality (Sloan Ratio) = (NI - CFO) / Total Assets
        if net_income is not None and total_assets and total_assets > 0:
            ocf_val = snap.get("_ocf")
            if ocf_val is not None:
                snap["accruals_quality"] = (net_income - ocf_val) / total_assets

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
            eps = None
            if net_inc and net_inc > 0:
                eps = net_inc / shares_outstanding
                snap["pe_ratio"] = price / eps

            # PB Ratio = Market Cap / Equity (Tier 1)
            equity = snap.get("_equity")
            if equity and equity > 0:
                snap["pb_ratio"] = market_cap / equity

            # FCF Yield = FCF / Market Cap
            fcf_annual = snap.get("_fcf_annual")
            if fcf_annual is not None:
                snap["fcf_yield"] = fcf_annual / market_cap

            # EV = Market Cap + Total Debt - Cash (improved from proxy)
            cash = snap.get("_cash", 0) or 0
            ebitda_annual = snap.get("_ebitda_annual")
            ev = market_cap  # base
            total_liab = snap.get("_total_liabilities")
            if total_liab:
                ev = market_cap + total_liab - cash

            if ebitda_annual and ebitda_annual > 0:
                snap["ev_ebitda"] = ev / ebitda_annual

            # EV/Revenue
            revenue_annual = snap.get("_revenue_annual")
            if revenue_annual and revenue_annual > 0:
                snap["ev_revenue"] = ev / revenue_annual

            # EBIT/EV (Greenblatt earnings yield)
            ebit_annual = snap.get("_ebit_annual")
            if ebit_annual and ev > 0:
                snap["ebit_ev"] = ebit_annual / ev

            # Dividend Yield
            shareholder_return = snap.get("_shareholder_return_annual", 0)
            if shareholder_return > 0:
                snap["shareholder_yield"] = shareholder_return / market_cap

            # Dividend yield alone
            if "_shareholder_return_annual" in snap:
                snap["dividend_yield"] = snap.get("shareholder_yield", 0) * 0.5

            # NCAV / Market Cap (Tier 1 — value.ncav_deep)
            ca = snap.get("_current_assets")
            tl = snap.get("_total_liabilities")
            if ca is not None and tl is not None and market_cap > 0:
                ncav = ca - tl
                snap["ncav_ratio"] = ncav / market_cap

            # PEG Ratio = PE / earnings_growth (Tier 1 — value.peg_low)
            eg = snap.get("earnings_growth_yoy")
            pe = snap.get("pe_ratio")
            if pe and eg and eg > 0.01:
                snap["peg_ratio"] = pe / (eg * 100)  # growth as %

            # Rule of 40 (Tier 1 — growth.rule_of_40)
            rev_growth = snap.get("revenue_growth_yoy")
            fcf_q = snap.get("_fcf_q")
            rev_q = snap.get("_revenue_q")
            if rev_growth is not None and fcf_q is not None and rev_q and rev_q > 0:
                fcf_margin = fcf_q / rev_q
                snap["rule_of_40"] = (rev_growth * 100) + (fcf_margin * 100)

        # Clean up internal fields
        for key in list(snap.keys()):
            if key.startswith("_"):
                del snap[key]

    # ── Tier 1: Multi-quarter lookback ───────────────────────────────────

    @staticmethod
    def _compute_multi_quarter_features(
        quarterly_snapshots: list[tuple[date, dict[str, float]]],
    ) -> None:
        """
        Compute features that require looking back across multiple quarters.
        Mutates the snapshots in-place.
        """
        for i, (q_date, snap) in enumerate(quarterly_snapshots):
            # ── YoY Growth (compare Q vs Q-4) ────────────────────────────
            if i >= 4:
                prev_snap = quarterly_snapshots[i - 4][1]
                # Revenue growth YoY
                rev_q = snap.get("_revenue_q")
                prev_rev = prev_snap.get("_revenue_q")
                if rev_q and prev_rev and prev_rev > 0:
                    snap["revenue_growth_yoy"] = (rev_q - prev_rev) / abs(prev_rev)

                # Earnings growth YoY
                eps_q = snap.get("_eps_q")
                prev_eps = prev_snap.get("_eps_q")
                if eps_q is not None and prev_eps is not None and abs(prev_eps) > 0.01:
                    snap["earnings_growth_yoy"] = (eps_q - prev_eps) / abs(prev_eps)

            # ── Revenue growth acceleration (slope of growth rates) ──────
            if i >= 5:
                growth_rates: list[float] = []
                for j in range(max(0, i - 3), i + 1):
                    g = quarterly_snapshots[j][1].get("revenue_growth_yoy")
                    if g is not None:
                        growth_rates.append(g)
                if len(growth_rates) >= 3:
                    # Simple slope: last - first / n
                    snap["revenue_acceleration"] = (
                        growth_rates[-1] - growth_rates[0]
                    ) / len(growth_rates)

            # ── Operating Leverage (Tier 1) ──────────────────────────────
            rev_g = snap.get("revenue_growth_yoy")
            earn_g = snap.get("earnings_growth_yoy")
            if rev_g and abs(rev_g) > 0.01 and earn_g is not None:
                snap["operating_leverage"] = earn_g / rev_g

            # ── Margin Trend (slope over 4 quarters) ─────────────────────
            if i >= 3:
                margins: list[float] = []
                for j in range(i - 3, i + 1):
                    m = quarterly_snapshots[j][1].get("ebit_margin")
                    if m is not None:
                        margins.append(m)
                if len(margins) >= 3:
                    snap["margin_trend"] = margins[-1] - margins[0]

            # ── Earnings Stability (1 - CV of EPS over 4Q) ──────────────
            if i >= 3:
                eps_vals: list[float] = []
                for j in range(i - 3, i + 1):
                    e = quarterly_snapshots[j][1].get("_eps_q")
                    if e is not None:
                        eps_vals.append(e)
                if len(eps_vals) >= 3:
                    mean_eps = sum(eps_vals) / len(eps_vals)
                    if abs(mean_eps) > 0.01:
                        std_eps = (
                            sum((x - mean_eps) ** 2 for x in eps_vals) / len(eps_vals)
                        ) ** 0.5
                        cv = std_eps / abs(mean_eps)
                        snap["earnings_stability"] = max(0.0, 1.0 - cv)

            # ── Piotroski F-Score ────────────────────────────────────────
            if i >= 1:
                snap["f_score"] = FundamentalProvider._compute_f_score(
                    snap, quarterly_snapshots[i - 1][1] if i >= 1 else None,
                )

    @staticmethod
    def _compute_f_score(
        current: dict[str, float],
        previous: dict[str, float] | None,
    ) -> float:
        """
        Piotroski F-Score (0-9 points).
        Tests: profitability (4), leverage (3), efficiency (2).
        """
        score = 0

        # 1. ROA > 0
        ni = current.get("_net_income_q", 0)
        ta = current.get("_total_assets")
        if ta and ta > 0 and ni > 0:
            score += 1

        # 2. OCF > 0
        ocf = current.get("_ocf", 0)
        if ocf and ocf > 0:
            score += 1

        # 3. Change in ROA > 0 (vs prior quarter)
        if previous and ta and ta > 0:
            curr_roa = ni / ta if ta else 0
            prev_ni = previous.get("_net_income_q", 0) or 0
            prev_ta = previous.get("_total_assets", 0) or 1
            prev_roa = prev_ni / prev_ta if prev_ta else 0
            if curr_roa > prev_roa:
                score += 1

        # 4. Accruals: OCF > Net Income (quality of earnings)
        if ocf and ni and ocf > ni:
            score += 1

        # 5. Change in leverage: debt_to_equity decreased
        if previous:
            curr_dte = current.get("debt_to_equity")
            prev_dte = previous.get("debt_to_equity")
            if curr_dte is not None and prev_dte is not None and curr_dte < prev_dte:
                score += 1

        # 6. Change in current ratio: increased
        if previous:
            curr_cr = current.get("current_ratio")
            prev_cr = previous.get("current_ratio")
            if curr_cr is not None and prev_cr is not None and curr_cr > prev_cr:
                score += 1

        # 7. No new shares issued (approximate: constant shares)
        # Skip — not easily available from quarterly data
        score += 1  # assume no dilution (generous)

        # 8. Change in gross margin: increased
        if previous:
            curr_gm = current.get("gross_margin")
            prev_gm = previous.get("gross_margin")
            if curr_gm is not None and prev_gm is not None and curr_gm > prev_gm:
                score += 1

        # 9. Change in asset turnover: increased
        if previous:
            curr_at = current.get("asset_turnover")
            prev_at = previous.get("asset_turnover")
            if curr_at is not None and prev_at is not None and curr_at > prev_at:
                score += 1

        return float(score)

    # ── Tier 1: Beta ─────────────────────────────────────────────────────

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_spy_returns() -> pd.Series | None:
        """Fetch SPY daily returns (cached globally per session)."""
        try:
            spy = yf.download("SPY", period="3y", progress=False)
            if spy is None or spy.empty:
                return None
            close = spy["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            return close.pct_change().dropna()
        except Exception:
            return None

    @staticmethod
    def _compute_beta(
        ticker: str,
        ohlcv: pd.DataFrame,
        window: int = 252,
    ) -> float | None:
        """Compute beta vs SPY over trailing window days."""
        spy_ret = FundamentalProvider._get_spy_returns()
        if spy_ret is None or ohlcv is None or ohlcv.empty:
            return None

        close = ohlcv["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        stock_ret = close.pct_change().dropna()

        # Align dates
        common = stock_ret.index.intersection(spy_ret.index)
        if len(common) < max(60, window // 2):
            return None

        common = sorted(common)[-window:]  # trailing
        sr = stock_ret.loc[common]
        mr = spy_ret.loc[common]

        cov = ((sr - sr.mean()) * (mr - mr.mean())).mean()
        var = ((mr - mr.mean()) ** 2).mean()
        if var == 0:
            return None
        return round(float(cov / var), 4)

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
