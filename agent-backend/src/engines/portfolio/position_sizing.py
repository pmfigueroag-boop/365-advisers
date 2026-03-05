from typing import TypedDict

class PositionAllocationResult(TypedDict):
    opportunity_score: float
    conviction_level: str
    risk_level: str
    base_position_size: float
    risk_adjustment: float
    suggested_allocation: float
    recommended_action: str

class PositionSizingModel:
    @staticmethod
    def calculate(opportunity_score: float, risk_condition: str) -> PositionAllocationResult:
        """
        Calculates the suggested portfolio allocation based on the Opportunity Score
        and the Volatility / Risk condition.
        """
        # Step 1: Score -> Conviction & Step 2: Conviction -> Base Size
        # Very High: 8-12% (target 10%)
        # High: 5-8% (target 6.5%)
        # Moderate: 2-5% (target 3.5%)
        # Watch: 1-2% (target 1.5%)
        # Avoid: 0%
        
        if opportunity_score >= 9.0:
            conviction = "Very High"
            base_size = 10.0
        elif opportunity_score >= 8.0:
            conviction = "High"
            base_size = 6.5
        elif opportunity_score >= 7.0:
            conviction = "Moderate"
            base_size = 3.5
        elif opportunity_score >= 6.0:
            conviction = "Watch"
            base_size = 1.5
        else:
            conviction = "Avoid"
            base_size = 0.0
            
        # Step 3: Risk Adjustment
        # risk_condition from VolatilityModule: LOW, NORMAL, ELEVATED, HIGH
        if risk_condition == "LOW":
            adj = 1.0
            r_level = "Low"
        elif risk_condition == "NORMAL":
            adj = 0.75
            r_level = "Medium"
        elif risk_condition == "ELEVATED":
            adj = 0.50
            r_level = "High"
        elif risk_condition == "HIGH":
            adj = 0.25
            r_level = "Extreme"
        else:
            adj = 0.75 # Default fallback
            r_level = "Medium"
            
        # Step 4: Final calculation & Limit
        adj_size = base_size * adj
        final_size = min(max(adj_size, 0.0), 10.0)  # Single position limit 10%
        
        # Step 5: Recommended Action
        if final_size >= 6.0:
            action = "Increase Position"
        elif final_size >= 3.0:
            action = "Maintain Position"
        elif final_size > 0.0:
            action = "Reduce Position"
        else:
            action = "Exit Position"
            
        return {
            "opportunity_score": round(opportunity_score, 2),
            "conviction_level": conviction,
            "risk_level": r_level,
            "base_position_size": round(base_size, 2),
            "risk_adjustment": round(adj, 2),
            "suggested_allocation": round(final_size, 2),
            "recommended_action": action
        }
