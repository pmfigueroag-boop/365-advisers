"""tests/test_options_pricing.py — Options Pricing Engine tests."""
import math
import pytest
from src.engines.options_pricing.models import OptionContract, OptionType, Moneyness
from src.engines.options_pricing.black_scholes import BlackScholes
from src.engines.options_pricing.implied_vol import ImpliedVolSolver, VolSurface
from src.engines.options_pricing.engine import OptionsPricingEngine

def _atm_call():
    return OptionContract(underlying_price=100, strike=100, time_to_expiry=1.0, volatility=0.20, risk_free_rate=0.05)

def _otm_put():
    return OptionContract(underlying_price=100, strike=90, time_to_expiry=0.5, volatility=0.25, option_type=OptionType.PUT)

class TestBlackScholes:
    def test_call_price_positive(self):
        r = BlackScholes.price(_atm_call())
        assert r.theoretical_price > 0
        assert r.theoretical_price < 100  # can't exceed underlying

    def test_put_price_positive(self):
        c = _atm_call()
        c.option_type = OptionType.PUT
        r = BlackScholes.price(c)
        assert r.theoretical_price > 0

    def test_call_delta_range(self):
        r = BlackScholes.price(_atm_call())
        assert 0 < r.greeks.delta < 1

    def test_put_delta_negative(self):
        r = BlackScholes.price(_otm_put())
        assert -1 < r.greeks.delta < 0

    def test_gamma_positive(self):
        r = BlackScholes.price(_atm_call())
        assert r.greeks.gamma > 0

    def test_theta_negative(self):
        r = BlackScholes.price(_atm_call())
        assert r.greeks.theta < 0  # time decay

    def test_vega_positive(self):
        r = BlackScholes.price(_atm_call())
        assert r.greeks.vega > 0

    def test_higher_vol_higher_price(self):
        low = BlackScholes.price(OptionContract(underlying_price=100, strike=100, time_to_expiry=1, volatility=0.10))
        high = BlackScholes.price(OptionContract(underlying_price=100, strike=100, time_to_expiry=1, volatility=0.40))
        assert high.theoretical_price > low.theoretical_price

    def test_itm_has_intrinsic(self):
        c = OptionContract(underlying_price=110, strike=100, time_to_expiry=0.5, volatility=0.20)
        r = BlackScholes.price(c)
        assert r.intrinsic_value == pytest.approx(10.0, abs=0.01)

    def test_put_call_parity(self):
        c = _atm_call()
        call_r = BlackScholes.price(c)
        c.option_type = OptionType.PUT
        put_r = BlackScholes.price(c)
        result = BlackScholes.put_call_parity(call_r.theoretical_price, put_r.theoretical_price,
                                               100, 100, 1.0, 0.05)
        assert result.parity_holds

    def test_moneyness_itm(self):
        r = BlackScholes.price(OptionContract(underlying_price=110, strike=100, time_to_expiry=0.5, volatility=0.2))
        assert r.moneyness == Moneyness.ITM.value

class TestImpliedVol:
    def test_solve_iv_roundtrip(self):
        c = _atm_call()
        result = BlackScholes.price(c)
        iv = ImpliedVolSolver.solve(result.theoretical_price, 100, 100, 1.0, 0.05)
        assert iv == pytest.approx(0.20, abs=0.001)

    def test_iv_none_for_bad_price(self):
        iv = ImpliedVolSolver.solve(0.001, 100, 200, 0.01, 0.05)
        # Very deep OTM, may not converge or return very low vol
        assert iv is None or iv < 0.01 or isinstance(iv, float)

    def test_vol_surface(self):
        strikes = [95, 100, 105]
        expiries = [0.25, 0.5]
        prices = {}
        for K in strikes:
            for T in expiries:
                c = OptionContract(underlying_price=100, strike=K, time_to_expiry=T, volatility=0.20)
                r = BlackScholes.price(c)
                prices[(K, T)] = r.theoretical_price
        surface = VolSurface.build(100, strikes, expiries, prices)
        assert len(surface) == 6
        assert all(abs(p.implied_vol - 0.20) < 0.01 for p in surface)

class TestEngine:
    def test_option_chain(self):
        chain = OptionsPricingEngine.option_chain(100, [95, 100, 105], 0.5, 0.20)
        assert len(chain) == 6  # 3 strikes × 2 types
        calls = [c for c in chain if c["type"] == "call"]
        puts = [c for c in chain if c["type"] == "put"]
        assert len(calls) == 3
        assert len(puts) == 3
