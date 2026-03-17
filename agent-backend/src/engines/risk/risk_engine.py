"""
src/engines/risk/risk_engine.py
─────────────────────────────────────────────────────────────────────────────
Stochastic Risk Engine (Monte Carlo VaR & CVaR)
Calculates Value at Risk and Expected Shortfall for a given portfolio.
Uses Geometric Brownian Motion (GBM) for future price path simulations.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import logging
from typing import Dict, Any, List

logger = logging.getLogger("365advisers.risk_engine")


class StochasticRiskEngine:
    """
    Evaluates Portfolio Risk over a specified horizon.
    Metrics: Historical VaR, Parametric VaR, Monte Carlo VaR, CVaR, Beta, Correlation Matrix.
    """
    
    def __init__(self, risk_free_rate: float = 0.04):
        self.risk_free_rate = risk_free_rate
        
    def fetch_historical_data(self, tickers: List[str], period: str = "2y") -> pd.DataFrame:
        """Fetches adjusted close prices for the portfolio universe + Benchmark."""
        try:
            # Add benchmark for Beta calculation
            if "SPY" not in tickers:
                tickers_to_fetch = tickers + ["SPY"]
            else:
                tickers_to_fetch = tickers
                
            data = yf.download(tickers_to_fetch, period=period, progress=False)
            
            # Extract 'Close' block correctly handling multiple shapes
            if isinstance(data.columns, pd.MultiIndex):
                if 'Close' in data.columns.levels[0]:
                    data = data['Close']
                elif 'Close' in data.columns.levels[1]:
                    data = data.xs('Close', axis=1, level=1)
            else:
                # If it's a single column (e.g. only 1 ticker was actually fetched)
                # Ensure it remains a DataFrame and we name the column properly
                if len(tickers_to_fetch) == 1:
                     if isinstance(data, pd.Series):
                         data = data.to_frame()
                     data.columns = tickers_to_fetch
            
            if 'SPY' not in data.columns:
                # Fallback if benchmark failed
                logger.warning("Benchmark SPY not found in downloaded data.")
                
            data.dropna(inplace=True)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch risk data: {e}")
            import traceback; traceback.print_exc()
            return pd.DataFrame()

    def calculate_risk_metrics(
        self, 
        portfolio: Dict[str, float], 
        horizon_days: int = 21, 
        confidence_level: float = 0.95,
        mc_simulations: int = 10000
    ) -> Dict[str, Any]:
        """
        Calculates all risk metrics for a weighted portfolio.
        portfolio = {"AAPL": 0.5, "MSFT": 0.5} (Weights must sum to 1.0)
        """
        tickers = list(portfolio.keys())
        if not tickers:
            return {"error": "Empty portfolio"}
            
        data = self.fetch_historical_data(tickers)
        if data.empty:
            return {"error": "Could not fetch historical data"}
            
        # 1. Calculate Daily Returns
        returns = data.pct_change().dropna()
        
        # Extract benchmark returns
        benchmark_returns = returns["SPY"]
        asset_returns = returns[tickers]
        
        # Calculate Portfolio Historical Returns
        weights = np.array([portfolio[t] for t in tickers])
        weights = weights / np.sum(weights) # Ensure it sums to 1
        
        port_returns = asset_returns.dot(weights)
        
        # 2. Historical VaR & CVaR
        # Percentile rank (1 - confidence) * 100
        alpha = 1 - confidence_level
        historical_var = np.percentile(port_returns, alpha * 100)
        historical_cvar = port_returns[port_returns <= historical_var].mean()
        
        # Scale to horizon
        hist_var_horizon = historical_var * np.sqrt(horizon_days)
        hist_cvar_horizon = historical_cvar * np.sqrt(horizon_days)
        
        # 3. Parametric VaR
        mu = np.mean(port_returns)
        sigma = np.std(port_returns)
        from scipy.stats import norm
        z_score = norm.ppf(alpha)
        
        parametric_var_daily = mu + z_score * sigma
        parametric_var_horizon = parametric_var_daily * np.sqrt(horizon_days)
        
        # 4. Monte Carlo VaR (GBM)
        # We simulate the portfolio as a single asset here for simplicity
        # A full multi-variate MC would use Cholesky decomposition of the covariance matrix
        
        dt = 1 # 1 day step
        mc_paths = np.zeros((horizon_days, mc_simulations))
        mc_paths[0] = 1.0 # Start at 100% value
        
        # Simulate Paths
        for t in range(1, horizon_days):
            rand = np.random.standard_normal(mc_simulations)
            mc_paths[t] = mc_paths[t-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rand)
            
        # Terminal returns
        terminal_returns = mc_paths[-1] - 1.0
        mc_var_horizon = np.percentile(terminal_returns, alpha * 100)
        mc_cvar_horizon = terminal_returns[terminal_returns <= mc_var_horizon].mean()
        
        # 5. Beta & Correlation
        covariance_matrix = returns.cov()
        correlation_matrix = returns.corr().to_dict()
        
        # Portfolio Beta vs SP500
        cov_with_market = np.cov(port_returns, benchmark_returns)[0, 1]
        market_var = np.var(benchmark_returns)
        portfolio_beta = cov_with_market / market_var if market_var > 0 else 1.0
        
        # Volatility
        annual_volatility = sigma * np.sqrt(252)
        
        return {
            "portfolio": portfolio,
            "horizon_days": horizon_days,
            "confidence_level": confidence_level,
            "metrics": {
                "historical_var": float(hist_var_horizon),
                "historical_cvar": float(hist_cvar_horizon),
                "parametric_var": float(parametric_var_horizon),
                "monte_carlo_var": float(mc_var_horizon),
                "monte_carlo_cvar": float(mc_cvar_horizon),
                "annual_volatility": float(annual_volatility),
                "portfolio_beta": float(portfolio_beta)
            },
            "correlation_matrix": correlation_matrix
        }


if __name__ == "__main__":
    # Quick Test
    logging.basicConfig(level=logging.INFO)
    engine = StochasticRiskEngine()
    
    # Simulate a $100k portfolio: $50k AAPL, $50k MSFT
    port = {"AAPL": 0.5, "MSFT": 0.5}
    res = engine.calculate_risk_metrics(port)
    
    import json
    print(json.dumps(res, indent=2))
