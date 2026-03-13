"""
src/engines/fundamental/scoring.py
──────────────────────────────────────────────────────────────────────────────
Deterministic Fundamental Scoring Engine — converts financial ratios into
a continuous 0–10 score with an evidence trail.

Four modules mirror the LLM agents:
  1. Value    — P/E, P/B, EV/EBITDA, FCF yield
  2. Quality  — gross margin, ROIC, ROE, revenue growth
  3. Capital  — debt/equity, current ratio, payout ratio, dividend yield
  4. Risk     — beta, leverage stress, earnings volatility

The deterministic score acts as a guardrail: if the LLM committee
produces a signal that contradicts the deterministic evidence, the
deterministic signal prevails.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.engines.fundamental.scoring")

# ─── Math Helpers ─────────────────────────────────────────────────────────────


def _sigmoid(x: float, center: float = 0.0, scale: float = 1.0) -> float:
    """Sigmoid mapping → 0–10 continuous score."""
    try:
        return 10.0 / (1.0 + math.exp(-scale * (x - center)))
    except OverflowError:
        return 0.0 if x < center else 10.0


def _clamp(v: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, v))


def _safe_float(val, default: float | None = None) -> float | None:
    """Convert a value to float, returning None for DATA_INCOMPLETE or bad values."""
    if val is None:
        return default
    if isinstance(val, str):
        if val == "DATA_INCOMPLETE":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ─── Module Score Result ──────────────────────────────────────────────────────


@dataclass
class FundamentalModuleScore:
    """Per-module deterministic score with evidence trail."""
    name: str
    score: float  # 0–10
    signal: str  # BULLISH / BEARISH / NEUTRAL
    evidence: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    data_available: int = 0  # how many ratios were available
    data_total: int = 0  # how many ratios were checked


@dataclass
class FundamentalScoreResult:
    """Complete deterministic scoring output."""
    score: float  # 0–10 aggregate
    signal: str  # STRONG_BUY → STRONG_SELL
    strength: str  # Strong / Moderate / Weak
    confidence: float  # 0–1 data completeness
    module_scores: list[FundamentalModuleScore] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    strongest_module: str = ""
    weakest_module: str = ""
    data_coverage: float = 0.0  # fraction of available ratios


# ─── Module Weights ───────────────────────────────────────────────────────────

MODULE_WEIGHTS = {
    "value": 0.30,
    "quality": 0.30,
    "capital": 0.20,
    "risk": 0.20,
}


# ─── Value Module ─────────────────────────────────────────────────────────────


def _score_value(ratios: dict) -> FundamentalModuleScore:
    """
    Value & Margin of Safety scoring.
    Low P/E, low P/B, low EV/EBITDA, high FCF yield → bullish.
    """
    evidence: list[str] = []
    details: dict = {}
    scores: list[float] = []
    available = 0
    total = 4

    # P/E ratio: lower is better (inverted sigmoid)
    pe = _safe_float(ratios.get("valuation", {}).get("pe_ratio"))
    details["pe_ratio"] = pe
    if pe is not None and pe > 0:
        available += 1
        # Center at 20, scale so PE=10→~7.3, PE=30→~2.7
        s = _sigmoid(-pe, center=-20.0, scale=0.10)
        scores.append(s)
        if pe < 15:
            evidence.append(f"P/E atractivo en {pe:.1f} → {s:.1f}")
        elif pe > 35:
            evidence.append(f"⚠ P/E elevado en {pe:.1f} → {s:.1f}")
        else:
            evidence.append(f"P/E neutral en {pe:.1f} → {s:.1f}")

    # P/B ratio: lower is better
    pb = _safe_float(ratios.get("valuation", {}).get("pb_ratio"))
    details["pb_ratio"] = pb
    if pb is not None and pb > 0:
        available += 1
        s = _sigmoid(-pb, center=-3.0, scale=0.8)
        scores.append(s)
        if pb < 1.5:
            evidence.append(f"P/B favorable en {pb:.2f} → {s:.1f}")
        elif pb > 5.0:
            evidence.append(f"⚠ P/B elevado en {pb:.2f} → {s:.1f}")

    # EV/EBITDA: lower is better
    ev_eb = _safe_float(ratios.get("valuation", {}).get("ev_ebitda"))
    details["ev_ebitda"] = ev_eb
    if ev_eb is not None and ev_eb > 0:
        available += 1
        s = _sigmoid(-ev_eb, center=-15.0, scale=0.2)
        scores.append(s)
        if ev_eb < 10:
            evidence.append(f"EV/EBITDA atractivo en {ev_eb:.1f} → {s:.1f}")
        elif ev_eb > 20:
            evidence.append(f"⚠ EV/EBITDA alto en {ev_eb:.1f} → {s:.1f}")

    # FCF yield: higher is better
    fcf_yield = _safe_float(ratios.get("valuation", {}).get("fcf_yield"))
    details["fcf_yield"] = fcf_yield
    if fcf_yield is not None:
        available += 1
        s = _sigmoid(fcf_yield, center=0.04, scale=30.0)
        scores.append(s)
        if fcf_yield > 0.06:
            evidence.append(f"FCF yield fuerte en {fcf_yield:.1%} → {s:.1f}")
        elif fcf_yield < 0.02:
            evidence.append(f"FCF yield bajo en {fcf_yield:.1%} → {s:.1f}")

    avg = sum(scores) / len(scores) if scores else 5.0
    signal = "BULLISH" if avg >= 6.0 else ("BEARISH" if avg <= 4.0 else "NEUTRAL")

    return FundamentalModuleScore(
        name="value", score=round(_clamp(avg), 2), signal=signal,
        evidence=evidence, details=details,
        data_available=available, data_total=total,
    )


# ─── Quality Module ───────────────────────────────────────────────────────────


def _score_quality(ratios: dict) -> FundamentalModuleScore:
    """
    Quality & Moat scoring.
    High margins, high ROIC, high ROE, strong growth → bullish.
    """
    evidence: list[str] = []
    details: dict = {}
    scores: list[float] = []
    available = 0
    total = 5

    prof = ratios.get("profitability", {})

    # Gross margin
    gm = _safe_float(prof.get("gross_margin"))
    details["gross_margin"] = gm
    if gm is not None:
        available += 1
        s = _sigmoid(gm, center=0.40, scale=8.0)
        scores.append(s)
        if gm > 0.60:
            evidence.append(f"Margen bruto premium en {gm:.0%} → {s:.1f}")
        elif gm < 0.20:
            evidence.append(f"⚠ Margen bruto bajo en {gm:.0%} → {s:.1f}")

    # ROIC
    roic = _safe_float(prof.get("roic"))
    details["roic"] = roic
    if roic is not None:
        available += 1
        s = _sigmoid(roic, center=0.12, scale=15.0)
        scores.append(s)
        if roic > 0.20:
            evidence.append(f"ROIC excelente en {roic:.0%} → {s:.1f}")
        elif roic < 0.08:
            evidence.append(f"⚠ ROIC débil en {roic:.0%} → {s:.1f}")

    # ROE
    roe = _safe_float(prof.get("roe"))
    details["roe"] = roe
    if roe is not None:
        available += 1
        s = _sigmoid(roe, center=0.15, scale=12.0)
        scores.append(s)
        if roe > 0.25:
            evidence.append(f"ROE fuerte en {roe:.0%} → {s:.1f}")

    # Net margin
    nm = _safe_float(prof.get("net_margin"))
    details["net_margin"] = nm
    if nm is not None:
        available += 1
        s = _sigmoid(nm, center=0.10, scale=12.0)
        scores.append(s)

    # Revenue growth
    quality = ratios.get("quality", {})
    rev_g = _safe_float(quality.get("revenue_growth_yoy"))
    details["revenue_growth_yoy"] = rev_g
    if rev_g is not None:
        available += 1
        s = _sigmoid(rev_g, center=0.10, scale=10.0)
        scores.append(s)
        if rev_g > 0.20:
            evidence.append(f"Crecimiento ingresos fuerte en {rev_g:.0%} → {s:.1f}")
        elif rev_g < 0:
            evidence.append(f"⚠ Ingresos en contracción {rev_g:.0%} → {s:.1f}")

    avg = sum(scores) / len(scores) if scores else 5.0
    signal = "BULLISH" if avg >= 6.0 else ("BEARISH" if avg <= 4.0 else "NEUTRAL")

    return FundamentalModuleScore(
        name="quality", score=round(_clamp(avg), 2), signal=signal,
        evidence=evidence, details=details,
        data_available=available, data_total=total,
    )


# ─── Capital Module ───────────────────────────────────────────────────────────


def _score_capital(ratios: dict) -> FundamentalModuleScore:
    """
    Capital Allocation scoring.
    Low leverage, good liquidity, disciplined payouts → bullish.
    """
    evidence: list[str] = []
    details: dict = {}
    scores: list[float] = []
    available = 0
    total = 4

    lev = ratios.get("leverage", {})

    # Debt-to-equity: lower is better
    dte = _safe_float(lev.get("debt_to_equity"))
    details["debt_to_equity"] = dte
    if dte is not None:
        available += 1
        s = _sigmoid(-dte, center=-1.0, scale=2.0)
        scores.append(s)
        if dte < 0.3:
            evidence.append(f"Bajo apalancamiento D/E={dte:.2f} → {s:.1f}")
        elif dte > 2.0:
            evidence.append(f"⚠ Alto apalancamiento D/E={dte:.2f} → {s:.1f}")

    # Current ratio: higher is better
    cr = _safe_float(lev.get("current_ratio"))
    details["current_ratio"] = cr
    if cr is not None:
        available += 1
        s = _sigmoid(cr, center=1.5, scale=2.0)
        scores.append(s)
        if cr > 2.0:
            evidence.append(f"Liquidez fuerte CR={cr:.2f} → {s:.1f}")
        elif cr < 1.0:
            evidence.append(f"⚠ Liquidez baja CR={cr:.2f} → {s:.1f}")

    # Payout ratio: moderate is best, >100% is bad
    quality = ratios.get("quality", {})
    payout = _safe_float(quality.get("payout_ratio"))
    details["payout_ratio"] = payout
    if payout is not None:
        available += 1
        # Bell-curve: optimal around 30-50%, drops for <10% or >70%
        if payout > 1.0:
            s = 1.5  # Paying more than earnings — unsustainable
            evidence.append(f"⚠ Payout ratio insostenible {payout:.0%} → {s:.1f}")
        elif payout < 0:
            s = 3.0  # Negative payout — unusual
        else:
            # Gaussian-like bell curve centered at 0.40
            distance = abs(payout - 0.40)
            s = 10.0 * math.exp(-8.0 * distance * distance)
            s = max(1.0, s)  # Floor at 1.0
            if payout > 0.70:
                evidence.append(f"⚠ Payout ratio alto {payout:.0%} → {s:.1f}")
        scores.append(s)

    # Dividend yield (bonus)
    div_y = _safe_float(quality.get("dividend_yield"))
    details["dividend_yield"] = div_y
    if div_y is not None:
        available += 1
        s = _sigmoid(div_y, center=0.02, scale=80.0)
        scores.append(s)
        if div_y > 0.04:
            evidence.append(f"Dividendo atractivo {div_y:.1%} → {s:.1f}")

    avg = sum(scores) / len(scores) if scores else 5.0
    signal = "BULLISH" if avg >= 6.0 else ("BEARISH" if avg <= 4.0 else "NEUTRAL")

    return FundamentalModuleScore(
        name="capital", score=round(_clamp(avg), 2), signal=signal,
        evidence=evidence, details=details,
        data_available=available, data_total=total,
    )


# ─── Risk Module ──────────────────────────────────────────────────────────────


def _score_risk(ratios: dict) -> FundamentalModuleScore:
    """
    Risk & Macro Stress scoring.
    Low beta, low leverage, stable earnings → bullish (lower risk).
    Higher score = lower risk = more attractive.
    """
    evidence: list[str] = []
    details: dict = {}
    scores: list[float] = []
    available = 0
    total = 4

    quality = ratios.get("quality", {})
    lev = ratios.get("leverage", {})

    # Beta: lower = less systematic risk
    beta = _safe_float(quality.get("beta"))
    details["beta"] = beta
    if beta is not None:
        available += 1
        # Center at 1.0, lower beta → higher score
        s = _sigmoid(-beta, center=-1.0, scale=2.0)
        scores.append(s)
        if beta < 0.8:
            evidence.append(f"Beta defensivo en {beta:.2f} → {s:.1f}")
        elif beta > 1.5:
            evidence.append(f"⚠ Beta elevado en {beta:.2f} → {s:.1f}")

    # Interest coverage: higher is better
    ic = _safe_float(lev.get("interest_coverage"))
    details["interest_coverage"] = ic
    if ic is not None and ic > 0:
        available += 1
        s = _sigmoid(ic, center=5.0, scale=0.3)
        scores.append(s)
        if ic > 10:
            evidence.append(f"Cobertura de intereses sólida {ic:.1f}x → {s:.1f}")
        elif ic < 2:
            evidence.append(f"⚠ Cobertura de intereses débil {ic:.1f}x → {s:.1f}")

    # Earnings growth volatility: steady growth = lower risk
    earn_g = _safe_float(quality.get("earnings_growth_yoy"))
    details["earnings_growth_yoy"] = earn_g
    if earn_g is not None:
        available += 1
        # Extreme swings (>50% or <-50%) are risky
        # Use absolute value as volatility proxy; don't confuse growth with risk
        volatility_proxy = abs(earn_g)
        s = _sigmoid(-volatility_proxy, center=-0.30, scale=5.0)
        scores.append(s)
        if volatility_proxy > 0.5:
            evidence.append(f"⚠ Volatilidad de earnings alta ({earn_g:.0%}) → {s:.1f}")
        elif volatility_proxy < 0.10:
            evidence.append(f"Earnings estables ({earn_g:.0%}) → {s:.1f}")

    # Quick ratio: higher = better liquidity buffer
    qr = _safe_float(lev.get("quick_ratio"))
    details["quick_ratio"] = qr
    if qr is not None:
        available += 1
        s = _sigmoid(qr, center=1.0, scale=2.5)
        scores.append(s)
        if qr < 0.8:
            evidence.append(f"⚠ Quick ratio bajo {qr:.2f} → {s:.1f}")

    avg = sum(scores) / len(scores) if scores else 5.0
    # Risk module: high score = low risk = bullish
    signal = "BULLISH" if avg >= 6.0 else ("BEARISH" if avg <= 4.0 else "NEUTRAL")

    return FundamentalModuleScore(
        name="risk", score=round(_clamp(avg), 2), signal=signal,
        evidence=evidence, details=details,
        data_available=available, data_total=total,
    )


# ─── Aggregate Scoring ───────────────────────────────────────────────────────


def _derive_signal(score: float) -> tuple[str, str]:
    """Convert aggregate 0–10 score to signal and strength."""
    if score >= 7.5:
        return "STRONG_BUY", "Strong"
    if score >= 6.0:
        return "BUY", "Moderate"
    if score >= 4.0:
        return "HOLD", "Weak"
    if score >= 2.5:
        return "SELL", "Moderate"
    return "STRONG_SELL", "Strong"


class FundamentalScoringEngine:
    """
    Deterministic fundamental scoring engine.

    Produces a continuous 0–10 score from financial ratios, with evidence
    trail and data coverage metrics. Analogous to
    ``technical/scoring.py::ScoringEngine``.
    """

    MODULE_FNS = {
        "value": _score_value,
        "quality": _score_quality,
        "capital": _score_capital,
        "risk": _score_risk,
    }

    @classmethod
    def compute(cls, ratios: dict) -> FundamentalScoreResult:
        """
        Run deterministic scoring on financial ratios.

        Parameters
        ----------
        ratios : dict
            The ``ratios`` dict from ``fetch_fundamental_data()``, containing
            keys: profitability, valuation, leverage, quality.

        Returns
        -------
        FundamentalScoreResult
            Aggregate score, per-module breakdowns, evidence, coverage.
        """
        modules: list[FundamentalModuleScore] = []
        for name, fn in cls.MODULE_FNS.items():
            modules.append(fn(ratios))

        # Weighted aggregate
        total_weight = 0.0
        weighted_sum = 0.0
        for m in modules:
            w = MODULE_WEIGHTS.get(m.name, 0.25)
            weighted_sum += m.score * w
            total_weight += w

        aggregate = weighted_sum / total_weight if total_weight > 0 else 5.0
        aggregate = round(_clamp(aggregate), 2)

        signal, strength = _derive_signal(aggregate)

        # Data coverage
        total_available = sum(m.data_available for m in modules)
        total_possible = sum(m.data_total for m in modules)
        coverage = total_available / total_possible if total_possible > 0 else 0.0

        # Confidence: based on data coverage
        confidence = round(min(1.0, coverage), 2)

        # Strongest / weakest
        sorted_modules = sorted(modules, key=lambda m: m.score)
        weakest = sorted_modules[0].name if sorted_modules else ""
        strongest = sorted_modules[-1].name if sorted_modules else ""

        # Collect evidence
        all_evidence: list[str] = []
        for m in modules:
            all_evidence.extend(m.evidence)

        return FundamentalScoreResult(
            score=aggregate,
            signal=signal,
            strength=strength,
            confidence=confidence,
            module_scores=modules,
            evidence=all_evidence,
            strongest_module=strongest,
            weakest_module=weakest,
            data_coverage=round(coverage, 2),
        )


# ─── Signal Guardrail ────────────────────────────────────────────────────────


_SIGNAL_DIRECTION = {
    "STRONG_BUY": 2,
    "BUY": 1,
    "HOLD": 0,
    "SELL": -1,
    "STRONG_SELL": -2,
    "AVOID": -2,
}


def apply_signal_guardrail(
    llm_signal: str,
    deterministic_signal: str,
    deterministic_score: float,
) -> tuple[str, bool]:
    """
    Enforce deterministic guardrail on LLM signal.

    If the LLM signal contradicts the deterministic direction by more than
    1 step, the deterministic signal prevails.

    Returns
    -------
    (final_signal, was_overridden)
    """
    llm_dir = _SIGNAL_DIRECTION.get(llm_signal.upper(), 0)
    det_dir = _SIGNAL_DIRECTION.get(deterministic_signal.upper(), 0)

    # Allow neutral (HOLD) without override
    if det_dir == 0 or llm_dir == 0:
        return llm_signal, False

    # If directions are opposite (one positive, one negative), override
    if (llm_dir > 0 and det_dir < 0) or (llm_dir < 0 and det_dir > 0):
        logger.warning(
            f"Signal guardrail: LLM={llm_signal} contradicts "
            f"deterministic={deterministic_signal} (score={deterministic_score:.2f}). "
            f"Overriding to {deterministic_signal}."
        )
        return deterministic_signal, True

    return llm_signal, False


# ─── LLM Score-Signal Coherence ───────────────────────────────────────────────

def validate_llm_coherence(
    llm_score: float,
    llm_signal: str,
) -> tuple[str, bool]:
    """
    Check that the LLM's own score and signal are internally consistent.
    E.g. score=8.5 with signal=SELL is incoherent.

    Returns (corrected_signal, was_corrected).
    """
    expected_dir = _SIGNAL_DIRECTION.get(llm_signal.upper(), 0)

    # Derive what signal the score implies
    if llm_score >= 7.0:
        score_dir = 1  # bullish
    elif llm_score <= 3.5:
        score_dir = -1  # bearish
    else:
        return llm_signal, False  # neutral zone — no correction

    if (score_dir > 0 and expected_dir < 0) or (score_dir < 0 and expected_dir > 0):
        corrected = "BUY" if score_dir > 0 else "SELL"
        logger.warning(
            f"LLM coherence fix: score={llm_score:.1f} contradicts signal={llm_signal}. "
            f"Correcting to {corrected}."
        )
        return corrected, True

    return llm_signal, False
