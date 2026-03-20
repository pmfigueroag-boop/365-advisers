"""
src/routes/validation_pkg/cost_analysis.py
─────────────────────────────────────────────────────────────────────────────
Transaction cost analysis and benchmark/factor evaluation endpoints.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.cost_model.engine import CostModelEngine
from src.engines.cost_model.models import CostModelConfig, SpreadMethod
from src.engines.cost_model.repository import CostModelRepository
from src.engines.benchmark_factor.engine import BenchmarkFactorEngine
from src.engines.benchmark_factor.models import BenchmarkConfig, FactorTickers
from src.engines.benchmark_factor.repository import BenchmarkFactorRepository

logger = logging.getLogger("365advisers.routes.validation")

router = APIRouter(tags=["Quantitative Validation Framework"])

_cost_engine = CostModelEngine()
_cost_repo = CostModelRepository()
_bf_engine = BenchmarkFactorEngine()
_bf_repo = BenchmarkFactorRepository()


class CostAnalysisRequest(BaseModel):
    run_id: str = Field(..., description="Backtest run to analyze")
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    eta: float = 0.1
    assumed_trade_usd: float = 100_000
    slippage_bps: float = 5.0
    commission_bps: float = 5.0
    spread_method: str = "auto"
    benchmark_ticker: str = "SPY"


class BenchmarkFactorRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    additional_benchmarks: list[str] = Field(
        default_factory=lambda: ["QQQ", "IWM"],
    )
    enable_factor_regression: bool = True
    benchmark_ticker: str = "SPY"


@router.post("/cost-analysis", summary="Run transaction cost analysis")
async def run_cost_analysis(request: CostAnalysisRequest):
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        import pandas as pd

        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker,
        )
        engine = BacktestEngine()

        all_tickers = list(set(config.universe + [config.benchmark_ticker]))
        ohlcv_data = await engine._fetch_historical_data(
            all_tickers, config.start_date, config.end_date,
        )

        signals = engine._get_signals(config.signal_ids)
        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        all_events = []
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

        if not all_events:
            return {"error": "No signal events generated", "signal_profiles": []}

        cost_cfg = CostModelConfig(
            eta=request.eta,
            assumed_trade_usd=request.assumed_trade_usd,
            slippage_bps=request.slippage_bps,
            commission_bps=request.commission_bps,
            spread_method=SpreadMethod(request.spread_method),
        )
        cost_engine = CostModelEngine(cost_cfg)
        adjusted_events, breakdowns = cost_engine.adjust_events(
            all_events, ohlcv_data, cost_cfg,
        )

        report = cost_engine.build_report(
            all_events, adjusted_events, breakdowns,
            config.forward_windows, cost_cfg,
        )

        _cost_repo.save_profiles(request.run_id, report.signal_profiles)
        return report.model_dump()

    except Exception as exc:
        logger.error("VALIDATION-API: Cost analysis failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/cost-analysis/{run_id}", summary="Get cost profiles for a run")
async def get_cost_profiles(run_id: str):
    profiles = _cost_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No cost profiles found for run {run_id}")
    return profiles


@router.get("/cost-analysis/signal/{signal_id}", summary="Get latest cost profile for a signal")
async def get_signal_cost_profile(signal_id: str):
    profile = _cost_repo.get_signal_profile(signal_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No cost profile found for signal {signal_id}")
    return profile


@router.post("/benchmark-factor", summary="Run benchmark & factor evaluation")
async def run_benchmark_factor(request: BenchmarkFactorRequest):
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        import pandas as pd

        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker,
        )
        engine = BacktestEngine()

        ft = FactorTickers()
        all_tickers = list(set(
            config.universe
            + [config.benchmark_ticker]
            + request.additional_benchmarks
            + [ft.market, ft.small_cap, ft.value, ft.growth, ft.momentum]
        ))
        ohlcv_data = await engine._fetch_historical_data(
            all_tickers, config.start_date, config.end_date,
        )

        signals = engine._get_signals(config.signal_ids)
        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        all_events = []
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

        if not all_events:
            return {"error": "No signal events generated", "signal_profiles": []}

        bf_config = BenchmarkConfig(
            market_benchmark=request.benchmark_ticker,
            additional_benchmarks=request.additional_benchmarks,
            enable_factor_regression=request.enable_factor_regression,
        )
        bf_engine = BenchmarkFactorEngine(bf_config)
        report = bf_engine.evaluate(all_events, ohlcv_data, bf_config)

        from uuid import uuid4
        run_id = str(uuid4())
        _bf_repo.save_profiles(run_id, report.signal_profiles)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Benchmark-factor evaluation failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/benchmark-factor/{run_id}", summary="Get benchmark/factor profiles for a run")
async def get_benchmark_factor_profiles(run_id: str):
    profiles = _bf_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No profiles found for run {run_id}")
    return profiles


@router.get("/benchmark-factor/signal/{signal_id}", summary="Get latest benchmark/factor profile for a signal")
async def get_signal_benchmark_profile(signal_id: str):
    profile = _bf_repo.get_signal_profile(signal_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No benchmark profile found for signal {signal_id}")
    return profile
