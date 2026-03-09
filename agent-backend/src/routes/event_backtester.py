"""src/routes/event_backtester.py — Event-Driven Backtester API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.engines.event_backtester.models import BacktestConfig
from src.engines.event_backtester.engine import EventBacktester

router = APIRouter(prefix="/alpha/event-backtest", tags=["Alpha: Event Backtester"])

class EventBacktestRequest(BaseModel):
    prices: dict[str, list[float]]
    strategy: str = "momentum"  # momentum | mean_reversion | trend_following
    initial_capital: float = 1_000_000.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    max_position_pct: float = 0.10
    enable_shorting: bool = True

def _builtin_strategy(name: str):
    """Return built-in strategy function."""
    if name == "momentum":
        def strat(ticker, price, positions, cash, _history={}):
            _history.setdefault(ticker, [])
            _history[ticker].append(price)
            if len(_history[ticker]) < 20:
                return None
            sma = sum(_history[ticker][-20:]) / 20
            return 1.0 if price > sma else -1.0
        return strat
    elif name == "mean_reversion":
        def strat(ticker, price, positions, cash, _history={}):
            _history.setdefault(ticker, [])
            _history[ticker].append(price)
            if len(_history[ticker]) < 20:
                return None
            sma = sum(_history[ticker][-20:]) / 20
            return -1.0 if price > sma * 1.02 else (1.0 if price < sma * 0.98 else None)
        return strat
    else:
        def strat(ticker, price, positions, cash, _history={}):
            _history.setdefault(ticker, [])
            _history[ticker].append(price)
            if len(_history[ticker]) < 50:
                return None
            sma50 = sum(_history[ticker][-50:]) / 50
            sma20 = sum(_history[ticker][-20:]) / 20
            return 1.0 if sma20 > sma50 else -1.0
        return strat

@router.post("/run")
async def run_backtest(req: EventBacktestRequest):
    try:
        config = BacktestConfig(
            initial_capital=req.initial_capital, commission_bps=req.commission_bps,
            slippage_bps=req.slippage_bps, max_position_pct=req.max_position_pct,
            enable_shorting=req.enable_shorting,
        )
        bt = EventBacktester(config)
        strategy = _builtin_strategy(req.strategy)
        result = bt.run(req.prices, strategy)
        # Limit equity curve and trade log for API response
        result_dict = result.model_dump()
        result_dict["equity_curve"] = result_dict["equity_curve"][-500:]
        result_dict["trade_log"] = result_dict["trade_log"][-100:]
        return result_dict
    except Exception as e:
        raise HTTPException(500, str(e))
