"""
src/routes/validation.py
──────────────────────────────────────────────────────────────────────────────
REST API endpoints for the Quantitative Validation Framework (QVF).

Provides access to:
  - Combination and regime-conditional backtesting
  - Rolling performance snapshots and degradation alerts
  - Opportunity performance tracking
  - Automated recalibration (with dry-run support)
  - Unified QVF dashboard
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.models import (
    BacktestConfig,
    CombinationBacktestResult,
    RegimePerformanceReport,
    CalibrationSuggestion,
)
from src.engines.backtesting.recalibration_engine import RecalibrationEngine
from src.engines.backtesting.rolling_analyzer import (
    DegradationReport,
    RollingPerformanceSnapshot,
)
from src.engines.opportunity_tracking.tracker import OpportunityTracker
from src.engines.opportunity_tracking.models import (
    DetectorAccuracy,
    OpportunityPerformanceSummary,
)
from src.engines.opportunity_tracking.repository import OpportunityRepository

logger = logging.getLogger("365advisers.routes.validation")

router = APIRouter(prefix="/validation", tags=["Quantitative Validation Framework"])


# ─── Request Models ──────────────────────────────────────────────────────────

class CombinationBacktestRequest(BaseModel):
    """Request to run combination backtesting."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_groups: list[list[str]] = Field(
        ...,
        description="Each inner list is a combination of signal IDs to test jointly",
    )
    benchmark_ticker: str = "SPY"


class RegimeBacktestRequest(BaseModel):
    """Request to run regime-conditional backtesting."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    benchmark_ticker: str = "SPY"


class RecalibrationRequest(BaseModel):
    """Request to apply recalibration suggestions."""
    suggestion_ids: list[int] | None = None
    dry_run: bool = True


class QVFDashboardResponse(BaseModel):
    """Unified dashboard data for the QVF."""
    rolling_snapshots: list[RollingPerformanceSnapshot] = Field(default_factory=list)
    degradation_alerts: list[DegradationReport] = Field(default_factory=list)
    opportunity_summary: OpportunityPerformanceSummary | None = None
    top_performers: list[str] = Field(default_factory=list)
    recalibration_suggestions: list[CalibrationSuggestion] = Field(default_factory=list)


# ─── Singleton engine instances ──────────────────────────────────────────────

_backtest_engine = BacktestEngine()
_recalibration_engine = RecalibrationEngine()
_opportunity_tracker = OpportunityTracker()


# ─── Combination Backtest ────────────────────────────────────────────────────

@router.post(
    "/backtest/combination",
    response_model=list[CombinationBacktestResult],
    summary="Run combination backtesting",
)
async def run_combination_backtest(request: CombinationBacktestRequest):
    """
    Test signal combinations using AND logic.

    For each group, finds dates where ALL signals fired simultaneously,
    then measures joint forward returns and computes incremental alpha.
    """
    config = BacktestConfig(
        universe=request.universe,
        start_date=request.start_date,
        end_date=request.end_date,
        benchmark_ticker=request.benchmark_ticker,
    )
    try:
        results = await _backtest_engine.run_combination(config, request.signal_groups)
        return results
    except Exception as exc:
        logger.error("VALIDATION-API: Combination backtest failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Regime-Conditional Backtest ─────────────────────────────────────────────

@router.post(
    "/backtest/regime",
    response_model=list[RegimePerformanceReport],
    summary="Run regime-conditional backtesting",
)
async def run_regime_backtest(request: RegimeBacktestRequest):
    """
    Partition historical data into Bull/Bear/Range/HighVol regimes
    and compute per-signal performance within each regime.
    """
    config = BacktestConfig(
        universe=request.universe,
        start_date=request.start_date,
        end_date=request.end_date,
        signal_ids=request.signal_ids,
        benchmark_ticker=request.benchmark_ticker,
    )
    try:
        results = await _backtest_engine.run_regime_conditional(config)
        return results
    except Exception as exc:
        logger.error("VALIDATION-API: Regime backtest failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Rolling Performance ────────────────────────────────────────────────────

@router.get(
    "/performance/rolling/{signal_id}",
    response_model=list[RollingPerformanceSnapshot],
    summary="Get rolling performance snapshots",
)
async def get_rolling_performance(signal_id: str):
    """Return rolling performance snapshots (30D/90D/252D) for a signal."""
    from src.engines.backtesting.performance_repository import SignalPerformanceRepository
    from src.engines.backtesting.rolling_analyzer import RollingAnalyzer

    events = SignalPerformanceRepository.get_events_for_signal(signal_id)
    if not events:
        return []

    analyzer = RollingAnalyzer()
    return analyzer.compute_rolling_metrics(signal_id, events)


# ─── Degradation Alerts ─────────────────────────────────────────────────────

@router.get(
    "/performance/degradation",
    response_model=list[DegradationReport],
    summary="Get active degradation alerts",
)
async def get_degradation_alerts():
    """Return all active (unresolved) signal degradation alerts."""
    return _recalibration_engine.scan_for_degradation()


# ─── Opportunity Tracking ───────────────────────────────────────────────────

@router.get(
    "/opportunities/summary",
    response_model=OpportunityPerformanceSummary,
    summary="Get opportunity tracking summary",
)
async def get_opportunity_summary(
    idea_type: str | None = Query(None, description="Filter by detector type"),
    min_age_days: int = Query(20, ge=1, le=365),
):
    """Aggregate performance of generated ideas by detector type and confidence."""
    return _opportunity_tracker.get_performance_summary(idea_type, min_age_days)


@router.get(
    "/opportunities/{idea_uid}",
    summary="Get single idea forward performance",
)
async def get_opportunity_detail(idea_uid: str):
    """Return tracking record for a specific idea."""
    record = OpportunityRepository.get_by_idea_uid(idea_uid)
    if not record:
        raise HTTPException(status_code=404, detail=f"Idea {idea_uid} not found")
    return {
        "idea_uid": record.idea_uid,
        "ticker": record.ticker,
        "idea_type": record.idea_type,
        "confidence": record.confidence,
        "signal_strength": record.signal_strength,
        "opportunity_score": record.opportunity_score,
        "price_at_gen": record.price_at_gen,
        "generated_at": record.generated_at.isoformat() if record.generated_at else None,
        "return_1d": record.return_1d,
        "return_5d": record.return_5d,
        "return_20d": record.return_20d,
        "return_60d": record.return_60d,
        "benchmark_return_20d": record.benchmark_return_20d,
        "excess_return_20d": record.excess_return_20d,
        "tracking_status": record.tracking_status,
    }


@router.get(
    "/opportunities/accuracy",
    response_model=dict[str, DetectorAccuracy],
    summary="Get per-detector accuracy",
)
async def get_detector_accuracy():
    """Per-detector precision: what % of ideas generated positive returns."""
    return _opportunity_tracker.get_detector_accuracy()


# ─── Recalibration ──────────────────────────────────────────────────────────

@router.post(
    "/recalibrate",
    response_model=list[CalibrationSuggestion],
    summary="Run recalibration scan (dry-run)",
)
async def run_recalibration():
    """
    Scan all signals for degradation and generate recalibration suggestions.
    Does NOT apply changes — use /recalibrate/apply for that.
    """
    degraded = _recalibration_engine.scan_for_degradation()
    return _recalibration_engine.generate_recalibration_plan(degraded)


@router.post(
    "/recalibrate/apply",
    summary="Apply recalibration suggestions",
)
async def apply_recalibration(request: RecalibrationRequest):
    """Apply recalibration suggestions to the live registry."""
    degraded = _recalibration_engine.scan_for_degradation()
    suggestions = _recalibration_engine.generate_recalibration_plan(degraded)
    records = _recalibration_engine.auto_apply(suggestions, dry_run=request.dry_run)
    return {
        "mode": "dry_run" if request.dry_run else "live",
        "applied": len(records),
        "records": [r.model_dump() for r in records],
    }


# ─── Dashboard ──────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=QVFDashboardResponse,
    summary="Unified QVF dashboard",
)
async def get_qvf_dashboard():
    """
    Aggregated view of the Quantitative Validation Framework.

    Returns rolling performance, degradation alerts, opportunity summary,
    top performers, and pending recalibration suggestions.
    """
    try:
        # Rolling snapshots (latest for all signals)
        snapshots = _recalibration_engine.compute_rolling_snapshots()

        # Degradation
        degraded = _recalibration_engine.scan_for_degradation()

        # Opportunities
        opp_summary = _opportunity_tracker.get_performance_summary()

        # Top performers
        top = _recalibration_engine.identify_top_performers()

        # Suggestions
        suggestions = _recalibration_engine.generate_recalibration_plan(degraded)

        return QVFDashboardResponse(
            rolling_snapshots=snapshots[:50],  # Limit for response size
            degradation_alerts=degraded,
            opportunity_summary=opp_summary,
            top_performers=top,
            recalibration_suggestions=suggestions,
        )
    except Exception as exc:
        logger.error("VALIDATION-API: Dashboard failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Walk-Forward Validation ────────────────────────────────────────────────

from src.engines.walk_forward.engine import WalkForwardEngine
from src.engines.walk_forward.models import (
    WalkForwardConfig,
    WalkForwardMode,
    WalkForwardRun,
    WFSignalSummary,
)
from src.engines.walk_forward.repository import WalkForwardRepository

_wf_engine = WalkForwardEngine()
_wf_repo = WalkForwardRepository()


class WalkForwardRequest(BaseModel):
    """Request body to start a walk-forward validation run."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    train_days: int = 756
    test_days: int = 126
    step_days: int | None = None
    mode: str = "rolling"
    signal_ids: list[str] | None = None
    benchmark_ticker: str = "SPY"
    min_train_events: int = 30
    is_hit_rate_threshold: float = 0.50


@router.post(
    "/walk-forward",
    summary="Start a walk-forward validation run",
)
async def start_walk_forward(request: WalkForwardRequest):
    """
    Run walk-forward validation across temporal folds.

    Separates in-sample calibration from out-of-sample evaluation to
    detect overfitting and compute stability scores per signal.
    """
    try:
        config = WalkForwardConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            train_days=request.train_days,
            test_days=request.test_days,
            step_days=request.step_days,
            mode=WalkForwardMode(request.mode),
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker,
            min_train_events=request.min_train_events,
            is_hit_rate_threshold=request.is_hit_rate_threshold,
        )
        run = await _wf_engine.run(config)

        # Persist results
        if run.status == "completed":
            _wf_repo.save_run(run)

        return run.model_dump()
    except Exception as exc:
        logger.error("VALIDATION-API: Walk-forward failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/walk-forward/runs",
    summary="List recent walk-forward runs",
)
async def list_walk_forward_runs(limit: int = Query(20, ge=1, le=100)):
    """Return compact summaries of recent walk-forward validation runs."""
    return _wf_repo.list_runs(limit=limit)


@router.get(
    "/walk-forward/{run_id}",
    summary="Get walk-forward run report",
)
async def get_walk_forward_run(run_id: str):
    """Get the full report for a specific walk-forward run."""
    summary = _wf_repo.get_run_summary(run_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return summary


@router.get(
    "/walk-forward/{run_id}/signal/{signal_id}",
    summary="Get signal detail in a walk-forward run",
)
async def get_walk_forward_signal(run_id: str, signal_id: str):
    """Get per-fold IS/OOS results for a specific signal in a run."""
    results = _wf_repo.get_signal_results(run_id, signal_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No results for signal {signal_id} in run {run_id}",
        )
    return results


@router.get(
    "/walk-forward/stability/{signal_id}",
    summary="Get latest stability score for a signal",
)
async def get_signal_stability(signal_id: str):
    """Return the stability score from the most recent walk-forward run."""
    runs = _wf_repo.list_runs(limit=1)
    if not runs:
        raise HTTPException(status_code=404, detail="No walk-forward runs found")

    latest_run_id = runs[0]["run_id"]
    results = _wf_repo.get_signal_results(latest_run_id, signal_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Signal {signal_id} not found in latest run {latest_run_id}",
        )
    return {
        "signal_id": signal_id,
        "run_id": latest_run_id,
        "fold_results": results,
    }


# ─── Transaction Cost Analysis ──────────────────────────────────────────────

from src.engines.cost_model.engine import CostModelEngine
from src.engines.cost_model.models import CostModelConfig, SpreadMethod
from src.engines.cost_model.repository import CostModelRepository

_cost_engine = CostModelEngine()
_cost_repo = CostModelRepository()


class CostAnalysisRequest(BaseModel):
    """Request to run transaction cost analysis on a backtest run."""
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


@router.post(
    "/cost-analysis",
    summary="Run transaction cost analysis",
)
async def run_cost_analysis(request: CostAnalysisRequest):
    """
    Apply transaction cost model to signal events from a backtest.

    Computes cost-adjusted returns, Sharpe ratios, and resilience
    scores for each signal.
    """
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig

        # Run a fresh backtest to get events + OHLCV data
        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker,
        )
        engine = BacktestEngine()

        # Fetch data
        all_tickers = list(set(config.universe + [config.benchmark_ticker]))
        ohlcv_data = await engine._fetch_historical_data(
            all_tickers, config.start_date, config.end_date,
        )

        # Get signals and evaluate
        signals = engine._get_signals(config.signal_ids)
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        import pandas as pd

        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        all_events = []
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker,
                ohlcv=ticker_ohlcv,
                signals=signals,
                forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

        if not all_events:
            return {"error": "No signal events generated", "signal_profiles": []}

        # Apply cost model
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

        # Persist
        _cost_repo.save_profiles(request.run_id, report.signal_profiles)

        return report.model_dump()

    except Exception as exc:
        logger.error("VALIDATION-API: Cost analysis failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/cost-analysis/{run_id}",
    summary="Get cost profiles for a run",
)
async def get_cost_profiles(run_id: str):
    """Return stored cost profiles from a previous analysis."""
    profiles = _cost_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(
            status_code=404,
            detail=f"No cost profiles found for run {run_id}",
        )
    return profiles


@router.get(
    "/cost-analysis/signal/{signal_id}",
    summary="Get latest cost profile for a signal",
)
async def get_signal_cost_profile(signal_id: str):
    """Return the most recent cost profile for a signal."""
    profile = _cost_repo.get_signal_profile(signal_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No cost profile found for signal {signal_id}",
        )
    return profile


# ─── Benchmark & Factor Evaluation ──────────────────────────────────────────

from src.engines.benchmark_factor.engine import BenchmarkFactorEngine
from src.engines.benchmark_factor.models import BenchmarkConfig, FactorTickers
from src.engines.benchmark_factor.repository import BenchmarkFactorRepository

_bf_engine = BenchmarkFactorEngine()
_bf_repo = BenchmarkFactorRepository()


class BenchmarkFactorRequest(BaseModel):
    """Request to run benchmark & factor evaluation."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    additional_benchmarks: list[str] = Field(
        default_factory=lambda: ["QQQ", "IWM"],
    )
    enable_factor_regression: bool = True
    benchmark_ticker: str = "SPY"


@router.post(
    "/benchmark-factor",
    summary="Run benchmark & factor evaluation",
)
async def run_benchmark_factor(request: BenchmarkFactorRequest):
    """
    Evaluate signals against multiple benchmarks and a 4-factor
    risk model to isolate pure alpha from factor exposure.
    """
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        import pandas as pd

        # Prepare full config
        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker,
        )
        engine = BacktestEngine()

        # Collect all tickers (universe + benchmarks + factor ETFs)
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

        # Generate signal events
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
                ticker=ticker,
                ohlcv=ticker_ohlcv,
                signals=signals,
                forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

        if not all_events:
            return {"error": "No signal events generated", "signal_profiles": []}

        # Run benchmark & factor evaluation
        bf_config = BenchmarkConfig(
            market_benchmark=request.benchmark_ticker,
            additional_benchmarks=request.additional_benchmarks,
            enable_factor_regression=request.enable_factor_regression,
        )
        bf_engine = BenchmarkFactorEngine(bf_config)
        report = bf_engine.evaluate(all_events, ohlcv_data, bf_config)

        # Persist
        from uuid import uuid4
        run_id = str(uuid4())
        _bf_repo.save_profiles(run_id, report.signal_profiles)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Benchmark-factor evaluation failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/benchmark-factor/{run_id}",
    summary="Get benchmark/factor profiles for a run",
)
async def get_benchmark_factor_profiles(run_id: str):
    """Return stored benchmark & factor profiles from a previous evaluation."""
    profiles = _bf_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(
            status_code=404,
            detail=f"No profiles found for run {run_id}",
        )
    return profiles


@router.get(
    "/benchmark-factor/signal/{signal_id}",
    summary="Get latest benchmark/factor profile for a signal",
)
async def get_signal_benchmark_profile(signal_id: str):
    """Return the most recent benchmark & factor profile for a signal."""
    profile = _bf_repo.get_signal_profile(signal_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No benchmark profile found for signal {signal_id}",
        )
    return profile


# ─── Validation Intelligence Dashboard ──────────────────────────────────────

from src.engines.validation_dashboard.aggregator import DashboardAggregator
from src.engines.validation_dashboard.models import ValidationIntelligence

_dashboard_aggregator = DashboardAggregator()


@router.get(
    "/intelligence",
    response_model=ValidationIntelligence,
    summary="Validation Intelligence Dashboard",
)
async def get_validation_intelligence():
    """
    Unified QVF intelligence dashboard.

    Aggregates data from all QVF modules (Signal Performance, Walk-Forward,
    Cost Model, Benchmark Factor, Opportunity Tracker, Recalibration Engine)
    into a single response with four sections:
      - Signal Leaderboard
      - Detector Performance
      - Opportunity Tracking
      - System Health
    """
    try:
        return _dashboard_aggregator.aggregate()
    except Exception as exc:
        logger.error("VALIDATION-API: Intelligence dashboard failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Signal Selection & Redundancy Pruning ──────────────────────────────────

from src.engines.signal_selection.engine import RedundancyPruningEngine
from src.engines.signal_selection.models import RedundancyConfig
from src.engines.signal_selection.repository import SignalSelectionRepository

_selection_engine = RedundancyPruningEngine()
_selection_repo = SignalSelectionRepository()


class SignalSelectionRequest(BaseModel):
    """Request to run signal redundancy analysis."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    corr_threshold: float = 0.80
    auto_disable_threshold: float = 0.75


class ApplySelectionRequest(BaseModel):
    """Request to apply redundancy recommendations."""
    run_id: str
    auto_disable: bool = True


@router.post(
    "/signal-selection",
    summary="Run signal redundancy analysis",
)
async def run_signal_selection(request: SignalSelectionRequest):
    """
    Analyze signals for redundancy, correlation, and incremental alpha.
    Classifies each signal as KEEP / REDUCE_WEIGHT / CANDIDATE_REMOVAL / REMOVE.
    """
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        from collections import defaultdict
        import pandas as pd

        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
        )
        engine = BacktestEngine()

        ohlcv_data = await engine._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date, config.end_date,
        )

        signals = engine._get_signals(config.signal_ids)
        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        events_by_signal = defaultdict(list)
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            for e in events:
                events_by_signal[e.signal_id].append(e)

        if not events_by_signal:
            return {"error": "No signal events generated", "profiles": []}

        redundancy_config = RedundancyConfig(
            forward_window=request.forward_window,
            corr_threshold=request.corr_threshold,
            auto_disable_threshold=request.auto_disable_threshold,
        )
        sel_engine = RedundancyPruningEngine(redundancy_config)
        report = sel_engine.analyze(dict(events_by_signal), redundancy_config)

        from uuid import uuid4
        run_id = str(uuid4())
        _selection_repo.save_profiles(run_id, report.profiles)

        result = report.model_dump()
        result["run_id"] = run_id
        # Exclude large correlation matrix from response
        result.pop("correlation_matrix", None)
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Signal selection failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/signal-selection/apply",
    summary="Apply redundancy recommendations",
)
async def apply_signal_selection(request: ApplySelectionRequest):
    """Apply redundancy results: disable REMOVE signals, flag others."""
    profiles = _selection_repo.get_profiles(request.run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No results for run {request.run_id}")

    from src.engines.signal_selection.models import SignalRedundancyProfile, RedundancyClass
    from src.engines.signal_selection.engine import RedundancyPruningEngine

    engine = RedundancyPruningEngine()
    # Reconstruct minimal report for apply
    from src.engines.signal_selection.models import RedundancyReport
    report = RedundancyReport(
        profiles=[
            SignalRedundancyProfile(
                signal_id=p["signal_id"],
                classification=RedundancyClass(p["classification"]),
                recommended_weight=p.get("recommended_weight", 1.0),
            )
            for p in profiles
        ],
    )
    actions = engine.apply_to_registry(report, request.auto_disable)
    return {"run_id": request.run_id, "actions": actions}


@router.get(
    "/signal-selection/{run_id}",
    summary="Get signal selection results",
)
async def get_signal_selection_results(run_id: str):
    """Return stored redundancy analysis from a previous run."""
    profiles = _selection_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return profiles


@router.get(
    "/signal-selection/signal/{signal_id}",
    summary="Get latest redundancy profile for a signal",
)
async def get_signal_redundancy_profile(signal_id: str):
    """Return the most recent redundancy profile for a signal."""
    profile = _selection_repo.get_signal_profile(signal_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No redundancy profile found for signal {signal_id}",
        )
    return profile


# ─── Regime-Adaptive Signal Weighting ───────────────────────────────────────

from src.engines.regime_weights.engine import AdaptiveWeightEngine
from src.engines.regime_weights.models import AdaptiveWeightConfig
from src.engines.regime_weights.repository import RegimeWeightRepository

_adaptive_engine = AdaptiveWeightEngine()
_regime_repo = RegimeWeightRepository()


class RegimeWeightRequest(BaseModel):
    """Request to compute regime-adaptive weights."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    min_events_per_regime: int = 10


@router.post(
    "/regime-weights",
    summary="Compute regime-adaptive signal weights",
)
async def compute_regime_weights(request: RegimeWeightRequest):
    """
    Evaluate signal performance per market regime and compute
    adaptive weight multipliers for the current regime.
    """
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        from collections import defaultdict
        import pandas as pd

        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
        )
        engine = BacktestEngine()

        ohlcv_data = await engine._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date, config.end_date,
        )

        signals = engine._get_signals(config.signal_ids)
        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        events_by_signal = defaultdict(list)
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            for e in events:
                events_by_signal[e.signal_id].append(e)

        if not events_by_signal:
            return {"error": "No signal events generated", "profiles": []}

        adaptive_config = AdaptiveWeightConfig(
            forward_window=request.forward_window,
            min_events_per_regime=request.min_events_per_regime,
        )
        aw_engine = AdaptiveWeightEngine(adaptive_config)
        report = aw_engine.compute_adaptive_weights(
            benchmark_ohlcv, dict(events_by_signal), adaptive_config,
        )

        from uuid import uuid4
        run_id = str(uuid4())
        _regime_repo.save_profiles(run_id, report.profiles)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Regime weights failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/regime-weights/{run_id}",
    summary="Get regime weight results",
)
async def get_regime_weight_results(run_id: str):
    """Return stored regime-adaptive weight profiles."""
    profiles = _regime_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return profiles


@router.get(
    "/regime-weights/current",
    summary="Get current market regime",
)
async def get_current_regime():
    """Detect and return the current market regime + summary."""
    try:
        from src.engines.backtesting.engine import BacktestEngine
        import pandas as pd

        engine = BacktestEngine()
        ohlcv = await engine._fetch_historical_data(
            ["SPY"], None, None,
        )
        spy_ohlcv = ohlcv.get("SPY", pd.DataFrame())
        if spy_ohlcv.empty:
            return {"regime": "unknown", "message": "Insufficient data"}

        regime = _adaptive_engine.get_current_regime(spy_ohlcv)
        return {"regime": regime}
    except Exception as exc:
        logger.error("VALIDATION-API: Current regime detection failed — %s", exc)
        return {"regime": "unknown", "error": str(exc)}


# ─── Signal Ensemble Intelligence ───────────────────────────────────────────

from src.engines.signal_ensemble.engine import EnsembleIntelligenceEngine
from src.engines.signal_ensemble.models import EnsembleConfig
from src.engines.signal_ensemble.repository import EnsembleRepository

_ensemble_engine = EnsembleIntelligenceEngine()
_ensemble_repo = EnsembleRepository()


class SignalEnsembleRequest(BaseModel):
    """Request to run signal ensemble analysis."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    min_co_fires: int = 10
    max_combo_size: int = 3
    min_synergy: float = 0.10


@router.post(
    "/signal-ensemble",
    summary="Run signal ensemble analysis",
)
async def run_signal_ensemble(request: SignalEnsembleRequest):
    """
    Discover synergistic signal combinations with greater predictive
    power than individual signals.
    """
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        from collections import defaultdict
        import pandas as pd

        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
        )
        engine = BacktestEngine()

        ohlcv_data = await engine._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date, config.end_date,
        )

        signals = engine._get_signals(config.signal_ids)
        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        events_by_signal = defaultdict(list)
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            for e in events:
                events_by_signal[e.signal_id].append(e)

        if not events_by_signal:
            return {"error": "No signal events generated", "combinations": []}

        ens_config = EnsembleConfig(
            forward_window=request.forward_window,
            min_co_fires=request.min_co_fires,
            max_combo_size=request.max_combo_size,
            min_synergy=request.min_synergy,
        )
        ens_engine = EnsembleIntelligenceEngine(ens_config)
        report = ens_engine.analyze(dict(events_by_signal), ens_config)

        from uuid import uuid4
        run_id = str(uuid4())
        if report.top_ensembles:
            _ensemble_repo.save_ensembles(run_id, report.top_ensembles)
        elif report.combinations:
            synergistic = [c for c in report.combinations if c.synergy_score > 0]
            if synergistic:
                _ensemble_repo.save_ensembles(run_id, synergistic[:10])

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Signal ensemble failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/signal-ensemble/{run_id}",
    summary="Get signal ensemble results",
)
async def get_signal_ensemble_results(run_id: str):
    """Return stored ensemble analysis from a previous run."""
    ensembles = _ensemble_repo.get_ensembles(run_id)
    if not ensembles:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return ensembles


@router.get(
    "/signal-ensemble/top",
    summary="Get top active ensembles",
)
async def get_top_ensembles(limit: int = 10):
    """Return the top-scoring signal ensembles across all runs."""
    return _ensemble_repo.get_top_ensembles(limit)


# ─── Meta-Learning Engine ───────────────────────────────────────────────────

from src.engines.meta_learning.engine import MetaLearningEngine
from src.engines.meta_learning.models import MetaLearningConfig
from src.engines.meta_learning.repository import MetaLearningRepository

_meta_engine = MetaLearningEngine()
_meta_repo = MetaLearningRepository()


class MetaLearningRequest(BaseModel):
    """Request to run meta-learning analysis."""
    lookback_days: int = 90
    sharpe_decline_warn: float = 0.20
    sharpe_decline_critical: float = 0.40


class MetaApplyRequest(BaseModel):
    """Request to apply meta-learning recommendations."""
    run_id: str
    dry_run: bool = True


@router.post(
    "/meta-learning",
    summary="Run meta-learning analysis",
)
async def run_meta_learning(request: MetaLearningRequest):
    """
    Analyze signal and detector performance to generate
    meta-learning recommendations.
    """
    try:
        config = MetaLearningConfig(
            lookback_days=request.lookback_days,
            sharpe_decline_warn=request.sharpe_decline_warn,
            sharpe_decline_critical=request.sharpe_decline_critical,
        )
        engine = MetaLearningEngine(config)
        report = engine.run_analysis(config)

        from uuid import uuid4
        run_id = str(uuid4())
        if report.recommendations:
            _meta_repo.save_recommendations(run_id, report.recommendations)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Meta-learning failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/meta-learning/{run_id}",
    summary="Get meta-learning results",
)
async def get_meta_learning_results(run_id: str):
    """Return stored meta-learning recommendations."""
    recs = _meta_repo.get_recommendations(run_id)
    if not recs:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return recs


@router.post(
    "/meta-learning/apply",
    summary="Apply meta-learning recommendations",
)
async def apply_meta_learning(request: MetaApplyRequest):
    """Apply recommendations from a meta-learning run (dry-run supported)."""
    try:
        recs_dicts = _meta_repo.get_recommendations(request.run_id)
        if not recs_dicts:
            raise HTTPException(
                status_code=404,
                detail=f"No recommendations for run {request.run_id}",
            )

        from src.engines.meta_learning.models import MetaRecommendation
        recs = [MetaRecommendation(**r) for r in recs_dicts]

        engine = MetaLearningEngine()
        results = engine.apply_recommendations(recs, dry_run=request.dry_run)

        if not request.dry_run:
            _meta_repo.mark_applied(request.run_id)

        return {
            "run_id": request.run_id,
            "dry_run": request.dry_run,
            "actions": results,
            "applied_count": sum(1 for r in results if r.get("applied")),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("VALIDATION-API: Meta-learning apply failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Concept Drift Detection Engine ────────────────────────────────────────

from src.engines.concept_drift.engine import ConceptDriftEngine
from src.engines.concept_drift.models import DriftConfig
from src.engines.concept_drift.repository import ConceptDriftRepository

_drift_engine = ConceptDriftEngine()
_drift_repo = ConceptDriftRepository()


class ConceptDriftRequest(BaseModel):
    """Request to run concept drift analysis."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    ks_alpha: float = 0.05
    rolling_window_days: int = 60


@router.post(
    "/concept-drift",
    summary="Run concept drift detection",
)
async def run_concept_drift(request: ConceptDriftRequest):
    """
    Detect structural changes in market behavior that may
    invalidate historical signal patterns.
    """
    try:
        from src.engines.backtesting.engine import BacktestEngine
        from src.engines.backtesting.models import BacktestConfig
        from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
        from src.engines.backtesting.return_tracker import ReturnTracker
        from collections import defaultdict
        import pandas as pd

        config = BacktestConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            signal_ids=request.signal_ids,
        )
        engine = BacktestEngine()

        ohlcv_data = await engine._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date, config.end_date,
        )

        signals = engine._get_signals(config.signal_ids)
        evaluator = HistoricalEvaluator()
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        events_by_signal = defaultdict(list)
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            for e in events:
                events_by_signal[e.signal_id].append(e)

        if not events_by_signal:
            return {"error": "No signal events generated", "alerts": []}

        drift_config = DriftConfig(
            ks_alpha=request.ks_alpha,
            rolling_window_days=request.rolling_window_days,
        )
        drift_engine = ConceptDriftEngine(drift_config)
        report = drift_engine.analyze(
            dict(events_by_signal), drift_config, request.forward_window,
        )

        from uuid import uuid4
        run_id = str(uuid4())
        if report.alerts:
            active_alerts = [a for a in report.alerts if a.active_detectors > 0]
            if active_alerts:
                _drift_repo.save_alerts(run_id, active_alerts)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Concept drift failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/concept-drift/{run_id}",
    summary="Get concept drift results",
)
async def get_concept_drift_results(run_id: str):
    """Return stored drift alerts from a previous run."""
    alerts = _drift_repo.get_alerts(run_id)
    if not alerts:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return alerts


@router.get(
    "/concept-drift/active",
    summary="Get active drift alerts",
)
async def get_active_drift_alerts(min_severity: str = "info"):
    """Return currently active drift alerts above a minimum severity."""
    return _drift_repo.get_active_alerts(min_severity)


# ─── Online Learning Engine ────────────────────────────────────────────────

from src.engines.online_learning.engine import OnlineLearningEngine
from src.engines.online_learning.models import (
    OnlineLearningConfig,
    SignalObservation,
)
from src.engines.online_learning.repository import OnlineLearningRepository

_ol_engine = OnlineLearningEngine()
_ol_repo = OnlineLearningRepository()


class OnlineLearningRequest(BaseModel):
    """Request to process new observations."""
    observations: list[dict]  # [{signal_id, forward_return, benchmark_return}]
    learning_rate: float = 0.05
    max_change_per_step: float = 0.10


@router.post(
    "/online-learning",
    summary="Process new observations (online learning)",
)
async def process_online_learning(request: OnlineLearningRequest):
    """
    Process new signal observations and incrementally
    update weights using EMA + dampening.
    """
    try:
        config = OnlineLearningConfig(
            learning_rate=request.learning_rate,
            max_change_per_step=request.max_change_per_step,
        )

        observations = [
            SignalObservation(**obs) for obs in request.observations
        ]

        engine = OnlineLearningEngine(config)
        report = engine.process_observations(observations)

        from uuid import uuid4
        run_id = str(uuid4())
        if report.updates:
            _ol_repo.save_updates(run_id, report.updates)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Online learning failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/online-learning/{run_id}",
    summary="Get online learning update history",
)
async def get_online_learning_updates(run_id: str):
    """Return weight updates from a previous run."""
    updates = _ol_repo.get_updates(run_id)
    if not updates:
        raise HTTPException(status_code=404, detail=f"No updates for run {run_id}")
    return updates


@router.get(
    "/online-learning/state",
    summary="Get current online learning weight state",
)
async def get_online_learning_state():
    """Return the current weight state from online learning."""
    return _ol_repo.get_latest_weights()


# ─── Signal Discovery Engine ───────────────────────────────────────────────

from src.engines.signal_discovery.engine import SignalDiscoveryEngine
from src.engines.signal_discovery.models import DiscoveryConfig
from src.engines.signal_discovery.repository import SignalDiscoveryRepository

_disc_engine = SignalDiscoveryEngine()
_disc_repo = SignalDiscoveryRepository()


class SignalDiscoveryRequest(BaseModel):
    """Request to run signal discovery."""
    signal_values: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Pre-computed signal values per candidate_id",
    )
    forward_returns: list[float] = Field(
        default_factory=list,
        description="Forward returns aligned to signal values",
    )
    features: list[str] | None = None
    min_ic: float = 0.03
    min_hit_rate: float = 0.52
    min_stability: float = 0.50


@router.post(
    "/signal-discovery",
    summary="Run signal discovery pipeline",
)
async def run_signal_discovery(request: SignalDiscoveryRequest):
    """
    Discover new signals from feature combinations.
    Evaluates predictive power, stability, and filters spurious signals.
    """
    try:
        config = DiscoveryConfig(
            min_ic=request.min_ic,
            min_hit_rate=request.min_hit_rate,
            min_stability=request.min_stability,
        )
        engine = SignalDiscoveryEngine(config)
        report = engine.discover(
            request.signal_values,
            request.forward_returns,
            request.features,
        )

        from uuid import uuid4
        run_id = str(uuid4())
        promoted = [c for c in report.candidates if c.status == "promoted"]
        if promoted:
            _disc_repo.save_candidates(run_id, promoted)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Signal discovery failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/signal-discovery/{run_id}",
    summary="Get signal discovery results",
)
async def get_signal_discovery_results(run_id: str):
    """Return discovered candidates from a previous run."""
    candidates = _disc_repo.get_candidates(run_id)
    if not candidates:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return candidates


@router.get(
    "/signal-discovery/promoted",
    summary="Get promoted signals",
)
async def get_promoted_signals():
    """Return all promoted signal candidates across all runs."""
    return _disc_repo.get_promoted()


# ─── Allocation Learning Engine ────────────────────────────────────────────

from src.engines.allocation_learning.engine import AllocationLearningEngine
from src.engines.allocation_learning.models import (
    AllocationConfig,
    AllocationOutcome,
)
from src.engines.allocation_learning.reward import RewardComputer
from src.engines.allocation_learning.repository import AllocationLearningRepository

_alloc_engine = AllocationLearningEngine()
_alloc_repo = AllocationLearningRepository()
_alloc_reward = RewardComputer()


class AllocationLearningRequest(BaseModel):
    """Request to process allocation outcomes."""
    outcomes: list[dict]  # [{ticker, bucket_id, allocation_pct, forward_return, ...}]


@router.post(
    "/allocation-learning",
    summary="Record outcomes & update allocation learning",
)
async def process_allocation_learning(request: AllocationLearningRequest):
    """
    Process allocation outcomes and update the multi-armed
    bandit to learn optimal position sizing.
    """
    try:
        outcomes = [AllocationOutcome(**o) for o in request.outcomes]
        report = _alloc_engine.process_outcomes(outcomes)

        from uuid import uuid4
        run_id = str(uuid4())
        rewards = [_alloc_reward.compute(o) for o in outcomes]
        if outcomes:
            _alloc_repo.save_outcomes(run_id, outcomes, rewards)

        result = report.model_dump()
        result["run_id"] = run_id
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Allocation learning failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/allocation-learning/{run_id}",
    summary="Get allocation learning results",
)
async def get_allocation_learning_results(run_id: str):
    """Return outcomes from a previous run."""
    results = _alloc_repo.get_outcomes(run_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return results


@router.get(
    "/allocation-learning/recommend",
    summary="Get current sizing recommendation",
)
async def get_allocation_recommendation():
    """Return the current recommended position sizing bucket."""
    bucket_id, alloc_pct = _alloc_engine.recommend()
    states = _alloc_engine.get_states()
    return {
        "recommended_bucket": bucket_id,
        "recommended_allocation_pct": alloc_pct,
        "bucket_states": [s.model_dump() for s in states],
    }
