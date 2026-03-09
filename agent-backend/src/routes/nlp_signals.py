"""src/routes/nlp_signals.py — NLP Signal Extraction API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.engines.nlp_signals.models import DocumentType
from src.engines.nlp_signals.engine import NLPSignalEngine

router = APIRouter(prefix="/alpha/nlp", tags=["Alpha: NLP Signals"])

class AnalyseRequest(BaseModel):
    text: str
    ticker: str
    doc_type: DocumentType = DocumentType.EARNINGS_CALL

class CompareRequest(BaseModel):
    current_text: str
    previous_text: str
    ticker: str

class BatchRequest(BaseModel):
    documents: list[dict]

@router.post("/analyse")
async def analyse(req: AnalyseRequest):
    try:
        return NLPSignalEngine.analyse_document(req.text, req.ticker, req.doc_type).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/filing")
async def analyse_filing(req: AnalyseRequest):
    try:
        return NLPSignalEngine.analyse_filing(req.text, req.ticker, req.doc_type).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/compare")
async def compare(req: CompareRequest):
    return NLPSignalEngine.compare_periods(req.current_text, req.previous_text, req.ticker)

@router.post("/batch")
async def batch(req: BatchRequest):
    results = NLPSignalEngine.batch_analyse(req.documents)
    return {"results": [r.model_dump() for r in results]}
