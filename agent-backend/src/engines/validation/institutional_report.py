"""
src/engines/validation/institutional_report.py
──────────────────────────────────────────────────────────────────────────────
Generates institutional-grade markdown report from backtest + statistical
validation results.
"""

from __future__ import annotations

import os
from datetime import datetime

from src.engines.validation.institutional_backtest import InstitutionalReport
from src.engines.validation.statistical_validator import StatisticalReport


VERDICT_EMOJI = {
    "INSTITUTIONAL": "🟢",
    "VALID": "✅",
    "WEAK": "⚠️",
    "NO_ALPHA": "❌",
    "UNKNOWN": "❓",
}


def generate_report(
    backtest: InstitutionalReport,
    stats: StatisticalReport,
    output_dir: str = "reports",
) -> str:
    """Generate full institutional report as markdown string, save to file."""

    verdict = stats.verdict
    emoji = VERDICT_EMOJI.get(verdict, "❓")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# Alpha Validation System — Institutional Report",
        f"**Generated:** {ts}",
        "",
        "---",
        "",
        f"## Executive Summary",
        "",
        f"| Metric | Value |",
        f"|:--|--:|",
        f"| **Verdict** | {emoji} **{verdict}** |",
        f"| Universe Size | {backtest.universe_size} stocks |",
        f"| Total Years | {backtest.total_years}Y |",
        f"| Total Evaluations | {backtest.total_evals:,} |",
        f"| Walk-Forward Windows | {len(backtest.windows)} |",
        f"| OOS BUY Trades | {backtest.agg_oos_trades:,} |",
        f"| OOS Avg T+20d | {backtest.agg_oos_avg_return_20d:+.2%} |",
        f"| OOS Hit Rate | {backtest.agg_oos_hit_rate_20d:.1%} |",
        f"| OOS Sharpe (20d) | {backtest.agg_oos_sharpe_20d:.2f} |",
        f"| Excess Return | {backtest.agg_oos_excess_return:+.2%} |",
        f"| Net Alpha (cost-adj) | {backtest.net_alpha:+.2%} |",
        f"| t-stat | {stats.excess_significance.t_stat:.2f} |" if stats.excess_significance else "| t-stat | N/A |",
        f"| p-value | {stats.excess_significance.p_value:.4f} |" if stats.excess_significance else "| p-value | N/A |",
        "",
    ]

    # ── Walk-Forward Performance ─────────────────────────────────────────
    lines.extend([
        "---",
        "",
        "## Walk-Forward Performance",
        "",
        "| Window | Test Period | OOS Trades | Avg T+20d | Hit Rate | Sharpe | Excess |",
        "|:--|:--|--:|--:|--:|--:|--:|",
    ])

    for w in backtest.windows:
        lines.append(
            f"| W{w.window_id} | {w.test_start[:7]}→{w.test_end[:7]} | "
            f"{w.oos_trades} | {w.oos_avg_return_20d:+.2%} | "
            f"{w.oos_hit_rate_20d:.0%} | {w.oos_sharpe_20d:.2f} | "
            f"{w.oos_excess_return:+.2%} |"
        )

    profitable_windows = sum(1 for w in backtest.windows if w.oos_excess_return > 0)
    total_windows = len(backtest.windows)
    consistency = profitable_windows / total_windows if total_windows > 0 else 0.0
    lines.append("")
    lines.append(f"**Window consistency:** {profitable_windows}/{total_windows} profitable ({consistency:.0%})")
    lines.append("")

    # ── Statistical Significance ─────────────────────────────────────────
    lines.extend([
        "---",
        "",
        "## Statistical Significance",
        "",
    ])

    if stats.alpha_significance:
        sig = stats.alpha_significance
        lines.extend([
            f"### Raw Alpha",
            f"- Mean OOS return: **{sig.mean_return:+.4f}** ({sig.mean_return*100:+.2f}%)",
            f"- Std: {sig.std_return:.4f}",
            f"- t-stat: **{sig.t_stat:.2f}** (n={sig.n_observations})",
            f"- p-value: **{sig.p_value:.4f}** {'✅ significant' if sig.is_significant else '❌ not significant'}",
            f"- 95% CI: [{sig.ci_lower:+.4f}, {sig.ci_upper:+.4f}]",
            "",
        ])

    if stats.excess_significance:
        sig = stats.excess_significance
        lines.extend([
            f"### Excess Return vs Benchmark",
            f"- Mean excess: **{sig.mean_return:+.4f}** ({sig.mean_return*100:+.2f}%)",
            f"- t-stat: **{sig.t_stat:.2f}**",
            f"- p-value: **{sig.p_value:.4f}** {'✅ significant' if sig.is_significant else '❌ not significant'}",
            f"- 95% CI: [{sig.ci_lower:+.4f}, {sig.ci_upper:+.4f}]",
            "",
        ])

    if stats.bootstrap:
        b = stats.bootstrap
        lines.extend([
            f"### Bootstrap Resampling ({b.n_iterations} iterations)",
            f"- Mean of means: {b.mean_of_means:+.4f}",
            f"- 95% CI: [{b.ci_lower:+.4f}, {b.ci_upper:+.4f}]",
            f"- % positive: **{b.pct_positive:.1%}**",
            f"- Robust: {'✅ CI excludes zero' if b.is_robust else '❌ CI includes zero'}",
            "",
        ])

    # ── Robustness Tests ─────────────────────────────────────────────────
    lines.extend([
        "---",
        "",
        "## Robustness Tests",
        "",
    ])

    if stats.noise_injection:
        ni = stats.noise_injection
        lines.extend([
            f"### Noise Injection",
            f"- Baseline alpha: {ni.baseline_alpha:+.4f}",
            f"- Noisy alpha: {ni.perturbed_alpha:+.4f}",
            f"- Degradation: {ni.degradation_pct:.1%}",
            f"- Robust: {'✅' if ni.is_robust else '❌'} (< 50% degradation)",
            "",
        ])

    if stats.param_perturbation:
        lines.extend([
            f"### Parameter Perturbation",
            "| Perturbation | Alpha | Degradation | Robust |",
            "|:--|--:|--:|:--|",
        ])
        for pp in stats.param_perturbation:
            lines.append(
                f"| {pp.test_name} | {pp.perturbed_alpha:+.4f} | "
                f"{pp.degradation_pct:.1%} | {'✅' if pp.is_robust else '❌'} |"
            )
        lines.append("")

    # ── Subsample Analysis ───────────────────────────────────────────────
    if stats.subsamples:
        lines.extend([
            "---",
            "",
            "## Subsample Analysis",
            "",
            "| Subsample | N | Mean Return | Hit Rate | Sharpe | Consistent |",
            "|:--|--:|--:|--:|--:|:--|",
        ])
        for ss in stats.subsamples:
            lines.append(
                f"| {ss.subsample_name} | {ss.n_observations} | "
                f"{ss.mean_return:+.2%} | {ss.hit_rate:.0%} | "
                f"{ss.sharpe:.2f} | {'✅' if ss.is_consistent else '❌'} |"
            )
        lines.append("")

    # ── Cross-Sectional Analysis ─────────────────────────────────────────
    if stats.quintile_returns:
        lines.extend([
            "---",
            "",
            "## Cross-Sectional Analysis (Quintile Portfolios)",
            "",
            "| Quintile | Avg T+20d Return |",
            "|:--|--:|",
        ])
        for q in range(1, 6):
            label = "⬆️ Top" if q == 1 else ("⬇️ Bottom" if q == 5 else f"Q{q}")
            ret = stats.quintile_returns.get(q, 0.0)
            lines.append(f"| {label} (Q{q}) | {ret:+.2%} |")

        lines.extend([
            "",
            f"- **Long-Short Spread:** {stats.long_short_spread:+.2%}",
            f"- **Monotonicity Score:** {stats.monotonicity_score:.0%} (1.0 = perfect)",
            "",
        ])

    # ── Decay Analysis ───────────────────────────────────────────────────
    if stats.decay_by_horizon:
        lines.extend([
            "---",
            "",
            "## Alpha Decay by Horizon",
            "",
            "| Horizon | Avg OOS Return |",
            "|:--|--:|",
        ])
        for h, ret in stats.decay_by_horizon.items():
            lines.append(f"| {h} | {ret:+.2%} |")
        lines.append("")

    # ── Final Verdict ────────────────────────────────────────────────────
    lines.extend([
        "---",
        "",
        f"## Final Verdict: {emoji} {verdict}",
        "",
    ])

    verdict_explanations = {
        "INSTITUTIONAL": "Alpha is statistically significant (t>2.5), robust across subsamples, and survives transaction costs. Suitable for institutional deployment.",
        "VALID": "Alpha is statistically significant (t>2) with positive evidence across most tests. Suitable for production with monitoring.",
        "WEAK": "Some evidence of alpha but not statistically conclusive. Requires further validation or larger sample.",
        "NO_ALPHA": "No statistically significant alpha detected. The signal does not demonstrate edge beyond random chance.",
    }
    lines.append(verdict_explanations.get(verdict, "Insufficient data for classification."))
    lines.append("")

    report_text = "\n".join(lines)

    # Save to file
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "institutional_report.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)

    return report_text
