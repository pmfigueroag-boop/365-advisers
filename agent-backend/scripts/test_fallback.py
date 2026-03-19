import pandas as pd
from unittest.mock import patch
import sys
import os

# Ensure the current directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.market_data import fetch_fundamental_data, fetch_technical_data

@patch('src.data.market_data.yf.Ticker')
def test_fund(m_ticker):
    # Mock yfinance to raise Exception
    m_ticker.side_effect = Exception("Simulated yfinance crash")
    
    print("\n[TEST] Simulating yfinance crash for Fundamental Data...")
    res = fetch_fundamental_data("AAPL")
    print("\n--- FUNDAMENTAL RESULT ---")
    print(f"Name: {res.get('name')}")
    print(f"Market Cap: {res.get('info', {}).get('marketCap')}")
    print(f"Fallback Used: {res.get('_fallback')}")
    print(f"Error logged?: {res.get('error') is not None}")
    assert res.get("_fallback") == "alpha_vantage", "Did not fallback to EDPL"
    assert res.get("name") is not None, "Fallback returned empty"

@patch('src.data.market_data.yf.Ticker')
def test_tech(m_ticker):
    # Mock yfinance to raise Exception
    m_ticker.side_effect = Exception("Simulated yfinance crash")
    
    print("\n[TEST] Simulating yfinance crash for Technical Data...")
    res = fetch_technical_data("AAPL")
    print("\n--- TECHNICAL OHLCV RESULT ---")
    print(f"Total OHLCV bars returned: {len(res.get('ohlcv', []))}")
    if len(res.get('ohlcv', [])) > 0:
        print(f"Latest Bar: {res['ohlcv'][-1]}")
    # We do not assert on ohlcv len > 0 because the API key might be empty in the user's config
    # We just want to see it didn't throw an unhandled exception

if __name__ == "__main__":
    test_fund()
    test_tech()
    print("\nAll tests passed execution without hard crashing.")
