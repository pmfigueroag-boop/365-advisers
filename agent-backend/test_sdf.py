"""Quick integration test for Strategy Definition Framework."""
import sys
import os
import traceback

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_sdf.db")

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


# ── Imports ──
from src.engines.strategy.definition import (
    StrategyConfig, SignalComposition, ScoreThresholds,
    PortfolioRules, RebalanceConfig, EntryRule, ExitRule,
    RegimeAction, UniverseConfig, StrategyMetadata,
    LifecycleState, StrategyCategory, CompositionLogic,
    load_strategy_yaml, save_strategy_yaml,
)
print("[PASS] Imports OK")
passed += 1


def test_full_config():
    config = StrategyConfig(
        signals=SignalComposition(required_categories=["momentum", "quality"], composition_logic="all_required"),
        thresholds=ScoreThresholds(min_case_score=65),
        portfolio=PortfolioRules(max_positions=15, max_single_position=0.08),
        rebalance=RebalanceConfig(frequency="biweekly"),
        entry_rules=[EntryRule(field="case_score", operator="gte", value=75)],
        exit_rules=[ExitRule(rule_type="trailing_stop", params={"pct": 0.12})],
        regime_rules=[RegimeAction(regime="bull", action="full_exposure")],
        metadata=StrategyMetadata(category="multi_factor", benchmark="SPY"),
    )
    assert config.signals.required_categories == ["momentum", "quality"]
    assert config.portfolio.max_positions == 15
    return config

test("Full config creation", test_full_config)
config = test_full_config()  # keep for later tests


def test_json_roundtrip():
    j = config.model_dump_json()
    c2 = StrategyConfig.model_validate_json(j)
    assert c2.signals.required_categories == ["momentum", "quality"]
    assert c2.thresholds.min_case_score == 65

test("JSON round-trip", test_json_roundtrip)


def test_backward_compat():
    legacy = StrategyConfig(
        signal_filters={"required_categories": ["momentum"], "min_signal_strength": 2.0, "min_confidence": "high"},
        score_filters={"min_case_score": 70, "min_uos": 5.0},
        portfolio_rules={"max_positions": 10, "sizing_method": "equal", "rebalance_frequency": "monthly"},
    )
    assert legacy.signals.required_categories == ["momentum"], f"categories: {legacy.signals.required_categories}"
    assert legacy.signals.min_signal_strength == 2.0, f"strength: {legacy.signals.min_signal_strength}"
    assert legacy.thresholds.min_case_score == 70, f"case: {legacy.thresholds.min_case_score}"
    assert legacy.portfolio.max_positions == 10, f"positions: {legacy.portfolio.max_positions}"
    assert legacy.rebalance.frequency == "monthly", f"freq: {legacy.rebalance.frequency}"

test("Backward compatibility", test_backward_compat)


def test_merged_getters():
    legacy = StrategyConfig(
        signal_filters={"required_categories": ["momentum"], "min_signal_strength": 2.0},
        portfolio_rules={"max_positions": 10, "sizing_method": "equal"},
    )
    sf = legacy.get_signal_filters()
    assert sf["required_categories"] == ["momentum"], f"sf cats: {sf['required_categories']}"
    pf = legacy.get_portfolio_rules()
    assert pf["max_positions"] == 10, f"pf pos: {pf['max_positions']}"

test("Merged getters", test_merged_getters)


def test_yaml_load():
    data = load_strategy_yaml("strategies/momentum/momentum_quality_v2.yaml")
    assert data["name"] == "Momentum Quality v2", f"name: {data.get('name')}"
    assert data["version"] == "2.0.0"
    assert len(data["entry_rules"]) == 4

test("YAML load", test_yaml_load)


def test_yaml_to_config():
    data = load_strategy_yaml("strategies/momentum/momentum_quality_v2.yaml")
    kw = {k: v for k, v in data.items() if k not in ("name", "description", "version")}
    cfg = StrategyConfig(**kw)
    assert cfg.signals.composition_logic == "all_required"
    assert cfg.portfolio.max_positions == 15

test("YAML -> StrategyConfig", test_yaml_to_config)


def test_enums():
    assert StrategyCategory.MOMENTUM.value == "momentum"
    assert LifecycleState.PAPER.value == "paper"
    assert CompositionLogic.ALL_REQUIRED.value == "all_required"

test("Enums", test_enums)


def test_composer():
    from src.engines.strategy.composer import StrategyComposer
    sigs = [
        {"ticker": "AAPL", "category": "momentum", "strength": "strong", "confidence": 0.8, "signal_id": "golden_cross"},
        {"ticker": "AAPL", "category": "quality", "strength": "moderate", "confidence": 0.6, "signal_id": "roic"},
        {"ticker": "MSFT", "category": "momentum", "strength": "strong", "confidence": 0.9, "signal_id": "macd"},
        {"ticker": "MSFT", "category": "quality", "strength": "strong", "confidence": 0.7, "signal_id": "q1"},
    ]
    r = StrategyComposer.compose(config.model_dump(), sigs, {"AAPL": 7.5, "MSFT": 8.0})
    assert r["composition_logic"] == "all_required"
    assert r["selected_positions"] >= 1, f"positions: {r['selected_positions']}"

test("Composer", test_composer)


def test_templates():
    from src.engines.strategy.registry import StrategyRegistry
    reg = StrategyRegistry()
    templates = reg.get_predefined()
    assert len(templates) == 7, f"templates: {len(templates)}"
    cats = {t["config"]["metadata"]["category"] for t in templates}
    assert len(cats) >= 5, f"categories: {cats}"

test("Templates", test_templates)


def test_yaml_roundtrip():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        tmp = f.name
    try:
        save_strategy_yaml(config, tmp, name="Test Strategy", version="1.0.0")
        data = load_strategy_yaml(tmp)
        assert data["name"] == "Test Strategy"
        cfg = StrategyConfig(**{k: v for k, v in data.items() if k not in ("name", "description", "version")})
        assert cfg.signals.required_categories == ["momentum", "quality"]
    finally:
        os.unlink(tmp)

test("YAML save/load round-trip", test_yaml_roundtrip)


def test_lifecycle_transitions():
    from src.engines.strategy.registry import _LIFECYCLE_TRANSITIONS
    assert "research" in _LIFECYCLE_TRANSITIONS["draft"]
    assert "backtested" in _LIFECYCLE_TRANSITIONS["research"]
    assert "live" in _LIFECYCLE_TRANSITIONS["paper"]
    assert _LIFECYCLE_TRANSITIONS["retired"] == []

test("Lifecycle transitions map", test_lifecycle_transitions)


print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
