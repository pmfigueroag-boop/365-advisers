"""
src/engines/options_pricing/implied_vol.py
──────────────────────────────────────────────────────────────────────────────
Implied Volatility solver and Vol Surface builder.
"""
from __future__ import annotations
import math
import logging
from src.engines.options_pricing.models import OptionContract, OptionType, VolSurfacePoint
from src.engines.options_pricing.black_scholes import BlackScholes

logger = logging.getLogger("365advisers.options.implied_vol")


class ImpliedVolSolver:
    """Newton-Raphson implied volatility solver."""

    MAX_ITER = 100
    PRECISION = 1e-6

    @classmethod
    def solve(
        cls,
        market_price: float,
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0.0,
        option_type: OptionType = OptionType.CALL,
        initial_vol: float = 0.30,
    ) -> float | None:
        """
        Solve for implied volatility using Newton-Raphson.

        Returns the implied vol or None if convergence fails.
        """
        vol = initial_vol
        for i in range(cls.MAX_ITER):
            contract = OptionContract(
                underlying_price=underlying_price,
                strike=strike,
                time_to_expiry=time_to_expiry,
                volatility=vol,
                risk_free_rate=risk_free_rate,
                dividend_yield=dividend_yield,
                option_type=option_type,
            )
            result = BlackScholes.price(contract)
            diff = result.theoretical_price - market_price

            if abs(diff) < cls.PRECISION:
                return round(vol, 6)

            # Vega is per 1% move, so multiply by 100 for actual derivative
            vega_actual = result.greeks.vega * 100
            if abs(vega_actual) < 1e-10:
                break

            vol -= diff / vega_actual
            vol = max(0.001, min(vol, 5.0))  # clamp to reasonable range

        logger.warning(
            "IV solve did not converge for S=%.2f K=%.2f T=%.4f market=%.4f",
            underlying_price, strike, time_to_expiry, market_price,
        )
        return None


class VolSurface:
    """Build a 2D volatility surface from market prices."""

    @classmethod
    def build(
        cls,
        underlying_price: float,
        strikes: list[float],
        expiries: list[float],
        market_prices: dict[tuple[float, float], float],
        risk_free_rate: float = 0.05,
        option_type: OptionType = OptionType.CALL,
    ) -> list[VolSurfacePoint]:
        """
        Build a vol surface grid.

        Args:
            underlying_price: Current spot price.
            strikes: List of strike prices.
            expiries: List of times to expiry (years).
            market_prices: Dict mapping (strike, expiry) → market price.
            risk_free_rate: Risk-free rate.
            option_type: CALL or PUT.

        Returns:
            List of VolSurfacePoint (one per solved strike/expiry pair).
        """
        points: list[VolSurfacePoint] = []

        for K in strikes:
            for T in expiries:
                mkt_price = market_prices.get((K, T))
                if mkt_price is None or mkt_price <= 0:
                    continue

                iv = ImpliedVolSolver.solve(
                    market_price=mkt_price,
                    underlying_price=underlying_price,
                    strike=K,
                    time_to_expiry=T,
                    risk_free_rate=risk_free_rate,
                    option_type=option_type,
                )
                if iv is not None:
                    points.append(VolSurfacePoint(
                        strike=K,
                        time_to_expiry=T,
                        implied_vol=iv,
                        moneyness=round(K / underlying_price, 4),
                    ))

        return points
