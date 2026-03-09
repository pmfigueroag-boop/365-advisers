"""
src/engines/options_pricing/black_scholes.py
──────────────────────────────────────────────────────────────────────────────
Black-Scholes-Merton pricing model with Greeks.

Supports European call/put options with continuous dividend yield.
"""
from __future__ import annotations
import math
import logging
from src.engines.options_pricing.models import (
    OptionContract, OptionType, Greeks, PricingResult, Moneyness, PutCallParityResult,
)

logger = logging.getLogger("365advisers.options.black_scholes")

_SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF (Abramowitz & Stegun approximation)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / _SQRT_2PI


class BlackScholes:
    """Black-Scholes-Merton option pricing with Greeks."""

    @classmethod
    def price(cls, contract: OptionContract) -> PricingResult:
        """Price an option and compute all Greeks."""
        S = contract.underlying_price
        K = contract.strike
        T = contract.time_to_expiry
        sigma = contract.volatility
        r = contract.risk_free_rate
        q = contract.dividend_yield

        d1, d2 = cls._d1_d2(S, K, T, sigma, r, q)

        if contract.option_type == OptionType.CALL:
            price = cls._call_price(S, K, T, r, q, d1, d2)
            intrinsic = max(S - K, 0)
        else:
            price = cls._put_price(S, K, T, r, q, d1, d2)
            intrinsic = max(K - S, 0)

        greeks = cls._greeks(contract, d1, d2)
        moneyness = cls._moneyness(S, K, contract.option_type)

        return PricingResult(
            theoretical_price=round(price, 4),
            greeks=greeks,
            intrinsic_value=round(intrinsic, 4),
            time_value=round(max(price - intrinsic, 0), 4),
            moneyness=moneyness,
            contract=contract,
        )

    @classmethod
    def _greeks(cls, c: OptionContract, d1: float, d2: float) -> Greeks:
        S, K, T, sigma, r, q = (
            c.underlying_price, c.strike, c.time_to_expiry,
            c.volatility, c.risk_free_rate, c.dividend_yield,
        )
        sqrt_T = math.sqrt(T)
        e_qT = math.exp(-q * T)
        e_rT = math.exp(-r * T)
        nd1 = _norm_pdf(d1)

        if c.option_type == OptionType.CALL:
            delta = e_qT * _norm_cdf(d1)
            theta_annual = (
                -(S * nd1 * sigma * e_qT) / (2 * sqrt_T)
                - r * K * e_rT * _norm_cdf(d2)
                + q * S * e_qT * _norm_cdf(d1)
            )
            rho = K * T * e_rT * _norm_cdf(d2) / 100
        else:
            delta = e_qT * (_norm_cdf(d1) - 1)
            theta_annual = (
                -(S * nd1 * sigma * e_qT) / (2 * sqrt_T)
                + r * K * e_rT * _norm_cdf(-d2)
                - q * S * e_qT * _norm_cdf(-d1)
            )
            rho = -K * T * e_rT * _norm_cdf(-d2) / 100

        gamma = (nd1 * e_qT) / (S * sigma * sqrt_T)
        vega = S * e_qT * nd1 * sqrt_T / 100  # per 1% vol move
        theta_daily = theta_annual / 365

        return Greeks(
            delta=round(delta, 6),
            gamma=round(gamma, 6),
            theta=round(theta_daily, 6),
            vega=round(vega, 6),
            rho=round(rho, 6),
        )

    @staticmethod
    def _d1_d2(S, K, T, sigma, r, q):
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        return d1, d2

    @staticmethod
    def _call_price(S, K, T, r, q, d1, d2):
        return S * math.exp(-q * T) * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)

    @staticmethod
    def _put_price(S, K, T, r, q, d1, d2):
        return K * math.exp(-r * T) * _norm_cdf(-d2) - S * math.exp(-q * T) * _norm_cdf(-d1)

    @staticmethod
    def _moneyness(S, K, opt_type):
        if opt_type == OptionType.CALL:
            if S > K * 1.02:
                return Moneyness.ITM.value
            elif S < K * 0.98:
                return Moneyness.OTM.value
        else:
            if S < K * 0.98:
                return Moneyness.ITM.value
            elif S > K * 1.02:
                return Moneyness.OTM.value
        return Moneyness.ATM.value

    @classmethod
    def put_call_parity(
        cls, call_price: float, put_price: float, S: float, K: float,
        T: float, r: float, q: float = 0.0,
    ) -> PutCallParityResult:
        """Verify put-call parity: C - P = S·e^{-qT} - K·e^{-rT}."""
        s_pv = S * math.exp(-q * T)
        k_pv = K * math.exp(-r * T)
        synthetic_call = put_price + s_pv - k_pv
        synthetic_put = call_price - s_pv + k_pv
        violation = abs(call_price - put_price - s_pv + k_pv)
        return PutCallParityResult(
            call_price=call_price, put_price=put_price,
            synthetic_call=round(synthetic_call, 4),
            synthetic_put=round(synthetic_put, 4),
            parity_violation=round(violation, 4),
            parity_holds=violation < 0.05,
        )
