"""
src/engines/options/black_scholes.py
─────────────────────────────────────────────────────────────────────────────
Black-Scholes-Merton Option Pricing Model & Greeks.
Calculates theoretical prices and sensitivities for European-style options.
"""

import numpy as np
from scipy.stats import norm
import math

class BlackScholesEngine:
    """Calculates Option Greeks and Theoretical Prices."""
    
    @staticmethod
    def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 probability factor."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return (math.log(S / K) + (r + (sigma ** 2) / 2) * T) / (sigma * math.sqrt(T))
        
    @staticmethod
    def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d2 probability factor."""
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = BlackScholesEngine._d1(S, K, T, r, sigma)
        return d1 - sigma * math.sqrt(T)

    @classmethod
    def price_call(cls, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """European Call Option Price."""
        if T <= 0:
            return max(0.0, S - K)
        d1 = cls._d1(S, K, T, r, sigma)
        d2 = cls._d2(S, K, T, r, sigma)
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        
    @classmethod
    def price_put(cls, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """European Put Option Price."""
        if T <= 0:
            return max(0.0, K - S)
        d1 = cls._d1(S, K, T, r, sigma)
        d2 = cls._d2(S, K, T, r, sigma)
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
    @classmethod
    def delta(cls, S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
        """Rate of change of option price with respect to underlying asset price."""
        if T <= 0:
            if option_type.lower() == "call":
                return 1.0 if S > K else 0.0
            return -1.0 if S < K else 0.0
            
        d1 = cls._d1(S, K, T, r, sigma)
        if option_type.lower() == "call":
            return norm.cdf(d1)
        elif option_type.lower() == "put":
            return norm.cdf(d1) - 1
        raise ValueError("option_type must be 'call' or 'put'")

    @classmethod
    def gamma(cls, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Rate of change of delta with respect to underlying asset price. Same for call/put."""
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = cls._d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * math.sqrt(T))

    @classmethod
    def theta(cls, S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
        """Rate of change of option price with respect to time (usually per year, divide by 365 for daily)."""
        if T <= 0:
            return 0.0
            
        d1 = cls._d1(S, K, T, r, sigma)
        d2 = cls._d2(S, K, T, r, sigma)
        
        term1 = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        
        if option_type.lower() == "call":
            term2 = r * K * math.exp(-r * T) * norm.cdf(d2)
            return term1 - term2
        elif option_type.lower() == "put":
            term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)
            return term1 + term2
        raise ValueError("option_type must be 'call' or 'put'")

    @classmethod
    def vega(cls, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Rate of change of option price with respect to volatility. Same for call/put."""
        if T <= 0:
            return 0.0
        d1 = cls._d1(S, K, T, r, sigma)
        # Note: Usually divided by 100 to show value per 1% change in vol
        return S * norm.pdf(d1) * math.sqrt(T)

    @classmethod
    def rho(cls, S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> float:
        """Rate of change of option price with respect to interest rate."""
        if T <= 0:
            return 0.0
            
        d2 = cls._d2(S, K, T, r, sigma)
        
        # Note: Usually divided by 100 to show value per 1% change in rate
        if option_type.lower() == "call":
            return K * T * math.exp(-r * T) * norm.cdf(d2)
        elif option_type.lower() == "put":
            return -K * T * math.exp(-r * T) * norm.cdf(-d2)
        raise ValueError("option_type must be 'call' or 'put'")
        
    @classmethod
    def analyze_option(cls, S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call") -> dict:
        """Returns a comprehensive dictionary of price and all Greeks."""
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("option_type must be 'call' or 'put'")
            
        price = cls.price_call(S, K, T, r, sigma) if option_type == "call" else cls.price_put(S, K, T, r, sigma)
        dlt = cls.delta(S, K, T, r, sigma, option_type)
        gmm = cls.gamma(S, K, T, r, sigma)
        tht = cls.theta(S, K, T, r, sigma, option_type) / 365.0 # Daily Theta
        vga = cls.vega(S, K, T, r, sigma) / 100.0 # Per 1% implied vol
        rh = cls.rho(S, K, T, r, sigma, option_type) / 100.0 # Per 1% interest rate
        
        return {
            "type": option_type.upper(),
            "underlying_price": S,
            "strike_price": K,
            "time_to_expiry_years": T,
            "risk_free_rate": r,
            "implied_volatility": sigma,
            "theoretical_price": round(price, 4),
            "greeks": {
                "delta": round(dlt, 4),
                "gamma": round(gmm, 4),
                "theta_daily": round(tht, 4),
                "vega_1pct": round(vga, 4),
                "rho_1pct": round(rh, 4)
            }
        }

if __name__ == "__main__":
    # Test example
    # Underlying: $100, Strike: $100, 1 year expiry, 5% rate, 20% vol
    call_eval = BlackScholesEngine.analyze_option(100, 100, 1.0, 0.05, 0.20, "call")
    put_eval = BlackScholesEngine.analyze_option(100, 100, 1.0, 0.05, 0.20, "put")
    
    import json
    print("CALL:")
    print(json.dumps(call_eval, indent=2))
    print("\nPUT:")
    print(json.dumps(put_eval, indent=2))
