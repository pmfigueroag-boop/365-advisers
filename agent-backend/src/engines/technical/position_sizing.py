"""
src/engines/technical/position_sizing.py
──────────────────────────────────────────────────────────────────────────────
Volatility-based position sizing with ATR stops.

No professional system recommends a trade without sizing advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PositionSuggestion:
    """Volatility-adjusted position sizing recommendation."""
    method: str = "VOLATILITY_ADJUSTED"
    suggested_pct_of_portfolio: float = 0.0   # 0–1 of portfolio
    stop_loss_price: float = 0.0
    stop_loss_pct: float = 0.0                # distance from entry
    take_profit_price: float = 0.0
    take_profit_pct: float = 0.0
    risk_per_trade_pct: float = 0.02          # max risk per trade (2% default)
    risk_reward_ratio: float = 1.0
    position_conviction: str = "MEDIUM"       # HIGH / MEDIUM / LOW
    rationale: list[str] = field(default_factory=list)


def compute_position_sizing(
    price: float,
    atr: float,
    atr_pct: float,
    signal: str,
    confidence: float,
    risk_reward_ratio: float = 1.0,
    nearest_support: float | None = None,
    nearest_resistance: float | None = None,
    max_risk_pct: float = 0.02,
) -> PositionSuggestion:
    """
    Compute position sizing based on volatility and confidence.

    Strategy:
      - Stop loss = 2× ATR from entry (standard institutional stop)
      - Position size = max_risk / stop_distance (Kelly fraction proxy)
      - Take profit = stop × R/R ratio
      - Conviction adjusts sizing ±30%

    Args:
        price: Current price
        atr: Average True Range
        atr_pct: ATR as percentage of price
        signal: Engine signal (BUY, SELL, etc.)
        confidence: Engine confidence (0–1)
        risk_reward_ratio: From structure analysis
        nearest_support: Nearest support level
        nearest_resistance: Nearest resistance level
        max_risk_pct: Maximum risk per trade as portfolio percentage

    Returns:
        PositionSuggestion with all sizing parameters.
    """
    rationale: list[str] = []

    if price <= 0 or atr <= 0:
        return PositionSuggestion(rationale=["Insufficient data for position sizing"])

    # ── Stop loss: 2× ATR or near support/resistance ─────────────────────
    atr_stop_distance = atr * 2.0
    stop_pct = (atr_stop_distance / price) * 100

    if signal in ("BUY", "STRONG_BUY"):
        # Long position: stop below entry
        if nearest_support and nearest_support < price:
            # Use structure-based stop if it's tighter than ATR stop
            structure_stop = price - nearest_support
            stop_distance = min(atr_stop_distance, structure_stop * 1.02)
        else:
            stop_distance = atr_stop_distance
        stop_loss = price - stop_distance
        stop_pct = (stop_distance / price) * 100
        rationale.append(f"LONG entry at ${price:.2f}, stop at ${stop_loss:.2f} ({stop_pct:.1f}% below)")
    elif signal in ("SELL", "STRONG_SELL"):
        # Short position: stop above entry
        if nearest_resistance and nearest_resistance > price:
            structure_stop = nearest_resistance - price
            stop_distance = min(atr_stop_distance, structure_stop * 1.02)
        else:
            stop_distance = atr_stop_distance
        stop_loss = price + stop_distance
        stop_pct = (stop_distance / price) * 100
        rationale.append(f"SHORT entry at ${price:.2f}, stop at ${stop_loss:.2f} ({stop_pct:.1f}% above)")
    else:
        stop_loss = price - atr_stop_distance
        stop_distance = atr_stop_distance
        stop_pct = (stop_distance / price) * 100
        rationale.append(f"NEUTRAL — no directional bias, monitoring stop at ${stop_loss:.2f}")

    # ── Take profit: R/R multiple of stop distance ───────────────────────
    effective_rr = max(risk_reward_ratio, 1.0)
    take_profit_distance = stop_distance * effective_rr

    if signal in ("BUY", "STRONG_BUY"):
        take_profit = price + take_profit_distance
    elif signal in ("SELL", "STRONG_SELL"):
        take_profit = price - take_profit_distance
    else:
        take_profit = price + take_profit_distance

    tp_pct = (take_profit_distance / price) * 100
    rationale.append(f"Take profit at ${take_profit:.2f} ({tp_pct:.1f}%), R/R = {effective_rr:.2f}")

    # ── Position sizing: max_risk / stop_distance ────────────────────────
    # This is the Kelly fraction proxy: how much to risk
    raw_position_pct = max_risk_pct / (stop_pct / 100) if stop_pct > 0 else 0.0

    # Adjust by confidence: higher confidence = larger position
    confidence_multiplier = 0.5 + confidence  # range [0.5, 1.5]
    adjusted_position_pct = raw_position_pct * confidence_multiplier

    # Cap at 25% of portfolio (hard institutional limit)
    position_pct = min(adjusted_position_pct, 0.25)
    rationale.append(f"Position size: {position_pct:.1%} of portfolio (confidence={confidence:.2f})")

    # ── Conviction classification ────────────────────────────────────────
    if confidence >= 0.75 and signal in ("STRONG_BUY", "STRONG_SELL"):
        conviction = "HIGH"
    elif confidence >= 0.5:
        conviction = "MEDIUM"
    else:
        conviction = "LOW"

    # Reduce position for low conviction
    if conviction == "LOW":
        position_pct *= 0.5
        rationale.append("⚠️ Low conviction — position halved")

    return PositionSuggestion(
        method="VOLATILITY_ADJUSTED",
        suggested_pct_of_portfolio=round(position_pct, 4),
        stop_loss_price=round(stop_loss, 2),
        stop_loss_pct=round(stop_pct, 2),
        take_profit_price=round(take_profit, 2),
        take_profit_pct=round(tp_pct, 2),
        risk_per_trade_pct=max_risk_pct,
        risk_reward_ratio=round(effective_rr, 2),
        position_conviction=conviction,
        rationale=rationale,
    )
