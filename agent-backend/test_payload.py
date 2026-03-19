import sys
import os
import json

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data.market_data import fetch_fundamental_data

data = fetch_fundamental_data("AAPL")
if "ratios" in data and "quality" in data["ratios"]:
    print(json.dumps(data["ratios"]["quality"], indent=2))
else:
    print("NO RATIOS FOUND", json.dumps(data, indent=2))
