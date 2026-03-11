from typing import TypedDict, Optional
from datetime import datetime, timezone

from src.engines.alpha_signals.models import SignalProfile
from src.engines.composite_alpha.models import CompositeAlphaResult

class OpportunitySubscores(TypedDict, total=False):
    competitive_moat: float
    growth_quality: float
    relative_valuation: float
    intrinsic_value_gap: float
    industry_structure: float
    management_capital_allocation: float

class DimensionScores(TypedDict):
    business_quality: float
    valuation: float
    financial_strength: float
    market_behavior: float

class OpportunityScoreResult(TypedDict):
    opportunity_score: float
    dimensions: DimensionScores
    factors: dict[str, float]
    recorded_at: str

class OpportunityModel:
    """
    Calculates the Institutional Opportunity Score (0-10) based on 12 factors
    divided into 4 dimensions.
    """

    @staticmethod
    def _safe_average(values: list[float]) -> float:
        valid_values = [v for v in values if v is not None]
        if not valid_values:
            return 5.0  # Neutral fallback
        return sum(valid_values) / len(valid_values)

    @classmethod
    def calculate(
        cls,
        fundamental_metrics: dict,
        fundamental_agents: list[dict],
        technical_summary: dict,
        signal_profile: SignalProfile | None = None,
        composite_alpha: CompositeAlphaResult | None = None,
    ) -> OpportunityScoreResult:
        
        # 1. Extract Agent Subscores
        agent_scores: OpportunitySubscores = {}
        lynch_signal_conf = 5.0
        buffett_signal_conf = 5.0
        marks_signal_conf = 5.0
        icahn_signal_conf = 5.0

        # Map graph agent names → scoring roles
        _AGENT_ROLE_MAP: dict[str, str] = {
            # New fundamental graph names
            "Value & Margin of Safety": "Buffett",
            "Quality & Moat": "Lynch",
            "Capital Allocation": "Icahn",
            "Risk & Macro Stress": "Marks",
            # Legacy names (backward compatible)
            "Lynch": "Lynch",
            "Buffett": "Buffett",
            "Marks": "Marks",
            "Icahn": "Icahn",
        }

        for agent in fundamental_agents:
            raw_name = agent.get("agent", agent.get("agent_name", ""))
            name = _AGENT_ROLE_MAP.get(raw_name, "")
            conf = agent.get("conviction", agent.get("confidence", 0.5))
            sig = agent.get("signal", "HOLD")
            base_score = 5.0 + (conf * 5.0 if sig == "BUY" else -conf * 5.0 if sig == "SELL" else 0)

            subscores = agent.get("opportunity_subscores", {})
            try:
                if name == "Lynch":
                    agent_scores["competitive_moat"] = float(subscores.get("competitive_moat", base_score))
                    agent_scores["growth_quality"] = float(subscores.get("growth_quality", base_score))
                    lynch_signal_conf = base_score
                elif name == "Buffett":
                    agent_scores["relative_valuation"] = float(subscores.get("relative_valuation", base_score))
                    agent_scores["intrinsic_value_gap"] = float(subscores.get("intrinsic_value_gap", base_score))
                    buffett_signal_conf = base_score
                elif name == "Marks":
                    agent_scores["industry_structure"] = float(subscores.get("industry_structure", base_score))
                    marks_signal_conf = base_score
                elif name == "Icahn":
                    agent_scores["management_capital_allocation"] = float(subscores.get("management_capital_allocation", base_score))
                    icahn_signal_conf = base_score
            except (ValueError, TypeError):
                pass

        # 2. Financial Metrics Extraction
        profitability = fundamental_metrics.get("profitability", {})
        valuation = fundamental_metrics.get("valuation", {})
        leverage = fundamental_metrics.get("leverage", {})

        # F6. Free Cash Flow Yield (Proxy from ROIC, capped to 0-10)
        fcf_yield_score = 5.0 
        roic = profitability.get("roic")
        if isinstance(roic, (int, float)):
            fcf_yield_score = min(10.0, max(0.0, (roic * 100) / 2))

        # F7. Balance Sheet Strength — use debt/equity if available, else agent conf
        balance_sheet_score = marks_signal_conf
        de = leverage.get("debt_to_equity")
        if isinstance(de, (int, float)) and de >= 0:
            # D/E 0 → 10 (pristine), D/E 1 → 5 (moderate), D/E 3+ → 0 (overleveraged)
            balance_sheet_score = min(10.0, max(0.0, 10.0 - (de * 10.0 / 3.0)))

        # F8. Earnings Stability — use operating margin if available, else agent conf
        earnings_stability_score = lynch_signal_conf
        op_margin = profitability.get("operating_margin")
        if isinstance(op_margin, (int, float)):
            # op_margin 30%+ → 10, 15% → 5, 0% → 0, negative → 0
            earnings_stability_score = min(10.0, max(0.0, op_margin * 100.0 / 3.0))

        # 3. Technical Engine Metrics — use real module subscores when available
        subscores = technical_summary.get("summary", {}).get("subscores", {})
        tech_score = technical_summary.get("technical_score",
                        technical_summary.get("summary", {}).get("technical_score", 5.0))

        trend_score = subscores.get("trend", tech_score)
        momentum_score = subscores.get("momentum", tech_score)
        # Institutional flow proxied by volume module (OBV + vol ratio)
        inst_flow_score = subscores.get("volume", tech_score)

        # 4. Map the 12 Factors
        factors = {
            # DIM 1: Business Quality
            "competitive_moat": agent_scores.get("competitive_moat", lynch_signal_conf),
            "management_capital_allocation": agent_scores.get("management_capital_allocation", icahn_signal_conf),
            "industry_structure": agent_scores.get("industry_structure", marks_signal_conf),

            # DIM 2: Valuation
            "relative_valuation": agent_scores.get("relative_valuation", buffett_signal_conf),
            "intrinsic_value_gap": agent_scores.get("intrinsic_value_gap", buffett_signal_conf),
            "fcf_yield": fcf_yield_score,

            # DIM 3: Financial Strength
            "balance_sheet_strength": balance_sheet_score,
            "earnings_stability": earnings_stability_score,
            "growth_quality": agent_scores.get("growth_quality", lynch_signal_conf),

            # DIM 4: Market Behavior
            "trend_strength": trend_score,
            "momentum": momentum_score,
            "institutional_flow": inst_flow_score
        }

        # 4b. Alpha Signals adjustment — prefer CASE result if available
        if composite_alpha is not None:
            try:
                from src.engines.scoring.signal_bridge import (
                    compute_case_factor_adjustments,
                    compute_case_alpha_weight,
                    blend_signal_adjustments,
                )
                signal_adjustments = compute_case_factor_adjustments(composite_alpha)
                alpha_weight = compute_case_alpha_weight(composite_alpha)
                if signal_adjustments:
                    factors = blend_signal_adjustments(
                        factors, signal_adjustments, alpha_weight=alpha_weight
                    )
            except Exception:
                pass  # Graceful degradation
        elif signal_profile is not None:
            try:
                from src.engines.scoring.signal_bridge import (
                    compute_signal_factor_adjustments,
                    blend_signal_adjustments,
                )
                signal_adjustments = compute_signal_factor_adjustments(signal_profile)
                if signal_adjustments:
                    factors = blend_signal_adjustments(
                        factors, signal_adjustments, alpha_weight=0.3
                    )
            except Exception:
                pass  # Graceful degradation — signals are optional

        # 5. Calculate Dimensions
        dimensions = DimensionScores(
            business_quality=cls._safe_average([factors["competitive_moat"], factors["management_capital_allocation"], factors["industry_structure"]]),
            valuation=cls._safe_average([factors["relative_valuation"], factors["intrinsic_value_gap"], factors["fcf_yield"]]),
            financial_strength=cls._safe_average([factors["balance_sheet_strength"], factors["earnings_stability"], factors["growth_quality"]]),
            market_behavior=cls._safe_average([factors["trend_strength"], factors["momentum"], factors["institutional_flow"]])
        )

        # 6. Calculate Final Opportunity Score (0-10)
        weights = 0.25
        opportunity_score = (
            (dimensions["business_quality"] * weights) +
            (dimensions["valuation"] * weights) +
            (dimensions["financial_strength"] * weights) +
            (dimensions["market_behavior"] * weights)
        )

        return {
            "opportunity_score": round(opportunity_score, 2),
            "dimensions": {k: round(v, 2) for k, v in dimensions.items()}, # type: ignore
            "factors": {k: round(v, 2) for k, v in factors.items()},
            "recorded_at": datetime.now(timezone.utc).isoformat()
        }
