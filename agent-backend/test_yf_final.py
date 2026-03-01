import yfinance as yf
import json

def test_yf():
    ticker = yf.Ticker("MSFT")
    print("INFO KEYS:", sorted(list(ticker.info.keys())))
    print("SAMPLE VALUES:")
    for k in ['trailingPE', 'forwardPE', 'returnOnEquity', 'marketCap', 'currentRatio']:
        print(f"{k}: {ticker.info.get(k)}")
    
    print("\nINCOME STMT EMPTY?", ticker.income_stmt.empty)
    print("BALANCE SHEET EMPTY?", ticker.balance_sheet.empty)
    print("CASHFLOW EMPTY?", ticker.cashflow.empty)
    
    if not ticker.income_stmt.empty:
        print("\nINCOME STMT INDEX:", list(ticker.income_stmt.index))

if __name__ == "__main__":
    test_yf()
