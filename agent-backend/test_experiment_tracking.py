"""Integration test for Research Experiment Tracking System."""
import sys
import os
import traceback

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_et.db")

passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"[PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        traceback.print_exc()
        failed += 1


# ── Tests ──

def test_imports():
    from src.engines.experiment_tracking import (
        ResearchExperimentTracker, ExperimentComparator,
        ReproducibilityEngine, ExperimentHook,
        ResearchExperimentType, compute_data_fingerprint,
    )

test("Imports", test_imports)


from src.engines.experiment_tracking.tracker import ResearchExperimentTracker
from src.engines.experiment_tracking.comparator import ExperimentComparator
from src.engines.experiment_tracking.reproducibility import ReproducibilityEngine
from src.engines.experiment_tracking.hooks import ExperimentHook
from src.engines.experiment_tracking.models import (
    ResearchExperimentCreate, ResearchExperimentType, compute_data_fingerprint,
)

# Clear state between tests
ResearchExperimentTracker.clear()


def test_register_experiment():
    ResearchExperimentTracker.clear()
    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Momentum Backtest v1",
        description="Testing momentum strategy",
        hypothesis="Momentum signals with quality filter outperform naive momentum",
        tags=["momentum", "v1", "quality"],
        author="researcher_1",
        config_snapshot={"strategy": "momentum_quality", "min_case_score": 60},
        data_fingerprint="abc123",
    ))
    assert exp_id, "No experiment ID returned"

    exp = ResearchExperimentTracker.get(exp_id)
    assert exp is not None
    assert exp.name == "Momentum Backtest v1"
    assert exp.experiment_type == "strategy_research"
    assert exp.status == "pending"
    assert "momentum" in exp.tags
    assert exp.data_fingerprint == "abc123"

test("Register experiment", test_register_experiment)


def test_lifecycle():
    ResearchExperimentTracker.clear()
    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.SIGNAL_RESEARCH,
        name="IC Test",
    ))

    exp = ResearchExperimentTracker.get(exp_id)
    assert exp.status == "pending"

    ResearchExperimentTracker.mark_running(exp_id)
    exp = ResearchExperimentTracker.get(exp_id)
    assert exp.status == "running"

    ResearchExperimentTracker.mark_completed(exp_id, metrics={"sharpe_ratio": 1.5, "cagr": 0.18})
    exp = ResearchExperimentTracker.get(exp_id)
    assert exp.status == "completed"
    assert exp.metrics["sharpe_ratio"] == 1.5

test("Lifecycle (pending → running → completed)", test_lifecycle)


def test_failed_lifecycle():
    ResearchExperimentTracker.clear()
    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.BACKTEST,
        name="Failed Test",
    ))
    ResearchExperimentTracker.mark_running(exp_id)
    ResearchExperimentTracker.mark_failed(exp_id, "Division by zero")

    exp = ResearchExperimentTracker.get(exp_id)
    assert exp.status == "failed"

test("Failed lifecycle", test_failed_lifecycle)


def test_tags():
    ResearchExperimentTracker.clear()
    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Tagging Test",
        tags=["initial"],
    ))

    ResearchExperimentTracker.tag_experiment(exp_id, ["new_tag", "v2"])
    exp = ResearchExperimentTracker.get(exp_id)
    assert "initial" in exp.tags
    assert "new_tag" in exp.tags
    assert "v2" in exp.tags

    ResearchExperimentTracker.untag_experiment(exp_id, ["initial"])
    exp = ResearchExperimentTracker.get(exp_id)
    assert "initial" not in exp.tags
    assert "new_tag" in exp.tags

test("Tag management", test_tags)


def test_filter_by_type():
    ResearchExperimentTracker.clear()
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.SIGNAL_RESEARCH, name="Signal 1",
    ))
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH, name="Strategy 1",
    ))
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.SIGNAL_RESEARCH, name="Signal 2",
    ))

    signals = ResearchExperimentTracker.list_experiments(experiment_type="signal_research")
    assert len(signals) == 2

    strategies = ResearchExperimentTracker.list_experiments(experiment_type="strategy_research")
    assert len(strategies) == 1

test("Filter by experiment type", test_filter_by_type)


def test_filter_by_tags():
    ResearchExperimentTracker.clear()
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Momentum v1", tags=["momentum", "v1"],
    ))
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Value v1", tags=["value", "v1"],
    ))
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Momentum v2", tags=["momentum", "v2"],
    ))

    momentum = ResearchExperimentTracker.list_experiments(tags=["momentum"])
    assert len(momentum) == 2

    v1 = ResearchExperimentTracker.list_experiments(tags=["v1"])
    assert len(v1) == 2

    momentum_v1 = ResearchExperimentTracker.list_experiments(tags=["momentum", "v1"])
    assert len(momentum_v1) == 1

test("Filter by tags", test_filter_by_tags)


def test_search():
    ResearchExperimentTracker.clear()
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Momentum Quality Test",
        description="Testing momentum with quality filter",
    ))
    ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.SIGNAL_RESEARCH,
        name="Value Signal Test",
        hypothesis="Value signals improve in bear markets",
    ))

    results = ResearchExperimentTracker.list_experiments(search="momentum")
    assert len(results) == 1
    assert results[0].name == "Momentum Quality Test"

    results = ResearchExperimentTracker.list_experiments(search="bear markets")
    assert len(results) == 1

test("Full-text search", test_search)


def test_lineage():
    ResearchExperimentTracker.clear()
    parent_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.SIGNAL_RESEARCH,
        name="Signal Discovery",
    ))
    child_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Strategy from Signal",
        parent_experiment_id=parent_id,
    ))

    lineage = ResearchExperimentTracker.get_lineage(child_id)
    assert len(lineage["parents"]) == 1
    assert lineage["parents"][0]["experiment_id"] == parent_id

    parent_lineage = ResearchExperimentTracker.get_lineage(parent_id)
    assert len(parent_lineage["children"]) == 1
    assert parent_lineage["children"][0]["experiment_id"] == child_id

test("Lineage (parent ↔ child)", test_lineage)


def test_full_ancestry():
    ResearchExperimentTracker.clear()
    id1 = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.SIGNAL_RESEARCH, name="Signal",
    ))
    id2 = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH, name="Strategy",
        parent_experiment_id=id1,
    ))
    id3 = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.PORTFOLIO_RESEARCH, name="Portfolio",
        parent_experiment_id=id2,
    ))

    ancestry = ResearchExperimentTracker.get_full_ancestry(id3)
    assert len(ancestry) == 3  # portfolio → strategy → signal
    assert ancestry[0]["name"] == "Portfolio"
    assert ancestry[2]["name"] == "Signal"

test("Full ancestry chain (signal → strategy → portfolio)", test_full_ancestry)


def test_experiment_comparison():
    ResearchExperimentTracker.clear()
    id1 = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Momentum v1",
        config_snapshot={"min_case_score": 60, "signals": "momentum"},
    ))
    ResearchExperimentTracker.mark_completed(id1, metrics={
        "sharpe_ratio": 0.82, "cagr": 0.15, "max_drawdown": -0.12,
    })

    id2 = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Momentum v2",
        config_snapshot={"min_case_score": 70, "signals": "momentum+quality"},
    ))
    ResearchExperimentTracker.mark_completed(id2, metrics={
        "sharpe_ratio": 1.05, "cagr": 0.22, "max_drawdown": -0.08,
    })

    exp1 = ResearchExperimentTracker.get(id1)
    exp2 = ResearchExperimentTracker.get(id2)

    comparison = ExperimentComparator.compare([exp1.model_dump(), exp2.model_dump()])
    assert comparison["experiment_count"] == 2
    assert "metrics_comparison" in comparison
    assert "rankings" in comparison
    assert "config_diff" in comparison
    assert "verdict" in comparison

    # V2 should be ranked higher
    assert comparison["rankings"]["best_sharpe"] == id2

test("Experiment comparison", test_experiment_comparison)


def test_data_fingerprint():
    data1 = {"prices": {"AAPL": {"2025-01-01": 150}}, "signals": []}
    data2 = {"prices": {"AAPL": {"2025-01-01": 150}}, "signals": []}
    data3 = {"prices": {"AAPL": {"2025-01-01": 151}}, "signals": []}

    fp1 = compute_data_fingerprint(data1)
    fp2 = compute_data_fingerprint(data2)
    fp3 = compute_data_fingerprint(data3)

    assert fp1 == fp2, "Same data should produce same fingerprint"
    assert fp1 != fp3, "Different data should produce different fingerprint"
    assert len(fp1) == 16, "Fingerprint should be 16 chars"

test("Data fingerprint", test_data_fingerprint)


def test_reproducibility_dry_run():
    ResearchExperimentTracker.clear()
    data = {"prices": {"AAPL": {"2025-01-01": 150}}}
    fp = compute_data_fingerprint(data)

    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Reproducible Test",
        config_snapshot={"min_score": 60},
        data_fingerprint=fp,
    ))
    ResearchExperimentTracker.mark_completed(exp_id, metrics={"sharpe_ratio": 1.0})

    result = ReproducibilityEngine.reproduce(exp_id, data)
    assert result.data_fingerprint_match is True
    assert result.config_match is True
    assert result.reproduction_status == "dry_run"

test("Reproducibility dry run", test_reproducibility_dry_run)


def test_reproducibility_with_run():
    ResearchExperimentTracker.clear()
    data = {"prices": {"AAPL": {"2025-01-01": 150}}}
    fp = compute_data_fingerprint(data)

    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Full Reproduction Test",
        config_snapshot={"min_score": 60},
        data_fingerprint=fp,
    ))
    ResearchExperimentTracker.mark_completed(exp_id, metrics={"sharpe_ratio": 1.0, "cagr": 0.15})

    def mock_run(config, data):
        return {"metrics": {"sharpe_ratio": 1.0, "cagr": 0.15}}

    result = ReproducibilityEngine.reproduce(exp_id, data, run_fn=mock_run)
    assert result.data_fingerprint_match is True
    assert result.reproduction_status == "exact_match"
    assert result.metric_drift.get("sharpe_ratio", 999) == 0

test("Reproducibility with execution (exact match)", test_reproducibility_with_run)


def test_experiment_hook():
    ResearchExperimentTracker.clear()
    hook = ExperimentHook.start(
        experiment_type="strategy_research",
        name="Hook Test",
        config={"strategy": "test"},
        tags=["test", "hook"],
    )

    exp = ResearchExperimentTracker.get(hook.experiment_id)
    assert exp.status == "running"
    assert "hook" in exp.tags

    hook.attach("metrics", {"sharpe": 1.2})
    hook.complete({"sharpe_ratio": 1.2, "cagr": 0.18})

    exp = ResearchExperimentTracker.get(hook.experiment_id)
    assert exp.status == "completed"
    assert exp.metrics["sharpe_ratio"] == 1.2

test("Experiment hook (start → attach → complete)", test_experiment_hook)


def test_check_reproducibility():
    ResearchExperimentTracker.clear()
    data = {"prices": {"AAPL": {"2025-01-01": 150}}}
    fp = compute_data_fingerprint(data)

    exp_id = ResearchExperimentTracker.register(ResearchExperimentCreate(
        experiment_type=ResearchExperimentType.STRATEGY_RESEARCH,
        name="Check Test",
        config_snapshot={"min_score": 60},
        data_fingerprint=fp,
    ))
    ResearchExperimentTracker.mark_completed(exp_id, metrics={"sharpe": 1.0})

    check = ReproducibilityEngine.check_reproducibility(exp_id, data)
    assert check["reproducible"] is True
    assert check["has_config"] is True
    assert check["has_metrics"] is True

test("Reproducibility check", test_check_reproducibility)


# Summary
print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
