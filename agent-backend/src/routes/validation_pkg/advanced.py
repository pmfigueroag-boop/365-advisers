"""
src/routes/validation_pkg/advanced.py
─────────────────────────────────────────────────────────────────────────────
Advanced QVF endpoints: signal selection, regime weights, signal ensemble,
meta-learning, concept drift, online learning, signal discovery,
allocation learning.
"""

from __future__ import annotations

import logging
from datetime import date
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.routes.validation")

router = APIRouter(tags=["Quantitative Validation Framework"])


# ── Shared backtest data preparation ─────────────────────────────────────────

async def _prepare_events_by_signal(universe, start_date, end_date, signal_ids=None):
    """Shared helper: fetch data, evaluate signals, return events_by_signal dict."""
    from src.engines.backtesting.engine import BacktestEngine
    from src.engines.backtesting.models import BacktestConfig
    from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
    from src.engines.backtesting.return_tracker import ReturnTracker
    import pandas as pd

    config = BacktestConfig(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        signal_ids=signal_ids,
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

    return events_by_signal, ohlcv_data, benchmark_ohlcv, config


# ── Signal Selection & Redundancy ────────────────────────────────────────────

from src.engines.signal_selection.engine import RedundancyPruningEngine
from src.engines.signal_selection.models import RedundancyConfig
from src.engines.signal_selection.repository import SignalSelectionRepository

_selection_engine = RedundancyPruningEngine()
_selection_repo = SignalSelectionRepository()


class SignalSelectionRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    corr_threshold: float = 0.80
    auto_disable_threshold: float = 0.75


class ApplySelectionRequest(BaseModel):
    run_id: str
    auto_disable: bool = True


@router.post("/signal-selection", summary="Run signal redundancy analysis")
async def run_signal_selection(request: SignalSelectionRequest):
    try:
        events_by_signal, *_ = await _prepare_events_by_signal(
            request.universe, request.start_date, request.end_date, request.signal_ids,
        )
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
        result.pop("correlation_matrix", None)
        return result

    except Exception as exc:
        logger.error("VALIDATION-API: Signal selection failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/signal-selection/apply", summary="Apply redundancy recommendations")
async def apply_signal_selection(request: ApplySelectionRequest):
    profiles = _selection_repo.get_profiles(request.run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No results for run {request.run_id}")

    from src.engines.signal_selection.models import SignalRedundancyProfile, RedundancyClass, RedundancyReport
    engine = RedundancyPruningEngine()
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


@router.get("/signal-selection/{run_id}", summary="Get signal selection results")
async def get_signal_selection_results(run_id: str):
    profiles = _selection_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return profiles


@router.get("/signal-selection/signal/{signal_id}", summary="Get latest redundancy profile for a signal")
async def get_signal_redundancy_profile(signal_id: str):
    profile = _selection_repo.get_signal_profile(signal_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No redundancy profile found for signal {signal_id}")
    return profile


# ── Regime-Adaptive Weights ──────────────────────────────────────────────────

from src.engines.regime_weights.engine import AdaptiveWeightEngine
from src.engines.regime_weights.models import AdaptiveWeightConfig
from src.engines.regime_weights.repository import RegimeWeightRepository

_adaptive_engine = AdaptiveWeightEngine()
_regime_repo = RegimeWeightRepository()


class RegimeWeightRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    min_events_per_regime: int = 10


@router.post("/regime-weights", summary="Compute regime-adaptive signal weights")
async def compute_regime_weights(request: RegimeWeightRequest):
    try:
        events_by_signal, _, benchmark_ohlcv, _ = await _prepare_events_by_signal(
            request.universe, request.start_date, request.end_date, request.signal_ids,
        )
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


@router.get("/regime-weights/{run_id}", summary="Get regime weight results")
async def get_regime_weight_results(run_id: str):
    profiles = _regime_repo.get_profiles(run_id)
    if not profiles:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return profiles


@router.get("/regime-weights/current", summary="Get current market regime")
async def get_current_regime():
    try:
        from src.engines.backtesting.engine import BacktestEngine
        import pandas as pd
        engine = BacktestEngine()
        ohlcv = await engine._fetch_historical_data(["SPY"], None, None)
        spy_ohlcv = ohlcv.get("SPY", pd.DataFrame())
        if spy_ohlcv.empty:
            return {"regime": "unknown", "message": "Insufficient data"}
        regime = _adaptive_engine.get_current_regime(spy_ohlcv)
        return {"regime": regime}
    except Exception as exc:
        logger.error("VALIDATION-API: Current regime detection failed — %s", exc)
        return {"regime": "unknown", "error": str(exc)}


# ── Signal Ensemble ──────────────────────────────────────────────────────────

from src.engines.signal_ensemble.engine import EnsembleIntelligenceEngine
from src.engines.signal_ensemble.models import EnsembleConfig
from src.engines.signal_ensemble.repository import EnsembleRepository

_ensemble_engine = EnsembleIntelligenceEngine()
_ensemble_repo = EnsembleRepository()


class SignalEnsembleRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    min_co_fires: int = 10
    max_combo_size: int = 3
    min_synergy: float = 0.10


@router.post("/signal-ensemble", summary="Run signal ensemble analysis")
async def run_signal_ensemble(request: SignalEnsembleRequest):
    try:
        events_by_signal, *_ = await _prepare_events_by_signal(
            request.universe, request.start_date, request.end_date, request.signal_ids,
        )
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


@router.get("/signal-ensemble/{run_id}", summary="Get signal ensemble results")
async def get_signal_ensemble_results(run_id: str):
    ensembles = _ensemble_repo.get_ensembles(run_id)
    if not ensembles:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return ensembles


@router.get("/signal-ensemble/top", summary="Get top active ensembles")
async def get_top_ensembles(limit: int = 10):
    return _ensemble_repo.get_top_ensembles(limit)


# ── Meta-Learning ────────────────────────────────────────────────────────────

from src.engines.meta_learning.engine import MetaLearningEngine
from src.engines.meta_learning.models import MetaLearningConfig
from src.engines.meta_learning.repository import MetaLearningRepository

_meta_engine = MetaLearningEngine()
_meta_repo = MetaLearningRepository()


class MetaLearningRequest(BaseModel):
    lookback_days: int = 90
    sharpe_decline_warn: float = 0.20
    sharpe_decline_critical: float = 0.40


class MetaApplyRequest(BaseModel):
    run_id: str
    dry_run: bool = True


@router.post("/meta-learning", summary="Run meta-learning analysis")
async def run_meta_learning(request: MetaLearningRequest):
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


@router.get("/meta-learning/{run_id}", summary="Get meta-learning results")
async def get_meta_learning_results(run_id: str):
    recs = _meta_repo.get_recommendations(run_id)
    if not recs:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return recs


@router.post("/meta-learning/apply", summary="Apply meta-learning recommendations")
async def apply_meta_learning(request: MetaApplyRequest):
    try:
        recs_dicts = _meta_repo.get_recommendations(request.run_id)
        if not recs_dicts:
            raise HTTPException(status_code=404, detail=f"No recommendations for run {request.run_id}")

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


# ── Concept Drift ────────────────────────────────────────────────────────────

from src.engines.concept_drift.engine import ConceptDriftEngine
from src.engines.concept_drift.models import DriftConfig
from src.engines.concept_drift.repository import ConceptDriftRepository

_drift_engine = ConceptDriftEngine()
_drift_repo = ConceptDriftRepository()


class ConceptDriftRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    forward_window: int = 20
    ks_alpha: float = 0.05
    rolling_window_days: int = 60


@router.post("/concept-drift", summary="Run concept drift detection")
async def run_concept_drift(request: ConceptDriftRequest):
    try:
        events_by_signal, *_ = await _prepare_events_by_signal(
            request.universe, request.start_date, request.end_date, request.signal_ids,
        )
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


@router.get("/concept-drift/{run_id}", summary="Get concept drift results")
async def get_concept_drift_results(run_id: str):
    alerts = _drift_repo.get_alerts(run_id)
    if not alerts:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return alerts


@router.get("/concept-drift/active", summary="Get active drift alerts")
async def get_active_drift_alerts(min_severity: str = "info"):
    return _drift_repo.get_active_alerts(min_severity)


# ── Online Learning ──────────────────────────────────────────────────────────

from src.engines.online_learning.engine import OnlineLearningEngine
from src.engines.online_learning.models import OnlineLearningConfig, SignalObservation
from src.engines.online_learning.repository import OnlineLearningRepository

_ol_engine = OnlineLearningEngine()
_ol_repo = OnlineLearningRepository()


class OnlineLearningRequest(BaseModel):
    observations: list[dict]
    learning_rate: float = 0.05
    max_change_per_step: float = 0.10


@router.post("/online-learning", summary="Process new observations (online learning)")
async def process_online_learning(request: OnlineLearningRequest):
    try:
        config = OnlineLearningConfig(
            learning_rate=request.learning_rate,
            max_change_per_step=request.max_change_per_step,
        )
        observations = [SignalObservation(**obs) for obs in request.observations]
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


@router.get("/online-learning/{run_id}", summary="Get online learning update history")
async def get_online_learning_updates(run_id: str):
    updates = _ol_repo.get_updates(run_id)
    if not updates:
        raise HTTPException(status_code=404, detail=f"No updates for run {run_id}")
    return updates


@router.get("/online-learning/state", summary="Get current online learning weight state")
async def get_online_learning_state():
    return _ol_repo.get_latest_weights()


# ── Signal Discovery ─────────────────────────────────────────────────────────

from src.engines.signal_discovery.engine import SignalDiscoveryEngine
from src.engines.signal_discovery.models import DiscoveryConfig
from src.engines.signal_discovery.repository import SignalDiscoveryRepository

_disc_engine = SignalDiscoveryEngine()
_disc_repo = SignalDiscoveryRepository()


class SignalDiscoveryRequest(BaseModel):
    signal_values: dict[str, list[float]] = Field(default_factory=dict)
    forward_returns: list[float] = Field(default_factory=list)
    features: list[str] | None = None
    min_ic: float = 0.03
    min_hit_rate: float = 0.52
    min_stability: float = 0.50


@router.post("/signal-discovery", summary="Run signal discovery pipeline")
async def run_signal_discovery(request: SignalDiscoveryRequest):
    try:
        config = DiscoveryConfig(
            min_ic=request.min_ic,
            min_hit_rate=request.min_hit_rate,
            min_stability=request.min_stability,
        )
        engine = SignalDiscoveryEngine(config)
        report = engine.discover(
            request.signal_values, request.forward_returns, request.features,
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


@router.get("/signal-discovery/{run_id}", summary="Get signal discovery results")
async def get_signal_discovery_results(run_id: str):
    candidates = _disc_repo.get_candidates(run_id)
    if not candidates:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return candidates


@router.get("/signal-discovery/promoted", summary="Get promoted signals")
async def get_promoted_signals():
    return _disc_repo.get_promoted()


# ── Allocation Learning ──────────────────────────────────────────────────────

from src.engines.allocation_learning.engine import AllocationLearningEngine
from src.engines.allocation_learning.models import AllocationConfig, AllocationOutcome
from src.engines.allocation_learning.reward import RewardComputer
from src.engines.allocation_learning.repository import AllocationLearningRepository

_alloc_engine = AllocationLearningEngine()
_alloc_repo = AllocationLearningRepository()
_alloc_reward = RewardComputer()


class AllocationLearningRequest(BaseModel):
    outcomes: list[dict]


@router.post("/allocation-learning", summary="Record outcomes & update allocation learning")
async def process_allocation_learning(request: AllocationLearningRequest):
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


@router.get("/allocation-learning/{run_id}", summary="Get allocation learning results")
async def get_allocation_learning_results(run_id: str):
    results = _alloc_repo.get_outcomes(run_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    return results


@router.get("/allocation-learning/recommend", summary="Get current sizing recommendation")
async def get_allocation_recommendation():
    bucket_id, alloc_pct = _alloc_engine.recommend()
    states = _alloc_engine.get_states()
    return {
        "recommended_bucket": bucket_id,
        "recommended_allocation_pct": alloc_pct,
        "bucket_states": [s.model_dump() for s in states],
    }
