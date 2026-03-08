"""Integration test for Strategy Marketplace."""
import sys
import os
import traceback

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_mp.db")

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
    from src.engines.strategy_marketplace import (
        StrategyMarketplace, MarketplaceRanking,
        PublishedStrategy, MarketplaceSearchParams,
    )

test("Imports", test_imports)


from src.engines.strategy_marketplace.engine import StrategyMarketplace
from src.engines.strategy_marketplace.ranking import MarketplaceRanking
from src.engines.strategy_marketplace.models import MarketplaceSearchParams


def _publish_test_strategies():
    """Publish a set of test strategies for testing."""
    StrategyMarketplace.clear()

    strategies = [
        {
            "strategy_id": "momentum_quality",
            "name": "Momentum Quality",
            "author": "researcher_1",
            "description": "Momentum strategy with quality filter",
            "strategy_type": "momentum",
            "signals_used": ["momentum_12m", "roe_trend"],
            "signal_categories": ["momentum", "quality"],
            "tags": ["momentum", "quality", "v2"],
            "regime_compatibility": ["bull", "range"],
            "risk_level": "medium",
            "backtest_summary": {"sharpe_ratio": 1.45, "cagr": 0.22, "max_drawdown": -0.12, "turnover": 1.8, "cost_drag_bps": 35},
        },
        {
            "strategy_id": "value_contrarian",
            "name": "Value Contrarian",
            "author": "researcher_2",
            "description": "Deep value contrarian strategy",
            "strategy_type": "value",
            "signals_used": ["pe_ratio", "book_value"],
            "signal_categories": ["value"],
            "tags": ["value", "contrarian"],
            "regime_compatibility": ["bear", "range"],
            "risk_level": "high",
            "backtest_summary": {"sharpe_ratio": 0.92, "cagr": 0.18, "max_drawdown": -0.25, "turnover": 0.5, "cost_drag_bps": 15},
        },
        {
            "strategy_id": "low_vol",
            "name": "Low Volatility",
            "author": "researcher_1",
            "description": "Minimum volatility defensive strategy",
            "strategy_type": "low_vol",
            "signals_used": ["realized_vol"],
            "signal_categories": ["volatility"],
            "tags": ["defensive", "low_vol"],
            "regime_compatibility": ["bear"],
            "risk_level": "low",
            "backtest_summary": {"sharpe_ratio": 0.75, "cagr": 0.08, "max_drawdown": -0.06, "turnover": 0.3, "cost_drag_bps": 10},
        },
    ]

    listings = []
    for s in strategies:
        listing = StrategyMarketplace.publish(**s, lifecycle_state="backtested")
        listings.append(listing)

    return listings


def test_publish():
    StrategyMarketplace.clear()
    listing = StrategyMarketplace.publish(
        strategy_id="test_strat", name="Test Strategy",
        lifecycle_state="backtested",
    )
    assert isinstance(listing, object)
    assert hasattr(listing, "listing_id")
    assert listing.name == "Test Strategy"

test("Publish strategy", test_publish)


def test_lifecycle_gate():
    StrategyMarketplace.clear()
    result = StrategyMarketplace.publish(
        strategy_id="draft_strat", name="Draft",
        lifecycle_state="research",
    )
    assert isinstance(result, dict)
    assert "error" in result

test("Lifecycle gate (reject research state)", test_lifecycle_gate)


def test_lifecycle_gate_valid():
    StrategyMarketplace.clear()
    for state in ["backtested", "validated", "paper", "live"]:
        result = StrategyMarketplace.publish(
            strategy_id=f"strat_{state}", name=f"Strategy ({state})",
            lifecycle_state=state,
        )
        assert hasattr(result, "listing_id"), f"Should accept state: {state}"

test("Lifecycle gate (accept valid states)", test_lifecycle_gate_valid)


def test_search_all():
    listings = _publish_test_strategies()
    results = StrategyMarketplace.search()
    assert len(results) == 3

test("Search all", test_search_all)


def test_search_text():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(search="momentum"))
    assert len(results) == 1
    assert results[0].name == "Momentum Quality"

test("Search by text", test_search_text)


def test_filter_type():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(strategy_type="value"))
    assert len(results) == 1
    assert results[0].name == "Value Contrarian"

test("Filter by strategy type", test_filter_type)


def test_filter_risk():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(risk_level="low"))
    assert len(results) == 1
    assert results[0].name == "Low Volatility"

test("Filter by risk level", test_filter_risk)


def test_filter_sharpe():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(min_sharpe=1.0))
    assert len(results) == 1
    assert results[0].name == "Momentum Quality"

test("Filter by min Sharpe", test_filter_sharpe)


def test_filter_regime():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(regime="bear"))
    assert len(results) == 2  # value_contrarian + low_vol

test("Filter by regime", test_filter_regime)


def test_filter_signals():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(signals=["pe_ratio"]))
    assert len(results) == 1
    assert results[0].name == "Value Contrarian"

test("Filter by signals", test_filter_signals)


def test_filter_tags():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(tags=["momentum"]))
    assert len(results) == 1

test("Filter by tags", test_filter_tags)


def test_sort_sharpe():
    _publish_test_strategies()
    results = StrategyMarketplace.search(MarketplaceSearchParams(sort_by="sharpe"))
    assert results[0].backtest_summary["sharpe_ratio"] >= results[1].backtest_summary["sharpe_ratio"]

test("Sort by Sharpe", test_sort_sharpe)


def test_import():
    listings = _publish_test_strategies()
    lid = listings[0].listing_id
    result = StrategyMarketplace.import_strategy(lid, "My Custom Momentum")
    assert result["cloned_name"] == "My Custom Momentum"
    assert result["download_count"] == 1

    # Import again
    result2 = StrategyMarketplace.import_strategy(lid)
    assert result2["download_count"] == 2

test("Import strategy (download tracking)", test_import)


def test_delist():
    listings = _publish_test_strategies()
    lid = listings[0].listing_id
    assert StrategyMarketplace.delist(lid) is True

    # Delisted should not appear in search
    results = StrategyMarketplace.search()
    assert len(results) == 2

test("Delist strategy", test_delist)


def test_feature():
    listings = _publish_test_strategies()
    lid = listings[0].listing_id
    assert StrategyMarketplace.feature(lid) is True
    assert StrategyMarketplace.get(lid).status.value == "featured"

test("Feature strategy", test_feature)


def test_trust_badges():
    listings = _publish_test_strategies()
    lid = listings[0].listing_id
    StrategyMarketplace.update_badges(lid, {
        "quality_score": 85,
        "validation_score": 78,
        "stability_score": 72,
        "reproducibility_score": 90,
        "research_depth_score": 65,
    })
    listing = StrategyMarketplace.get(lid)
    assert listing.quality_grade == "A"
    assert listing.marketplace_score > 0

test("Trust badges + marketplace score", test_trust_badges)


def test_ranking_all():
    listings = _publish_test_strategies()
    # Add badges for ranking
    for l in listings:
        StrategyMarketplace.update_badges(l.listing_id, {
            "quality_score": 70, "validation_score": 60,
            "stability_score": 50, "reproducibility_score": 80,
            "research_depth_score": 40,
        })

    all_listings = StrategyMarketplace.search()
    rankings = MarketplaceRanking.rank_all(all_listings)
    assert rankings["total_strategies"] == 3
    assert len(rankings["rankings"]) == 6
    assert "top_performing" in rankings["rankings"]
    assert "most_stable" in rankings["rankings"]

test("Full ranking (6 categories)", test_ranking_all)


def test_ranking_performance():
    listings = _publish_test_strategies()
    all_listings = StrategyMarketplace.search()
    rankings = MarketplaceRanking.rank_all(all_listings)
    top = rankings["rankings"]["top_performing"]
    # Momentum Quality has the highest Sharpe
    assert top[0]["name"] == "Momentum Quality"
    assert top[0]["rank"] == 1

test("Performance ranking (Momentum on top)", test_ranking_performance)


def test_leaderboard():
    listings = _publish_test_strategies()
    all_listings = StrategyMarketplace.search()
    board = MarketplaceRanking.get_leaderboard(all_listings, "top_performing", top_n=2)
    assert len(board) == 2

test("Leaderboard (top N)", test_leaderboard)


# Summary
print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
