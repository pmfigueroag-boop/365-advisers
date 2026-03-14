"""
tests/test_agent_registry.py
─────────────────────────────────────────────────────────────────────────────
Tests for the Agent Capability Registry and Tools.
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


# ── Registry ─────────────────────────────────────────────────────────────────


class TestAgentRegistry:
    def test_registry_is_singleton(self, mock_settings):
        from src.agents.registry import AgentRegistry
        r1 = AgentRegistry()
        r2 = AgentRegistry()
        assert r1 is r2

    def test_default_agents_registered(self, mock_settings):
        from src.agents.registry import AgentRegistry
        registry = AgentRegistry()
        caps = registry.list_capabilities()
        assert len(caps) >= 10  # At least 10 default agents

    def test_known_agents_present(self, mock_settings):
        from src.agents.registry import AgentRegistry
        registry = AgentRegistry()
        expected = [
            "value_agent",
            "quality_agent",
            "capital_agent",
            "risk_agent",
            "committee_supervisor",
            "technical_analyst",
            "cio_agent",
            "autonomous_pm",
        ]
        for name in expected:
            cap = registry.get(name)
            assert cap is not None, f"Agent '{name}' not found in registry"

    def test_agent_has_required_fields(self, mock_settings):
        from src.agents.registry import AgentRegistry
        registry = AgentRegistry()
        for cap_dict in registry.list_capabilities():
            assert "name" in cap_dict
            assert "description" in cap_dict
            assert "category" in cap_dict
            assert "model" in cap_dict
            assert "tools" in cap_dict
            assert "input_schema" in cap_dict
            assert "output_schema" in cap_dict

    def test_tool_enabled_agents(self, mock_settings):
        from src.agents.registry import AgentRegistry
        registry = AgentRegistry()
        autonomous = [
            c for c in registry.list_capabilities() if c.get("is_autonomous")
        ]
        assert len(autonomous) >= 4  # Value, Quality, Capital, Risk agents

    def test_register_custom_agent(self, mock_settings):
        from src.agents.registry import AgentRegistry, AgentCapability
        registry = AgentRegistry()
        custom = AgentCapability(
            name="test_agent",
            description="Test agent",
            category="test",
            model="test-model",
            tools=["test_tool"],
            input_schema={"ticker": "str"},
            output_schema={"result": "str"},
        )
        registry.register(custom)
        cap = registry.get("test_agent")
        assert cap is not None
        assert cap.name == "test_agent"
        # Cleanup
        del registry._agents["test_agent"]

    def test_summary(self, mock_settings):
        from src.agents.registry import AgentRegistry
        registry = AgentRegistry()
        summary = registry.summary()
        assert "total_agents" in summary
        assert "tool_enabled_agents" in summary
        assert "categories" in summary
        assert summary["total_agents"] >= 10


# ── Tools ─────────────────────────────────────────────────────────────────────


class TestToolDeclarations:
    def test_declarations_are_valid(self, mock_settings):
        from src.agents.tools import TOOL_DECLARATIONS
        assert len(TOOL_DECLARATIONS) >= 4

        for tool in TOOL_DECLARATIONS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert tool["parameters"]["type"] == "object"

    def test_tool_names(self, mock_settings):
        from src.agents.tools import TOOL_DECLARATIONS
        names = {t["name"] for t in TOOL_DECLARATIONS}
        assert "fetch_peer_comparison" in names
        assert "get_sector_performance" in names
        assert "query_price_history" in names
        assert "get_macro_indicators" in names


class TestToolExecution:
    def test_execute_unknown_tool(self, mock_settings):
        from src.agents.tools import execute_tool
        result = execute_tool("nonexistent_tool", {})
        assert "error" in result

    def test_execute_macro_indicators(self, mock_settings):
        from src.agents.tools import execute_tool
        result = execute_tool("get_macro_indicators", {})
        assert isinstance(result, dict)
        # Should return data or a graceful fallback
        assert "error" not in result or "note" in result or "fed_rate" in result

    def test_execute_price_history(self, mock_settings):
        """Test price history with mocked yfinance."""
        import pandas as pd
        from unittest.mock import MagicMock, patch

        mock_ticker = MagicMock()
        mock_data = pd.DataFrame({
            "Close": [100.0, 102.0, 105.0],
            "Volume": [1000000, 1200000, 900000],
        })
        mock_ticker.history.return_value = mock_data

        with patch("yfinance.Ticker", return_value=mock_ticker):
            from src.agents.tools import _query_price_history
            result = _query_price_history("AAPL", days=30)
            assert isinstance(result, dict)
            assert result.get("ticker") == "AAPL"

    def test_execute_sector_performance(self, mock_settings):
        """Test sector performance with mocked yfinance."""
        import pandas as pd
        from unittest.mock import MagicMock, patch

        mock_ticker = MagicMock()
        mock_data = pd.DataFrame({"Close": [100.0, 105.0, 110.0]})
        mock_ticker.history.return_value = mock_data

        with patch("yfinance.Ticker", return_value=mock_ticker):
            from src.agents.tools import _get_sector_performance
            result = _get_sector_performance("Technology", "3m")
            assert isinstance(result, dict)
            assert result.get("sector") == "Technology"


# ── Agent Capability Model ────────────────────────────────────────────────────


class TestAgentCapability:
    def test_model_serialization(self, mock_settings):
        from src.agents.registry import AgentCapability
        cap = AgentCapability(
            name="test",
            description="Test",
            category="test",
            model="test-model",
            tools=["tool1", "tool2"],
            input_schema={"ticker": "str"},
            output_schema={"result": "dict"},
            is_autonomous=True,
            max_tool_calls=5,
        )
        d = cap.model_dump()
        assert d["name"] == "test"
        assert d["is_autonomous"] is True
        assert d["max_tool_calls"] == 5
        assert len(d["tools"]) == 2
