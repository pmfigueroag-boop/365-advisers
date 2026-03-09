"""
src/routes/ml_signals.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the ML Signal Factory.

Provides:
  POST /alpha/ml/train           → Train a new ML model
  POST /alpha/ml/predict         → Generate ML signal for a ticker
  GET  /alpha/ml/models          → List all registered models
  GET  /alpha/ml/models/{id}     → Get model card
  POST /alpha/ml/deploy/{id}     → Deploy a model
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.ml_signals.engine import MLSignalFactory
from src.engines.ml_signals.models import MLModelConfig, ModelType

logger = logging.getLogger("365advisers.routes.ml_signals")

router = APIRouter(prefix="/alpha/ml", tags=["Alpha: ML Signals"])

# Shared factory instance
_factory = MLSignalFactory()


# ── Request schemas ──────────────────────────────────────────────────────────

class TrainRequest(BaseModel):
    features: list[list[float]] = Field(..., description="2D feature matrix")
    target: list[float] = Field(..., description="Target values (forward returns)")
    feature_names: list[str] = Field(default_factory=list)
    config: MLModelConfig = Field(default_factory=MLModelConfig)


class PredictRequest(BaseModel):
    ticker: str
    feature_vector: dict[str, float] = Field(
        default_factory=dict,
        description="Named feature values for prediction",
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/train")
async def train_model(req: TrainRequest):
    """Train a new ML model on provided data."""
    try:
        card = _factory.train_model(
            features=req.features,
            target=req.target,
            feature_names=req.feature_names or None,
            config=req.config,
        )
        return card.model_dump()
    except Exception as e:
        logger.error("ML train failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict_signal(req: PredictRequest):
    """Generate an ML signal for a ticker using the deployed model."""
    try:
        from src.engines.ml_signals.predictor import MLPredictor
        from src.engines.ml_signals.trainer import MLTrainer

        entry = _factory.registry.get_deployed()
        if not entry:
            raise HTTPException(status_code=404, detail="No deployed model found")

        model = _factory._models_cache.get(entry.card.model_id)
        if model is None and entry.model_bytes_b64:
            model = MLTrainer.deserialize_model(entry.model_bytes_b64)
            _factory._models_cache[entry.card.model_id] = model

        if model is None:
            raise HTTPException(status_code=500, detail="Model could not be loaded")

        fv = req.feature_vector.copy()
        fv["_ticker"] = req.ticker
        signal = MLPredictor.predict(model, fv, entry.card)
        signal.ticker = req.ticker
        return signal.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ML predict failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List all registered ML models."""
    try:
        cards = _factory.list_models()
        return {"models": [c.model_dump() for c in cards], "total": len(cards)}
    except Exception as e:
        logger.error("Model list failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """Get a specific model card."""
    card = _factory.registry.get_card(model_id)
    if not card:
        raise HTTPException(status_code=404, detail="Model not found")
    return card.model_dump()


@router.post("/deploy/{model_id}")
async def deploy_model(model_id: str):
    """Deploy a model to production (retires previous of same type)."""
    success = _factory.deploy_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found or not deployable")
    return {"status": "deployed", "model_id": model_id}
