"""
src/agents/registry.py
─────────────────────────────────────────────────────────────────────────────
Agent Capability Registry — exposes a machine-readable manifest of all
agentic capabilities in the 365 Advisers system.

MCP-compatible schema for external orchestrators to discover and invoke
the platform's AI agents.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("365advisers.agents.registry")


class AgentCapability(BaseModel):
    """Describes a single agent's capabilities."""
    name: str
    description: str
    category: str                       # fundamental | technical | alpha | decision | portfolio
    model: str                          # LLM model used (e.g. "gemini-2.5-flash")
    tools: list[str]                    # List of tool names the agent can invoke
    input_schema: dict[str, Any]        # Expected input parameters
    output_schema: dict[str, Any]       # Expected output structure
    is_autonomous: bool = False         # Can self-direct via tool-use
    max_tool_calls: int = 0             # Max tool calls per invocation (0 = traditional prompt-only)


class AgentRegistry:
    """
    Singleton registry of all agent capabilities.

    Usage:
        registry = AgentRegistry()
        registry.register(AgentCapability(...))
        caps = registry.list_capabilities()
    """

    _instance: AgentRegistry | None = None
    _agents: dict[str, AgentCapability] = {}

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._agents = {}
            cls._register_defaults()
        return cls._instance

    @classmethod
    def _register_defaults(cls) -> None:
        """Register all known agents on first instantiation."""
        defaults = [
            AgentCapability(
                name="value_agent",
                description="Análisis de Valor e Margen de Seguridad (framework Graham/Buffett). Evalúa valor intrínseco, DCF, P/E, P/B, FCF yield.",
                category="fundamental",
                model="gemini-2.5-flash",
                tools=["fetch_peer_comparison", "query_price_history"],
                input_schema={"ticker": "str", "fundamental_data": "dict"},
                output_schema={"signal": "BUY|SELL|HOLD|AVOID", "conviction": "float", "memo": "str"},
                is_autonomous=True,
                max_tool_calls=3,
            ),
            AgentCapability(
                name="quality_agent",
                description="Análisis de Calidad y Moat (framework Munger/Fisher). Evalúa ROIC, márgenes, poder de fijación de precios.",
                category="fundamental",
                model="gemini-2.5-flash",
                tools=["fetch_peer_comparison"],
                input_schema={"ticker": "str", "fundamental_data": "dict"},
                output_schema={"signal": "BUY|SELL|HOLD|AVOID", "conviction": "float", "memo": "str"},
                is_autonomous=True,
                max_tool_calls=2,
            ),
            AgentCapability(
                name="capital_agent",
                description="Análisis de Asignación de Capital (framework Icahn). Evalúa buybacks, dividendos, leverage, FCF deployment.",
                category="fundamental",
                model="gemini-2.5-flash",
                tools=["fetch_peer_comparison"],
                input_schema={"ticker": "str", "fundamental_data": "dict"},
                output_schema={"signal": "BUY|SELL|HOLD|AVOID", "conviction": "float", "memo": "str"},
                is_autonomous=True,
                max_tool_calls=2,
            ),
            AgentCapability(
                name="risk_agent",
                description="Análisis de Riesgo y Estrés Macro (framework Marks/Dalio). Evalúa riesgo de cola, ciclo, leverage stress.",
                category="fundamental",
                model="gemini-2.5-flash",
                tools=["get_macro_indicators", "get_sector_performance"],
                input_schema={"ticker": "str", "fundamental_data": "dict", "web_context": "str"},
                output_schema={"signal": "BUY|SELL|HOLD|AVOID", "conviction": "float", "memo": "str"},
                is_autonomous=True,
                max_tool_calls=3,
            ),
            AgentCapability(
                name="committee_supervisor",
                description="Chief Investment Officer que sintetiza 4 memos de analistas en un veredicto final del Comité de Inversión.",
                category="fundamental",
                model="gemini-2.5-pro",
                tools=[],
                input_schema={"ticker": "str", "agent_memos": "list[AgentMemo]"},
                output_schema={"signal": "BUY|SELL|HOLD", "score": "float", "consensus_narrative": "str"},
                is_autonomous=False,
                max_tool_calls=0,
            ),
            AgentCapability(
                name="technical_analyst",
                description="Analista técnico LLM que genera un memo narrativo sobre regímenes, multi-timeframe, y structure analysis.",
                category="technical",
                model="gemini-2.5-flash",
                tools=[],
                input_schema={"ticker": "str", "technical_summary": "dict"},
                output_schema={"opinions": "list[Opinion]", "consensus": "ConsensusOpinion"},
                is_autonomous=False,
            ),
            AgentCapability(
                name="alpha_memo_agent",
                description="Genera narrativa sobre señales alpha evaluadas: qué señales firaron y su significado estadístico.",
                category="alpha",
                model="gemini-2.5-flash",
                tools=[],
                input_schema={"ticker": "str", "signal_profile": "dict"},
                output_schema={"signal": "str", "conviction": "str", "narrative": "str"},
            ),
            AgentCapability(
                name="evidence_memo_agent",
                description="Analiza la evidencia del Composite Alpha Score y subscores por categoría.",
                category="alpha",
                model="gemini-2.5-flash",
                tools=[],
                input_schema={"ticker": "str", "composite_alpha": "dict"},
                output_schema={"signal": "str", "conviction": "str", "narrative": "str"},
            ),
            AgentCapability(
                name="signal_map_memo_agent",
                description="Mapea todas las señales activas con su strength, confidence y category para visibilidad total.",
                category="alpha",
                model="gemini-2.5-flash",
                tools=[],
                input_schema={"ticker": "str", "signals": "list[Signal]"},
                output_schema={"signal": "str", "conviction": "str", "narrative": "str"},
            ),
            AgentCapability(
                name="cio_agent",
                description="Chief Investment Officer que sintetiza TODA la información (fundamental, técnico, alpha stack, macro, EDPL) en el Investment Memo final.",
                category="decision",
                model="gemini-2.5-pro",
                tools=[],
                input_schema={"ticker": "str", "investment_position": "str", "all_analysis_data": "dict"},
                output_schema={"thesis_summary": "str", "key_catalysts": "list", "key_risks": "list"},
                is_autonomous=False,
            ),
            AgentCapability(
                name="autonomous_pm",
                description="Portfolio Manager autónomo que construye, asigna, rebalancea y monitorea portafolios using 5 sub-engines.",
                category="portfolio",
                model="N/A (deterministic)",
                tools=[],
                input_schema={"alpha_profiles": "list[dict]", "regime": "str"},
                output_schema={"portfolios": "list[APMPortfolio]", "risk_report": "RiskReport"},
                is_autonomous=False,
            ),
        ]

        for cap in defaults:
            cls._agents[cap.name] = cap

        logger.info(f"Agent registry initialized with {len(defaults)} agents")

    def register(self, capability: AgentCapability) -> None:
        """Register or update an agent capability."""
        self._agents[capability.name] = capability
        logger.info(f"Agent registered: {capability.name} ({capability.category})")

    def get(self, name: str) -> AgentCapability | None:
        """Get a specific agent's capability."""
        return self._agents.get(name)

    def list_capabilities(self) -> list[dict]:
        """Return all capabilities as MCP-compatible JSON-serialisable dicts."""
        return [cap.model_dump() for cap in self._agents.values()]

    def summary(self) -> dict:
        """Summary statistics for the registry."""
        categories = {}
        for cap in self._agents.values():
            categories.setdefault(cap.category, []).append(cap.name)

        tool_enabled = sum(1 for c in self._agents.values() if c.is_autonomous)

        return {
            "total_agents": len(self._agents),
            "tool_enabled_agents": tool_enabled,
            "categories": {k: len(v) for k, v in categories.items()},
            "agents_by_category": categories,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
