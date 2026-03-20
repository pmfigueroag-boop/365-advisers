"""
src/engines/backtesting/backtest_memo_agent.py
──────────────────────────────────────────────────────────────────────────────
Backtest Analyst Agent — LLM-powered interpretive memo for Backtest Evidence.

Interprets backtest results (win rate, avg return, sharpe, profit factor)
to produce an institutional-grade memo evaluating statistical edge.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from src.utils.helpers import extract_json
from src.config import get_settings
from src.llm import get_llm, LLMTaskType

logger = logging.getLogger("365advisers.engines.backtesting.memo_agent")
_settings = get_settings()

_llm = get_llm(LLMTaskType.FAST)


class BacktestMemoOutput(TypedDict):
    signal: str
    conviction: str
    narrative: str
    key_data: list[str]
    risk_factors: list[str]


def synthesize_backtest_memo(
    ticker: str,
    backtest_results: list[dict],
) -> BacktestMemoOutput:
    """Generate a backtest evidence memo analyzing statistical edge."""

    def n(v) -> float:
        return float(v) if isinstance(v, (int, float)) and not (isinstance(v, float) and v != v) else 0.0

    if not backtest_results:
        return {
            "signal": "NEUTRAL",
            "conviction": "LOW",
            "narrative": f"No backtest results available for {ticker}.",
            "key_data": [],
            "risk_factors": ["No backtest data — cannot evaluate statistical edge."],
        }

    count = len(backtest_results)

    # Helper: backend returns hit_rate, avg_return, sharpe_ratio as dicts
    # keyed by forward window (1/5/10/20/60). Extract T+20 as reference.
    def extract_window(v, window: int = 20) -> float:
        if isinstance(v, (int, float)):
            return float(v) if v == v else 0.0  # NaN guard
        if isinstance(v, dict):
            return float(v.get(str(window), v.get(window, 0.0)))
        return 0.0

    total_signals = sum(n(r.get("total_firings", 0)) for r in backtest_results)
    avg_wr = sum(extract_window(r.get("hit_rate", r.get("win_rate", 0))) for r in backtest_results) / count * 100
    avg_ret = sum(extract_window(r.get("avg_return", 0)) for r in backtest_results) / count * 100
    avg_sharpe = sum(extract_window(r.get("sharpe_ratio", 0)) for r in backtest_results) / count
    avg_excess = sum(extract_window(r.get("avg_excess_return", 0)) for r in backtest_results) / count * 100

    # Compute proper Profit Factor from individual signal returns at T+20:
    # PF = sum(winning returns) / abs(sum(losing returns))
    all_returns = [extract_window(r.get("avg_return", 0)) for r in backtest_results]
    total_gains = sum(r for r in all_returns if r > 0)
    total_losses = abs(sum(r for r in all_returns if r < 0))
    avg_pf = round(total_gains / total_losses, 2) if total_losses > 0 else (999.0 if total_gains > 0 else 0.0)

    # Build per-signal results
    results_block = "\n".join(
        f"  - {r.get('signal_name', r.get('signal_id', 'N/A'))}: "
        f"WR={extract_window(r.get('hit_rate', r.get('win_rate', 0))) * 100:.1f}%, "
        f"Return={extract_window(r.get('avg_return', 0)) * 100:.2f}%, "
        f"Sharpe={extract_window(r.get('sharpe_ratio', 0)):.2f}, "
        f"Excess={extract_window(r.get('avg_excess_return', 0)) * 100:.2f}%, "
        f"N={n(r.get('total_firings', 0)):.0f}"
        for r in backtest_results[:10]
    )

    fallback: BacktestMemoOutput = {
        "signal": "BULLISH" if avg_wr >= 60 and avg_excess > 0 else
                  "BEARISH" if avg_wr < 40 or avg_ret < -1 else "NEUTRAL",
        "conviction": "HIGH" if total_signals >= 10 and avg_wr >= 65 else
                      "MEDIUM" if total_signals >= 5 else "LOW",
        "narrative": f"Backtest of {count} strategies. WR: {avg_wr:.1f}%, "
                     f"Ret: {avg_ret:.2f}%, Excess vs SPY: {avg_excess:+.2f}%, "
                     f"Sharpe: {avg_sharpe:.2f}, PF: {avg_pf:.2f}.",
        "key_data": [
            f"Win Rate: {avg_wr:.1f}%",
            f"Return T+20: {avg_ret:+.2f}%",
            f"Excess vs SPY: {avg_excess:+.2f}%",
            f"Profit Factor: {avg_pf:.2f}",
        ],
        "risk_factors": ["LLM analysis not available — using deterministic fallback."],
    }

    prompt = f"""You are an institutional quantitative analyst evaluating BACKTEST EVIDENCE.
You are provided with REAL backtesting results of Alpha signals for {ticker}.

BACKTEST RESULTS FOR {ticker}:

[AGGREGATES — T+20 day window]
- Strategies evaluated: {count}
- Total observations: {total_signals:.0f}
- Average Win Rate: {avg_wr:.1f}%
- Average Return T+20: {avg_ret:+.2f}%
- Excess Return vs SPY: {avg_excess:+.2f}%  ← KEY ALPHA METRIC
- Average Sharpe: {avg_sharpe:.2f}
- Profit Factor: {avg_pf:.2f}

[RESULTS PER SIGNAL]
{results_block}

INSTRUCTIONS:
Respond ONLY with valid JSON (no markdown, no code blocks). ALL text in ENGLISH.
Evaluate whether the signals have real statistical edge. Are the win rate and return
significant? Does the Sharpe justify the risk? Are there enough observations?

{{
  "signal": "BULLISH|BEARISH|NEUTRAL",
  "conviction": "HIGH|MEDIUM|LOW",
  "narrative": "<3-4 sentences evaluating statistical edge: do the signals predict correctly? Does the return justify risk? Is the sample sufficient? Cite specific metrics.>",
  "key_data": ["<data 1>", "<data 2>", "<data 3>"],
  "risk_factors": ["<risk 1>", "<risk 2>"]
}}"""

    try:
        raw = _llm.invoke(prompt).content
        parsed = extract_json(raw)
        if not parsed:
            return fallback
        return {
            "signal": str(parsed.get("signal", fallback["signal"])).upper(),
            "conviction": str(parsed.get("conviction", fallback["conviction"])).upper(),
            "narrative": str(parsed.get("narrative", fallback["narrative"])),
            "key_data": list(parsed.get("key_data", fallback["key_data"])),
            "risk_factors": list(parsed.get("risk_factors", fallback["risk_factors"])),
        }
    except Exception as exc:
        logger.error(f"Backtest Memo Agent error for {ticker}: {exc}")
        return fallback
