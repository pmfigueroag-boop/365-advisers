import sys
import os
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.data.market_data import fetch_fundamental_data

data = fetch_fundamental_data("AAPL")
with open("payload.json", "w") as f:
    json.dump(data.get("ratios", {}).get("quality", {}), f, indent=2)
