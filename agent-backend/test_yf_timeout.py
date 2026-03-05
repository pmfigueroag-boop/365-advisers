import yfinance as yf
from curl_cffi import requests

try:
    print("Fetching NVDA with curl_cffi timeout...")
    # Initialize a curl_cffi session with a 5-second timeout
    session = requests.Session(timeout=5)
    stock = yf.Ticker("NVDA", session=session)
    print(stock.info.get("sector"))
    print("Done!")
except Exception as e:
    print("Error:", e)
