"""
src/engines/validation/composite_backtest.py
──────────────────────────────────────────────────────────────────────────────
Phase 1: Composite Backtest.

Runs the full SignalEvaluator → SignalCombiner → CompositeScore pipeline
historically and measures portfolio-level performance:
  - Sharpe, Sortino, CAGR, max drawdown
  - Hit rates at T+5, T+20
  - IS vs OOS performance comparison (last 3 months held out)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.alpha_signals.combiner import SignalCombiner
from src.engines.alpha_signals.models import CompositeScore
from src.engines.validation.data_loader import ValidationDataLoader
from src.engines.validation.metrics import compute_metrics, PerformanceMetrics

logger = logging.getLogger("365advisers.validation.composite_backtest")


# ─── Result Contract ────────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    """One trade (signal-based entry)."""
    ticker: str
    entry_date: str
    composite_score: float
    signal_level: str = "hold"  # strong_buy / buy / hold
    dominant_category: str = ""
    active_categories: int = 0
    fwd_return_5d: float | None = None
    fwd_return_20d: float | None = None
    is_oos: bool = False


@dataclass
class CompositeBacktestReport:
    """Complete backtest report."""
    universe: list[str]
    eval_period: str = ""
    oos_cutoff: str = ""

    # Portfolio-level metrics
    total_signals: int = 0
    strong_buy_signals: int = 0      # composite_score > 0.35
    buy_signals: int = 0             # composite_score > 0.20 (includes strong_buy)
    buy_threshold: float = 0.20
    strong_buy_threshold: float = 0.35

    # IS metrics
    is_metrics_5d: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    is_metrics_20d: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    is_hit_rate_5d: float = 0.0
    is_hit_rate_20d: float = 0.0
    is_avg_return_5d: float = 0.0
    is_avg_return_20d: float = 0.0

    # OOS metrics (all BUY-level trades)
    oos_hit_rate_5d: float = 0.0
    oos_hit_rate_20d: float = 0.0
    oos_avg_return_5d: float = 0.0
    oos_avg_return_20d: float = 0.0
    oos_trade_count: int = 0

    # Per-level metrics
    strong_buy_avg_20d: float = 0.0
    strong_buy_hit_20d: float = 0.0
    strong_buy_count: int = 0
    buy_only_avg_20d: float = 0.0    # BUY but not STRONG_BUY
    buy_only_hit_20d: float = 0.0
    buy_only_count: int = 0

    # Benchmark
    benchmark_return_20d: float = 0.0  # Average 20d return for ALL observations (buy or not)

    # All trades
    trades: list[TradeRecord] = field(default_factory=list)

    # Score distribution
    score_buckets: dict[str, dict] = field(default_factory=dict)


# ─── Composite Backtest ─────────────────────────────────────────────────────

class CompositeBacktest:
    """
    Run full composite alpha engine historically and measure performance.

    Usage::

        bt = CompositeBacktest()
        report = bt.run(
            tickers=["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"],
            years=2,
            buy_threshold=0.35,
        )
        bt.print_report(report)
    """

    def __init__(self) -> None:
        self._loader = ValidationDataLoader()
        self._evaluator = SignalEvaluator()
        self._combiner = SignalCombiner()

    def run(
        self,
        tickers: list[str],
        years: int = 2,
        eval_frequency_days: int = 5,
        buy_threshold: float = 0.35,
        oos_months: int = 3,
    ) -> CompositeBacktestReport:
        """
        Run composite backtest.

        Parameters
        ----------
        tickers : list[str]
            Universe.
        years : int
            Years of history.
        eval_frequency_days : int
            Days between evaluations.
        buy_threshold : float
            Composite score above this = BUY signal.
        oos_months : int
            Months reserved for out-of-sample testing.
        """
        self._ensure_signals_loaded()

        # Determine OOS cutoff
        end = date.today()
        oos_cutoff = end - timedelta(days=oos_months * 30)
        oos_cutoff_str = oos_cutoff.isoformat()

        all_trades: list[TradeRecord] = []
        sector_cache: dict[str, str] = {}  # ticker → sector string

        for ticker in tickers:
            logger.info(f"AVS-BT: Processing {ticker}...")
            try:
                data = self._loader.load(ticker, years=years)
            except Exception as exc:
                logger.error(f"AVS-BT: Failed to load {ticker}: {exc}")
                continue

            ohlcv = data["ohlcv"]
            fundamentals = data["fundamentals"]
            indicators = data["indicators"]

            if ohlcv.empty or not indicators:
                continue

            ind_dates = sorted(indicators.keys())
            close_map = self._build_close_map(ohlcv)
            sorted_close_dates = sorted(close_map.keys())

            for idx in range(0, len(ind_dates), eval_frequency_days):
                eval_date = ind_dates[idx]
                inds = indicators[eval_date]

                # Build feature sets
                tech_fs = self._build_technical_features(ticker, inds)
                funda_fs = self._build_fundamental_features(
                    ticker, eval_date, fundamentals,
                )

                # Full pipeline: evaluate → combine (sector-adaptive v3)
                profile = self._evaluator.evaluate(ticker, funda_fs, tech_fs)

                # Resolve sector for combiner v3
                if ticker not in sector_cache:
                    try:
                        import yfinance as yf
                        info = yf.Ticker(ticker).info
                        sector_cache[ticker] = info.get("sector", "")
                    except Exception:
                        sector_cache[ticker] = ""

                composite = self._combiner.combine(
                    profile, sector=sector_cache[ticker],
                )

                # Forward returns
                fwd_5 = self._forward_return(eval_date, 5, close_map, sorted_close_dates)
                fwd_20 = self._forward_return(eval_date, 20, close_map, sorted_close_dates)

                trade = TradeRecord(
                    ticker=ticker,
                    entry_date=eval_date,
                    composite_score=round(composite.overall_strength, 4),
                    signal_level=composite.signal_level.value,
                    dominant_category=composite.dominant_category.value if composite.dominant_category else "",
                    active_categories=composite.active_categories,
                    fwd_return_5d=round(fwd_5, 6) if fwd_5 is not None else None,
                    fwd_return_20d=round(fwd_20, 6) if fwd_20 is not None else None,
                    is_oos=eval_date >= oos_cutoff_str,
                )
                all_trades.append(trade)

        # ── Analyze results ──────────────────────────────────────────────────
        return self._analyze(all_trades, tickers, years, oos_cutoff_str, buy_threshold)

    def _analyze(
        self,
        trades: list[TradeRecord],
        tickers: list[str],
        years: int,
        oos_cutoff: str,
        buy_threshold: float,
    ) -> CompositeBacktestReport:
        """Compute all metrics from trade records."""
        # Split IS/OOS
        is_trades = [t for t in trades if not t.is_oos]
        oos_trades = [t for t in trades if t.is_oos]

        # BUY signals: score > 0.20 (includes strong buy)
        is_buys = [t for t in is_trades if t.composite_score > buy_threshold and t.fwd_return_20d is not None]
        oos_buys = [t for t in oos_trades if t.composite_score > buy_threshold and t.fwd_return_20d is not None]
        all_buys = [t for t in trades if t.composite_score > buy_threshold]

        # STRONG BUY signals: score > 0.35
        strong_buy_threshold = 0.35
        all_strong = [t for t in trades if t.composite_score > strong_buy_threshold and t.fwd_return_20d is not None]
        # BUY-only: 0.20 < score <= 0.35
        all_buy_only = [t for t in trades if buy_threshold < t.composite_score <= strong_buy_threshold and t.fwd_return_20d is not None]

        # Overall benchmark (all observations)
        all_valid = [t for t in trades if t.fwd_return_20d is not None]
        benchmark_20d = sum(t.fwd_return_20d for t in all_valid) / len(all_valid) if all_valid else 0.0

        # IS metrics
        is_returns_5d = [t.fwd_return_5d for t in is_buys if t.fwd_return_5d is not None]
        is_returns_20d = [t.fwd_return_20d for t in is_buys if t.fwd_return_20d is not None]

        is_hit_5 = sum(1 for r in is_returns_5d if r > 0) / len(is_returns_5d) if is_returns_5d else 0.0
        is_hit_20 = sum(1 for r in is_returns_20d if r > 0) / len(is_returns_20d) if is_returns_20d else 0.0
        is_avg_5 = sum(is_returns_5d) / len(is_returns_5d) if is_returns_5d else 0.0
        is_avg_20 = sum(is_returns_20d) / len(is_returns_20d) if is_returns_20d else 0.0

        is_metrics_5d = compute_metrics(is_returns_5d) if is_returns_5d else PerformanceMetrics()
        is_metrics_20d = compute_metrics(is_returns_20d) if is_returns_20d else PerformanceMetrics()

        # OOS metrics
        oos_returns_5d = [t.fwd_return_5d for t in oos_buys if t.fwd_return_5d is not None]
        oos_returns_20d = [t.fwd_return_20d for t in oos_buys if t.fwd_return_20d is not None]

        oos_hit_5 = sum(1 for r in oos_returns_5d if r > 0) / len(oos_returns_5d) if oos_returns_5d else 0.0
        oos_hit_20 = sum(1 for r in oos_returns_20d if r > 0) / len(oos_returns_20d) if oos_returns_20d else 0.0
        oos_avg_5 = sum(oos_returns_5d) / len(oos_returns_5d) if oos_returns_5d else 0.0
        oos_avg_20 = sum(oos_returns_20d) / len(oos_returns_20d) if oos_returns_20d else 0.0

        # Score distribution buckets
        score_buckets = self._compute_score_buckets(trades)

        # Per-level metrics
        sb_rets = [t.fwd_return_20d for t in all_strong if t.fwd_return_20d is not None]
        bo_rets = [t.fwd_return_20d for t in all_buy_only if t.fwd_return_20d is not None]

        return CompositeBacktestReport(
            universe=tickers,
            eval_period=f"~{years}Y",
            oos_cutoff=oos_cutoff,
            total_signals=len(trades),
            strong_buy_signals=len(all_strong),
            buy_signals=len(all_buys),
            buy_threshold=buy_threshold,
            strong_buy_threshold=strong_buy_threshold,
            is_metrics_5d=is_metrics_5d,
            is_metrics_20d=is_metrics_20d,
            is_hit_rate_5d=round(is_hit_5, 4),
            is_hit_rate_20d=round(is_hit_20, 4),
            is_avg_return_5d=round(is_avg_5, 6),
            is_avg_return_20d=round(is_avg_20, 6),
            oos_hit_rate_5d=round(oos_hit_5, 4),
            oos_hit_rate_20d=round(oos_hit_20, 4),
            oos_avg_return_5d=round(oos_avg_5, 6),
            oos_avg_return_20d=round(oos_avg_20, 6),
            oos_trade_count=len(oos_buys),
            benchmark_return_20d=round(benchmark_20d, 6),
            trades=trades,
            score_buckets=score_buckets,
            # Per-level
            strong_buy_avg_20d=round(sum(sb_rets)/len(sb_rets), 6) if sb_rets else 0.0,
            strong_buy_hit_20d=round(sum(1 for r in sb_rets if r > 0)/len(sb_rets), 4) if sb_rets else 0.0,
            strong_buy_count=len(all_strong),
            buy_only_avg_20d=round(sum(bo_rets)/len(bo_rets), 6) if bo_rets else 0.0,
            buy_only_hit_20d=round(sum(1 for r in bo_rets if r > 0)/len(bo_rets), 4) if bo_rets else 0.0,
            buy_only_count=len(all_buy_only),
        )

    @staticmethod
    def _compute_score_buckets(trades: list[TradeRecord]) -> dict[str, dict]:
        """Compute avg return by composite score bucket."""
        buckets = {
            "0.0-0.2": {"count": 0, "returns_20d": []},
            "0.2-0.35": {"count": 0, "returns_20d": []},
            "0.35-0.5": {"count": 0, "returns_20d": []},
            "0.5-0.7": {"count": 0, "returns_20d": []},
            "0.7-1.0": {"count": 0, "returns_20d": []},
        }
        for t in trades:
            if t.fwd_return_20d is None:
                continue
            s = t.composite_score
            if s < 0.2:
                key = "0.0-0.2"
            elif s < 0.35:
                key = "0.2-0.35"
            elif s < 0.5:
                key = "0.35-0.5"
            elif s < 0.7:
                key = "0.5-0.7"
            else:
                key = "0.7-1.0"
            buckets[key]["count"] += 1
            buckets[key]["returns_20d"].append(t.fwd_return_20d)

        result = {}
        for key, data in buckets.items():
            rets = data["returns_20d"]
            result[key] = {
                "count": data["count"],
                "avg_return_20d": round(sum(rets) / len(rets), 6) if rets else 0.0,
                "hit_rate": round(
                    sum(1 for r in rets if r > 0) / len(rets), 4
                ) if rets else 0.0,
            }
        return result

    # ── Report ───────────────────────────────────────────────────────────────

    @staticmethod
    def print_report(report: CompositeBacktestReport) -> str:
        """Pretty-print the composite backtest report."""
        lines: list[str] = []
        lines.append("=" * 90)
        lines.append("ALPHA VALIDATION SYSTEM — Phase 1: Composite Backtest Report")
        lines.append("=" * 90)
        lines.append(f"Universe:       {', '.join(report.universe)}")
        lines.append(f"Period:         {report.eval_period}")
        lines.append(f"OOS cutoff:     {report.oos_cutoff}")
        lines.append(f"Total evals:    {report.total_signals}")
        lines.append(f"Benchmark:      avg 20d return for ALL observations = {report.benchmark_return_20d:.2%}")
        lines.append("")

        # 2-Level Buy System
        lines.append("─── 2-LEVEL BUY SYSTEM ────────────────────────────────────────────")
        lines.append(f"  {'Level':<14} {'Threshold':<12} {'Trades':<8} {'Avg T+20d':<12} {'Hit Rate':<10}")
        lines.append("  " + "-" * 56)
        lines.append(
            f"  {'STRONG BUY':<14} {'> 0.35':<12} {report.strong_buy_count:<8} "
            f"{report.strong_buy_avg_20d:>+9.2%}   {report.strong_buy_hit_20d:>7.1%}"
        )
        lines.append(
            f"  {'BUY':<14} {'0.20-0.35':<12} {report.buy_only_count:<8} "
            f"{report.buy_only_avg_20d:>+9.2%}   {report.buy_only_hit_20d:>7.1%}"
        )
        combined_count = report.strong_buy_count + report.buy_only_count
        if combined_count > 0:
            combined_rets = (
                report.strong_buy_avg_20d * report.strong_buy_count +
                report.buy_only_avg_20d * report.buy_only_count
            ) / combined_count
            combined_hit = (
                report.strong_buy_hit_20d * report.strong_buy_count +
                report.buy_only_hit_20d * report.buy_only_count
            ) / combined_count
            lines.append("  " + "-" * 56)
            lines.append(
                f"  {'ALL BUY':<14} {'> 0.20':<12} {combined_count:<8} "
                f"{combined_rets:>+9.2%}   {combined_hit:>7.1%}"
            )
        lines.append("")

        # IS Performance (all BUY-level trades)
        lines.append("─── IN-SAMPLE Performance (all BUY-level trades) ────────────────")
        lines.append(f"  Avg return T+5d:   {report.is_avg_return_5d:+.2%}")
        lines.append(f"  Avg return T+20d:  {report.is_avg_return_20d:+.2%}")
        lines.append(f"  Hit rate T+5d:     {report.is_hit_rate_5d:.1%}")
        lines.append(f"  Hit rate T+20d:    {report.is_hit_rate_20d:.1%}")
        if report.is_metrics_20d.sharpe != 0:
            lines.append(f"  Sharpe (20d):      {report.is_metrics_20d.sharpe:.2f}")
        lines.append("")

        lines.append("─── OUT-OF-SAMPLE Performance ─────────────────────────────────────")
        lines.append(f"  Trades:            {report.oos_trade_count}")
        lines.append(f"  Avg return T+5d:   {report.oos_avg_return_5d:+.2%}")
        lines.append(f"  Avg return T+20d:  {report.oos_avg_return_20d:+.2%}")
        lines.append(f"  Hit rate T+5d:     {report.oos_hit_rate_5d:.1%}")
        lines.append(f"  Hit rate T+20d:    {report.oos_hit_rate_20d:.1%}")
        lines.append("")

        # Overfitting check
        if report.is_avg_return_20d > 0 and report.oos_avg_return_20d > 0:
            decay = 1 - (report.oos_avg_return_20d / report.is_avg_return_20d) if report.is_avg_return_20d != 0 else 0
            if decay < 0.3:
                lines.append(f"  ✅ OOS decay: {decay:.1%} — ROBUST (< 30%)")
            elif decay < 0.6:
                lines.append(f"  ⚠️ OOS decay: {decay:.1%} — MODERATE (30-60%)")
            else:
                lines.append(f"  🔴 OOS decay: {decay:.1%} — HIGH (> 60%) — potential overfit")
        elif report.is_avg_return_20d > 0 > report.oos_avg_return_20d:
            lines.append("  🔴 IS positive / OOS negative — OVERFIT or regime change")
        lines.append("")

        # Score buckets
        lines.append("─── Return by Composite Score Bucket ──────────────────────────────")
        lines.append(f"  {'Bucket':<12} {'Count':>6} {'Avg 20d Return':>15} {'Hit Rate':>10}")
        for bucket, data in sorted(report.score_buckets.items()):
            lines.append(
                f"  {bucket:<12} {data['count']:>6} "
                f"{data['avg_return_20d']:>14.2%} {data['hit_rate']:>9.1%}"
            )
        lines.append("")

        # Alpha vs benchmark
        excess = report.is_avg_return_20d - report.benchmark_return_20d
        lines.append(f"─── Alpha ─────────────────────────────────────────────────────────")
        lines.append(f"  Strategy avg 20d:    {report.is_avg_return_20d:+.2%}")
        lines.append(f"  Benchmark avg 20d:   {report.benchmark_return_20d:+.2%}")
        lines.append(f"  Excess return:       {excess:+.2%}")
        if excess > 0:
            lines.append("  ✅ Strategy generates EXCESS RETURN over unconditional benchmark")
        else:
            lines.append("  🔴 Strategy UNDERPERFORMS unconditional benchmark")
        lines.append("")

        lines.append("=" * 90)
        output = "\n".join(lines)
        print(output)
        return output

    # ── Helpers (shared with ICScreen) ───────────────────────────────────────

    def _ensure_signals_loaded(self) -> None:
        from src.engines.alpha_signals.registry import registry
        if registry.size == 0:
            import src.engines.alpha_signals.signals.value_signals
            import src.engines.alpha_signals.signals.quality_signals
            import src.engines.alpha_signals.signals.growth_signals
            import src.engines.alpha_signals.signals.momentum_signals
            import src.engines.alpha_signals.signals.volatility_signals
            import src.engines.alpha_signals.signals.flow_signals
            import src.engines.alpha_signals.signals.event_signals
            import src.engines.alpha_signals.signals.macro_signals
            try:
                import src.engines.alpha_signals.signals.risk_signals
            except ImportError:
                pass
            try:
                import src.engines.alpha_signals.signals.fundamental_momentum_signals
            except ImportError:
                pass
            try:
                import src.engines.alpha_signals.signals.price_cycle_signals
            except ImportError:
                pass

    @staticmethod
    def _build_close_map(ohlcv) -> dict[str, float]:
        close_map: dict[str, float] = {}
        for idx in ohlcv.index:
            dt = idx.date() if hasattr(idx, "date") else idx
            close_val = ohlcv.loc[idx, "Close"]
            if hasattr(close_val, "item"):
                close_val = close_val.item()
            close_map[dt.isoformat()] = float(close_val)
        return close_map

    @staticmethod
    def _forward_return(eval_date, horizon, close_map, sorted_dates):
        if eval_date not in sorted_dates:
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
    def _build_technical_features(ticker, indicators):
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
            # Tier 2
            realized_vol_20d=indicators.get("realized_vol_20d", 0.0),
            bb_width=indicators.get("bb_width", 0.0),
            mfi=indicators.get("mfi", 50.0),
            effort_result_ratio=indicators.get("effort_result_ratio", 0.0),
        )

    @staticmethod
    def _build_fundamental_features(ticker, eval_date, fundamentals):
        snap = fundamentals.get(eval_date)
        if not snap:
            avail_dates = sorted(d for d in fundamentals.keys() if d <= eval_date)
            if avail_dates:
                snap = fundamentals[avail_dates[-1]]
            else:
                return None

        valid_fields = FundamentalFeatureSet.model_fields.keys()
        kwargs: dict = {"ticker": ticker}
        for key, val in snap.items():
            if key in valid_fields and not key.startswith("_"):
                kwargs[key] = val

        return FundamentalFeatureSet(**kwargs)
