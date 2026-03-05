from typing import TypedDict, List, Dict

class PortfolioRecommendationResult(TypedDict):
    total_allocation: float
    core_allocation_total: float
    satellite_allocation_total: float
    risk_level: str
    sector_exposures: Dict[str, float]
    core_positions: List[Dict]
    satellite_positions: List[Dict]
    violations_detected: List[str]

class PortfolioConstructionModel:
    MAX_SINGLE_POSITION = 10.0
    MAX_SECTOR_EXPOSURE = 25.0
    MAX_HIGH_VOLATILITY = 15.0

    @classmethod
    def categorize_position(cls, dimensions: dict, risk_condition: str) -> str:
        """Determines whether a position fits the CORE or SATELLITE bucket."""
        business_quality = dimensions.get("business_quality", 0)
        financial_strength = dimensions.get("financial_strength", 0)
        
        # High quality and safe -> CORE
        if business_quality >= 7 and financial_strength >= 7 and risk_condition in ["LOW", "NORMAL"]:
            return "CORE"
            
        return "SATELLITE"

    @classmethod
    def apply_volatility_parity(cls, positions: List[Dict]) -> None:
        """
        Adjusts target_weight based on the volatility (ATR) of each asset.
        Formula: Risk-adjusted weight = Base Conviction / max(ATR, 1.0)
        Then it normalizes the new weights to maintain the original sum of weights.
        """
        if not positions:
            return
            
        original_sum = sum(p["target_weight"] for p in positions)
        if original_sum == 0:
            return

        # 1. Calculate unnormalized risk-parity weights
        raw_vp_weights = []
        for p in positions:
            # We enforce a floor of 1.0% ATR to avoid dividing by zero or tiny numbers blowing up weights
            atr = max(float(p.get("volatility_atr", 2.0)), 1.0) 
            # Inverse volatility weighted by original conviction (target_weight)
            parity_weight = p["target_weight"] / atr
            raw_vp_weights.append(parity_weight)

        # 2. Normalize to the original sum of weights
        vp_sum = sum(raw_vp_weights)
        if vp_sum > 0:
            for i, p in enumerate(positions):
                p["target_weight"] = (raw_vp_weights[i] / vp_sum) * original_sum


    @classmethod
    def build_portfolio(cls, analyses: List[Dict]) -> PortfolioRecommendationResult:
        """
        Takes a list of individual ticker analyses and builds a structured portfolio,
        respecting Risk Budgeting limits.
        
        Expected structure of each item in `analyses`:
        {
            "ticker": "AAPL",
            "sector": "Technology",
            "opportunity_score": 8.5,
            "dimensions": {"business_quality": 9, ...},
            "position_sizing": {
                "suggested_allocation": 8.5,
                "risk_level": "NORMAL"
            }
        }
        """
        core_pos = []
        satellite_pos = []
        violations = []
        sector_exposures = {}
        high_vol_total = 0.0
        
        # 1. Classification & Initial Aggregation
        for stock in analyses:
            ticker = stock.get("ticker", "UNKNOWN")
            pos_sizing = stock.get("position_sizing", {})
            raw_weight = min(pos_sizing.get("suggested_allocation", 0.0), cls.MAX_SINGLE_POSITION)
            
            if raw_weight <= 0:
                continue

            role = cls.categorize_position(
                stock.get("dimensions", {}), 
                pos_sizing.get("risk_level", "NORMAL")
            )
            
            item = {
                "ticker": ticker,
                "target_weight": raw_weight,
                "role": role,
                "sector": stock.get("sector", "Unknown"),
                "volatility_atr": stock.get("volatility_atr") or stock.get("position_sizing", {}).get("volatility_atr") or 2.0,
            }
            
            if role == "CORE":
                core_pos.append(item)
            else:
                satellite_pos.append(item)

        # 1.5 Apply Volatility Parity within buckets to equalize risk contribution
        cls.apply_volatility_parity(core_pos)
        cls.apply_volatility_parity(satellite_pos)

        total_capital = sum(p["target_weight"] for p in core_pos + satellite_pos)

        # 2. Risk Checks & Scaling
        if total_capital > 100.0:
            scale_factor = 100.0 / total_capital
            violations.append(f"Portfolio exceeded 100% capacity ({total_capital:.1f}%). Pro-rata scale down applied ({scale_factor:.2f}x).")
            for p in core_pos + satellite_pos:
                p["target_weight"] *= scale_factor
                
        # 3. Recalculate buckets and sector mapping after scaling
        final_core_total = 0.0
        final_sat_total = 0.0
        
        for p in core_pos + satellite_pos:
            sec = p["sector"]
            sector_exposures[sec] = sector_exposures.get(sec, 0.0) + p["target_weight"]
            
            if p["role"] == "CORE":
                final_core_total += p["target_weight"]
            else:
                final_sat_total += p["target_weight"]

        # 4. Enforce Sector Limits
        for sec, exposure in list(sector_exposures.items()):
            if exposure > cls.MAX_SECTOR_EXPOSURE:
                violations.append(f"Sector {sec} exceeded {cls.MAX_SECTOR_EXPOSURE}% limit (was {exposure:.1f}%). Automatically trimmed.")
                scale = cls.MAX_SECTOR_EXPOSURE / exposure
                sector_exposures[sec] = cls.MAX_SECTOR_EXPOSURE
                for p in core_pos + satellite_pos:
                    if p["sector"] == sec:
                        p["target_weight"] *= scale

        # 5. Recalculate totals AFTER all trims (fixes #18 — was using broken inline delta math)
        final_core_total = sum(p["target_weight"] for p in core_pos)
        final_sat_total = sum(p["target_weight"] for p in satellite_pos)

        # Compile final outputs
        final_total = final_core_total + final_sat_total
        
        return {
            "total_allocation": round(final_total, 2),
            "core_allocation_total": round(final_core_total, 2),
            "satellite_allocation_total": round(final_sat_total, 2),
            "risk_level": "MODERATE" if final_sat_total <= 50.0 else "ELEVATED",
            "sector_exposures": {k: round(v, 2) for k, v in sector_exposures.items() if v > 0},
            "core_positions": [{k: v if k != "target_weight" else round(v, 2) for k, v in p.items()} for p in sorted(core_pos, key=lambda x: x["target_weight"], reverse=True)],
            "satellite_positions": [{k: v if k != "target_weight" else round(v, 2) for k, v in p.items()} for p in sorted(satellite_pos, key=lambda x: x["target_weight"], reverse=True)],
            "violations_detected": violations
        }

