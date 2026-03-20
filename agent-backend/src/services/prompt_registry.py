"""
src/services/prompt_registry.py
─────────────────────────────────────────────────────────────────────────────
Version-controlled prompt registry with instant rollback.

Every agent's system prompt is stored with version number, content hash,
and timestamp. Supports rollback to any previous version and diff between
versions.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.prompt_registry")


class PromptVersion(BaseModel):
    """A single versioned prompt."""
    agent_name: str
    version: int
    prompt_text: str
    model: str = "gemini-2.5-pro"
    sha256: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.prompt_text.encode()).hexdigest()[:16]


class PromptDiff(BaseModel):
    """Diff between two prompt versions."""
    agent_name: str
    from_version: int
    to_version: int
    from_sha: str
    to_sha: str
    lines_added: int = 0
    lines_removed: int = 0
    char_diff: int = 0
    from_model: str = ""
    to_model: str = ""


class PromptRegistry:
    """
    Version-controlled prompt registry.

    Usage:
        registry = PromptRegistry()
        v1 = registry.register("cio_agent", "You are a CIO...", "gemini-2.5-pro")
        v2 = registry.register("cio_agent", "You are the Chief...", "gemini-2.5-pro")
        registry.rollback("cio_agent", 1)  # Rollback to v1
        active = registry.get_active("cio_agent")
    """

    def __init__(self):
        self._versions: dict[str, list[PromptVersion]] = {}
        logger.info("PromptRegistry initialized")

    def register(
        self,
        agent_name: str,
        prompt_text: str,
        model: str = "gemini-2.5-pro",
        metadata: dict | None = None,
    ) -> PromptVersion:
        """Register a new prompt version for an agent."""
        if agent_name not in self._versions:
            self._versions[agent_name] = []

        versions = self._versions[agent_name]

        # Check for duplicate content
        new_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]
        if versions and versions[-1].sha256 == new_hash and versions[-1].is_active:
            logger.debug("Prompt unchanged for %s, skipping", agent_name)
            return versions[-1]

        # Deactivate all previous versions
        for v in versions:
            v.is_active = False

        next_version = len(versions) + 1
        pv = PromptVersion(
            agent_name=agent_name,
            version=next_version,
            prompt_text=prompt_text,
            model=model,
            metadata=metadata or {},
        )
        versions.append(pv)

        logger.info(
            "Registered %s v%d (sha=%s, model=%s)",
            agent_name, next_version, pv.sha256, model,
        )
        return pv

    def get_active(self, agent_name: str) -> PromptVersion | None:
        """Get the currently active prompt version for an agent."""
        versions = self._versions.get(agent_name, [])
        for v in reversed(versions):
            if v.is_active:
                return v
        return None

    def get_version(self, agent_name: str, version: int) -> PromptVersion | None:
        """Get a specific version."""
        versions = self._versions.get(agent_name, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_versions(self, agent_name: str) -> list[PromptVersion]:
        """List all versions for an agent."""
        return self._versions.get(agent_name, [])

    def list_agents(self) -> list[dict]:
        """List all registered agents with their active version."""
        result = []
        for agent_name, versions in self._versions.items():
            active = self.get_active(agent_name)
            result.append({
                "agent_name": agent_name,
                "total_versions": len(versions),
                "active_version": active.version if active else None,
                "active_model": active.model if active else None,
                "active_sha": active.sha256 if active else None,
            })
        return result

    def rollback(self, agent_name: str, version: int) -> PromptVersion | None:
        """Rollback to a specific version."""
        versions = self._versions.get(agent_name, [])
        target = None
        for v in versions:
            if v.version == version:
                target = v
                break

        if not target:
            logger.warning("Version %d not found for %s", version, agent_name)
            return None

        # Deactivate all, activate target
        for v in versions:
            v.is_active = False
        target.is_active = True

        logger.info(
            "Rolled back %s to v%d (sha=%s)",
            agent_name, version, target.sha256,
        )
        return target

    def diff(self, agent_name: str, from_v: int, to_v: int) -> PromptDiff | None:
        """Get a diff summary between two versions."""
        v_from = self.get_version(agent_name, from_v)
        v_to = self.get_version(agent_name, to_v)
        if not v_from or not v_to:
            return None

        from_lines = v_from.prompt_text.splitlines()
        to_lines = v_to.prompt_text.splitlines()

        # Simple line-level diff
        from_set = set(from_lines)
        to_set = set(to_lines)

        return PromptDiff(
            agent_name=agent_name,
            from_version=from_v,
            to_version=to_v,
            from_sha=v_from.sha256,
            to_sha=v_to.sha256,
            lines_added=len(to_set - from_set),
            lines_removed=len(from_set - to_set),
            char_diff=len(v_to.prompt_text) - len(v_from.prompt_text),
            from_model=v_from.model,
            to_model=v_to.model,
        )


# Singleton
_prompt_registry = PromptRegistry()


def get_prompt_registry() -> PromptRegistry:
    return _prompt_registry
