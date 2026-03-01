from graph import fetch_financial_data
import json

def test_full_fetch(symbol):
    print(f"--- Testing fetch_financial_data for {symbol} ---")
    data = fetch_financial_data(symbol)
    
    # Check technical indicators
    tech = data.get("tech_indicators", {})
    print(f"Technical Indicators for {symbol}:")
    for k, v in tech.items():
        print(f"  {k}: {v}")
    
    # Check TradingView data
    tv = data.get("tradingview", {})
    print(f"TradingView Summary: {tv.get('summary', {}).get('RECOMMENDATION')}")

if __name__ == "__main__":
    test_full_fetch("MSFT")
    test_full_fetch("AAPL")
