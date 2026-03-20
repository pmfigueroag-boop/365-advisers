"""
src/engines/validation/signal_diagnostics.py
──────────────────────────────────────────────────────────────────────────────
Phase 2: Signal Robustness Diagnostics.

Three tests to determine if signals are robust or overfit:
  1. Correlation Matrix — detect redundant signals
  2. IC Decay Curves — how quickly does predictive power fade?
  3. Noise Injection — does IC survive 5% random perturbation?
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.validation.data_loader import ValidationDataLoader

logger = logging.getLogger("365advisers.validation.diagnostics")


# ─── Result Contracts ────────────────────────────────────────────────────────

@dataclass
class CorrelationPair:
    signal_a: str
    signal_b: str
    correlation: float  # Spearman


@dataclass
class DecayCurve:
    signal_id: str
    signal_name: str
    category: str
    ic_by_horizon: dict[int, float] = field(default_factory=dict)  # horizon → IC
    peak_horizon: int = 0  # Horizon with max abs(IC)
    half_life: int | None = None  # Horizon where IC drops to 50% of peak


@dataclass
class NoiseTest:
    signal_id: str
    ic_original: float
    ic_noisy: float  # After 5% perturbation
    ic_retained: float  # ic_noisy / ic_original (1.0 = fully robust)
    robust: bool  # True if retained > 0.5


@dataclass
class DiagnosticsReport:
    universe: list[str]
    # Correlation
    high_correlations: list[CorrelationPair] = field(default_factory=list)  # |corr| > 0.7
    # Decay
    decay_curves: list[DecayCurve] = field(default_factory=list)
    # Noise
    noise_tests: list[NoiseTest] = field(default_factory=list)
    noise_survival_rate: float = 0.0  # % signals that survive noise


# ─── Signal Diagnostics ─────────────────────────────────────────────────────

class SignalDiagnostics:
    """
    Run robustness diagnostics on all active alpha signals.

    Usage::

        diag = SignalDiagnostics()
        report = diag.run(
            tickers=["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"],
        )
        diag.print_report(report)
    """

    def __init__(self) -> None:
        self._loader = ValidationDataLoader()
        self._evaluator = SignalEvaluator()

    def run(
        self,
        tickers: list[str],
        years: int = 2,
        eval_frequency_days: int = 5,
        noise_pct: float = 0.05,
        seed: int = 42,
    ) -> DiagnosticsReport:
        """Run all diagnostics."""
        self._ensure_signals_loaded()

        # Collect signal values and forward returns at multiple horizons
        horizons = [1, 5, 10, 20, 40]
        # signal_id → list of (value, {horizon: fwd_return})
        signal_data: dict[str, list[tuple[float, dict[int, float | None]]]] = {}

        for ticker in tickers:
            logger.info(f"AVS-DIAG: Processing {ticker}...")
            try:
                data = self._loader.load(ticker, years=years)
            except Exception as exc:
                logger.error(f"AVS-DIAG: Failed to load {ticker}: {exc}")
                continue

            ohlcv = data["ohlcv"]
            indicators = data["indicators"]
            fundamentals = data["fundamentals"]

            if ohlcv.empty or not indicators:
                continue

            ind_dates = sorted(indicators.keys())
            close_map = self._build_close_map(ohlcv)
            sorted_close_dates = sorted(close_map.keys())

            for idx in range(0, len(ind_dates), eval_frequency_days):
                eval_date = ind_dates[idx]
                inds = indicators[eval_date]

                tech_fs = self._build_tech(ticker, inds)
                funda_fs = self._build_funda(ticker, eval_date, fundamentals)

                profile = self._evaluator.evaluate(ticker, funda_fs, tech_fs)

                # Forward returns at multiple horizons
                fwd_returns = {}
                for h in horizons:
                    fwd_returns[h] = self._forward_return(
                        eval_date, h, close_map, sorted_close_dates,
                    )

                for sig in profile.signals:
                    val = sig.confidence if sig.fired else 0.0
                    if sig.signal_id not in signal_data:
                        signal_data[sig.signal_id] = []
                    signal_data[sig.signal_id].append((val, fwd_returns))

        # ── 1. Correlation Matrix ────────────────────────────────────────────
        high_corrs = self._compute_correlations(signal_data)

        # ── 2. IC Decay Curves ───────────────────────────────────────────────
        decay_curves = self._compute_decay(signal_data, horizons)

        # ── 3. Noise Injection ───────────────────────────────────────────────
        noise_tests = self._compute_noise(signal_data, noise_pct, seed)

        survival = sum(1 for t in noise_tests if t.robust) / len(noise_tests) if noise_tests else 0.0

        return DiagnosticsReport(
            universe=tickers,
            high_correlations=high_corrs,
            decay_curves=decay_curves,
            noise_tests=noise_tests,
            noise_survival_rate=round(survival, 4),
        )

    # ── Diagnostics ──────────────────────────────────────────────────────────

    def _compute_correlations(
        self, signal_data: dict[str, list[tuple[float, dict]]],
    ) -> list[CorrelationPair]:
        """Compute pairwise Spearman correlations between signal value series."""
        # Only signals with meaningful variation
        active_ids = [
            sid for sid, obs in signal_data.items()
            if len(set(v for v, _ in obs)) > 2 and len(obs) >= 10
        ]

        pairs: list[CorrelationPair] = []
        for i, sid_a in enumerate(active_ids):
            vals_a = [v for v, _ in signal_data[sid_a]]
            for sid_b in active_ids[i+1:]:
                vals_b = [v for v, _ in signal_data[sid_b]]
                min_len = min(len(vals_a), len(vals_b))
                if min_len < 10:
                    continue
                corr = _spearman(vals_a[:min_len], vals_b[:min_len])
                if abs(corr) > 0.7:
                    pairs.append(CorrelationPair(
                        signal_a=sid_a, signal_b=sid_b,
                        correlation=round(corr, 4),
                    ))

        pairs.sort(key=lambda p: abs(p.correlation), reverse=True)
        return pairs

    def _compute_decay(
        self,
        signal_data: dict[str, list[tuple[float, dict]]],
        horizons: list[int],
    ) -> list[DecayCurve]:
        """Compute IC at each horizon for each signal."""
        from src.engines.alpha_signals.registry import registry
        curves: list[DecayCurve] = []

        for sid, obs in signal_data.items():
            sig_def = registry.get(sid)
            if not sig_def:
                continue

            vals = [v for v, _ in obs]
            if len(set(vals)) < 3:
                continue  # Skip constant signals

            ic_by_h: dict[int, float] = {}
            for h in horizons:
                fwds = [fwd.get(h) for _, fwd in obs]
                valid_pairs = [
                    (v, f) for v, f in zip(vals, fwds)
                    if f is not None
                ]
                if len(valid_pairs) < 10:
                    continue
                v_list, f_list = zip(*valid_pairs)
                ic_by_h[h] = round(_spearman(list(v_list), list(f_list)), 4)

            if not ic_by_h:
                continue

            # Peak horizon
            peak_h = max(ic_by_h, key=lambda h: abs(ic_by_h[h]))
            peak_ic = abs(ic_by_h[peak_h])

            # Half-life: first horizon after peak where IC drops below 50%
            half_life = None
            if peak_ic > 0:
                sorted_h = sorted(ic_by_h.keys())
                peak_idx = sorted_h.index(peak_h) if peak_h in sorted_h else 0
                for h in sorted_h[peak_idx + 1:]:
                    if abs(ic_by_h[h]) < peak_ic * 0.5:
                        half_life = h
                        break

            curves.append(DecayCurve(
                signal_id=sid,
                signal_name=sig_def.name,
                category=sig_def.category.value,
                ic_by_horizon=ic_by_h,
                peak_horizon=peak_h,
                half_life=half_life,
            ))

        # Sort by peak IC descending
        curves.sort(key=lambda c: abs(c.ic_by_horizon.get(c.peak_horizon, 0)), reverse=True)
        return curves

    def _compute_noise(
        self,
        signal_data: dict[str, list[tuple[float, dict]]],
        noise_pct: float,
        seed: int,
    ) -> list[NoiseTest]:
        """Inject noise into signal values and check if IC survives."""
        rng = random.Random(seed)
        tests: list[NoiseTest] = []

        for sid, obs in signal_data.items():
            vals = [v for v, _ in obs]
            fwds_20 = [fwd.get(20) for _, fwd in obs]

            # Filter valid pairs
            valid = [(v, f) for v, f in zip(vals, fwds_20) if f is not None]
            if len(valid) < 10 or len(set(v for v, _ in valid)) < 3:
                continue

            v_list, f_list = zip(*valid)
            ic_original = _spearman(list(v_list), list(f_list))

            # Add noise: Gaussian perturbation scaled to signal range
            v_range = max(v_list) - min(v_list)
            if v_range == 0:
                continue
            noise_scale = v_range * noise_pct
            noisy_vals = [v + rng.gauss(0, noise_scale) for v in v_list]
            ic_noisy = _spearman(noisy_vals, list(f_list))

            # Retention ratio
            retained = ic_noisy / ic_original if ic_original != 0 else 0.0
            robust = retained > 0.5 and math.copysign(1, ic_noisy) == math.copysign(1, ic_original)

            tests.append(NoiseTest(
                signal_id=sid,
                ic_original=round(ic_original, 4),
                ic_noisy=round(ic_noisy, 4),
                ic_retained=round(retained, 4),
                robust=robust,
            ))

        tests.sort(key=lambda t: abs(t.ic_original), reverse=True)
        return tests

    # ── Report ───────────────────────────────────────────────────────────────

    @staticmethod
    def print_report(report: DiagnosticsReport) -> str:
        lines: list[str] = []
        lines.append("=" * 90)
        lines.append("ALPHA VALIDATION SYSTEM — Phase 2: Signal Diagnostics Report")
        lines.append("=" * 90)
        lines.append(f"Universe: {', '.join(report.universe)}")
        lines.append("")

        # 1. Correlations
        lines.append("─── 1. SIGNAL CORRELATION (|ρ| > 0.7) ────────────────────────────")
        if report.high_correlations:
            for p in report.high_correlations:
                lines.append(f"  {p.signal_a:<40} ↔ {p.signal_b:<40} ρ={p.correlation:+.3f}")
        else:
            lines.append("  ✅ No highly correlated signal pairs found")
        lines.append("")

        # 2. Decay curves (only for signals with meaningful IC)
        lines.append("─── 2. IC DECAY CURVES ────────────────────────────────────────────")
        lines.append(f"  {'Signal':<40} {'T+1':>6} {'T+5':>6} {'T+10':>6} {'T+20':>6} {'T+40':>6} {'Peak':>5} {'HL':>4}")
        lines.append("  " + "-" * 85)
        for c in report.decay_curves:
            if abs(c.ic_by_horizon.get(c.peak_horizon, 0)) < 0.01:
                continue  # Skip near-zero
            hl_str = str(c.half_life) if c.half_life else "—"
            line = (
                f"  {c.signal_id:<40} "
                f"{c.ic_by_horizon.get(1, 0):>+5.3f} "
                f"{c.ic_by_horizon.get(5, 0):>+5.3f} "
                f"{c.ic_by_horizon.get(10, 0):>+5.3f} "
                f"{c.ic_by_horizon.get(20, 0):>+5.3f} "
                f"{c.ic_by_horizon.get(40, 0):>+5.3f} "
                f"{'T+' + str(c.peak_horizon):>5} "
                f"{hl_str:>4}"
            )
            lines.append(line)
        lines.append("")

        # 3. Noise injection
        lines.append("─── 3. NOISE INJECTION (5% perturbation) ──────────────────────────")
        lines.append(f"  Survival rate: {report.noise_survival_rate:.1%}")
        lines.append("")
        lines.append(f"  {'Signal':<40} {'IC_orig':>8} {'IC_noisy':>8} {'Retained':>8} {'Robust':>6}")
        lines.append("  " + "-" * 75)
        for t in report.noise_tests:
            if abs(t.ic_original) < 0.01:
                continue
            robust_str = "✓" if t.robust else "✗"
            lines.append(
                f"  {t.signal_id:<40} {t.ic_original:>+7.4f} {t.ic_noisy:>+7.4f} "
                f"{t.ic_retained:>7.1%} {robust_str:>6}"
            )
        lines.append("")
        lines.append("=" * 90)

        output = "\n".join(lines)
        print(output)
        return output

    # ── Shared helpers ───────────────────────────────────────────────────────

    def _ensure_signals_loaded(self):
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
        close_map = {}
        for idx in ohlcv.index:
            dt = idx.date() if hasattr(idx, "date") else idx
            cv = ohlcv.loc[idx, "Close"]
            if hasattr(cv, "item"):
                cv = cv.item()
            close_map[dt.isoformat()] = float(cv)
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
        p0 = close_map.get(sorted_dates[pos], 0)
        p1 = close_map.get(sorted_dates[target_pos], 0)
        return (p1 - p0) / p0 if p0 > 0 else None

    @staticmethod
    def _build_tech(ticker, indicators):
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
            sma_50_200_spread=indicators.get("sma_50_200_spread", 0.0),
            pct_from_52w_high=indicators.get("pct_from_52w_high"),
            mean_reversion_z=indicators.get("mean_reversion_z"),
        )

    @staticmethod
    def _build_funda(ticker, eval_date, fundamentals):
        snap = fundamentals.get(eval_date)
        if not snap:
            avail = sorted(d for d in fundamentals if d <= eval_date)
            snap = fundamentals[avail[-1]] if avail else None
        if not snap:
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


# ─── Statistics ──────────────────────────────────────────────────────────────

def _rank(values: list[float]) -> list[float]:
    n = len(values)
    indexed = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and values[indexed[j]] == values[indexed[j + 1]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 3:
        return 0.0
    rx, ry = _rank(x), _rank(y)
    n = len(rx)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0
