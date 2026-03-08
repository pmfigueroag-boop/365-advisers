"""
src/engines/strategy_assistant/agent.py
─────────────────────────────────────────────────────────────────────────────
StrategyAssistant — tool-calling AI agent for quantitative research.

Architecture:
  1. User query → Intent classification
  2. Intent → Tool selection + execution
  3. Tool results → Context assembly
  4. Context → LLM synthesis → Explainable response
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .tools import TOOL_REGISTRY, get_tool_descriptions

logger = logging.getLogger("365advisers.strategy_assistant.agent")


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are the 365 Advisers Strategy Research Assistant — an expert
quantitative research analyst with deep knowledge of alpha signals,
strategy construction, portfolio theory, and backtesting methodology.

You have access to the full research platform:
- 50+ alpha signals across 8 categories
- Strategy registry with lifecycle management
- Backtesting engine with transaction cost models
- Experiment tracking with reproducibility
- Knowledge Graph connecting all research artifacts
- Strategy Marketplace with quality rankings

When answering:
1. Always ground your answers in data from the research tools
2. Cite specific metrics and experiments
3. Explain your reasoning step by step
4. Provide actionable recommendations
5. Acknowledge limitations and caveats
6. Use precise quantitative language
"""

# ── Intent classification ─────────────────────────────────────────────────────

INTENT_TOOL_MAP = {
    "generate_strategy": ["list_signals", "search_strategies", "get_rankings"],
    "analyze_strategy": ["get_strategy", "get_scorecard", "search_experiments"],
    "improve_strategy": ["get_strategy", "get_scorecard", "list_signals"],
    "analyze_signals": ["list_signals", "discover_patterns", "query_graph"],
    "portfolio_advice": ["search_strategies", "get_rankings", "compare_strategies"],
    "experiment_analysis": ["search_experiments", "query_graph"],
    "market_context": ["search_strategies", "get_rankings"],
    "general": ["search_strategies", "list_signals"],
}


class StrategyAssistant:
    """Tool-calling AI agent for Strategy research."""

    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}

    def chat(
        self,
        message: str,
        session_id: str = "default",
        context: dict | None = None,
    ) -> dict:
        """Process a user message and return an explainable response.

        This is a deterministic tool-calling agent that:
        1. Classifies intent from the message
        2. Selects and executes appropriate tools
        3. Assembles context from tool results
        4. Synthesizes an explainable response

        In production, step 4 would use the LLM. Here we provide
        structured context assembly for the LLM to consume.
        """
        # Store message in session
        self._sessions.setdefault(session_id, [])
        self._sessions[session_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # 1. Classify intent
        intent = self._classify_intent(message)

        # 2. Select and execute tools
        tool_results = self._execute_tools(intent, message, context)

        # 3. Assemble context
        assembled_context = self._assemble_context(tool_results)

        # 4. Build response
        response = {
            "intent": intent,
            "tool_calls": list(tool_results.keys()),
            "context": assembled_context,
            "data_sources": [
                {"tool": name, "summary": _summarize_result(result)}
                for name, result in tool_results.items()
            ],
            "recommendations": self._generate_recommendations(intent, tool_results),
            "system_prompt": SYSTEM_PROMPT,
            "assembled_prompt": self._build_llm_prompt(message, assembled_context),
            "session_id": session_id,
            "message_count": len(self._sessions[session_id]),
        }

        # Store response
        self._sessions[session_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return response

    def _classify_intent(self, message: str) -> str:
        """Classify user intent from the message."""
        message_lower = message.lower()

        # Weighted keywords: (keyword, weight) — higher weight = stronger signal
        keywords: dict[str, list[tuple[str, int]]] = {
            "generate_strategy": [("generate", 3), ("create", 3), ("build", 2), ("design", 2), ("new strategy", 3), ("construct", 2)],
            "analyze_strategy": [("analyze", 3), ("explain", 3), ("why did", 3), ("how does", 2), ("performance", 1), ("evaluate", 2)],
            "improve_strategy": [("improve", 3), ("optimize", 3), ("enhance", 2), ("fix", 2), ("better", 1), ("adjust", 2), ("tune", 2)],
            "analyze_signals": [("signal", 2), ("redundant", 3), ("overlap", 2), ("which signals", 3), ("signal quality", 3)],
            "portfolio_advice": [("portfolio", 3), ("diversif", 3), ("allocat", 2), ("combine", 2), ("multi-strategy", 3)],
            "experiment_analysis": [("experiment", 3), ("backtest result", 3), ("best result", 2)],
            "market_context": [("what works in", 3), ("current regime", 3), ("regime strategy", 2)],
        }

        best_intent = "general"
        best_score = 0

        for intent, kws in keywords.items():
            score = sum(w for kw, w in kws if kw in message_lower)
            if score > best_score:
                best_score = score
                best_intent = intent

        return best_intent

    def _execute_tools(self, intent: str, message: str, context: dict | None) -> dict[str, Any]:
        """Execute the tools associated with the intent."""
        tool_names = INTENT_TOOL_MAP.get(intent, ["search_strategies"])
        results = {}

        for tool_name in tool_names:
            tool_fn = TOOL_REGISTRY.get(tool_name)
            if not tool_fn:
                continue

            try:
                # Call tool with context-appropriate args
                args = self._infer_tool_args(tool_name, message, context)
                result = tool_fn(**args)
                results[tool_name] = result
            except Exception as e:
                results[tool_name] = {"error": str(e)}
                logger.warning("Tool %s failed: %s", tool_name, e)

        return results

    def _infer_tool_args(self, tool_name: str, message: str, context: dict | None) -> dict:
        """Infer tool arguments from the message and context."""
        args: dict[str, Any] = {}
        ctx = context or {}

        if tool_name == "list_signals":
            # Extract category from message
            categories = ["momentum", "value", "quality", "volatility", "flow", "sentiment", "macro", "technical"]
            for cat in categories:
                if cat in message.lower():
                    args["category"] = cat
                    break

        elif tool_name == "get_strategy":
            args["strategy_id"] = ctx.get("strategy_id", "")

        elif tool_name == "search_strategies":
            # Extract search terms
            args["search"] = _extract_search_terms(message)
            for regime in ["bull", "bear", "range"]:
                if regime in message.lower():
                    args["regime"] = regime
                    break

        elif tool_name == "search_experiments":
            args["search"] = _extract_search_terms(message)

        elif tool_name == "get_scorecard":
            args["backtest_result"] = ctx.get("backtest_result")

        elif tool_name == "query_graph":
            args["node_id"] = ctx.get("node_id", "")
            args["query_type"] = "neighbors"

        elif tool_name == "get_rankings":
            if "stable" in message.lower():
                args["category"] = "most_stable"
            elif "robust" in message.lower():
                args["category"] = "most_robust"
            elif "efficient" in message.lower():
                args["category"] = "most_efficient"
            else:
                args["category"] = "top_performing"

        return args

    def _assemble_context(self, tool_results: dict[str, Any]) -> str:
        """Assemble tool results into a structured context block for the LLM."""
        sections = []

        for tool_name, result in tool_results.items():
            if isinstance(result, dict) and "error" in result:
                continue

            if tool_name == "list_signals" and isinstance(result, list):
                section = f"## Available Signals ({len(result)} found)\n"
                for s in result[:10]:
                    section += f"- {s.get('id', '?')}: {s.get('name', '?')} [{s.get('category', '?')}]\n"
                sections.append(section)

            elif tool_name == "search_strategies" and isinstance(result, list):
                section = f"## Marketplace Strategies ({len(result)} found)\n"
                for s in result[:5]:
                    name = s.get("name", "?")
                    sharpe = s.get("backtest_summary", {}).get("sharpe_ratio", "N/A")
                    grade = s.get("quality_grade", "?")
                    section += f"- {name}: Sharpe={sharpe}, Grade={grade}\n"
                sections.append(section)

            elif tool_name == "get_scorecard" and isinstance(result, dict):
                section = f"## Strategy Quality Scorecard\n"
                section += f"- Total Score: {result.get('total_score', 'N/A')}/100\n"
                section += f"- Grade: {result.get('grade', 'N/A')}\n"
                dims = result.get("dimensions", {})
                for dim_name, dim_data in dims.items():
                    score = dim_data.get("score", "N/A") if isinstance(dim_data, dict) else dim_data
                    section += f"- {dim_name}: {score}\n"
                sections.append(section)

            elif tool_name == "search_experiments" and isinstance(result, list):
                section = f"## Related Experiments ({len(result)} found)\n"
                for e in result[:5]:
                    section += f"- {e.get('name', '?')} [{e.get('experiment_type', '?')}]: {e.get('status', '?')}\n"
                sections.append(section)

            elif tool_name == "get_rankings" and isinstance(result, list):
                section = "## Strategy Rankings\n"
                for r in result[:5]:
                    section += f"- #{r.get('rank', '?')} {r.get('name', '?')}\n"
                sections.append(section)

            elif tool_name == "discover_patterns" and isinstance(result, dict):
                section = "## Research Patterns\n"
                hubs = result.get("hub_nodes", [])
                if hubs:
                    section += f"- Hub nodes: {', '.join(h.get('node_id','?') for h in hubs[:3])}\n"
                orphans = result.get("orphan_nodes", [])
                if orphans:
                    section += f"- Orphan nodes: {len(orphans)} unused\n"
                sections.append(section)

        return "\n".join(sections) if sections else "No data available from research tools."

    def _generate_recommendations(self, intent: str, tool_results: dict) -> list[dict]:
        """Generate structured recommendations based on intent and data."""
        recs = []

        if intent == "generate_strategy":
            signals = tool_results.get("list_signals", [])
            if isinstance(signals, list) and signals:
                cats = list(set(s.get("category", "") for s in signals if isinstance(s, dict)))
                if cats:
                    recs.append({
                        "action": f"Consider combining signals from categories: {', '.join(cats[:3])}",
                        "rationale": "Multi-factor strategies tend to be more robust than single-factor ones",
                    })

        elif intent == "improve_strategy":
            scorecard = tool_results.get("get_scorecard", {})
            if isinstance(scorecard, dict):
                dims = scorecard.get("dimensions", {})
                weakest = min(dims.items(), key=lambda x: x[1].get("score", 100) if isinstance(x[1], dict) else 100) if dims else None
                if weakest:
                    recs.append({
                        "action": f"Focus on improving {weakest[0]} dimension",
                        "rationale": f"Currently the weakest dimension in the scorecard",
                    })

        elif intent == "portfolio_advice":
            recs.append({
                "action": "Diversify across strategy types to reduce correlation",
                "rationale": "Multi-strategy portfolios with low inter-strategy correlation outperform concentrated approaches",
            })

        return recs

    def _build_llm_prompt(self, user_message: str, context: str) -> str:
        """Build the full prompt for the LLM."""
        return f"""{SYSTEM_PROMPT}

## Research Data Context
{context}

## User Question
{user_message}

## Instructions
Based on the research data above, provide a comprehensive answer that:
1. Directly addresses the user's question
2. References specific data from the research context
3. Provides actionable recommendations
4. Notes any caveats or limitations
"""

    def get_session(self, session_id: str) -> list[dict]:
        """Get chat history for a session."""
        return self._sessions.get(session_id, [])

    def clear_session(self, session_id: str) -> None:
        """Clear a chat session."""
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        """List active session IDs."""
        return list(self._sessions.keys())


def _extract_search_terms(message: str) -> str:
    """Extract meaningful search terms from a message."""
    stop_words = {"a", "an", "the", "is", "are", "what", "which", "how", "can", "do", "does",
                  "i", "me", "my", "for", "in", "on", "to", "of", "and", "or", "that", "this",
                  "with", "from", "about", "best", "top", "want", "need", "help", "please"}
    words = message.lower().split()
    terms = [w for w in words if w not in stop_words and len(w) > 2]
    return " ".join(terms[:5])


def _summarize_result(result: Any) -> str:
    """Create a brief summary of a tool result."""
    if isinstance(result, list):
        return f"{len(result)} items returned"
    elif isinstance(result, dict):
        if "error" in result:
            return f"Error: {result['error']}"
        return f"{len(result)} fields"
    return str(type(result).__name__)
