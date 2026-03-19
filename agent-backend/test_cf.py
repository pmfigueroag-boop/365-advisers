import yfinance as yf
import json

stock = yf.Ticker('AAPL')
res = {}

cf = stock.cashflow
if cf is not None and not cf.empty:
    res['cf_keys'] = list(cf.index)

print(json.dumps(res, indent=2))
