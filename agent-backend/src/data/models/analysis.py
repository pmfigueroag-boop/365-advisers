"""
src/data/models/analysis.py
─────────────────────────────────────────────────────────────────────────────
Core analysis storage models: fundamental, technical, score history.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Index

from src.data.models.base import Base


class FundamentalAnalysis(Base):
    __tablename__ = "fundamental_analyses"
    __table_args__ = (
        Index("idx_fund_ticker_date", "ticker", "analyzed_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analyzed_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    signal          = Column(String(10))
    score           = Column(Float)
    confidence      = Column(Float)
    risk_adj_score  = Column(Float)
    allocation      = Column(String(30))
    committee_json  = Column(Text)
    agent_memos_json= Column(Text)
    ratios_json     = Column(Text)
    research_memo   = Column(Text)
    expires_at      = Column(Float)


class TechnicalAnalysis(Base):
    __tablename__ = "technical_analyses"
    __table_args__ = (
        Index("idx_tech_ticker_date", "ticker", "interval", "analyzed_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    interval        = Column(String(8), default="1D")
    analyzed_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    signal          = Column(String(20))
    technical_score = Column(Float)
    trend_status    = Column(String(20))
    momentum_status = Column(String(20))
    signal_strength = Column(String(10))
    summary_json    = Column(Text)
    indicators_json = Column(Text)
    expires_at      = Column(Float)


class ScoreHistory(Base):
    __tablename__ = "score_history"
    __table_args__ = (
        Index("idx_score_history", "ticker", "analysis_type", "recorded_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analysis_type   = Column(String(15), nullable=False)
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    score           = Column(Float)
    signal          = Column(String(20))


class OpportunityScoreHistory(Base):
    __tablename__ = "opportunity_score_history"
    __table_args__ = (
        Index("idx_opp_score_history", "ticker", "recorded_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    opportunity_score = Column(Float)
    business_quality  = Column(Float)
    valuation         = Column(Float)
    financial_strength= Column(Float)
    market_behavior   = Column(Float)
    score_breakdown_json = Column(Text)
