"""
src/engines/technical/indicators.py
─────────────────────────────────────────────────────────────────────────────
IndicatorEngine — pure-Python, deterministic computation of all technical
indicators. No LLM required. Uses raw indicator values from MarketDataFetcher.

Modules:
  TrendModule       — SMA50/200, EMA20, MACD crossover, golden/death cross
  MomentumModule    — RSI, Stochastic
  VolatilityModule  — Bollinger Bands, ATR
  VolumeModule      — OBV trend, volume vs 20-period average
  StructureModule   — Support/Resistance via pivot logic, breakout detection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ─── Result dataclasses ───────────────────────────────────────────────────────

@dataclass
class TrendResult:
    sma_50: float
    sma_200: float
    ema_20: float
    macd_value: float
    macd_signal: float
    macd_histogram: float
    price_vs_sma50:  Literal["ABOVE", "BELOW", "AT"]
    price_vs_sma200: Literal["ABOVE", "BELOW", "AT"]
    macd_crossover:  Literal["BULLISH", "BEARISH", "NEUTRAL"]
    golden_cross:    bool   # SMA50 > SMA200
    death_cross:     bool   # SMA50 < SMA200
    status: Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]


@dataclass
class MomentumResult:
    rsi: float
    rsi_zone: Literal["OVERBOUGHT", "NEUTRAL", "OVERSOLD"]
    stoch_k: float
    stoch_d: float
    stoch_zone: Literal["OVERBOUGHT", "NEUTRAL", "OVERSOLD"]
    status: Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]


@dataclass
class VolatilityResult:
    bb_upper: float
    bb_lower: float
    bb_basis: float
    bb_width: float
    bb_position: Literal["UPPER", "UPPER_MID", "MID", "LOWER_MID", "LOWER"]
    atr: float
    atr_pct: float          # ATR as % of price
    condition: Literal["HIGH", "ELEVATED", "NORMAL", "LOW"]


@dataclass
class VolumeResult:
    obv: float
    obv_trend: Literal["RISING", "FLAT", "FALLING"]
    current_volume: float
    volume_vs_avg: float    # ratio: current / 20-period avg (proxy)
    status: Literal["STRONG", "NORMAL", "WEAK"]


@dataclass
class StructureResult:
    resistance_levels: list[float] = field(default_factory=list)
    support_levels: list[float] = field(default_factory=list)
    breakout_probability: float = 0.0   # 0.0 – 1.0
    breakout_direction: Literal["BULLISH", "BEARISH", "NEUTRAL"] = "NEUTRAL"
    nearest_resistance: float | None = None
    nearest_support: float | None = None
    distance_to_resistance_pct: float | None = None
    distance_to_support_pct: float | None = None
    # ── V2 fields ──
    market_structure: Literal["HH_HL", "LH_LL", "MIXED"] = "MIXED"
    level_strength: dict = field(default_factory=dict)  # {"level": touches}
    patterns: list[str] = field(default_factory=list)   # detected patterns


@dataclass
class IndicatorResult:
    trend:      TrendResult
    momentum:   MomentumResult
    volatility: VolatilityResult
    volume:     VolumeResult
    structure:  StructureResult


# ─── TrendModule ──────────────────────────────────────────────────────────────

class TrendModule:
    @staticmethod
    def compute(price: float, inds: dict) -> TrendResult:
        sma50  = inds.get("sma50", 0.0) or 0.0
        sma200 = inds.get("sma200", 0.0) or 0.0
        ema20  = inds.get("ema20", 0.0) or 0.0
        macd   = inds.get("macd", 0.0) or 0.0
        macd_s = inds.get("macd_signal", 0.0) or 0.0
        macd_h = inds.get("macd_hist", 0.0) or macd - macd_s

        def rel(p, ref) -> Literal["ABOVE", "BELOW", "AT"]:
            if ref == 0:
                return "AT"
            diff = (p - ref) / ref
            if diff > 0.005:
                return "ABOVE"
            if diff < -0.005:
                return "BELOW"
            return "AT"

        p_vs_50  = rel(price, sma50)
        p_vs_200 = rel(price, sma200)
        golden   = sma50 > sma200 and sma50 > 0 and sma200 > 0
        death    = sma50 < sma200 and sma50 > 0 and sma200 > 0

        if macd > macd_s:
            crossover = "BULLISH"
        elif macd < macd_s:
            crossover = "BEARISH"
        else:
            crossover = "NEUTRAL"

        # Status logic
        bullish_signals = sum([
            p_vs_50 == "ABOVE",
            p_vs_200 == "ABOVE",
            golden,
            crossover == "BULLISH",
        ])
        if bullish_signals >= 4:
            status = "STRONG_BULLISH"
        elif bullish_signals >= 2:
            status = "BULLISH"
        elif bullish_signals == 0:
            bearish = sum([p_vs_50 == "BELOW", p_vs_200 == "BELOW", death, crossover == "BEARISH"])
            status = "STRONG_BEARISH" if bearish >= 3 else "BEARISH"
        else:
            status = "NEUTRAL"

        return TrendResult(
            sma_50=sma50, sma_200=sma200, ema_20=ema20,
            macd_value=macd, macd_signal=macd_s, macd_histogram=macd_h,
            price_vs_sma50=p_vs_50, price_vs_sma200=p_vs_200,
            macd_crossover=crossover,
            golden_cross=golden, death_cross=death,
            status=status,
        )


# ─── MomentumModule ───────────────────────────────────────────────────────────

class MomentumModule:
    @staticmethod
    def compute(inds: dict) -> MomentumResult:
        rsi     = inds.get("rsi", 50.0) or 50.0
        stoch_k = inds.get("stoch_k", 50.0) or 50.0
        stoch_d = inds.get("stoch_d", 50.0) or 50.0

        def rsi_zone(v: float) -> Literal["OVERBOUGHT", "NEUTRAL", "OVERSOLD"]:
            if v >= 70:
                return "OVERBOUGHT"
            if v <= 30:
                return "OVERSOLD"
            return "NEUTRAL"

        def stoch_zone(v: float) -> Literal["OVERBOUGHT", "NEUTRAL", "OVERSOLD"]:
            if v >= 80:
                return "OVERBOUGHT"
            if v <= 20:
                return "OVERSOLD"
            return "NEUTRAL"

        rz = rsi_zone(rsi)
        sz = stoch_zone(stoch_k)

        if rz == "OVERSOLD" and sz == "OVERSOLD":
            status = "STRONG_BULLISH"
        elif rz == "OVERSOLD" or (sz == "OVERSOLD" and 40 <= rsi <= 50):
            status = "BULLISH"
        elif rz == "OVERBOUGHT" and sz == "OVERBOUGHT":
            status = "STRONG_BEARISH"
        elif rz == "OVERBOUGHT" or sz == "OVERBOUGHT":
            status = "BEARISH"
        else:
            # Neutral zone — mild directional bias
            status = "BULLISH" if rsi > 55 else "BEARISH" if rsi < 45 else "NEUTRAL"

        return MomentumResult(
            rsi=round(rsi, 2), rsi_zone=rz,
            stoch_k=round(stoch_k, 2), stoch_d=round(stoch_d, 2), stoch_zone=sz,
            status=status,
        )


# ─── VolatilityModule ─────────────────────────────────────────────────────────

class VolatilityModule:
    @staticmethod
    def compute(price: float, inds: dict) -> VolatilityResult:
        bb_upper = inds.get("bb_upper", 0.0) or 0.0
        bb_lower = inds.get("bb_lower", 0.0) or 0.0
        bb_basis = inds.get("bb_basis", 0.0) or (bb_upper + bb_lower) / 2 if bb_upper else 0.0
        atr      = inds.get("atr", 0.0) or 0.0

        bb_width = bb_upper - bb_lower if bb_upper and bb_lower else 0.0
        atr_pct  = (atr / price) if price > 0 and atr > 0 else 0.0

        # BB position
        if bb_width > 0 and bb_upper > 0:
            pos_pct = (price - bb_lower) / bb_width   # 0=at lower, 1=at upper
            if pos_pct >= 0.85:
                bb_position = "UPPER"
            elif pos_pct >= 0.6:
                bb_position = "UPPER_MID"
            elif pos_pct >= 0.4:
                bb_position = "MID"
            elif pos_pct >= 0.15:
                bb_position = "LOWER_MID"
            else:
                bb_position = "LOWER"
        else:
            bb_position = "MID"

        # Condition based on ATR%
        if atr_pct >= 0.04:
            condition = "HIGH"
        elif atr_pct >= 0.025:
            condition = "ELEVATED"
        elif atr_pct >= 0.01:
            condition = "NORMAL"
        else:
            condition = "LOW"

        return VolatilityResult(
            bb_upper=round(bb_upper, 4), bb_lower=round(bb_lower, 4),
            bb_basis=round(bb_basis, 4), bb_width=round(bb_width, 4),
            bb_position=bb_position,
            atr=round(atr, 4), atr_pct=round(atr_pct, 4),
            condition=condition,
        )


# ─── VolumeModule ─────────────────────────────────────────────────────────────

class VolumeModule:
    @staticmethod
    def compute(inds: dict, ohlcv: list[dict]) -> VolumeResult:
        obv     = inds.get("obv", 0.0) or 0.0
        cur_vol = inds.get("volume", 0.0) or 0.0

        # Volume vs 20-period average from OHLCV
        vol_avg = 0.0
        if ohlcv and len(ohlcv) >= 20:
            recent = ohlcv[-20:]
            vols = [b.get("volume", 0) for b in recent if b.get("volume")]
            vol_avg = sum(vols) / len(vols) if vols else 0.0

        vol_ratio = (cur_vol / vol_avg) if vol_avg > 0 else 1.0

        # OBV trend: compare last 5 OBV readings (we only have current — proxy via price trend)
        # Without OBV series, use TV obv value sign as a rough indicator
        obv_trend: Literal["RISING", "FLAT", "FALLING"] = "FLAT"
        if len(ohlcv) >= 5:
            recent_closes = [b["close"] for b in ohlcv[-5:] if "close" in b]
            if len(recent_closes) >= 5:
                price_up = recent_closes[-1] > recent_closes[0]
                if obv > 0:
                    obv_trend = "RISING" if price_up else "FLAT"
                elif obv < 0:
                    obv_trend = "FALLING" if not price_up else "FLAT"

        strength: Literal["STRONG", "NORMAL", "WEAK"] = (
            "STRONG" if vol_ratio >= 1.5
            else "WEAK" if vol_ratio < 0.7
            else "NORMAL"
        )

        return VolumeResult(
            obv=round(obv, 2), obv_trend=obv_trend,
            current_volume=round(cur_vol, 0),
            volume_vs_avg=round(vol_ratio, 2),
            status=strength,
        )


# ─── StructureModule ──────────────────────────────────────────────────────────

class StructureModule:
    @staticmethod
    def compute(price: float, ohlcv: list[dict]) -> StructureResult:
        """
        Detect support / resistance via pivot highs and lows.
        V2: Adds market structure (HH/HL), level strength, and pattern detection.
        """
        if len(ohlcv) < 20:
            return StructureResult()

        recent = ohlcv[-60:]  # last 60 days for pivot detection

        # ── Pivot detection ────────────────────────────────────────────────
        window = 5
        pivot_highs: list[tuple[int, float]] = []  # (index, price)
        pivot_lows: list[tuple[int, float]] = []
        resistance_levels: list[float] = []
        support_levels: list[float] = []

        for i in range(window, len(recent) - window):
            h = recent[i].get("high", 0)
            l = recent[i].get("low", 0)
            # Pivot high: highest in window
            if h == max(b.get("high", 0) for b in recent[i - window: i + window + 1]):
                pivot_highs.append((i, h))
                if h > price:
                    resistance_levels.append(round(h, 2))
            # Pivot low: lowest in window
            if l == min(b.get("low", float("inf")) for b in recent[i - window: i + window + 1]):
                pivot_lows.append((i, l))
                if l < price:
                    support_levels.append(round(l, 2))

        # ── Cluster S/R within 1% band ─────────────────────────────────────
        def cluster(levels: list[float], threshold=0.01) -> list[float]:
            if not levels:
                return []
            levels = sorted(set(levels))
            clustered, group = [], [levels[0]]
            for v in levels[1:]:
                if (v - group[0]) / group[0] <= threshold:
                    group.append(v)
                else:
                    clustered.append(round(sum(group) / len(group), 2))
                    group = [v]
            clustered.append(round(sum(group) / len(group), 2))
            return clustered

        res = cluster(resistance_levels)[:3]
        sup = cluster(support_levels)[-3:]

        nearest_res = min(res, default=None)
        nearest_sup = max(sup, default=None)

        dist_res = ((nearest_res - price) / price) if nearest_res and price else None
        dist_sup = ((price - nearest_sup) / price) if nearest_sup and price else None

        # ── V2: Market Structure (HH/HL vs LH/LL) ──────────────────────────
        market_structure = _detect_market_structure(pivot_highs, pivot_lows)

        # ── V2: Key Level Strength ──────────────────────────────────────────
        all_levels = res + sup
        level_strength = _compute_level_strength(all_levels, ohlcv[-60:], price)

        # ── V2: Pattern Recognition ─────────────────────────────────────────
        patterns = _detect_patterns(pivot_highs, pivot_lows, price)

        # ── Breakout probability (enhanced with V2 data) ────────────────────
        bp = 0.3  # baseline
        if dist_res is not None:
            if dist_res < 0.02:
                bp += 0.25
            elif dist_res < 0.05:
                bp += 0.10

        # Market structure bonus
        if market_structure == "HH_HL":
            bp += 0.10
        elif market_structure == "LH_LL":
            bp -= 0.05

        # Strong level support bonus
        if nearest_sup and any(s.get("touches", 0) >= 3 for s in level_strength.values()):
            bp += 0.05

        # Pattern bonus
        if "DOUBLE_BOTTOM" in patterns or "HIGHER_LOWS" in patterns:
            bp += 0.10
        if "DOUBLE_TOP" in patterns or "LOWER_HIGHS" in patterns:
            bp -= 0.05

        if dist_sup is not None and dist_res is not None:
            if dist_res < dist_sup:
                direction = "BULLISH"
            elif dist_sup < dist_res:
                direction = "BEARISH"
                bp = max(0.0, bp - 0.1)
            else:
                direction = "NEUTRAL"
        else:
            direction = "NEUTRAL"

        bp = round(min(bp, 0.95), 2)

        return StructureResult(
            resistance_levels=res,
            support_levels=sup,
            breakout_probability=bp,
            breakout_direction=direction,
            nearest_resistance=nearest_res,
            nearest_support=nearest_sup,
            distance_to_resistance_pct=round(dist_res * 100, 2) if dist_res is not None else None,
            distance_to_support_pct=round(dist_sup * 100, 2) if dist_sup is not None else None,
            market_structure=market_structure,
            level_strength=level_strength,
            patterns=patterns,
        )


# ─── Structure V2 helpers ─────────────────────────────────────────────────────

def _detect_market_structure(
    pivot_highs: list[tuple[int, float]],
    pivot_lows: list[tuple[int, float]],
) -> Literal["HH_HL", "LH_LL", "MIXED"]:
    """
    Analyze the last 3+ swing points to determine if the market is making
    Higher Highs & Higher Lows (uptrend), Lower Highs & Lower Lows (downtrend),
    or a mixed/choppy structure.
    """
    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        return "MIXED"

    # Take last 3 of each
    last_highs = [p for _, p in pivot_highs[-3:]]
    last_lows = [p for _, p in pivot_lows[-3:]]

    # Check for Higher Highs
    hh = all(last_highs[i] > last_highs[i-1] for i in range(1, len(last_highs)))
    # Check for Higher Lows
    hl = all(last_lows[i] > last_lows[i-1] for i in range(1, len(last_lows)))
    # Check for Lower Highs
    lh = all(last_highs[i] < last_highs[i-1] for i in range(1, len(last_highs)))
    # Check for Lower Lows
    ll = all(last_lows[i] < last_lows[i-1] for i in range(1, len(last_lows)))

    if hh and hl:
        return "HH_HL"
    elif lh and ll:
        return "LH_LL"
    return "MIXED"


def _compute_level_strength(
    levels: list[float],
    ohlcv: list[dict],
    current_price: float,
    touch_band: float = 0.005,  # 0.5% proximity counts as a "touch"
) -> dict:
    """
    Count how many times price came within `touch_band` of each S/R level.
    Returns {"level": {"touches": N, "strong": bool}}.
    """
    result = {}
    for level in levels:
        touches = 0
        for bar in ohlcv:
            h = bar.get("high", 0)
            l = bar.get("low", 0)
            if h > 0 and l > 0:
                if abs(h - level) / level <= touch_band or abs(l - level) / level <= touch_band:
                    touches += 1
        result[str(round(level, 2))] = {
            "touches": touches,
            "strong": touches >= 3,
        }
    return result


def _detect_patterns(
    pivot_highs: list[tuple[int, float]],
    pivot_lows: list[tuple[int, float]],
    price: float,
) -> list[str]:
    """
    Detect basic chart patterns from swing points.
    Returns list of pattern names.
    """
    patterns: list[str] = []

    # Double Top: 2 pivot highs at same level (within 1%) in last N pivots
    if len(pivot_highs) >= 2:
        last_two_h = pivot_highs[-2:]
        h1, h2 = last_two_h[0][1], last_two_h[1][1]
        if h1 > 0 and abs(h1 - h2) / h1 < 0.01 and price < h1:
            patterns.append("DOUBLE_TOP")

    # Double Bottom: 2 pivot lows at same level (within 1%)
    if len(pivot_lows) >= 2:
        last_two_l = pivot_lows[-2:]
        l1, l2 = last_two_l[0][1], last_two_l[1][1]
        if l1 > 0 and abs(l1 - l2) / l1 < 0.01 and price > l1:
            patterns.append("DOUBLE_BOTTOM")

    # Higher Lows: last 3 pivot lows are ascending
    if len(pivot_lows) >= 3:
        lasts = [p for _, p in pivot_lows[-3:]]
        if all(lasts[i] > lasts[i-1] for i in range(1, len(lasts))):
            patterns.append("HIGHER_LOWS")

    # Lower Highs: last 3 pivot highs are descending
    if len(pivot_highs) >= 3:
        lasts = [p for _, p in pivot_highs[-3:]]
        if all(lasts[i] < lasts[i-1] for i in range(1, len(lasts))):
            patterns.append("LOWER_HIGHS")

    return patterns


# ─── IndicatorEngine (façade) ─────────────────────────────────────────────────

class IndicatorEngine:
    """
    Top-level façade. Runs all 5 modules from raw technical data.
    """

    @staticmethod
    def compute(tech_data: dict) -> IndicatorResult:
        """
        Args:
            tech_data: output of MarketDataFetcher.fetch_technical_data()

        Returns:
            IndicatorResult with all 5 module results.
        """
        price = tech_data.get("current_price", 0.0) or 0.0
        inds  = tech_data.get("indicators", {})
        ohlcv = tech_data.get("ohlcv", [])

        return IndicatorResult(
            trend      = TrendModule.compute(price, inds),
            momentum   = MomentumModule.compute(inds),
            volatility = VolatilityModule.compute(price, inds),
            volume     = VolumeModule.compute(inds, ohlcv),
            structure  = StructureModule.compute(price, ohlcv),
        )
