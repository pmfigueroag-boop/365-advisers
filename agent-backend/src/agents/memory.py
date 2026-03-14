"""
src/agents/memory.py
─────────────────────────────────────────────────────────────────────────────
Agent Memory — persistent context that allows agents to reference
prior analyses when re-analyzing the same ticker.

Architecture:
  - Per-ticker memory store with configurable TTL
  - Stores key conclusions, signals, and catalysts from past analyses
  - DB-backed with in-memory LRU for performance
  - Agents receive memory context as additional prompt context

Memory is valuable because:
  - Agents can track thesis evolution over time
  - Pattern detection across repeated analyses
  - Reduced token waste (don't re-explain known context)
"""

from __future__ import annotations

import json
import time
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("365advisers.agents.memory")


class MemoryEntry:
    """A single memory entry for an agent-ticker pair."""

    def __init__(
        self,
        ticker: str,
        agent_name: str,
        signal: str,
        conviction: float,
        key_insights: list[str],
        catalysts: list[str],
        risks: list[str],
        timestamp: str | None = None,
    ):
        self.ticker = ticker
        self.agent_name = agent_name
        self.signal = signal
        self.conviction = conviction
        self.key_insights = key_insights
        self.catalysts = catalysts
        self.risks = risks
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "agent": self.agent_name,
            "signal": self.signal,
            "conviction": self.conviction,
            "key_insights": self.key_insights,
            "catalysts": self.catalysts,
            "risks": self.risks,
            "timestamp": self.timestamp,
        }

    def to_prompt_context(self) -> str:
        """Format memory entry for inclusion in agent prompt."""
        return (
            f"[PRIOR ANALYSIS — {self.timestamp}] "
            f"Signal: {self.signal} (conviction: {self.conviction:.1f}). "
            f"Key insights: {'; '.join(self.key_insights[:3])}. "
            f"Catalysts: {'; '.join(self.catalysts[:2])}. "
            f"Risks: {'; '.join(self.risks[:2])}."
        )


class AgentMemoryStore:
    """
    In-memory agent memory with LRU eviction and TTL.

    Keys: (ticker, agent_name)
    Values: list of MemoryEntry (most recent first, max 3 per pair)
    """

    def __init__(self, max_entries: int = 200, ttl_hours: int = 72):
        self._store: OrderedDict[str, list[MemoryEntry]] = OrderedDict()
        self.max_entries = max_entries
        self.ttl_seconds = ttl_hours * 3600
        self._max_memories_per_key = 3

    def _key(self, ticker: str, agent_name: str) -> str:
        return f"{ticker.upper()}:{agent_name}"

    def store(self, entry: MemoryEntry) -> None:
        """Store a memory entry for a ticker-agent pair."""
        key = self._key(entry.ticker, entry.agent_name)

        # Get or create memory list
        if key in self._store:
            memories = self._store.pop(key)  # Move to end (LRU)
        else:
            memories = []

        # Prepend new entry
        memories.insert(0, entry)

        # Cap at max memories per key
        memories = memories[:self._max_memories_per_key]

        self._store[key] = memories

        # Evict oldest entries if over capacity
        while len(self._store) > self.max_entries:
            evicted_key, _ = self._store.popitem(last=False)
            logger.debug(f"Memory evicted: {evicted_key}")

        logger.info(f"Memory stored: {key} (signal={entry.signal})")

    def recall(self, ticker: str, agent_name: str) -> list[MemoryEntry]:
        """
        Recall memories for a ticker-agent pair.

        Returns recent memories (max 3), filtered by TTL.
        """
        key = self._key(ticker, agent_name)
        memories = self._store.get(key, [])

        now = time.time()
        valid = []
        for m in memories:
            try:
                ts = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00"))
                age_seconds = now - ts.timestamp()
                if age_seconds < self.ttl_seconds:
                    valid.append(m)
            except Exception:
                valid.append(m)  # Keep if timestamp parsing fails

        return valid

    def recall_for_prompt(self, ticker: str, agent_name: str) -> str:
        """
        Get formatted memory context for inclusion in an agent prompt.

        Returns empty string if no memories exist.
        """
        memories = self.recall(ticker, agent_name)
        if not memories:
            return ""

        lines = ["\n--- PRIOR ANALYSES (your previous conclusions for this ticker) ---"]
        for m in memories:
            lines.append(m.to_prompt_context())
        lines.append("--- END OF PRIOR ANALYSES ---\n")
        lines.append(
            "Consider how your previous analysis compares to current data. "
            "Note any thesis evolution or changed conditions."
        )

        return "\n".join(lines)

    def store_from_agent_result(self, ticker: str, agent_name: str, result: dict) -> None:
        """
        Create and store a memory entry from an agent result dict.

        Extracts signal, conviction, memo as key insights, catalysts, and risks.
        """
        try:
            entry = MemoryEntry(
                ticker=ticker.upper(),
                agent_name=agent_name,
                signal=result.get("signal", "HOLD"),
                conviction=float(result.get("conviction", 0.5)),
                key_insights=[result.get("memo", "")][:3] if isinstance(result.get("memo"), list) else [str(result.get("memo", ""))],
                catalysts=list(result.get("catalysts", []))[:3],
                risks=list(result.get("risks", []))[:3],
            )
            self.store(entry)
        except Exception as exc:
            logger.warning(f"Failed to store memory for {ticker}/{agent_name}: {exc}")

    def get_all_memories_for_ticker(self, ticker: str) -> list[dict]:
        """Get all agent memories for a ticker."""
        results = []
        prefix = f"{ticker.upper()}:"
        for key, memories in self._store.items():
            if key.startswith(prefix):
                for m in memories:
                    results.append(m.to_dict())
        return results

    def stats(self) -> dict:
        """Return memory store statistics."""
        total_memories = sum(len(v) for v in self._store.values())
        tickers = set(k.split(":")[0] for k in self._store.keys())
        return {
            "unique_keys": len(self._store),
            "total_memories": total_memories,
            "unique_tickers": len(tickers),
            "max_entries": self.max_entries,
            "ttl_hours": self.ttl_seconds / 3600,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

agent_memory = AgentMemoryStore()
