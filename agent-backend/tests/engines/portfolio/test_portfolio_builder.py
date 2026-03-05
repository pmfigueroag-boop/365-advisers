from src.engines.portfolio.portfolio_builder import PortfolioConstructionModel

def test_categorize_position_core():
    # High quality, strong financials, normal risk -> CORE
    dims = {"business_quality": 8, "financial_strength": 9}
    assert PortfolioConstructionModel.categorize_position(dims, "NORMAL") == "CORE"
    assert PortfolioConstructionModel.categorize_position(dims, "LOW") == "CORE"

def test_categorize_position_satellite():
    # Missing qualities -> SATELLITE
    assert PortfolioConstructionModel.categorize_position({"business_quality": 6, "financial_strength": 9}, "NORMAL") == "SATELLITE"
    assert PortfolioConstructionModel.categorize_position({"business_quality": 8, "financial_strength": 6}, "NORMAL") == "SATELLITE"
    # High qualities but elevated risk -> SATELLITE
    assert PortfolioConstructionModel.categorize_position({"business_quality": 9, "financial_strength": 9}, "ELEVATED") == "SATELLITE"
    assert PortfolioConstructionModel.categorize_position({"business_quality": 9, "financial_strength": 9}, "HIGH") == "SATELLITE"

def test_build_portfolio_basic():
    positions = [
        {"ticker": "AAPL", "sector": "Technology", "dimensions": {"business_quality": 9, "financial_strength": 9}, "position_sizing": {"suggested_allocation": 8.0, "risk_level": "NORMAL"}},
        {"ticker": "MSFT", "sector": "Technology", "dimensions": {"business_quality": 8, "financial_strength": 8}, "position_sizing": {"suggested_allocation": 9.0, "risk_level": "LOW"}},
        {"ticker": "NVDA", "sector": "Technology", "dimensions": {"business_quality": 9, "financial_strength": 8}, "position_sizing": {"suggested_allocation": 12.0, "risk_level": "ELEVATED"}}
    ]
    
    res = PortfolioConstructionModel.build_portfolio(positions)
    
    # AAPL: 8% CORE
    # MSFT: 9% CORE
    # NVDA: capped at 10% SATELLITE
    # Total Tech: 8+9+10 = 27%
    # Sector limit Tech = 25%.
    # Proportionate scaling of 25 / 27 applied to all 3.
    
    assert res["violations_detected"]
    assert "Sector Technology exceeded 25.0% limit" in res["violations_detected"][0]
    
    assert res["sector_exposures"]["Technology"] == 25.0
    assert res["total_allocation"] == 25.0
    
    assert 15 <= res["core_allocation_total"] <= 16 # (8+9) * (25/27) = 15.74
    assert len(res["core_positions"]) == 2
    assert len(res["satellite_positions"]) == 1

def test_build_portfolio_total_capacity():
    positions = [{"ticker": f"T{i}", "sector": f"Sec{i}", "dimensions": {"business_quality": 8, "financial_strength": 8}, "position_sizing": {"suggested_allocation": 8.0, "risk_level": "NORMAL"}} for i in range(15)]
    # 15 * 8% = 120%. Should scale down to 100%.
    
    res = PortfolioConstructionModel.build_portfolio(positions)
    
    assert res["total_allocation"] == 100.0
    assert "Portfolio exceeded 100% capacity" in res["violations_detected"][0]

def test_volatility_parity():
    # Asset A has ATR 2.0 (Normal volatility)
    # Asset B has ATR 4.0 (Double volatility)
    # Both start with same conviction (10.0%)
    positions = [
        {"ticker": "A", "sector": "Tech", "dimensions": {"business_quality": 9, "financial_strength": 9}, "volatility_atr": 2.0, "position_sizing": {"suggested_allocation": 10.0, "risk_level": "NORMAL"}},
        {"ticker": "B", "sector": "Tech", "dimensions": {"business_quality": 9, "financial_strength": 9}, "volatility_atr": 4.0, "position_sizing": {"suggested_allocation": 10.0, "risk_level": "NORMAL"}},
    ]
    
    res = PortfolioConstructionModel.build_portfolio(positions)
    # Total Allocation = 20.0
    # Before Parity: A=10, B=10
    # Parity inverted weights: A = 10/2 = 5. B = 10/4 = 2.5
    # Sum of inverted = 7.5
    # Normalized: 
    # A = (5 / 7.5) * 20 = 13.33%
    # B = (2.5 / 7.5) * 20 = 6.66%
    
    core = sorted(res["core_positions"], key=lambda x: x["ticker"])
    assert len(core) == 2
    assert core[0]["ticker"] == "A"
    assert round(core[0]["target_weight"], 1) == 13.3
    assert core[1]["ticker"] == "B"
    assert round(core[1]["target_weight"], 1) == 6.7
    assert res["total_allocation"] == 20.0

if __name__ == "__main__":
    print("Testing categorize_position_core...")
    test_categorize_position_core()
    print("Testing categorize_position_satellite...")
    test_categorize_position_satellite()
    print("Testing build_portfolio_basic...")
    test_build_portfolio_basic()
    print("Testing build_portfolio_total_capacity...")
    test_build_portfolio_total_capacity()
    print("Testing volatility_parity...")
    test_volatility_parity()
    print("Testing build_portfolio_total_capacity...")
    test_build_portfolio_total_capacity()
    print("All tests passed!")
