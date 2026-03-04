from typing import TypedDict, Optional
from datetime import datetime, timezone

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
        technical_summary: dict
    ) -> OpportunityScoreResult:
        
        # 1. Extract Agent Subscores
        agent_scores: OpportunitySubscores = {}
        lynch_signal_conf = 5.0
        buffett_signal_conf = 5.0
        marks_signal_conf = 5.0
        icahn_signal_conf = 5.0

        for agent in fundamental_agents:
            name = agent.get("agent_name", "")
            conf = agent.get("confidence", 0.5)
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
        
        # F6. Free Cash Flow Yield (Proxy from ROIC or general profitability if raw FCF isn't available)
        fcf_yield_score = 5.0 
        roic = profitability.get("roic")
        if isinstance(roic, (int, float)):
            fcf_yield_score = min(10.0, max(0.0, (roic * 100) / 2)) # Rough mapping, 20% ROIC = 10 score

        # F7. Balance Sheet Strength (Proxy from Debt/Equity if we add it, otherwise fallback to Mark's risk modifier)
        balance_sheet_score = marks_signal_conf

        # F8. Earnings Stability
        earnings_stability_score = lynch_signal_conf

        # 3. Technical Engine Metrics
        # F10, F11, F12 from technical summary
        tech_score = technical_summary.get("technical_score", 5.0)
        
        # We need to extract the raw module scores if available, otherwise proxy from tech_score
        trend_score = tech_score
        momentum_score = tech_score
        inst_flow_score = tech_score

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
