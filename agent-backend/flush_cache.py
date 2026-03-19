import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.services.cache_manager import cache_manager

res = cache_manager.invalidate_all("AAPL")
print("Cache Invalidated:", res)
