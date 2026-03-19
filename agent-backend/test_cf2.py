import yfinance as yf

cf = yf.Ticker('AAPL').cashflow
if cf is not None and not cf.empty:
    print("KEYS CONTAINING CAP OR EXP:")
    for k in cf.index:
        if 'cap' in k.lower() or 'exp' in k.lower():
            print(" -", k)
    
    print("\nKEYS CONTAINING REP OR BUY:")
    for k in cf.index:
        if 'rep' in k.lower() or 'buy' in k.lower():
            print(" -", k)
else:
    print("cashflow is empty!")
