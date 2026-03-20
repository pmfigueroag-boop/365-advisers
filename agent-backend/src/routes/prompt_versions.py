"""
src/routes/prompt_versions.py
─────────────────────────────────────────────────────────────────────────────
REST API for prompt version management — list, rollback, diff.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.prompt_registry import get_prompt_registry

router = APIRouter(prefix="/prompts", tags=["Prompt Versioning"])
_registry = get_prompt_registry()


class RegisterPromptRequest(BaseModel):
    agent_name: str
    prompt_text: str
    model: str = "gemini-2.5-pro"
    metadata: dict = {}


class RollbackRequest(BaseModel):
    version: int


@router.get("/agents", summary="List all registered agents")
async def list_agents():
    return _registry.list_agents()


@router.get("/{agent_name}/versions", summary="List all versions for an agent")
async def list_versions(agent_name: str):
    versions = _registry.list_versions(agent_name)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    return [v.model_dump() for v in versions]


@router.get("/{agent_name}/active", summary="Get active prompt version")
async def get_active(agent_name: str):
    active = _registry.get_active(agent_name)
    if not active:
        raise HTTPException(status_code=404, detail=f"No active version for {agent_name}")
    return active.model_dump()


@router.get("/{agent_name}/version/{version}", summary="Get specific version")
async def get_version(agent_name: str, version: int):
    v = _registry.get_version(agent_name, version)
    if not v:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    return v.model_dump()


@router.post("/register", summary="Register a new prompt version")
async def register_prompt(request: RegisterPromptRequest):
    pv = _registry.register(
        agent_name=request.agent_name,
        prompt_text=request.prompt_text,
        model=request.model,
        metadata=request.metadata,
    )
    return {
        "agent_name": pv.agent_name,
        "version": pv.version,
        "sha256": pv.sha256,
        "is_active": pv.is_active,
    }


@router.post("/{agent_name}/rollback", summary="Rollback to a specific version")
async def rollback(agent_name: str, request: RollbackRequest):
    result = _registry.rollback(agent_name, request.version)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Version {request.version} not found for {agent_name}",
        )
    return {
        "agent_name": result.agent_name,
        "rolled_back_to": result.version,
        "sha256": result.sha256,
    }


@router.get("/{agent_name}/diff/{from_v}/{to_v}", summary="Diff between versions")
async def diff_versions(agent_name: str, from_v: int, to_v: int):
    result = _registry.diff(agent_name, from_v, to_v)
    if not result:
        raise HTTPException(status_code=404, detail="Version(s) not found")
    return result.model_dump()
