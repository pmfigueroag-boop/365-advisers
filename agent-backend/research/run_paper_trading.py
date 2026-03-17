"""
research/run_paper_trading.py
─────────────────────────────────────────────────────────────────────────────
Executes a single live portfolio rebalance using the Mock Broker.
"""

import sys
import os
import logging

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.execution.broker_adapter import MockBrokerAdapter
from src.execution.portfolio_manager import PortfolioManager
from src.orchestration.analysis_pipeline import AnalysisPipeline
from src.services.cache_manager import cache_manager

import asyncio

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("365advisers.paper_trading")

async def main():
    logger.info("Initializing 365 Advisers Live Paper Trading Engine...")
    
    # 1. Initialize Pipeline via DI
    fund_cache = cache_manager.fundamental
    tech_cache = cache_manager.technical
    decision_cache = cache_manager.decision
    pipeline = AnalysisPipeline(fund_cache, tech_cache, decision_cache)
    
    # 2. Initialize Broker (Mock)
    broker = MockBrokerAdapter(db_path="mock_trading_db.sqlite", initial_capital=100000.0)
    
    # 3. Create Manager
    manager = PortfolioManager(broker, pipeline)
    
    # 4. Define Universe
    universe = ["AAPL", "MSFT"]
    
    logger.info(f"Target Universe: {universe}")
    
    # 5. Run Rebalance Event
    result = await manager.evaluate_and_rebalance(universe=universe, target_holdings=1)
    
    print("\n" + "="*50)
    print("LIVE REBALANCE COMPLETE")
    print("="*50)
    print(f"Initial Cash: ${result.get('initial_cash', 0):,.2f}")
    
    final = result.get("final_account", {})
    print(f"Final Equity: ${final.get('equity', 0):,.2f}")
    
    print("\nGenerated Trades:")
    for trade in result.get("trades", []):
        print(f"  - {trade['status']}: {trade.get('filled_qty', 0):.2f} shares @ ${trade.get('filled_price', 0):.2f}")
    
    # Show active positions
    positions = broker.get_positions()
    print("\nCurrent Portfolio:")
    for pos in positions:
        print(f"  {pos['qty']:.2f} {pos['ticker']} (P/L: ${pos['unrealized_pl']:.2f})")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
