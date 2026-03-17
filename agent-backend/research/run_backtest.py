"""
run_backtest.py
--------------------------------------------------------------------------------
Orchestrates the Phase 2 Fast-Run Quantitative Backtest.
"""

import sys
import os
import logging
from datetime import datetime

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from research.backtest.historical_data import TimeMachine
from research.backtest.quantitative_simulator import QuantitativeSimulator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("365advisers.backtest.main")

def run():
    universe = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA'] # Fast run universe
    
    start_date = "2024-01-01"
    end_date = "2026-03-16"
    
    logger.info(f"Initializing Quantitative Backtester for {len(universe)} assets...")
    tm = TimeMachine(tickers=universe, start_date=start_date, end_date=end_date)
    tm.download_bulk()
    
    sim = QuantitativeSimulator(time_machine=tm, universe=universe)
    logger.info("Starting simulation loop...")
    results = sim.run_simulation(rebalance_freq='M')
    
    logger.info("=" * 60)
    logger.info("BACKTEST RESULTS (FAST-RUN QUANTS ONLY):")
    logger.info(f"INITIAL CAPITAL: $100,000.00")
    logger.info(f"FINAL CAPITAL:   ${results['final_equity']:,.2f}")
    logger.info(f"TOTAL RETURN:    {results['return_pct']:.2f}%")
    logger.info("=" * 60)
    
if __name__ == "__main__":
    run()
