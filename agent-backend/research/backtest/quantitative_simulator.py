"""
quantitative_simulator.py
--------------------------------------------------------------------------------
Executes point-in-time scoring using historical TimeMachine slices, generating 
portfolio performance metrics.
"""
from __future__ import annotations

import logging
from datetime import datetime
import pandas as pd
import numpy as np

from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine
from src.engines.technical.regime_detector import (
    TrendRegimeDetector,
    VolatilityRegimeDetector,
    combine_regime_adjustments,
)
from src.engines.scoring.opportunity_model import OpportunityModel
from src.engines.portfolio.position_sizing import PositionSizingModel

logger = logging.getLogger("365advisers.backtest.simulator")

class QuantitativeSimulator:
    """Runs the Fast-Run Quant Backtester across history."""
    
    def __init__(self, time_machine, universe: list[str]):
        self.time_machine = time_machine
        self.universe = universe
        self.results = []
        self.portfolio_history = []
        
    def _run_scoring_engine(self, ticker: str, current_date: datetime) -> dict:
        """Runs the actual Alpha Engine V3 over the historical slice."""
        df = self.time_machine.get_slice(ticker, current_date, lookback_days=252)
        if len(df) < 50:
            return None # Not enough data
            
        # Convert DataFrame to OHLCV format expected by IndicatorEngine
        # df index is DatetimeIndex
        ohlcv = []
        for date, row in df.iterrows():
            ohlcv.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            })
            
        # Calculate technical indicators manually using pandas
        # This mirrors the TradingView live data fetch for point-in-time backtesting
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        
        inds = {}
        inds["close"] = float(close.iloc[-1])
        inds["sma50"] = float(close.rolling(50).mean().iloc[-1])
        inds["sma200"] = float(close.rolling(200).mean().iloc[-1])
        inds["ema20"] = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        
        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        inds["macd"] = float(macd.iloc[-1])
        inds["macd_signal"] = float(macd_signal.iloc[-1])
        inds["macd_hist"] = float(macd.iloc[-1] - macd_signal.iloc[-1])
        
        # Bollinger Bands (20, 2)
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        inds["bb_basis"] = float(sma20.iloc[-1])
        inds["bb_upper"] = float((sma20 + 2 * std20).iloc[-1])
        inds["bb_lower"] = float((sma20 - 2 * std20).iloc[-1])
        
        # ATR (14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        inds["atr"] = float(atr.iloc[-1])
        
        # RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        inds["rsi"] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        
        # ADX / DI (14)
        up = high.diff()
        down = -low.diff()
        plus_dm = np.where((up > down) & (up > 0), up, 0.0)
        minus_dm = np.where((down > up) & (down > 0), down, 0.0)
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).sum() / atr.values)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).sum() / atr.values)
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.rolling(14).mean()
        inds["plus_di"] = float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 20.0
        inds["minus_di"] = float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 20.0
        inds["adx"] = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 20.0
        
        # Volume / OBV
        inds["volume"] = float(df["Volume"].iloc[-1])
        inds["obv"] = 0.0 # Will be computed by VolumeModule internally using OHLCV
        
        raw = {"ohlcv": ohlcv, "indicators": inds}
        
        # 1. Indicators
        indicators = IndicatorEngine.compute(raw)
        
        # 2. Regimes
        raw_inds = raw["indicators"]
        trend_regime = TrendRegimeDetector.detect(adx=raw_inds.get("adx", 20.0), plus_di=raw_inds.get("plus_di", 20.0), minus_di=raw_inds.get("minus_di", 20.0))
        vol_regime = VolatilityRegimeDetector.detect(ohlcv=raw.get("ohlcv", []), current_bb_upper=indicators.volatility.bb_upper, current_bb_lower=indicators.volatility.bb_lower, current_atr=indicators.volatility.atr)
        regime_adj = combine_regime_adjustments(trend_regime, vol_regime)
        
        # 3. Technical Score
        tech_score = ScoringEngine.compute(indicators, None, regime_adj, trend_regime=trend_regime.regime)
        
        # 4. Fundamental Proxy (Fast Run Quantitative bypasses LLM agents)
        # For this test, we assume a static neutral fundamental proxy.
        # This isolates the predictive power of the structural and technical engine.
        fundamental_metrics = {"pe_ratio": 15, "roe": 0.15, "debt_to_equity": 0.5, "free_cash_flow": 1e9}
        fundamental_agents = [{"name": "value", "score": 7, "confidence": 0.5}]
        
        tech_summary = {"summary": {"technical_score": tech_score.aggregate, "trend_condition": trend_regime, "volatility_condition": vol_regime}}
        
        opportunity = OpportunityModel.calculate(
            fundamental_metrics, fundamental_agents, tech_summary
        )
        
        return {
            "date": current_date,
            "ticker": ticker,
            "opportunity_score": opportunity["opportunity_score"],
            "technical_score": tech_score.aggregate,
            "signal": tech_score.signal,
            "price": raw["ohlcv"][-1]["close"]
        }

    def run_simulation(self, rebalance_freq: str = 'M'):
        """Simulates time going forward and rebalancing."""
        dates = self.time_machine.get_trading_dates()
        if not dates:
            logger.error("No trading dates available in Time Machine.")
            return

        df_dates = pd.DataFrame({"Date": dates})
        df_dates.set_index("Date", inplace=True)
        # Get last trading day of each month
        rebalance_dates = df_dates.resample("M").last().index.tolist()
        
        cash = 100000.0
        shares_held = {}
        
        for i, current_date in enumerate(rebalance_dates):
            current_date = current_date.to_pydatetime()
            if current_date > dates[-1]:
                break
                
            logger.info(f"Rebalancing on {current_date.strftime('%Y-%m-%d')}...")
            
            # 1. Mark to Market
            portfolio_val = 0.0
            for ticker, sh in shares_held.items():
                p = self.time_machine.get_latest_price(ticker, current_date)
                if p:
                    portfolio_val += p * sh
            
            # Update total equity
            current_total_equity = cash + portfolio_val
            
            # Simulated sell-all
            cash = current_total_equity
            shares_held = {}
            
            # 2. Score Universe
            scores = []
            for ticker in self.universe:
                try:
                    res = self._run_scoring_engine(ticker, current_date)
                    if res:
                        scores.append(res)
                        self.results.append(res)
                except Exception as e:
                    logger.warning(f"Failed to score {ticker} on {current_date}: {e}")
            
            if not scores:
                self.portfolio_history.append({
                    "date": current_date,
                    "equity": current_total_equity,
                    "holdings": 0
                })
                continue
                
            # 3. Select Top Assets (Score > 7 for example)
            scores.sort(key=lambda x: x["opportunity_score"], reverse=True)
            top_assets = [s for s in scores if s["opportunity_score"] > 7.0]
            
            if not top_assets:
                # If nothing looks good, hold top 2 relative
                top_assets = scores[:2]
                
            # 4. Execute trades (equal weight for simplicity)
            allocation_per_asset = cash / len(top_assets)
            new_shares = {}
            for asset in top_assets:
                p = asset["price"]
                sh = allocation_per_asset / p
                new_shares[asset["ticker"]] = sh
                
            shares_held = new_shares
            cash = 0.0 # Fully invested
            
            # Log Equity
            self.portfolio_history.append({
                "date": current_date,
                "equity": current_total_equity,
                "holdings": len(shares_held)
            })
            
        final_portfolio_val = sum([shares_held[t] * self.time_machine.get_latest_price(t, dates[-1]) for t in shares_held])
        final_equity = cash + final_portfolio_val
        logger.info(f"Simulation ended. Final Equity: ${final_equity:,.2f}")
        return {
            "final_equity": final_equity,
            "return_pct": ((final_equity / 100000.0) - 1.0) * 100,
            "history": self.portfolio_history
        }
