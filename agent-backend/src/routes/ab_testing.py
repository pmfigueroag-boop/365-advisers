"""
src/routes/ab_testing.py
─────────────────────────────────────────────────────────────────────────────
REST API for LLM A/B testing experiments.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.services.ab_testing import (
    get_ab_engine,
    PromptVariant,
)

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/experiments", tags=["LLM A/B Testing"], dependencies=[Depends(get_current_user)])
_engine = get_ab_engine()


class CreateExperimentRequest(BaseModel):
    name: str
    description: str = ""
    variants: list[dict] = Field(
        ...,
        min_length=2,
        description="Each dict needs: name, prompt_template, and optionally model",
    )
    traffic_split: list[float] | None = None


class RecordOutcomeRequest(BaseModel):
    variant_id: str
    ticker: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    quality_score: float = 0.0
    success: bool = True
    metadata: dict = Field(default_factory=dict)


@router.post("/", summary="Create a new A/B experiment")
async def create_experiment(request: CreateExperimentRequest):
    variants = [PromptVariant(**v) for v in request.variants]
    exp = _engine.create_experiment(
        name=request.name,
        description=request.description,
        variants=variants,
        traffic_split=request.traffic_split,
    )
    return {
        "experiment_id": exp.experiment_id,
        "name": exp.name,
        "variants": len(exp.variants),
        "status": exp.status,
    }


@router.get("/", summary="List all experiments")
async def list_experiments(status: str | None = None):
    return [s.model_dump() for s in _engine.list_experiments(status)]


@router.get("/{experiment_id}", summary="Get experiment results")
async def get_experiment(experiment_id: str):
    result = _engine.get_results(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result.model_dump()


@router.get("/{experiment_id}/select", summary="Select a variant for a run")
async def select_variant(experiment_id: str, seed: str = ""):
    variant = _engine.select_variant(experiment_id, seed)
    if not variant:
        raise HTTPException(status_code=404, detail="Experiment not found or not active")
    return variant.model_dump()


@router.post("/{experiment_id}/outcome", summary="Record an experiment outcome")
async def record_outcome(experiment_id: str, request: RecordOutcomeRequest):
    ok = _engine.record_outcome(
        experiment_id=experiment_id,
        variant_id=request.variant_id,
        ticker=request.ticker,
        latency_ms=request.latency_ms,
        tokens_used=request.tokens_used,
        quality_score=request.quality_score,
        success=request.success,
        metadata=request.metadata,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"recorded": True}


@router.post("/{experiment_id}/complete", summary="Complete experiment and determine winner")
async def complete_experiment(experiment_id: str):
    result = _engine.complete_experiment(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return result.model_dump()


@router.post("/{experiment_id}/pause", summary="Pause an experiment")
async def pause_experiment(experiment_id: str):
    if not _engine.pause_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {"paused": True}


@router.post("/{experiment_id}/resume", summary="Resume a paused experiment")
async def resume_experiment(experiment_id: str):
    if not _engine.resume_experiment(experiment_id):
        raise HTTPException(status_code=404, detail="Experiment not found or not paused")
    return {"resumed": True}
