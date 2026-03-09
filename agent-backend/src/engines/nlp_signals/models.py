"""
src/engines/nlp_signals/models.py — NLP signal contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    EARNINGS_CALL = "earnings_call"
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    PRESS_RELEASE = "press_release"
    ANALYST_REPORT = "analyst_report"


class SentimentResult(BaseModel):
    score: float = 0.0       # -1 (bearish) to +1 (bullish)
    magnitude: float = 0.0   # 0-1 strength
    positive_pct: float = 0.0
    negative_pct: float = 0.0
    neutral_pct: float = 0.0


class KeyPhrase(BaseModel):
    phrase: str
    category: str = ""      # risk, guidance, growth, concern
    sentiment: float = 0.0
    frequency: int = 1


class NLPSignal(BaseModel):
    ticker: str
    document_type: DocumentType
    signal: float = 0.0      # -1 to +1
    confidence: float = 0.0
    sentiment: SentimentResult = Field(default_factory=SentimentResult)
    key_phrases: list[KeyPhrase] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    tone_change: float = 0.0  # vs previous period
    readability_score: float = 0.0
    word_count: int = 0


class FilingAnalysis(BaseModel):
    ticker: str
    document_type: DocumentType
    sections: dict[str, SentimentResult] = Field(default_factory=dict)
    management_tone: float = 0.0   # -1 to +1
    risk_factor_count: int = 0
    new_risk_factors: list[str] = Field(default_factory=list)
    guidance_sentiment: float = 0.0
    litigation_mentions: int = 0
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
