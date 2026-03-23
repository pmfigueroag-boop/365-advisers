"""src/routes/dl_signals.py — Deep Learning Signals API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.engines.dl_signals.models import DLModelType, DLSignalConfig
from src.engines.dl_signals.engine import DLSignalEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/dl-signals", tags=["Alpha: DL Signals"], dependencies=[Depends(get_current_user)])

class DLSignalRequest(BaseModel):
    prices: dict[str, list[float]]
    model_type: DLModelType = DLModelType.LSTM
    lookback: int = 60
    horizon: int = 5
    epochs: int = 20
    hidden_size: int = 32

@router.post("/predict")
async def predict(req: DLSignalRequest):
    try:
        config = DLSignalConfig(
            model_type=req.model_type, lookback=req.lookback,
            horizon=req.horizon, epochs=req.epochs, hidden_size=req.hidden_size,
        )
        preds = DLSignalEngine.train_and_predict(req.prices, config)
        return {t: p.model_dump() for t, p in preds.items()}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/ensemble")
async def ensemble(req: DLSignalRequest):
    try:
        config = DLSignalConfig(
            lookback=req.lookback, horizon=req.horizon,
            epochs=req.epochs, hidden_size=req.hidden_size,
        )
        preds = DLSignalEngine.generate_ensemble(req.prices, config)
        return {t: p.model_dump() for t, p in preds.items()}
    except Exception as e:
        raise HTTPException(500, str(e))
