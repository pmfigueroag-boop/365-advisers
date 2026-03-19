import yfinance as yf
import json

stock = yf.Ticker('AAPL')
out = list(stock.cashflow.index) if stock.cashflow is not None else []
with open("cf.json", "w") as f:
    json.dump(out, f, indent=2)
