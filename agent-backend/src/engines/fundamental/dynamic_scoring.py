"""
src/engines/fundamental/dynamic_scoring.py
──────────────────────────────────────────────────────────────────────────────
Dynamic Fundamental Score V3 — 3-layer calibration that adapts scoring
thresholds to the company's sector context.

Architecture:
  Layer 1 — Theoretical Gate: Binary pass/fail on minimum viability
  Layer 2 — Z-Score Sector-Relative: Score vs sector peers (percentile)
  Layer 3 — Dispersion-Based Weights: Weight inversely proportional to
            sector CV (high-dispersion metrics get less weight)

Modules:
  1. Profitability  — ROIC, ROE, gross margin, net margin
  2. Value          — P/E, P/B, EV/EBITDA, FCF yield
  3. Capital        — D/E, current ratio, interest coverage
  4. Growth         — Revenue growth, earnings growth
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field as dc_field

logger = logging.getLogger("365advisers.engines.fundamental.dynamic_scoring")


# ─── Sector Statistics (pre-computed medians) ─────────────────────────────────
# These represent approximate US sector statistics for calibration.
# In production, these should be refreshed from a data provider.

_SECTOR_STATS: dict[str, dict[str, dict[str, float]]] = {
    "Technology": {
        "roic":           {"median": 0.18, "std": 0.12, "gate": 0.06},
        "roe":            {"median": 0.22, "std": 0.15, "gate": 0.05},
        "gross_margin":   {"median": 0.58, "std": 0.18, "gate": 0.30},
        "net_margin":     {"median": 0.18, "std": 0.12, "gate": 0.0},
        "pe_ratio":       {"median": 28.0, "std": 15.0, "gate": 0.0},
        "pb_ratio":       {"median": 6.0,  "std": 4.0,  "gate": 0.0},
        "ev_ebitda":      {"median": 20.0, "std": 10.0, "gate": 0.0},
        "fcf_yield":      {"median": 0.03, "std": 0.02, "gate": 0.0},
        "debt_to_equity": {"median": 0.50, "std": 0.40, "gate_max": 3.0},
        "current_ratio":  {"median": 2.0,  "std": 1.0,  "gate": 0.80},
        "interest_cov":   {"median": 15.0, "std": 12.0, "gate": 2.0},
        "rev_growth":     {"median": 0.12, "std": 0.15, "gate": -0.20},
        "earn_growth":    {"median": 0.10, "std": 0.25, "gate": -0.50},
    },
    "Financial Services": {
        "roic":           {"median": 0.10, "std": 0.05, "gate": 0.03},
        "roe":            {"median": 0.12, "std": 0.06, "gate": 0.03},
        "gross_margin":   {"median": 0.55, "std": 0.20, "gate": 0.20},
        "net_margin":     {"median": 0.25, "std": 0.12, "gate": 0.0},
        "pe_ratio":       {"median": 13.0, "std": 5.0,  "gate": 0.0},
        "pb_ratio":       {"median": 1.3,  "std": 0.6,  "gate": 0.0},
        "ev_ebitda":      {"median": 10.0, "std": 5.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.05, "std": 0.03, "gate": 0.0},
        "debt_to_equity": {"median": 2.5,  "std": 2.0,  "gate_max": 8.0},
        "current_ratio":  {"median": 1.2,  "std": 0.5,  "gate": 0.50},
        "interest_cov":   {"median": 5.0,  "std": 4.0,  "gate": 1.5},
        "rev_growth":     {"median": 0.06, "std": 0.10, "gate": -0.15},
        "earn_growth":    {"median": 0.08, "std": 0.20, "gate": -0.40},
    },
    "Healthcare": {
        "roic":           {"median": 0.14, "std": 0.10, "gate": 0.04},
        "roe":            {"median": 0.20, "std": 0.15, "gate": 0.04},
        "gross_margin":   {"median": 0.62, "std": 0.18, "gate": 0.25},
        "net_margin":     {"median": 0.15, "std": 0.12, "gate": 0.0},
        "pe_ratio":       {"median": 22.0, "std": 12.0, "gate": 0.0},
        "pb_ratio":       {"median": 4.5,  "std": 3.5,  "gate": 0.0},
        "ev_ebitda":      {"median": 16.0, "std": 8.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.04, "std": 0.03, "gate": 0.0},
        "debt_to_equity": {"median": 0.70, "std": 0.60, "gate_max": 4.0},
        "current_ratio":  {"median": 1.8,  "std": 0.8,  "gate": 0.80},
        "interest_cov":   {"median": 10.0, "std": 8.0,  "gate": 2.0},
        "rev_growth":     {"median": 0.08, "std": 0.12, "gate": -0.15},
        "earn_growth":    {"median": 0.06, "std": 0.20, "gate": -0.40},
    },
    "Consumer Defensive": {
        "roic":           {"median": 0.15, "std": 0.08, "gate": 0.05},
        "roe":            {"median": 0.25, "std": 0.15, "gate": 0.05},
        "gross_margin":   {"median": 0.35, "std": 0.15, "gate": 0.15},
        "net_margin":     {"median": 0.08, "std": 0.05, "gate": 0.0},
        "pe_ratio":       {"median": 22.0, "std": 8.0,  "gate": 0.0},
        "pb_ratio":       {"median": 5.0,  "std": 3.0,  "gate": 0.0},
        "ev_ebitda":      {"median": 15.0, "std": 6.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.04, "std": 0.02, "gate": 0.0},
        "debt_to_equity": {"median": 1.0,  "std": 0.8,  "gate_max": 4.0},
        "current_ratio":  {"median": 1.0,  "std": 0.4,  "gate": 0.60},
        "interest_cov":   {"median": 8.0,  "std": 5.0,  "gate": 2.0},
        "rev_growth":     {"median": 0.04, "std": 0.06, "gate": -0.10},
        "earn_growth":    {"median": 0.05, "std": 0.12, "gate": -0.30},
    },
    "Industrials": {
        "roic":           {"median": 0.12, "std": 0.06, "gate": 0.04},
        "roe":            {"median": 0.18, "std": 0.10, "gate": 0.04},
        "gross_margin":   {"median": 0.32, "std": 0.12, "gate": 0.15},
        "net_margin":     {"median": 0.08, "std": 0.05, "gate": 0.0},
        "pe_ratio":       {"median": 20.0, "std": 8.0,  "gate": 0.0},
        "pb_ratio":       {"median": 4.0,  "std": 2.5,  "gate": 0.0},
        "ev_ebitda":      {"median": 14.0, "std": 6.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.04, "std": 0.02, "gate": 0.0},
        "debt_to_equity": {"median": 1.0,  "std": 0.8,  "gate_max": 4.0},
        "current_ratio":  {"median": 1.5,  "std": 0.6,  "gate": 0.70},
        "interest_cov":   {"median": 8.0,  "std": 5.0,  "gate": 2.0},
        "rev_growth":     {"median": 0.06, "std": 0.10, "gate": -0.15},
        "earn_growth":    {"median": 0.08, "std": 0.18, "gate": -0.40},
    },
    "Energy": {
        "roic":           {"median": 0.10, "std": 0.08, "gate": 0.02},
        "roe":            {"median": 0.15, "std": 0.12, "gate": 0.02},
        "gross_margin":   {"median": 0.40, "std": 0.20, "gate": 0.10},
        "net_margin":     {"median": 0.10, "std": 0.10, "gate": 0.0},
        "pe_ratio":       {"median": 12.0, "std": 8.0,  "gate": 0.0},
        "pb_ratio":       {"median": 1.8,  "std": 1.2,  "gate": 0.0},
        "ev_ebitda":      {"median": 8.0,  "std": 5.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.07, "std": 0.05, "gate": 0.0},
        "debt_to_equity": {"median": 0.50, "std": 0.40, "gate_max": 3.0},
        "current_ratio":  {"median": 1.2,  "std": 0.5,  "gate": 0.60},
        "interest_cov":   {"median": 6.0,  "std": 5.0,  "gate": 1.5},
        "rev_growth":     {"median": 0.05, "std": 0.20, "gate": -0.25},
        "earn_growth":    {"median": 0.05, "std": 0.30, "gate": -0.50},
    },
    "Utilities": {
        "roic":           {"median": 0.06, "std": 0.02, "gate": 0.02},
        "roe":            {"median": 0.10, "std": 0.04, "gate": 0.03},
        "gross_margin":   {"median": 0.35, "std": 0.15, "gate": 0.10},
        "net_margin":     {"median": 0.12, "std": 0.06, "gate": 0.0},
        "pe_ratio":       {"median": 18.0, "std": 6.0,  "gate": 0.0},
        "pb_ratio":       {"median": 1.8,  "std": 0.6,  "gate": 0.0},
        "ev_ebitda":      {"median": 12.0, "std": 4.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.04, "std": 0.02, "gate": 0.0},
        "debt_to_equity": {"median": 1.5,  "std": 0.8,  "gate_max": 5.0},
        "current_ratio":  {"median": 0.8,  "std": 0.3,  "gate": 0.40},
        "interest_cov":   {"median": 3.5,  "std": 1.5,  "gate": 1.5},
        "rev_growth":     {"median": 0.04, "std": 0.06, "gate": -0.10},
        "earn_growth":    {"median": 0.04, "std": 0.10, "gate": -0.25},
    },
    "Real Estate": {
        "roic":           {"median": 0.05, "std": 0.03, "gate": 0.01},
        "roe":            {"median": 0.08, "std": 0.06, "gate": 0.01},
        "gross_margin":   {"median": 0.55, "std": 0.15, "gate": 0.20},
        "net_margin":     {"median": 0.20, "std": 0.15, "gate": 0.0},
        "pe_ratio":       {"median": 35.0, "std": 20.0, "gate": 0.0},
        "pb_ratio":       {"median": 2.5,  "std": 1.5,  "gate": 0.0},
        "ev_ebitda":      {"median": 22.0, "std": 10.0, "gate": 0.0},
        "fcf_yield":      {"median": 0.04, "std": 0.02, "gate": 0.0},
        "debt_to_equity": {"median": 1.2,  "std": 0.8,  "gate_max": 5.0},
        "current_ratio":  {"median": 1.0,  "std": 0.5,  "gate": 0.30},
        "interest_cov":   {"median": 3.0,  "std": 2.0,  "gate": 1.0},
        "rev_growth":     {"median": 0.05, "std": 0.10, "gate": -0.15},
        "earn_growth":    {"median": 0.04, "std": 0.15, "gate": -0.40},
    },
    "Consumer Cyclical": {
        "roic":           {"median": 0.14, "std": 0.10, "gate": 0.04},
        "roe":            {"median": 0.20, "std": 0.15, "gate": 0.04},
        "gross_margin":   {"median": 0.40, "std": 0.18, "gate": 0.15},
        "net_margin":     {"median": 0.07, "std": 0.05, "gate": 0.0},
        "pe_ratio":       {"median": 22.0, "std": 10.0, "gate": 0.0},
        "pb_ratio":       {"median": 5.0,  "std": 4.0,  "gate": 0.0},
        "ev_ebitda":      {"median": 15.0, "std": 8.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.04, "std": 0.03, "gate": 0.0},
        "debt_to_equity": {"median": 0.80, "std": 0.60, "gate_max": 4.0},
        "current_ratio":  {"median": 1.5,  "std": 0.6,  "gate": 0.70},
        "interest_cov":   {"median": 8.0,  "std": 6.0,  "gate": 2.0},
        "rev_growth":     {"median": 0.08, "std": 0.12, "gate": -0.15},
        "earn_growth":    {"median": 0.08, "std": 0.20, "gate": -0.40},
    },
    "Communication Services": {
        "roic":           {"median": 0.12, "std": 0.08, "gate": 0.04},
        "roe":            {"median": 0.15, "std": 0.10, "gate": 0.04},
        "gross_margin":   {"median": 0.55, "std": 0.20, "gate": 0.20},
        "net_margin":     {"median": 0.15, "std": 0.10, "gate": 0.0},
        "pe_ratio":       {"median": 20.0, "std": 10.0, "gate": 0.0},
        "pb_ratio":       {"median": 3.0,  "std": 2.5,  "gate": 0.0},
        "ev_ebitda":      {"median": 12.0, "std": 6.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.05, "std": 0.03, "gate": 0.0},
        "debt_to_equity": {"median": 1.0,  "std": 0.8,  "gate_max": 4.0},
        "current_ratio":  {"median": 1.2,  "std": 0.5,  "gate": 0.50},
        "interest_cov":   {"median": 6.0,  "std": 4.0,  "gate": 1.5},
        "rev_growth":     {"median": 0.08, "std": 0.12, "gate": -0.15},
        "earn_growth":    {"median": 0.08, "std": 0.20, "gate": -0.40},
    },
    "Basic Materials": {
        "roic":           {"median": 0.10, "std": 0.06, "gate": 0.03},
        "roe":            {"median": 0.15, "std": 0.10, "gate": 0.03},
        "gross_margin":   {"median": 0.35, "std": 0.15, "gate": 0.10},
        "net_margin":     {"median": 0.10, "std": 0.08, "gate": 0.0},
        "pe_ratio":       {"median": 18.0, "std": 8.0,  "gate": 0.0},
        "pb_ratio":       {"median": 3.0,  "std": 2.0,  "gate": 0.0},
        "ev_ebitda":      {"median": 12.0, "std": 5.0,  "gate": 0.0},
        "fcf_yield":      {"median": 0.05, "std": 0.03, "gate": 0.0},
        "debt_to_equity": {"median": 0.60, "std": 0.40, "gate_max": 3.0},
        "current_ratio":  {"median": 1.5,  "std": 0.6,  "gate": 0.70},
        "interest_cov":   {"median": 8.0,  "std": 5.0,  "gate": 2.0},
        "rev_growth":     {"median": 0.05, "std": 0.12, "gate": -0.20},
        "earn_growth":    {"median": 0.06, "std": 0.20, "gate": -0.40},
    },
}

# Fallback when sector is not recognized
_DEFAULT_SECTOR = "Industrials"


# ─── Indicator Extraction Mapping ─────────────────────────────────────────────

_RATIO_MAP = {
    "roic":           lambda r: _sf(r.get("profitability", {}).get("roic")),
    "roe":            lambda r: _sf(r.get("profitability", {}).get("roe")),
    "gross_margin":   lambda r: _sf(r.get("profitability", {}).get("gross_margin")),
    "net_margin":     lambda r: _sf(r.get("profitability", {}).get("net_margin")),
    "pe_ratio":       lambda r: _sf(r.get("valuation", {}).get("pe_ratio")),
    "pb_ratio":       lambda r: _sf(r.get("valuation", {}).get("pb_ratio")),
    "ev_ebitda":      lambda r: _sf(r.get("valuation", {}).get("ev_ebitda")),
    "fcf_yield":      lambda r: _sf(r.get("valuation", {}).get("fcf_yield")),
    "debt_to_equity": lambda r: _sf(r.get("leverage", {}).get("debt_to_equity")),
    "current_ratio":  lambda r: _sf(r.get("leverage", {}).get("current_ratio")),
    "interest_cov":   lambda r: _sf(r.get("leverage", {}).get("interest_coverage")),
    "rev_growth":     lambda r: _sf(r.get("quality", {}).get("revenue_growth_yoy")),
    "earn_growth":    lambda r: _sf(r.get("quality", {}).get("earnings_growth_yoy")),
}

# Which indicators should be scored as "lower is better" (valuation/leverage)
_LOWER_BETTER = {"pe_ratio", "pb_ratio", "ev_ebitda", "debt_to_equity"}


def _sf(val) -> float | None:
    """Safe float conversion."""
    if val is None:
        return None
    if isinstance(val, str):
        if val == "DATA_INCOMPLETE":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ─── Output Dataclasses ──────────────────────────────────────────────────────

@dataclass
class DynamicDimensionScore:
    """Score for one fundamental dimension."""
    name: str
    score: float  # 0-10
    gate_passed: bool
    z_score: float  # sector-relative z
    weight: float  # dynamic dispersion weight
    evidence: str = ""


@dataclass
class DynamicFundamentalScore:
    """Complete output of the Dynamic Fundamental Scoring Engine V3."""
    aggregate: float  # 0-10
    signal: str  # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    strength: str  # Strong / Moderate / Weak
    confidence: float  # 0-1 (data coverage)
    sector_used: str = ""
    gates_passed: int = 0
    gates_total: int = 0
    dimensions: list[DynamicDimensionScore] = dc_field(default_factory=list)
    evidence: list[str] = dc_field(default_factory=list)


# ─── Core Engine ──────────────────────────────────────────────────────────────

def _sigmoid_0_10(z: float) -> float:
    """Sigmoid mapping z-score → 0-10 continuous score."""
    z = max(min(z, 5.0), -5.0)
    return 10.0 / (1.0 + math.exp(-z))


def _derive_signal(score: float) -> tuple[str, str]:
    """Convert 0-10 aggregate to (signal, strength)."""
    if score >= 7.5:
        return "STRONG_BUY", "Strong"
    if score >= 6.0:
        return "BUY", "Moderate"
    if score >= 4.0:
        return "HOLD", "Weak"
    if score >= 2.5:
        return "SELL", "Moderate"
    return "STRONG_SELL", "Strong"


class DynamicFundamentalScoringEngine:
    """
    Dynamic Fundamental Score V3 with 3-layer calibration.

    Layer 1 — Theoretical Gate: Binary pass/fail on viability thresholds
    Layer 2 — Z-Score Sector-Relative: Score vs sector statistical norms
    Layer 3 — Dispersion-Based Weights: High-CV metrics get less weight
    """

    @classmethod
    def compute(
        cls,
        ratios: dict,
        sector: str = "",
    ) -> DynamicFundamentalScore:
        """
        Compute the Dynamic Fundamental Score.

        Parameters
        ----------
        ratios : dict
            Financial ratios from ``fetch_fundamental_data()``.
        sector : str
            Company sector (e.g. "Technology", "Financial Services").

        Returns
        -------
        DynamicFundamentalScore with aggregate, signal, and dimension breakdown.
        """
        # Resolve sector stats
        sector_key = sector if sector in _SECTOR_STATS else _DEFAULT_SECTOR
        stats = _SECTOR_STATS[sector_key]

        dimensions: list[DynamicDimensionScore] = []
        evidence: list[str] = []
        gates_passed = 0
        gates_total = 0
        available = 0

        for ind_name, extractor in _RATIO_MAP.items():
            val = extractor(ratios)
            if val is None:
                continue

            ind_stats = stats.get(ind_name)
            if not ind_stats:
                continue

            available += 1
            median = ind_stats["median"]
            std = ind_stats["std"]
            is_lower_better = ind_name in _LOWER_BETTER

            # ── Layer 1: Theoretical Gate ─────────────────────────────
            gate_passed = True
            if "gate" in ind_stats:
                gate_val = ind_stats["gate"]
                if is_lower_better:
                    # For "lower is better", the gate is a maximum
                    pass  # No min gate for valuation
                else:
                    # For "higher is better", value must exceed gate
                    if val < gate_val:
                        gate_passed = False
            if "gate_max" in ind_stats:
                if val > ind_stats["gate_max"]:
                    gate_passed = False

            if gate_passed:
                gates_passed += 1
            gates_total += 1

            # ── Layer 2: Z-Score Sector-Relative ──────────────────────
            if std > 0:
                z = (val - median) / std
            else:
                z = 0.0

            # Invert for "lower is better" metrics
            if is_lower_better:
                z = -z

            # Gate penalty: failed gates get z capped at -1
            if not gate_passed:
                z = min(z, -1.0)

            # Sigmoid → 0-10
            score = _sigmoid_0_10(z)

            # ── Layer 3: Dispersion-Based Weight ──────────────────────
            cv = std / abs(median) if abs(median) > 0.001 else 1.0
            # Weight inversely proportional to CV — stable metrics get more weight
            weight = 1.0 / (1.0 + cv)

            # Build evidence
            direction = "↑" if not is_lower_better else "↓"
            ev_text = (
                f"{ind_name}={val:.3f} vs sector {median:.3f} "
                f"(z={z:+.2f}, score={score:.1f}, w={weight:.2f})"
            )
            if not gate_passed:
                ev_text = f"⛔ GATE FAIL: {ev_text}"
                evidence.append(ev_text)
            elif score >= 7.0:
                evidence.append(f"✅ {ev_text}")
            elif score <= 3.0:
                evidence.append(f"⚠ {ev_text}")

            dimensions.append(DynamicDimensionScore(
                name=ind_name, score=round(score, 2),
                gate_passed=gate_passed, z_score=round(z, 3),
                weight=round(weight, 3), evidence=ev_text,
            ))

        # ── Weighted Aggregate ────────────────────────────────────────
        total_weight = sum(d.weight for d in dimensions)
        if total_weight > 0:
            aggregate = sum(d.score * d.weight for d in dimensions) / total_weight
        else:
            aggregate = 5.0

        aggregate = max(0.0, min(10.0, round(aggregate, 2)))
        signal, strength = _derive_signal(aggregate)
        confidence = available / len(_RATIO_MAP) if _RATIO_MAP else 0.0

        return DynamicFundamentalScore(
            aggregate=aggregate,
            signal=signal,
            strength=strength,
            confidence=round(confidence, 2),
            sector_used=sector_key,
            gates_passed=gates_passed,
            gates_total=gates_total,
            dimensions=dimensions,
            evidence=evidence,
        )
