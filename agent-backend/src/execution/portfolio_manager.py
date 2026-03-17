"""
src/execution/portfolio_manager.py
─────────────────────────────────────────────────────────────────────────────
Orchestrates live portfolio rebalancing using the AnalysisPipeline
and the BaseBroker connection.
"""

import logging
from typing import List, Dict, Any

from src.orchestration.analysis_pipeline import AnalysisPipeline
from src.execution.broker_adapter import BaseBroker

logger = logging.getLogger("365advisers.portfolio_manager")


class PortfolioManager:
    """
    Evaluates a universe of tickers using the Alpha Engine and aligns
    a real/mock brokerage portfolio to the suggested optimal allocations.
    """
    
    def __init__(self, broker: BaseBroker, pipeline: AnalysisPipeline):
        self.broker = broker
        self.pipeline = pipeline

    async def evaluate_and_rebalance(self, universe: List[str], target_holdings: int = 3) -> Dict[str, Any]:
        """
        1. Sells current portfolio.
        2. Scores the universe.
        3. Buys the top `target_holdings` equal weight.
        """
        logger.info("Starting Live Portfolio Rebalance Event")
        
        # 1. Sell Current Holdings
        logger.info("Liquidating existing positions...")
        liq_result = self.broker.liquid_all_positions()
        
        # 2. Get available capital
        account = self.broker.get_account()
        capital = account["cash"]
        logger.info(f"Available Cash to Deploy: ${capital:,.2f}")
        
        # 3. Score Universe
        scored_assets = []
        for ticker in universe:
            logger.info(f"Evaluating {ticker}...")
            try:
                score = 0.0
                price = 0.0
                
                async for chunk in self.pipeline.run_combined_stream(ticker, force=True):
                    if not isinstance(chunk, str):
                        continue
                        
                    lines = chunk.strip().split('\n')
                    event_name = ""
                    data_str = ""
                    for line in lines:
                        if line.startswith("event:"):
                            event_name = line.replace("event:", "").strip()
                        elif line.startswith("data:"):
                            data_str = line.replace("data:", "").strip()
                            
                    if event_name == "opportunity_score" and data_str:
                        import json
                        try:
                            payload = json.loads(data_str)
                            score = payload.get("overall_score", 0.0)
                        except:
                            pass
                            
                import yfinance as yf
                try:
                    price = float(yf.Ticker(ticker).fast_info.get('lastPrice', 0.0))
                except:
                    price = 0.0
                
                # We need a valid price to trade
                if price <= 0:
                    continue
                    
                scored_assets.append({
                    "ticker": ticker,
                    "score": score,
                    "price": price,
                })
            except Exception as e:
                logger.error(f"Error evaluating {ticker}: {e}")
                
        # 4. Rank and Filter Top Quintile
        scored_assets.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = [a for a in scored_assets if a["score"] >= 7.0]
        
        if not top_candidates:
            # Revert to best available if no highly scored assets exist
            top_candidates = scored_assets[:target_holdings]
        else:
            # Constrain to target constraints
            top_candidates = top_candidates[:target_holdings]
            
        if not top_candidates:
            logger.warning("No investable assets found. Remaining cash.")
            return {"status": "SUCCESS", "message": "No assets met criteria", "trades": []}
            
        # 5. Execute Trades
        allocation_per_asset = capital / len(top_candidates)
        trades_executed = []
        
        for asset in top_candidates:
            ticker = asset["ticker"]
            price = asset["price"]
            
            # Floor down the shares; we only buy fractional if the broker supports it
            # Mock broker supports fractional, so we use exact allocation
            qty = allocation_per_asset / price
            
            logger.info(f"Submitting BUY {qty:.2f} {ticker} (Score: {asset['score']:.1f})")
            trade = self.broker.submit_market_order(ticker, qty, "BUY")
            trades_executed.append(trade)
            
        # Final Account State
        final_acct = self.broker.get_account()
        logger.info(f"Rebalance Complete. New Equity: ${final_acct['equity']:,.2f}")
        
        return {
            "status": "SUCCESS",
            "initial_cash": capital,
            "final_account": final_acct,
            "trades": trades_executed,
            "selected_assets": top_candidates
        }
