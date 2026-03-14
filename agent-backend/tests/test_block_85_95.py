"""
tests/test_block_85_95.py
─────────────────────────────────────────────────────────────────────────────
Tests for Block 85→95: MCP server, cost tracker, agent memory.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from src.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


# ── Cost Tracker ──────────────────────────────────────────────────────────────


class TestCostTracker:
    def setup_method(self):
        from src.services.cost_tracker import reset_tracker
        reset_tracker()

    def test_record_cost(self, mock_settings):
        from src.services.cost_tracker import record_llm_cost
        status = record_llm_cost("gemini-2.5-flash", 1000, 500, 0.01)
        assert status["total_today_usd"] > 0
        assert status["budget_usd"] > 0

    def test_cumulative_tracking(self, mock_settings):
        from src.services.cost_tracker import record_llm_cost
        record_llm_cost("gemini-2.5-flash", 100, 50, 0.01)
        status = record_llm_cost("gemini-2.5-flash", 200, 100, 0.02)
        assert abs(status["total_today_usd"] - 0.03) < 0.001

    def test_budget_exceeded_detection(self, mock_settings, monkeypatch):
        from src.services.cost_tracker import record_llm_cost, should_downgrade_model
        monkeypatch.setenv("DAILY_LLM_BUDGET_USD", "0.01")
        record_llm_cost("gemini-2.5-pro", 1000, 500, 0.02)
        assert should_downgrade_model() is True

    def test_no_downgrade_under_budget(self, mock_settings, monkeypatch):
        from src.services.cost_tracker import should_downgrade_model
        monkeypatch.setenv("DAILY_LLM_BUDGET_USD", "100.00")
        assert should_downgrade_model() is False

    def test_auto_downgrade_model(self, mock_settings, monkeypatch):
        from src.services.cost_tracker import record_llm_cost, get_recommended_model
        monkeypatch.setenv("DAILY_LLM_BUDGET_USD", "0.01")
        record_llm_cost("gemini-2.5-pro", 1000, 500, 0.02)
        model = get_recommended_model("gemini-2.5-pro")
        assert model == "gemini-2.5-flash"

    def test_keep_model_under_budget(self, mock_settings, monkeypatch):
        from src.services.cost_tracker import get_recommended_model
        monkeypatch.setenv("DAILY_LLM_BUDGET_USD", "100.00")
        model = get_recommended_model("gemini-2.5-pro")
        assert model == "gemini-2.5-pro"

    def test_cost_report_format(self, mock_settings):
        from src.services.cost_tracker import record_llm_cost, get_cost_report
        record_llm_cost("gemini-2.5-flash", 100, 50, 0.001)
        report = get_cost_report()
        assert "budget" in report
        assert "summary" in report
        assert "by_model" in report
        assert report["summary"]["total_calls"] == 1

    def test_alert_at_threshold(self, mock_settings, monkeypatch):
        from src.services.cost_tracker import record_llm_cost, get_cost_report
        monkeypatch.setenv("DAILY_LLM_BUDGET_USD", "0.01")
        record_llm_cost("gemini-2.5-pro", 1000, 500, 0.009)
        report = get_cost_report()
        assert len(report["recent_alerts"]) > 0


# ── Agent Memory ──────────────────────────────────────────────────────────────


class TestAgentMemory:
    def test_store_and_recall(self, mock_settings):
        from src.agents.memory import AgentMemoryStore, MemoryEntry
        store = AgentMemoryStore()
        entry = MemoryEntry(
            ticker="AAPL", agent_name="value_agent",
            signal="BUY", conviction=0.8,
            key_insights=["Strong moat"], catalysts=["iPhone"], risks=["China"],
        )
        store.store(entry)
        memories = store.recall("AAPL", "value_agent")
        assert len(memories) == 1
        assert memories[0].signal == "BUY"

    def test_recall_empty(self, mock_settings):
        from src.agents.memory import AgentMemoryStore
        store = AgentMemoryStore()
        memories = store.recall("AAPL", "value_agent")
        assert len(memories) == 0

    def test_max_memories_per_key(self, mock_settings):
        from src.agents.memory import AgentMemoryStore, MemoryEntry
        store = AgentMemoryStore()
        for i in range(5):
            entry = MemoryEntry(
                ticker="AAPL", agent_name="value_agent",
                signal="BUY" if i % 2 == 0 else "HOLD",
                conviction=0.5 + i * 0.1,
                key_insights=[f"Insight {i}"], catalysts=[], risks=[],
            )
            store.store(entry)
        memories = store.recall("AAPL", "value_agent")
        assert len(memories) == 3  # Max 3 per key

    def test_prompt_context_format(self, mock_settings):
        from src.agents.memory import AgentMemoryStore, MemoryEntry
        store = AgentMemoryStore()
        entry = MemoryEntry(
            ticker="MSFT", agent_name="quality_agent",
            signal="BUY", conviction=0.9,
            key_insights=["Strong cloud growth"], catalysts=["AI"], risks=["Regulation"],
        )
        store.store(entry)
        context = store.recall_for_prompt("MSFT", "quality_agent")
        assert "PRIOR ANALYSIS" in context
        assert "BUY" in context
        assert "Strong cloud growth" in context

    def test_store_from_agent_result(self, mock_settings):
        from src.agents.memory import AgentMemoryStore
        store = AgentMemoryStore()
        result = {
            "signal": "SELL",
            "conviction": 0.3,
            "memo": "Overvalued",
            "catalysts": ["Market correction"],
            "risks": ["Recession"],
        }
        store.store_from_agent_result("TSLA", "risk_agent", result)
        memories = store.recall("TSLA", "risk_agent")
        assert len(memories) == 1
        assert memories[0].signal == "SELL"

    def test_lru_eviction(self, mock_settings):
        from src.agents.memory import AgentMemoryStore, MemoryEntry
        store = AgentMemoryStore(max_entries=3)
        for i in range(5):
            entry = MemoryEntry(
                ticker=f"TICK{i}", agent_name="agent",
                signal="HOLD", conviction=0.5,
                key_insights=[], catalysts=[], risks=[],
            )
            store.store(entry)
        assert store.stats()["unique_keys"] == 3  # Evicted oldest

    def test_stats(self, mock_settings):
        from src.agents.memory import AgentMemoryStore, MemoryEntry
        store = AgentMemoryStore()
        entry = MemoryEntry(
            ticker="AAPL", agent_name="value",
            signal="BUY", conviction=0.8,
            key_insights=[], catalysts=[], risks=[],
        )
        store.store(entry)
        stats = store.stats()
        assert stats["unique_keys"] == 1
        assert stats["unique_tickers"] == 1


# ── MCP Server ────────────────────────────────────────────────────────────────


class TestMCPServer:
    def test_server_info(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import server_info
        result = asyncio.run(server_info())
        assert result["name"] == "365-advisers-mcp"
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]

    def test_list_tools(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import list_tools
        result = asyncio.run(list_tools())
        tools = result["tools"]
        assert len(tools) > 0
        # Should include data tools
        tool_names = [t["name"] for t in tools]
        assert "fetch_peer_comparison" in tool_names
        assert "get_macro_indicators" in tool_names

    def test_list_tools_includes_agents(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import list_tools
        result = asyncio.run(list_tools())
        tool_names = [t["name"] for t in result["tools"]]
        # Should include agent invocation tools for autonomous agents
        has_invoke = any(n.startswith("invoke_") for n in tool_names)
        assert has_invoke is True

    def test_call_tool_macro(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import call_tool, MCPToolCallRequest
        request = MCPToolCallRequest(name="get_macro_indicators", arguments={})
        result = asyncio.run(call_tool(request))
        assert result.content[0]["type"] == "text"

    def test_call_invalid_tool(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import call_tool, MCPToolCallRequest
        request = MCPToolCallRequest(name="nonexistent_tool", arguments={})
        result = asyncio.run(call_tool(request))
        assert result.isError is True

    def test_list_resources(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import list_resources
        result = asyncio.run(list_resources())
        resources = result["resources"]
        assert len(resources) >= 3
        uris = [r["uri"] for r in resources]
        assert "365advisers://agents/registry" in uris
        assert "365advisers://system/health" in uris

    def test_read_agent_registry_resource(self, mock_settings):
        import asyncio
        from src.agents.mcp_server import read_resource
        result = asyncio.run(read_resource("agents/registry"))
        assert "contents" in result
        assert result["contents"][0]["uri"] == "365advisers://agents/registry"
