"""src/routes/alt_data.py — Alternative Data API."""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.engines.alt_data.models import AltDataType
from src.engines.alt_data.engine import AltDataEngine

router = APIRouter(prefix="/alpha/alt-data", tags=["Alpha: Alternative Data"])

class AltDataRequest(BaseModel):
    ticker: str
    seed: int | None = None

class BatchRequest(BaseModel):
    tickers: list[str]
    seed: int | None = None

@router.post("/analyse")
async def analyse(req: AltDataRequest):
    return AltDataEngine.analyse(req.ticker, req.seed).model_dump()

@router.post("/batch")
async def batch(req: BatchRequest):
    reports = AltDataEngine.batch_analyse(req.tickers, req.seed)
    return {t: r.model_dump() for t, r in reports.items()}

@router.get("/sources")
async def list_sources():
    return {"sources": [t.value for t in AltDataType]}

@router.get("/source/{source_type}/{ticker}")
async def source_signal(source_type: str, ticker: str):
    try:
        dt = AltDataType(source_type)
    except ValueError:
        return {"error": f"Unknown source: {source_type}"}
    sig = AltDataEngine.get_source_signal(ticker, dt)
    return sig.model_dump() if sig else {"error": "Not found"}
