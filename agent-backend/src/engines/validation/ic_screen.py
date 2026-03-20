"""
src/engines/validation/ic_screen.py
──────────────────────────────────────────────────────────────────────────────
Phase 0: Signal Information Coefficient (IC) Screen.

For each signal in the registry, compute Spearman rank correlation between
the signal's value (or fired×confidence) and forward returns at T+5d/T+20d.

IC > 0.02 → signal has predictive power
IC < 0   → signal is worse than noise
IC ~ 0   → no edge

Evaluation frequency: weekly (every 5 trading days) to reduce autocorrelation
from overlapping forward-return windows.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.alpha_signals.models import EvaluatedSignal, SignalDirection
from src.engines.validation.data_loader import ValidationDataLoader

logger = logging.getLogger("365advisers.validation.ic_screen")


# ─── Result Contracts ────────────────────────────────────────────────────────

@dataclass
class SignalICResult:
    """IC result for a single signal."""
    signal_id: str
    signal_name: str
    category: str
    n_observations: int = 0        # Total observations across all tickers
    ic_5d: float = 0.0             # Spearman IC vs T+5d return
    ic_20d: float = 0.0            # Spearman IC vs T+20d return
    hit_rate_5d: float = 0.0       # % directional hits at T+5
    hit_rate_20d: float = 0.0      # % directional hits at T+20
    fire_rate: float = 0.0         # % of observations where signal fired
    avg_return_5d_fired: float = 0.0   # Mean 5d return when signal fires
    avg_return_5d_unfired: float = 0.0 # Mean 5d return when NOT fired
    avg_return_20d_fired: float = 0.0
    avg_return_20d_unfired: float = 0.0
    ic_stable: bool = False        # True if IC sign is consistent across tickers
    per_ticker_ic_20d: dict[str, float] = field(default_factory=dict)


@dataclass
class ICScreenReport:
    """Complete IC screen report."""
    universe: list[str]
    eval_period: str = ""
    total_signals: int = 0
    signals_with_ic_gt_002: int = 0
    signals_with_negative_ic: int = 0
    results: list[SignalICResult] = field(default_factory=list)


# ─── IC Screen ───────────────────────────────────────────────────────────────

class ICScreen:
    """
    Signal IC Screen — computes Information Coefficient for all registered
    alpha signals across a universe of tickers.

    Usage::

        screen = ICScreen()
        report = screen.run(
            tickers=["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"],
            years=2,
        )
        screen.print_report(report)
    """

    def __init__(self) -> None:
        self._loader = ValidationDataLoader()
        self._evaluator = SignalEvaluator()

    def run(
        self,
        tickers: list[str],
        years: int = 2,
        eval_frequency_days: int = 5,
        forward_horizons: tuple[int, int] = (5, 20),
    ) -> ICScreenReport:
        """
        Run IC screen for all signals across the given universe.

        Parameters
        ----------
        tickers : list[str]
            Universe of tickers.
        years : int
            Years of history.
        eval_frequency_days : int
            Days between evaluations (5 = weekly).
        forward_horizons : tuple
            (short, long) forward return horizons in trading days.
        """
        # Ensure signals are loaded
        self._ensure_signals_loaded()

        short_h, long_h = forward_horizons

        # Collect per-signal data across all tickers
        # signal_id → {ticker → [(signal_value, fwd_return_short, fwd_return_long)]}
        signal_data: dict[str, dict[str, list[tuple[float | None, float | None, float | None, bool]]]] = {}

        for ticker in tickers:
            logger.info(f"AVS-IC: Processing {ticker}...")
            try:
                data = self._loader.load(ticker, years=years)
            except Exception as exc:
                logger.error(f"AVS-IC: Failed to load {ticker}: {exc}")
                continue

            ohlcv = data["ohlcv"]
            fundamentals = data["fundamentals"]
            indicators = data["indicators"]

            if ohlcv.empty or not indicators:
                logger.warning(f"AVS-IC: Insufficient data for {ticker}")
                continue

            # Sort dates
            ind_dates = sorted(indicators.keys())

            # Get OHLCV close by date for forward returns
            close_by_date = self._build_close_map(ohlcv)
            sorted_close_dates = sorted(close_by_date.keys())

            # Evaluate at weekly intervals
            for idx in range(0, len(ind_dates), eval_frequency_days):
                eval_date = ind_dates[idx]
                inds = indicators[eval_date]

                # Build feature sets
                tech_fs = self._build_technical_features(ticker, inds)
                funda_fs = self._build_fundamental_features(
                    ticker, eval_date, fundamentals,
                )

                # Evaluate all signals
                profile = self._evaluator.evaluate(ticker, funda_fs, tech_fs)

                # Compute forward returns
                fwd_short = self._forward_return(eval_date, short_h, close_by_date, sorted_close_dates)
                fwd_long = self._forward_return(eval_date, long_h, close_by_date, sorted_close_dates)

                # Record each signal's result
                for sig in profile.signals:
                    if sig.signal_id not in signal_data:
                        signal_data[sig.signal_id] = {}
                    if ticker not in signal_data[sig.signal_id]:
                        signal_data[sig.signal_id][ticker] = []

                    # Signal value: use confidence×weight if fired, 0 if not
                    sig_value = sig.confidence if sig.fired else 0.0

                    signal_data[sig.signal_id][ticker].append(
                        (sig_value, fwd_short, fwd_long, sig.fired)
                    )

        # ── Compute IC per signal ────────────────────────────────────────────
        results: list[SignalICResult] = []
        for sig_id, ticker_data in signal_data.items():
            result = self._compute_signal_ic(sig_id, ticker_data, tickers)
            results.append(result)

        # Sort by IC_20d descending
        results.sort(key=lambda r: r.ic_20d, reverse=True)

        # Count categories
        positive_ic = sum(1 for r in results if r.ic_20d > 0.02)
        negative_ic = sum(1 for r in results if r.ic_20d < 0)

        return ICScreenReport(
            universe=tickers,
            eval_period=f"~{years}Y",
            total_signals=len(results),
            signals_with_ic_gt_002=positive_ic,
            signals_with_negative_ic=negative_ic,
            results=results,
        )

    # ── Computation ──────────────────────────────────────────────────────────

    def _compute_signal_ic(
        self,
        sig_id: str,
        ticker_data: dict[str, list[tuple[float | None, float | None, float | None, bool]]],
        all_tickers: list[str],
    ) -> SignalICResult:
        """Compute IC, hit rates, and stability for a single signal."""
        # Get signal metadata from registry
        from src.engines.alpha_signals.registry import registry
        sig_def = registry.get(sig_id)
        sig_name = sig_def.name if sig_def else sig_id
        sig_cat = sig_def.category.value if sig_def else "unknown"

        # Flatten all observations
        all_values: list[float] = []
        all_fwd_5: list[float] = []
        all_fwd_20: list[float] = []
        all_fired: list[bool] = []

        for ticker, observations in ticker_data.items():
            for val, fwd_s, fwd_l, fired in observations:
                if val is not None and fwd_s is not None and fwd_l is not None:
                    all_values.append(val)
                    all_fwd_5.append(fwd_s)
                    all_fwd_20.append(fwd_l)
                    all_fired.append(fired)

        n = len(all_values)
        if n < 10:
            return SignalICResult(
                signal_id=sig_id, signal_name=sig_name,
                category=sig_cat, n_observations=n,
            )

        # Spearman IC
        ic_5d = _spearman_correlation(all_values, all_fwd_5)
        ic_20d = _spearman_correlation(all_values, all_fwd_20)

        # Fire rate
        fire_count = sum(1 for f in all_fired if f)
        fire_rate = fire_count / n if n > 0 else 0.0

        # Hit rates (directional accuracy when fired)
        # Determine signal direction
        is_bullish = True
        if sig_def:
            # BELOW direction with non-negative threshold → typically bearish (like risk signals)
            # Check tags for 'bearish'
            is_bullish = "bearish" not in [t.lower() for t in sig_def.tags]
            if sig_def.direction == SignalDirection.BELOW and "risk" in sig_cat:
                is_bullish = False

        hits_5 = 0
        hits_20 = 0
        fired_count_valid = 0
        for val, f5, f20, fired in zip(all_values, all_fwd_5, all_fwd_20, all_fired):
            if not fired:
                continue
            fired_count_valid += 1
            if is_bullish and f5 > 0:
                hits_5 += 1
            elif not is_bullish and f5 < 0:
                hits_5 += 1
            if is_bullish and f20 > 0:
                hits_20 += 1
            elif not is_bullish and f20 < 0:
                hits_20 += 1

        hit_rate_5 = hits_5 / fired_count_valid if fired_count_valid > 0 else 0.0
        hit_rate_20 = hits_20 / fired_count_valid if fired_count_valid > 0 else 0.0

        # Average returns when fired vs unfired
        fired_returns_5 = [f5 for v, f5, f20, f in zip(all_values, all_fwd_5, all_fwd_20, all_fired) if f]
        unfired_returns_5 = [f5 for v, f5, f20, f in zip(all_values, all_fwd_5, all_fwd_20, all_fired) if not f]
        fired_returns_20 = [f20 for v, f5, f20, f in zip(all_values, all_fwd_5, all_fwd_20, all_fired) if f]
        unfired_returns_20 = [f20 for v, f5, f20, f in zip(all_values, all_fwd_5, all_fwd_20, all_fired) if not f]

        avg_5_fired = sum(fired_returns_5) / len(fired_returns_5) if fired_returns_5 else 0.0
        avg_5_unfired = sum(unfired_returns_5) / len(unfired_returns_5) if unfired_returns_5 else 0.0
        avg_20_fired = sum(fired_returns_20) / len(fired_returns_20) if fired_returns_20 else 0.0
        avg_20_unfired = sum(unfired_returns_20) / len(unfired_returns_20) if unfired_returns_20 else 0.0

        # Per-ticker IC stability
        per_ticker_ic: dict[str, float] = {}
        for ticker, observations in ticker_data.items():
            vals = [v for v, f5, f20, _ in observations if v is not None and f20 is not None]
            fwds = [f20 for v, f5, f20, _ in observations if v is not None and f20 is not None]
            if len(vals) >= 5:
                per_ticker_ic[ticker] = round(_spearman_correlation(vals, fwds), 4)

        # IC stable if sign is consistent across >= 50% of tickers
        if per_ticker_ic:
            positive_count = sum(1 for v in per_ticker_ic.values() if v > 0)
            negative_count = sum(1 for v in per_ticker_ic.values() if v < 0)
            ic_stable = (
                positive_count >= len(per_ticker_ic) * 0.6
                or negative_count >= len(per_ticker_ic) * 0.6
            )
        else:
            ic_stable = False

        return SignalICResult(
            signal_id=sig_id,
            signal_name=sig_name,
            category=sig_cat,
            n_observations=n,
            ic_5d=round(ic_5d, 4),
            ic_20d=round(ic_20d, 4),
            hit_rate_5d=round(hit_rate_5, 4),
            hit_rate_20d=round(hit_rate_20, 4),
            fire_rate=round(fire_rate, 4),
            avg_return_5d_fired=round(avg_5_fired, 4),
            avg_return_5d_unfired=round(avg_5_unfired, 4),
            avg_return_20d_fired=round(avg_20_fired, 4),
            avg_return_20d_unfired=round(avg_20_unfired, 4),
            ic_stable=ic_stable,
            per_ticker_ic_20d=per_ticker_ic,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _ensure_signals_loaded(self) -> None:
        """Ensure all signal modules are registered."""
        from src.engines.alpha_signals.registry import registry
        if registry.size == 0:
            # Import all signal modules to trigger registration
            import src.engines.alpha_signals.signals.value_signals  # noqa: F401
            import src.engines.alpha_signals.signals.quality_signals  # noqa: F401
            import src.engines.alpha_signals.signals.growth_signals  # noqa: F401
            import src.engines.alpha_signals.signals.momentum_signals  # noqa: F401
            import src.engines.alpha_signals.signals.volatility_signals  # noqa: F401
            import src.engines.alpha_signals.signals.flow_signals  # noqa: F401
            import src.engines.alpha_signals.signals.event_signals  # noqa: F401
            import src.engines.alpha_signals.signals.macro_signals  # noqa: F401
            try:
                import src.engines.alpha_signals.signals.risk_signals  # noqa: F401
            except ImportError:
                pass
            try:
                import src.engines.alpha_signals.signals.fundamental_momentum_signals  # noqa: F401
            except ImportError:
                pass
            try:
                import src.engines.alpha_signals.signals.price_cycle_signals  # noqa: F401
            except ImportError:
                pass
            logger.info(f"AVS-IC: Loaded {registry.size} signals from registry")

    @staticmethod
    def _build_close_map(ohlcv) -> dict[str, float]:
        """Build date_str → close price mapping from OHLCV DataFrame."""
        close_map: dict[str, float] = {}
        for idx in ohlcv.index:
            dt = idx.date() if hasattr(idx, "date") else idx
            close_val = ohlcv.loc[idx, "Close"]
            if hasattr(close_val, "item"):
                close_val = close_val.item()
            close_map[dt.isoformat()] = float(close_val)
        return close_map

    @staticmethod
    def _forward_return(
        eval_date: str, horizon: int,
        close_map: dict[str, float],
        sorted_dates: list[str],
    ) -> float | None:
        """Compute forward return at T+horizon from eval_date."""
        if eval_date not in sorted_dates:
            # Find nearest available date
            try:
                pos = next(i for i, d in enumerate(sorted_dates) if d >= eval_date)
            except StopIteration:
                return None
        else:
            pos = sorted_dates.index(eval_date)

        target_pos = pos + horizon
        if target_pos >= len(sorted_dates):
            return None

        price_now = close_map.get(sorted_dates[pos], 0)
        price_future = close_map.get(sorted_dates[target_pos], 0)

        if price_now <= 0:
            return None

        return (price_future - price_now) / price_now

    @staticmethod
    def _build_technical_features(
        ticker: str, indicators: dict,
    ) -> TechnicalFeatureSet:
        """Build TechnicalFeatureSet from computed indicators."""
        return TechnicalFeatureSet(
            ticker=ticker,
            current_price=indicators.get("current_price", 0.0),
            sma_50=indicators.get("sma_50", 0.0),
            sma_200=indicators.get("sma_200", 0.0),
            ema_20=indicators.get("ema_20", 0.0),
            rsi=indicators.get("rsi", 50.0),
            stoch_k=indicators.get("stoch_k", 50.0),
            stoch_d=indicators.get("stoch_d", 50.0),
            macd=indicators.get("macd", 0.0),
            macd_signal=indicators.get("macd_signal", 0.0),
            macd_hist=indicators.get("macd_hist", 0.0),
            bb_upper=indicators.get("bb_upper", 0.0),
            bb_lower=indicators.get("bb_lower", 0.0),
            bb_basis=indicators.get("bb_basis", 0.0),
            atr=indicators.get("atr", 0.0),
            volume=indicators.get("volume", 0.0),
            obv=indicators.get("obv", 0.0),
            volume_avg_20=indicators.get("volume_avg_20", 0.0),
            volume_surprise=indicators.get("volume_surprise", 0.0),
            relative_volume=indicators.get("relative_volume", 1.0),
            ohlcv=indicators.get("ohlcv_bars", []),
            adx=indicators.get("adx", 20.0),
            plus_di=indicators.get("plus_di", 20.0),
            minus_di=indicators.get("minus_di", 20.0),
            tv_recommendation=indicators.get("tv_recommendation", "UNKNOWN"),
            sma_50_200_spread=indicators.get("sma_50_200_spread", 0.0),
            pct_from_52w_high=indicators.get("pct_from_52w_high"),
            mean_reversion_z=indicators.get("mean_reversion_z"),
        )

    @staticmethod
    def _build_fundamental_features(
        ticker: str, eval_date: str, fundamentals: dict[str, dict[str, float]],
    ) -> FundamentalFeatureSet | None:
        """Build FundamentalFeatureSet from PIT fundamental snapshot."""
        snap = fundamentals.get(eval_date)
        if not snap:
            # Forward-fill: find most recent available snapshot
            avail_dates = sorted(d for d in fundamentals.keys() if d <= eval_date)
            if avail_dates:
                snap = fundamentals[avail_dates[-1]]
            else:
                return None

        return FundamentalFeatureSet(
            ticker=ticker,
            pe_ratio=snap.get("pe_ratio"),
            pb_ratio=snap.get("pb_ratio"),
            ev_ebitda=snap.get("ev_ebitda"),
            fcf_yield=snap.get("fcf_yield"),
            roic=snap.get("roic"),
            roe=snap.get("roe"),
            gross_margin=snap.get("gross_margin"),
            ebit_margin=snap.get("ebit_margin"),
            net_margin=snap.get("net_margin"),
            debt_to_equity=snap.get("debt_to_equity"),
            current_ratio=snap.get("current_ratio"),
            asset_turnover=snap.get("asset_turnover"),
            ev_revenue=snap.get("ev_revenue"),
            ebit_ev=snap.get("ebit_ev"),
            shareholder_yield=snap.get("shareholder_yield"),
            dividend_yield=snap.get("dividend_yield", 0.0),
            market_cap=snap.get("market_cap"),
        )

    # ── Reporting ────────────────────────────────────────────────────────────

    @staticmethod
    def print_report(report: ICScreenReport) -> str:
        """Pretty-print the IC screen report and return as string."""
        lines: list[str] = []
        lines.append("=" * 100)
        lines.append("ALPHA VALIDATION SYSTEM — Signal IC Screen Report")
        lines.append("=" * 100)
        lines.append(f"Universe:  {', '.join(report.universe)}")
        lines.append(f"Period:    {report.eval_period}")
        lines.append(f"Signals:   {report.total_signals}")
        lines.append(f"IC > 0.02: {report.signals_with_ic_gt_002}")
        lines.append(f"IC < 0:    {report.signals_with_negative_ic}")
        lines.append("")

        # Header
        header = (
            f"{'Signal ID':<45} {'Cat':<10} {'N':>5} "
            f"{'IC_5d':>7} {'IC_20d':>7} {'Fire%':>6} "
            f"{'HitR_5d':>7} {'HitR_20d':>8} "
            f"{'AvgR_20d_F':>10} {'AvgR_20d_U':>10} {'Stable':>6}"
        )
        lines.append(header)
        lines.append("-" * len(header))

        for r in report.results:
            stable_str = "✓" if r.ic_stable else "✗"
            ic_5_str = f"{r.ic_5d:+.4f}"
            ic_20_str = f"{r.ic_20d:+.4f}"

            # Color coding via prefix
            if r.ic_20d > 0.02:
                prefix = "🟢"
            elif r.ic_20d < 0:
                prefix = "🔴"
            else:
                prefix = "⚪"

            line = (
                f"{prefix} {r.signal_id:<43} {r.category:<10} {r.n_observations:>5} "
                f"{ic_5_str:>7} {ic_20_str:>7} {r.fire_rate:>5.1%} "
                f"{r.hit_rate_5d:>6.1%} {r.hit_rate_20d:>7.1%} "
                f"{r.avg_return_20d_fired:>9.2%} {r.avg_return_20d_unfired:>9.2%} "
                f"{stable_str:>6}"
            )
            lines.append(line)

        lines.append("")
        lines.append("=" * 100)
        lines.append("LEGEND: IC = Spearman rank correlation (signal value vs forward return)")
        lines.append("  IC > +0.02 = 🟢 signal has predictive power")
        lines.append("  IC ~ 0     = ⚪ no edge")
        lines.append("  IC < 0     = 🔴 inverse predictor (worse than random)")
        lines.append("  Stable     = IC sign consistent across ≥60% of tickers")
        lines.append("=" * 100)

        output = "\n".join(lines)
        print(output)
        return output

    @staticmethod
    def to_json(report: ICScreenReport) -> str:
        """Export report as JSON."""
        data = {
            "universe": report.universe,
            "eval_period": report.eval_period,
            "total_signals": report.total_signals,
            "signals_with_ic_gt_002": report.signals_with_ic_gt_002,
            "signals_with_negative_ic": report.signals_with_negative_ic,
            "results": [
                {
                    "signal_id": r.signal_id,
                    "signal_name": r.signal_name,
                    "category": r.category,
                    "n_observations": r.n_observations,
                    "ic_5d": r.ic_5d,
                    "ic_20d": r.ic_20d,
                    "hit_rate_5d": r.hit_rate_5d,
                    "hit_rate_20d": r.hit_rate_20d,
                    "fire_rate": r.fire_rate,
                    "avg_return_20d_fired": r.avg_return_20d_fired,
                    "avg_return_20d_unfired": r.avg_return_20d_unfired,
                    "ic_stable": r.ic_stable,
                    "per_ticker_ic_20d": r.per_ticker_ic_20d,
                }
                for r in report.results
            ],
        }
        return json.dumps(data, indent=2)


# ─── Statistics ──────────────────────────────────────────────────────────────

def _rank(values: list[float]) -> list[float]:
    """Compute fractional ranks (handling ties with average rank)."""
    n = len(values)
    indexed = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n

    i = 0
    while i < n:
        j = i
        # Find all ties
        while j < n - 1 and values[indexed[j]] == values[indexed[j + 1]]:
            j += 1
        # Average rank for ties
        avg_rank = (i + j) / 2.0 + 1.0  # 1-indexed
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1

    return ranks


def _spearman_correlation(x: list[float], y: list[float]) -> float:
    """
    Spearman rank correlation coefficient.

    Returns value in [-1, 1]. Robust to outliers and non-linearity.
    """
    if len(x) != len(y) or len(x) < 3:
        return 0.0

    rx = _rank(x)
    ry = _rank(y)

    n = len(rx)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n

    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den_x = math.sqrt(sum((rx[i] - mean_rx) ** 2 for i in range(n)))
    den_y = math.sqrt(sum((ry[i] - mean_ry) ** 2 for i in range(n)))

    if den_x == 0 or den_y == 0:
        return 0.0

    return num / (den_x * den_y)
