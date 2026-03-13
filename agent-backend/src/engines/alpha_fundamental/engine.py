"""
src/engines/alpha_fundamental/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Fundamental Engine — identifies investment opportunities via
fundamental analysis across growth, profitability, balance sheet, and
valuation dimensions.

Data Sources: FMP, Alpha Vantage, Finnhub (via EDPL contracts)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_fundamental.models import (
    FundamentalScore, FundamentalGrade, FundamentalRanking,
    GrowthScore, ProfitabilityScore, BalanceSheetScore, ValuationScore,
)
from src.engines._utils import safe_float as _f

logger = logging.getLogger("365advisers.alpha_fundamental.engine")


class AlphaFundamentalEngine:
    """
    Produces a 0–100 FundamentalScore for a ticker from normalized
    financial data.

    Usage::

        engine = AlphaFundamentalEngine()
        score = engine.analyze(ratios_dict, statements_dict)
        ranking = engine.rank([score1, score2, ...])
    """

    # Sub-score weights
    W_GROWTH = 0.25
    W_PROFIT = 0.25
    W_BALANCE = 0.25
    W_VALUATION = 0.25

    def analyze(
        self,
        ticker: str,
        ratios: dict | None = None,
        growth_data: dict | None = None,
    ) -> FundamentalScore:
        """
        Analyze a ticker's fundamentals and produce a composite score.

        Parameters
        ----------
        ticker : str
        ratios : dict
            Flat dict of financial ratios (from FinancialRatios contract or
            feature extractor). Keys: pe_ratio, pb_ratio, roe, roic, etc.
        growth_data : dict
            Growth metrics. Keys: revenue_growth_yoy, earnings_growth_yoy, etc.
        """
        r = ratios or {}
        g = growth_data or {}

        growth = self._score_growth(g, r)
        profit = self._score_profitability(r)
        balance = self._score_balance_sheet(r)
        valuation = self._score_valuation(r)

        composite = (
            self.W_GROWTH * growth.score
            + self.W_PROFIT * profit.score
            + self.W_BALANCE * balance.score
            + self.W_VALUATION * valuation.score
        )
        composite = round(min(max(composite, 0), 100), 1)

        # Collect top signals from all sub-scores
        top = []
        for sub in [growth, profit, balance, valuation]:
            top.extend(sub.signals[:2])

        return FundamentalScore(
            ticker=ticker,
            composite_score=composite,
            grade=self._grade(composite),
            growth=growth,
            profitability=profit,
            balance_sheet=balance,
            valuation=valuation,
            top_signals=top[:8],
            evaluated_at=datetime.now(timezone.utc),
        )

    def rank(self, scores: list[FundamentalScore]) -> FundamentalRanking:
        """Sort scores and pick top opportunities."""
        ranked = sorted(scores, key=lambda s: s.composite_score, reverse=True)
        top = [s.ticker for s in ranked if s.composite_score >= 70][:10]
        return FundamentalRanking(
            rankings=ranked,
            top_opportunities=top,
            total_analyzed=len(ranked),
        )

    # ── Sub-score computations (sigmoid-based) ─────────────────────────────

    def _score_growth(self, g: dict, r: dict) -> GrowthScore:
        from src.engines._utils import sigmoid
        pts = 0.0
        signals: list[str] = []
        rev_g = _f(g.get("revenue_growth_yoy", r.get("revenue_growth_yoy")))
        earn_g = _f(g.get("earnings_growth_yoy", r.get("earnings_growth_yoy")))
        fcf_g = _f(g.get("fcf_growth_yoy", r.get("fcf_growth_yoy")))

        accel = False
        if rev_g is not None:
            s = sigmoid(rev_g, center=0.12, scale=8.0) * 3.5  # 0-35 range
            pts += s
            if rev_g > 0.20:
                signals.append(f"Strong revenue growth: {rev_g:.0%}")
            elif rev_g > 0.08:
                signals.append(f"Solid revenue growth: {rev_g:.0%}")
        if earn_g is not None:
            s = sigmoid(earn_g, center=0.15, scale=6.0) * 3.5  # 0-35 range
            pts += s
            if earn_g > 0.20:
                signals.append(f"Earnings growth: {earn_g:.0%}")
        if fcf_g is not None:
            s = sigmoid(fcf_g, center=0.10, scale=6.0) * 3.0  # 0-30 range
            pts += s
            if fcf_g > 0.15:
                signals.append("FCF expanding"); accel = True

        return GrowthScore(
            score=min(pts, 100), revenue_growth_yoy=rev_g,
            earnings_growth_yoy=earn_g, fcf_growth_yoy=fcf_g,
            revenue_acceleration=accel, signals=signals,
        )

    def _score_profitability(self, r: dict) -> ProfitabilityScore:
        from src.engines._utils import sigmoid
        pts = 0.0
        signals: list[str] = []
        gm = _f(r.get("gross_margin"))
        om = _f(r.get("operating_margin"))
        nm = _f(r.get("net_margin"))
        roic = _f(r.get("roic"))
        roe = _f(r.get("roe"))

        expanding = False
        if gm is not None:
            s = sigmoid(gm, center=0.40, scale=6.0) * 2.0  # 0-20 range
            pts += s
            if gm > 0.55:
                signals.append(f"Premium gross margin: {gm:.0%}")
        if om is not None:
            s = sigmoid(om, center=0.15, scale=8.0) * 2.0  # 0-20 range
            pts += s
            if om > 0.20:
                signals.append(f"Strong operating margin: {om:.0%}")
        if roic is not None:
            s = sigmoid(roic, center=0.12, scale=10.0) * 3.0  # 0-30 range
            pts += s
            if roic > 0.18:
                signals.append(f"Excellent ROIC: {roic:.0%}"); expanding = True
        if roe is not None:
            s = sigmoid(roe, center=0.12, scale=8.0) * 2.0  # 0-20 range
            pts += s
            if roe > 0.18:
                signals.append(f"High ROE: {roe:.0%}")
        if nm is not None:
            s = sigmoid(nm, center=0.10, scale=8.0) * 1.0  # 0-10 range
            pts += s

        return ProfitabilityScore(
            score=min(pts, 100), gross_margin=gm, operating_margin=om,
            net_margin=nm, roic=roic, roe=roe,
            margin_expanding=expanding, signals=signals,
        )

    def _score_balance_sheet(self, r: dict) -> BalanceSheetScore:
        from src.engines._utils import sigmoid
        pts = 50.0  # Start neutral
        signals: list[str] = []
        cr = _f(r.get("current_ratio"))
        dte = _f(r.get("debt_to_equity"))
        ic = _f(r.get("interest_coverage"))
        nde = _f(r.get("net_debt_to_ebitda"))

        cash_rich = False
        if cr is not None:
            # Higher cr = better, center at 1.5
            s = (sigmoid(cr, center=1.5, scale=2.0) - 5.0) * 3.0  # -15..+15
            pts += s
            if cr > 2.0:
                signals.append("Strong liquidity"); cash_rich = True
            elif cr < 1.0:
                signals.append("⚠ Low current ratio")
        if dte is not None:
            # Lower dte = better → invert
            s = (sigmoid(-dte, center=-1.0, scale=1.5) - 5.0) * 4.0  # -20..+20
            pts += s
            if dte < 0.3:
                signals.append("Low leverage"); cash_rich = True
            elif dte > 2.0:
                signals.append("⚠ High leverage")
        if ic is not None:
            # Higher ic = better, center at 5
            s = (sigmoid(ic, center=5.0, scale=0.3) - 5.0) * 2.0  # -10..+10
            pts += s
            if ic < 2:
                signals.append("⚠ Weak interest coverage")
        if nde is not None and nde < 1.0:
            pts += 5

        return BalanceSheetScore(
            score=min(max(pts, 0), 100), current_ratio=cr,
            debt_to_equity=dte, interest_coverage=ic,
            net_debt_to_ebitda=nde, cash_rich=cash_rich, signals=signals,
        )

    def _score_valuation(self, r: dict) -> ValuationScore:
        from src.engines._utils import sigmoid
        pts = 50.0  # Neutral baseline
        signals: list[str] = []
        pe = _f(r.get("pe_ratio"))
        pb = _f(r.get("pb_ratio"))
        ev_eb = _f(r.get("ev_to_ebitda"))
        ptf = _f(r.get("price_to_fcf"))
        peg = _f(r.get("peg_ratio"))

        undervalued = False
        if pe is not None and pe > 0:
            # Lower PE = better → invert
            s = (sigmoid(-pe, center=-20.0, scale=0.10) - 5.0) * 4.0  # -20..+20
            pts += s
            if pe < 12:
                signals.append(f"Low P/E: {pe:.1f}"); undervalued = True
            elif pe > 40:
                signals.append(f"⚠ Elevated P/E: {pe:.1f}")
        if ev_eb is not None and ev_eb > 0:
            s = (sigmoid(-ev_eb, center=-15.0, scale=0.12) - 5.0) * 3.0  # -15..+15
            pts += s
            if ev_eb < 10:
                signals.append(f"Attractive EV/EBITDA: {ev_eb:.1f}")
        if peg is not None and 0 < peg < 1.0:
            pts += 15; signals.append(f"PEG < 1: {peg:.2f}"); undervalued = True
        if ptf is not None and 0 < ptf < 15:
            pts += 10; signals.append("Attractive price-to-FCF")
        if pb is not None and 0 < pb < 1.5:
            pts += 10

        return ValuationScore(
            score=min(max(pts, 0), 100), pe_ratio=pe, pb_ratio=pb,
            ev_to_ebitda=ev_eb, price_to_fcf=ptf, peg_ratio=peg,
            undervalued=undervalued, signals=signals,
        )

    @staticmethod
    def _grade(score: float) -> FundamentalGrade:
        if score >= 90: return FundamentalGrade.A_PLUS
        if score >= 75: return FundamentalGrade.A
        if score >= 60: return FundamentalGrade.B
        if score >= 45: return FundamentalGrade.C
        if score >= 30: return FundamentalGrade.D
        return FundamentalGrade.F
