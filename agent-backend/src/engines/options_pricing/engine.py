"""
src/engines/options_pricing/engine.py
──────────────────────────────────────────────────────────────────────────────
Options Pricing Engine — orchestrates pricing, Greeks, and IV.
"""
from __future__ import annotations
import logging
from src.engines.options_pricing.models import OptionContract, OptionType, PricingResult
from src.engines.options_pricing.black_scholes import BlackScholes
from src.engines.options_pricing.implied_vol import ImpliedVolSolver, VolSurface

logger = logging.getLogger("365advisers.options.engine")


class OptionsPricingEngine:
    """Orchestrator for option pricing, Greeks, and IV analysis."""

    @classmethod
    def price_option(cls, contract: OptionContract) -> PricingResult:
        """Price an option and compute Greeks."""
        return BlackScholes.price(contract)

    @classmethod
    def compute_iv(
        cls, market_price: float, underlying_price: float, strike: float,
        time_to_expiry: float, option_type: OptionType = OptionType.CALL,
        risk_free_rate: float = 0.05,
    ) -> float | None:
        """Solve for implied volatility."""
        return ImpliedVolSolver.solve(
            market_price=market_price, underlying_price=underlying_price,
            strike=strike, time_to_expiry=time_to_expiry,
            risk_free_rate=risk_free_rate, option_type=option_type,
        )

    @classmethod
    def option_chain(
        cls, underlying_price: float, strikes: list[float],
        time_to_expiry: float, volatility: float, risk_free_rate: float = 0.05,
    ) -> list[dict]:
        """Price a full option chain (calls + puts for all strikes)."""
        chain = []
        for K in strikes:
            for opt_type in [OptionType.CALL, OptionType.PUT]:
                contract = OptionContract(
                    underlying_price=underlying_price, strike=K,
                    time_to_expiry=time_to_expiry, volatility=volatility,
                    risk_free_rate=risk_free_rate, option_type=opt_type,
                )
                result = BlackScholes.price(contract)
                chain.append({
                    "strike": K, "type": opt_type.value,
                    "price": result.theoretical_price,
                    "delta": result.greeks.delta,
                    "gamma": result.greeks.gamma,
                    "theta": result.greeks.theta,
                    "vega": result.greeks.vega,
                    "moneyness": result.moneyness,
                })
        return chain
