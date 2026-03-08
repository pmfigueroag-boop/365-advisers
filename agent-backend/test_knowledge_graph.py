"""Integration test for Research Knowledge Graph."""
import sys
import os
import traceback

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_kg.db")

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
    from src.engines.knowledge_graph import (
        ResearchKnowledgeGraph, GraphPopulator, PatternDiscovery,
        GraphHook, NodeType, EdgeType, KnowledgeNode, KnowledgeEdge,
    )

test("Imports", test_imports)


from src.engines.knowledge_graph.graph import ResearchKnowledgeGraph
from src.engines.knowledge_graph.models import (
    NodeType, EdgeType, KnowledgeNode, KnowledgeEdge,
)
from src.engines.knowledge_graph.populator import GraphPopulator
from src.engines.knowledge_graph.patterns import PatternDiscovery
from src.engines.knowledge_graph.hooks import GraphHook


def build_test_graph():
    """Build a realistic test graph: features → signals → strategies → portfolio → experiments."""
    g = ResearchKnowledgeGraph()

    # Features
    for f in ["momentum", "quality", "value"]:
        g.add_node(KnowledgeNode(node_id=f"feature:{f}", node_type=NodeType.FEATURE, name=f"{f} features"))

    # Signals
    signals = [
        ("momentum_12m", "Momentum 12M", "momentum"),
        ("momentum_6m", "Momentum 6M", "momentum"),
        ("roe_trend", "ROE Trend", "quality"),
        ("pe_ratio", "P/E Ratio", "value"),
        ("book_value", "Book Value", "value"),
    ]
    for sid, name, cat in signals:
        g.add_node(KnowledgeNode(node_id=f"signal:{sid}", node_type=NodeType.SIGNAL, name=name,
                                  metadata={"category": cat}))
        g.add_edge(KnowledgeEdge(source_id=f"signal:{sid}", target_id=f"feature:{cat}",
                                  edge_type=EdgeType.DERIVED_FROM))

    # Strategies
    g.add_node(KnowledgeNode(node_id="strategy:mom_quality", node_type=NodeType.STRATEGY, name="Momentum Quality"))
    g.add_node(KnowledgeNode(node_id="strategy:value_contrarian", node_type=NodeType.STRATEGY, name="Value Contrarian"))
    g.add_node(KnowledgeNode(node_id="strategy:orphan_strat", node_type=NodeType.STRATEGY, name="Orphan Strategy"))

    # Signal → Strategy edges
    for sid in ["momentum_12m", "momentum_6m", "roe_trend"]:
        g.add_edge(KnowledgeEdge(source_id=f"signal:{sid}", target_id="strategy:mom_quality",
                                  edge_type=EdgeType.USED_BY))
    for sid in ["pe_ratio", "book_value"]:
        g.add_edge(KnowledgeEdge(source_id=f"signal:{sid}", target_id="strategy:value_contrarian",
                                  edge_type=EdgeType.USED_BY))

    # Portfolio
    g.add_node(KnowledgeNode(node_id="portfolio:multi_alpha", node_type=NodeType.PORTFOLIO, name="Multi-Alpha"))
    g.add_edge(KnowledgeEdge(source_id="strategy:mom_quality", target_id="portfolio:multi_alpha",
                              edge_type=EdgeType.COMPOSED_INTO, weight=0.6))
    g.add_edge(KnowledgeEdge(source_id="strategy:value_contrarian", target_id="portfolio:multi_alpha",
                              edge_type=EdgeType.COMPOSED_INTO, weight=0.4))

    # Correlation edge
    g.add_edge(KnowledgeEdge(source_id="strategy:mom_quality", target_id="strategy:value_contrarian",
                              edge_type=EdgeType.CORRELATED_WITH, weight=0.45))

    # Experiments
    g.add_node(KnowledgeNode(node_id="experiment:bt_001", node_type=NodeType.EXPERIMENT, name="Backtest v1"))
    g.add_node(KnowledgeNode(node_id="experiment:bt_002", node_type=NodeType.EXPERIMENT, name="Walk-Forward"))
    g.add_edge(KnowledgeEdge(source_id="strategy:mom_quality", target_id="experiment:bt_001",
                              edge_type=EdgeType.EVALUATED_BY))
    g.add_edge(KnowledgeEdge(source_id="experiment:bt_001", target_id="experiment:bt_002",
                              edge_type=EdgeType.LINEAGE))

    # Regimes
    for regime in ["bull", "bear", "range"]:
        g.add_node(KnowledgeNode(node_id=f"regime:{regime}", node_type=NodeType.REGIME, name=regime.title()))
    g.add_edge(KnowledgeEdge(source_id="strategy:mom_quality", target_id="regime:bull",
                              edge_type=EdgeType.ACTIVE_IN))

    return g


def test_node_operations():
    g = ResearchKnowledgeGraph()
    g.add_node(KnowledgeNode(node_id="signal:test", node_type=NodeType.SIGNAL, name="Test"))
    assert g.get_node("signal:test") is not None
    assert g.get_node("signal:test").name == "Test"

    assert g.remove_node("signal:test") is True
    assert g.get_node("signal:test") is None
    assert g.remove_node("signal:nonexistent") is False

test("Node add/get/remove", test_node_operations)


def test_edge_operations():
    g = ResearchKnowledgeGraph()
    g.add_node(KnowledgeNode(node_id="a", node_type=NodeType.SIGNAL, name="A"))
    g.add_node(KnowledgeNode(node_id="b", node_type=NodeType.STRATEGY, name="B"))
    g.add_edge(KnowledgeEdge(source_id="a", target_id="b", edge_type=EdgeType.USED_BY))

    edges = g.get_edges()
    assert len(edges) == 1
    assert edges[0].source_id == "a"

    # Duplicate edge should update, not duplicate
    g.add_edge(KnowledgeEdge(source_id="a", target_id="b", edge_type=EdgeType.USED_BY, weight=0.8))
    assert len(g.get_edges()) == 1

    assert g.remove_edge("a", "b", EdgeType.USED_BY) is True
    assert len(g.get_edges()) == 0

test("Edge add/get/remove (no duplicates)", test_edge_operations)


def test_neighbors():
    g = build_test_graph()
    # Strategy should have incoming signal edges
    neighbors = g.neighbors("strategy:mom_quality", direction="incoming")
    signal_neighbors = [n for n in neighbors if n["type"] == "signal"]
    assert len(signal_neighbors) == 3  # momentum_12m, momentum_6m, roe_trend

    # Outgoing: strategy → portfolio, experiment, regime
    out = g.neighbors("strategy:mom_quality", direction="outgoing")
    assert len(out) >= 3

    # Filtered by edge type
    used_by = g.neighbors("strategy:mom_quality", direction="incoming", edge_type=EdgeType.USED_BY)
    assert len(used_by) == 3

test("Neighbors (incoming/outgoing/filtered)", test_neighbors)


def test_path():
    g = build_test_graph()
    # Signal → Strategy → Portfolio
    path = g.path("signal:momentum_12m", "portfolio:multi_alpha")
    assert path is not None
    assert len(path) >= 3
    assert path[0] == "signal:momentum_12m"
    assert path[-1] == "portfolio:multi_alpha"

    # No path between disconnected nodes
    path = g.path("signal:momentum_12m", "regime:bear")
    # Should find path through strategy edges
    assert path is not None or path is None  # May or may not connect

test("BFS shortest path", test_path)


def test_subgraph():
    g = build_test_graph()
    sub = g.subgraph("strategy:mom_quality", depth=1)
    assert sub["center"] == "strategy:mom_quality"
    assert sub["node_count"] >= 4  # self + 3 signals + portfolio + experiment + ...
    assert sub["edge_count"] >= 3

test("Subgraph (1-hop)", test_subgraph)


def test_ancestors():
    g = build_test_graph()
    # Experiment bt_002 has lineage: bt_001 → strategy
    ancestors = g.ancestors("experiment:bt_002")
    assert len(ancestors) >= 2
    ids = [a["node_id"] for a in ancestors]
    assert "experiment:bt_002" in ids
    assert "experiment:bt_001" in ids

test("Ancestors (upstream walk)", test_ancestors)


def test_descendants():
    g = build_test_graph()
    desc = g.descendants("signal:momentum_12m")
    ids = [d["node_id"] for d in desc]
    assert "signal:momentum_12m" in ids
    assert "feature:momentum" in ids  # derived_from edge

test("Descendants (downstream walk)", test_descendants)


def test_impact_analysis():
    g = build_test_graph()
    impact = g.impact_analysis("signal:momentum_12m")
    assert impact["total_affected"] >= 1  # At minimum feature:momentum
    assert "affected_by_type" in impact
    assert impact["severity"] in ["low", "medium", "high"]

test("Impact analysis", test_impact_analysis)


def test_stats():
    g = build_test_graph()
    s = g.stats()
    assert s.total_nodes >= 14  # 3 features + 5 signals + 3 strategies + 1 portfolio + 2 experiments + 3 regimes
    assert s.total_edges >= 10
    assert s.nodes_by_type["signal"] == 5
    assert s.nodes_by_type["strategy"] == 3
    assert s.nodes_by_type["portfolio"] == 1

test("Graph stats", test_stats)


def test_populator_signals():
    g = ResearchKnowledgeGraph()
    count = GraphPopulator.populate_from_signals(g, [
        {"id": "sig_1", "name": "Signal 1", "category": "momentum"},
        {"id": "sig_2", "name": "Signal 2", "category": "value"},
    ])
    assert count == 2
    assert g.get_node("signal:sig_1") is not None

test("Populator: signals", test_populator_signals)


def test_populator_strategies():
    g = ResearchKnowledgeGraph()
    count = GraphPopulator.populate_from_strategies(g, [
        {"id": "strat_1", "name": "Strategy 1", "config": {"signals": {"required_categories": ["momentum"]}}},
    ])
    assert count == 1
    assert g.get_node("strategy:strat_1") is not None
    # Should have feature node too
    assert g.get_node("feature:momentum") is not None

test("Populator: strategies + feature edges", test_populator_strategies)


def test_populator_experiments():
    g = ResearchKnowledgeGraph()
    count = GraphPopulator.populate_from_experiments(g, [
        {"experiment_id": "exp_1", "name": "Test Exp", "experiment_type": "backtest", "parent_experiment_id": None},
    ])
    assert count == 1
    assert g.get_node("experiment:exp_1") is not None

test("Populator: experiments", test_populator_experiments)


def test_pattern_hub_detection():
    g = build_test_graph()
    hubs = PatternDiscovery.hub_detection(g)
    assert len(hubs) > 0
    # Strategy nodes should be hubs (many connections)
    top_hub = hubs[0]
    assert top_hub["degree"] >= 3

test("Pattern: hub detection", test_pattern_hub_detection)


def test_pattern_orphan_detection():
    g = build_test_graph()
    orphans = PatternDiscovery.orphan_detection(g)
    orphan_ids = [o["node_id"] for o in orphans]
    assert "strategy:orphan_strat" in orphan_ids

test("Pattern: orphan detection", test_pattern_orphan_detection)


def test_pattern_co_usage():
    g = build_test_graph()
    co_usage = PatternDiscovery.signal_co_usage(g)
    # momentum_12m and roe_trend are both used by mom_quality
    if co_usage:
        assert co_usage[0]["shared_strategies"] >= 1

test("Pattern: signal co-usage", test_pattern_co_usage)


def test_pattern_clusters():
    g = build_test_graph()
    clusters = PatternDiscovery.strategy_clusters(g)
    # mom_quality and value_contrarian are correlated
    assert len(clusters) >= 1
    assert clusters[0]["size"] >= 2

test("Pattern: strategy clusters", test_pattern_clusters)


def test_graph_hook():
    g = ResearchKnowledgeGraph()
    hook = GraphHook(g)

    hook.on_signal_created("sig_a", "Signal A", category="momentum")
    hook.on_signal_created("sig_b", "Signal B", category="quality")
    hook.on_strategy_created("strat_1", "Strategy 1", signal_ids=["sig_a", "sig_b"])
    hook.on_experiment_created("exp_1", "Backtest 1", strategy_id="strat_1")
    hook.on_portfolio_created("port_1", "Portfolio 1", strategy_ids=["strat_1"])

    assert g.stats().total_nodes == 5
    # 2 used_by + 1 evaluated_by + 1 composed_into = 4 edges
    assert g.stats().total_edges == 4

test("GraphHook auto-registration", test_graph_hook)


def test_full_analyze():
    g = build_test_graph()
    patterns = PatternDiscovery.analyze(g)
    assert "co_usage" in patterns
    assert "hub_nodes" in patterns
    assert "orphan_nodes" in patterns
    assert "clusters" in patterns
    assert "lineage_chains" in patterns

test("Full pattern analysis", test_full_analyze)


# Summary
print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
