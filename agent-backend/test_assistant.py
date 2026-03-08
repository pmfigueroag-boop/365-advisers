"""Integration test for Strategy AI Assistant."""
import sys
import os
import traceback

sys.path.insert(0, ".")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_assistant.db")

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
    from src.engines.strategy_assistant import (
        StrategyAssistant, SYSTEM_PROMPT, TOOL_REGISTRY, get_tool_descriptions,
    )

test("Imports", test_imports)


from src.engines.strategy_assistant.agent import StrategyAssistant
from src.engines.strategy_assistant.tools import TOOL_REGISTRY, get_tool_descriptions


def test_tool_registry():
    assert len(TOOL_REGISTRY) == 10
    expected = [
        "list_signals", "get_strategy", "search_strategies",
        "run_research", "get_scorecard", "search_experiments",
        "query_graph", "discover_patterns", "get_rankings",
        "compare_strategies",
    ]
    for name in expected:
        assert name in TOOL_REGISTRY, f"Missing tool: {name}"

test("Tool registry (10 tools)", test_tool_registry)


def test_tool_descriptions():
    descs = get_tool_descriptions()
    assert len(descs) == 10
    for d in descs:
        assert "name" in d
        assert "description" in d
        assert len(d["description"]) > 0, f"Tool {d['name']} has no description"

test("Tool descriptions", test_tool_descriptions)


def test_intent_generate():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("Generate a new momentum strategy for bull markets")
    assert intent == "generate_strategy"

test("Intent: generate_strategy", test_intent_generate)


def test_intent_analyze():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("Analyze why this strategy performed poorly")
    assert intent == "analyze_strategy"

test("Intent: analyze_strategy", test_intent_analyze)


def test_intent_improve():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("How can I improve and optimize this strategy?")
    assert intent == "improve_strategy"

test("Intent: improve_strategy", test_intent_improve)


def test_intent_signals():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("Which signals are redundant in this strategy?")
    assert intent == "analyze_signals"

test("Intent: analyze_signals", test_intent_signals)


def test_intent_portfolio():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("Suggest a diversified multi-strategy portfolio")
    assert intent == "portfolio_advice"

test("Intent: portfolio_advice", test_intent_portfolio)


def test_intent_experiment():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("Which experiment had the best result?")
    assert intent == "experiment_analysis"

test("Intent: experiment_analysis", test_intent_experiment)


def test_intent_market():
    assistant = StrategyAssistant()
    intent = assistant._classify_intent("What works in bear market regimes?")
    assert intent == "market_context"

test("Intent: market_context", test_intent_market)


def test_chat_basic():
    assistant = StrategyAssistant()
    response = assistant.chat("What momentum strategies are available?")
    assert "intent" in response
    assert "tool_calls" in response
    assert "context" in response
    assert "data_sources" in response
    assert "recommendations" in response
    assert "assembled_prompt" in response
    assert "session_id" in response

test("Chat basic (response structure)", test_chat_basic)


def test_chat_intent_routing():
    assistant = StrategyAssistant()

    # Generate intent should call list_signals + search_strategies + get_rankings
    response = assistant.chat("Generate a new value strategy")
    assert response["intent"] == "generate_strategy"
    assert "list_signals" in response["tool_calls"]

test("Chat intent routing", test_chat_intent_routing)


def test_chat_context_assembly():
    assistant = StrategyAssistant()
    response = assistant.chat("Show me available momentum signals")
    # Context should be a string (assembled from tool results)
    assert isinstance(response["context"], str)

test("Context assembly", test_chat_context_assembly)


def test_chat_recommendations():
    assistant = StrategyAssistant()
    response = assistant.chat("Build a diversified portfolio of strategies")
    assert isinstance(response["recommendations"], list)

test("Recommendations generated", test_chat_recommendations)


def test_session_management():
    assistant = StrategyAssistant()
    assistant.chat("First question", session_id="session_1")
    assistant.chat("Second question", session_id="session_1")
    assistant.chat("Different session", session_id="session_2")

    history = assistant.get_session("session_1")
    assert len(history) == 4  # 2 user + 2 assistant messages

    assert "session_1" in assistant.list_sessions()
    assert "session_2" in assistant.list_sessions()

test("Session management (history)", test_session_management)


def test_clear_session():
    assistant = StrategyAssistant()
    assistant.chat("Test", session_id="temp")
    assert len(assistant.get_session("temp")) > 0
    assistant.clear_session("temp")
    assert len(assistant.get_session("temp")) == 0

test("Clear session", test_clear_session)


def test_llm_prompt_structure():
    assistant = StrategyAssistant()
    response = assistant.chat("Analyze this momentum strategy")
    prompt = response["assembled_prompt"]
    assert "Research Data Context" in prompt
    assert "User Question" in prompt
    assert "Instructions" in prompt
    assert "momentum" in prompt.lower()

test("LLM prompt structure", test_llm_prompt_structure)


def test_data_sources():
    assistant = StrategyAssistant()
    response = assistant.chat("What signals exist?")
    assert isinstance(response["data_sources"], list)
    for ds in response["data_sources"]:
        assert "tool" in ds
        assert "summary" in ds

test("Data sources tracking", test_data_sources)


def test_context_with_strategy():
    assistant = StrategyAssistant()
    response = assistant.chat(
        "Analyze strategy performance",
        context={"strategy_id": "momentum_quality"},
    )
    assert response["intent"] == "analyze_strategy"

test("Context-aware chat", test_context_with_strategy)


# Summary
print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
print("=" * 60)
