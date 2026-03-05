"""
src/data/database.py
─────────────────────────────────────────────────────────────────────────────
SQLite persistence layer using SQLAlchemy (sync engine for simplicity).

Tables:
  fundamental_analyses  — full snapshots, 24h cache backing
  technical_analyses    — full snapshots, 15min cache backing
  score_history         — time-series of scores for charts

The DB-backed cache classes (FundamentalDBCache, TechnicalDBCache) expose
the same .get()/.set()/.invalidate() interface as the in-memory caches,
making them drop-in replacements in main.py.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, create_engine, text, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, relationship


# ─── Database setup ───────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent.parent / "advisers.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ─── Models ───────────────────────────────────────────────────────────────────

class FundamentalAnalysis(Base):
    __tablename__ = "fundamental_analyses"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analyzed_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    signal          = Column(String(10))            # BUY | SELL | HOLD
    score           = Column(Float)                 # 0–10
    confidence      = Column(Float)
    risk_adj_score  = Column(Float)
    allocation      = Column(String(30))
    committee_json  = Column(Text)                  # CommitteeOutput dict
    agent_memos_json= Column(Text)                  # list of AgentMemo
    ratios_json     = Column(Text)                  # fundamental ratios snapshot
    research_memo   = Column(Text)                  # 1-pager markdown
    expires_at      = Column(Float)                 # Unix timestamp


class TechnicalAnalysis(Base):
    __tablename__ = "technical_analyses"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    interval        = Column(String(8), default="1D")
    analyzed_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    signal          = Column(String(20))            # STRONG_BUY … STRONG_SELL
    technical_score = Column(Float)
    trend_status    = Column(String(20))
    momentum_status = Column(String(20))
    signal_strength = Column(String(10))
    summary_json    = Column(Text)                  # full TechnicalSummary
    indicators_json = Column(Text)                  # raw indicator snapshot
    expires_at      = Column(Float)


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analysis_type   = Column(String(15), nullable=False)  # fundamental | technical
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    score           = Column(Float)
    signal          = Column(String(20))


class OpportunityScoreHistory(Base):
    __tablename__ = "opportunity_score_history"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    recorded_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    opportunity_score = Column(Float)               # 0-10
    business_quality  = Column(Float)               # 0-10
    valuation         = Column(Float)               # 0-10
    financial_strength= Column(Float)               # 0-10
    market_behavior   = Column(Float)               # 0-10
    score_breakdown_json = Column(Text)             # Full 12-factor JSON payload


class Portfolio(Base):
    __tablename__ = "portfolios"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    name             = Column(String(100), nullable=False)
    strategy         = Column(String(100))
    risk_level       = Column(String(50))
    total_allocation = Column(Float)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to positions
    positions        = relationship("PortfolioPosition", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id     = Column(Integer, ForeignKey("portfolios.id"), nullable=False, index=True)
    ticker           = Column(String(16), nullable=False)
    target_weight    = Column(Float, nullable=False)
    role             = Column(String(20))           # CORE | SATELLITE
    sector           = Column(String(100))
    volatility_atr   = Column(Float)

    # Relationship back to Portfolio
    portfolio        = relationship("Portfolio", back_populates="positions")


class IdeaRecord(Base):
    """Persisted investment idea generated by the Idea Generation Engine."""
    __tablename__ = "ideas"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    idea_uid         = Column(String(16), nullable=False, unique=True)
    ticker           = Column(String(16), nullable=False, index=True)
    name             = Column(String(200), default="")
    sector           = Column(String(100), default="")
    idea_type        = Column(String(20), nullable=False)   # value|quality|momentum|reversal|event
    confidence       = Column(String(10), nullable=False)   # high|medium|low
    signal_strength  = Column(Float, nullable=False)
    priority         = Column(Integer, nullable=False, default=0)
    signals_json     = Column(Text, nullable=False)         # JSON array of SignalDetail
    status           = Column(String(20), default="active") # active|analyzed|dismissed
    generated_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at       = Column(DateTime)
    analyzed_at      = Column(DateTime)                     # set when user runs full analysis
    metadata_json    = Column(Text, default="{}")


class SignalSnapshot(Base):
    """Persisted alpha signal evaluation snapshot for a single ticker."""
    __tablename__ = "signal_snapshots"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    ticker            = Column(String(16), nullable=False, index=True)
    evaluated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    category          = Column(String(20), nullable=False)       # value|quality|momentum|...
    signals_json      = Column(Text, nullable=False)             # JSON array of EvaluatedSignal
    composite_strength= Column(Float, nullable=False, default=0.0)
    confidence        = Column(String(10), nullable=False)       # high|medium|low
    fired_count       = Column(Integer, default=0)
    total_count       = Column(Integer, default=0)
    scan_id           = Column(String(20))                       # Optional reference to IGE scan


class CompositeAlphaHistory(Base):
    """Persisted Composite Alpha Score for historical tracking."""
    __tablename__ = "composite_alpha_history"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    score           = Column(Float, nullable=False)
    environment     = Column(String(30), nullable=False)
    subscores_json  = Column(Text, nullable=False)           # JSON blob of category subscores
    active_categories = Column(Integer, default=0)
    conflicts_json  = Column(Text, default="[]")             # JSON array of conflict descriptions
    evaluated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class SignalActivationRecord(Base):
    """Persisted activation timestamps for the Alpha Decay engine."""
    __tablename__ = "signal_activations"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    signal_id          = Column(String(64), nullable=False)
    ticker             = Column(String(16), nullable=False, index=True)
    activated_at       = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    deactivated_at     = Column(DateTime, nullable=True)
    initial_strength   = Column(String(10), default="weak")
    initial_confidence = Column(Float, default=0.0)
    category           = Column(String(20), nullable=False)
    half_life_days     = Column(Float, nullable=False, default=30.0)
    is_expired         = Column(Integer, default=0)  # SQLite boolean


# ─── Create tables ────────────────────────────────────────────────────────────

def init_db():
    """Call once at startup to create all tables if they don't exist."""
    Base.metadata.create_all(ENGINE)
    # Add index for fast ticker+date queries
    with ENGINE.connect() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_fund_ticker_date "
            "ON fundamental_analyses(ticker, analyzed_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_tech_ticker_date "
            "ON technical_analyses(ticker, interval, analyzed_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_score_history "
            "ON score_history(ticker, analysis_type, recorded_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_opp_score_history "
            "ON opportunity_score_history(ticker, recorded_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ideas_status_priority "
            "ON ideas(status, priority)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ideas_ticker "
            "ON ideas(ticker, generated_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_signal_snapshots_ticker "
            "ON signal_snapshots(ticker, evaluated_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_signal_snapshots_category "
            "ON signal_snapshots(ticker, category, evaluated_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_composite_alpha_ticker "
            "ON composite_alpha_history(ticker, evaluated_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_signal_activations_ticker "
            "ON signal_activations(ticker, is_expired)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_signal_activations_signal "
            "ON signal_activations(signal_id, ticker, is_expired)"
        ))
        conn.commit()
    print(f"[DB] Database initialised at {DB_PATH}")


# ─── DB-backed Fundamental Cache ──────────────────────────────────────────────

class FundamentalDBCache:
    """
    Drop-in replacement for the in-memory FundamentalCache.
    Persists results to SQLite so they survive server restarts.
    TTL: 24 hours
    """
    TTL = 86_400  # seconds

    def get(self, ticker: str) -> dict | None:
        symbol = ticker.upper()
        now = time.time()
        with SessionLocal() as db:
            row = (
                db.query(FundamentalAnalysis)
                .filter(
                    FundamentalAnalysis.ticker == symbol,
                    FundamentalAnalysis.expires_at > now,
                )
                .order_by(FundamentalAnalysis.analyzed_at.desc())
                .first()
            )
            if not row:
                return None
            print(f"[FUND-DB-CACHE] HIT for {symbol}")
            return self._row_to_events(row)

    def set(self, ticker: str, data: dict):
        """data = {events: [...]} — the same format as in-memory cache."""
        symbol = ticker.upper()
        events = data.get("events", [])
        expires = time.time() + self.TTL

        # Extract key fields from events for indexed columns
        committee = next(
            (e["data"] for e in events if e["event"] == "committee_verdict"), {}
        )
        data_ready = next(
            (e["data"] for e in events if e["event"] == "data_ready"), {}
        )
        agent_memos = [e["data"] for e in events if e["event"] == "agent_memo"]
        research = next(
            (e["data"].get("memo", "") for e in events if e["event"] == "research_memo"), ""
        )

        row = FundamentalAnalysis(
            ticker=symbol,
            signal=committee.get("signal"),
            score=committee.get("score"),
            confidence=committee.get("confidence"),
            risk_adj_score=committee.get("risk_adjusted_score"),
            allocation=committee.get("allocation_recommendation"),
            committee_json=json.dumps(committee),
            agent_memos_json=json.dumps(agent_memos),
            ratios_json=json.dumps(data_ready.get("ratios", {})),
            research_memo=research,
            expires_at=expires,
        )

        with SessionLocal() as db:
            db.add(row)
            db.commit()
            # Append to score history
            if committee.get("score") is not None:
                db.add(ScoreHistory(
                    ticker=symbol,
                    analysis_type="fundamental",
                    score=committee["score"],
                    signal=committee.get("signal"),
                ))
                db.commit()

        print(f"[FUND-DB-CACHE] Stored {symbol} (TTL {self.TTL}s, expires {datetime.fromtimestamp(expires).isoformat()})")

    def invalidate(self, ticker: str) -> bool:
        symbol = ticker.upper()
        with SessionLocal() as db:
            deleted = (
                db.query(FundamentalAnalysis)
                .filter(FundamentalAnalysis.ticker == symbol)
                .delete()
            )
            db.commit()
        return deleted > 0

    def status(self) -> list[dict]:
        now = time.time()
        with SessionLocal() as db:
            rows = (
                db.query(FundamentalAnalysis)
                .filter(FundamentalAnalysis.expires_at > now)
                .all()
            )
            return [
                {
                    "ticker": r.ticker,
                    "signal": r.signal,
                    "score": r.score,
                    "age_s": round(now - r.analyzed_at.timestamp()) if r.analyzed_at else None,
                    "expires_in_s": round(r.expires_at - now),
                }
                for r in rows
            ]

    @staticmethod
    def _row_to_events(row: FundamentalAnalysis) -> dict:
        """Reconstruct the events list from a DB row."""
        events = []
        try:
            ratios = json.loads(row.ratios_json or "{}")
            events.append({"event": "data_ready", "data": {"ticker": row.ticker, "ratios": ratios}})
        except Exception:
            pass

        try:
            memos = json.loads(row.agent_memos_json or "[]")
            for m in memos:
                events.append({"event": "agent_memo", "data": m})
        except Exception:
            pass

        try:
            committee = json.loads(row.committee_json or "{}")
            events.append({"event": "committee_verdict", "data": committee})
        except Exception:
            pass

        if row.research_memo:
            events.append({"event": "research_memo", "data": {"memo": row.research_memo}})

        return {"events": events}


# ─── DB-backed Technical Cache ────────────────────────────────────────────────

class TechnicalDBCache:
    """
    Drop-in replacement for in-memory TechnicalCache.
    TTL: 15 minutes
    """
    TTL = 900  # seconds

    def get(self, ticker: str) -> dict | None:
        symbol = ticker.upper()
        now = time.time()
        with SessionLocal() as db:
            row = (
                db.query(TechnicalAnalysis)
                .filter(
                    TechnicalAnalysis.ticker == symbol,
                    TechnicalAnalysis.expires_at > now,
                )
                .order_by(TechnicalAnalysis.analyzed_at.desc())
                .first()
            )
            if not row:
                return None
            print(f"[TECH-DB-CACHE] HIT for {symbol}")
            try:
                return json.loads(row.summary_json or "{}")
            except Exception:
                return None

    def set(self, ticker: str, data: dict):
        symbol = ticker.upper()
        expires = time.time() + self.TTL
        summary = data.get("summary", {})

        row = TechnicalAnalysis(
            ticker=symbol,
            signal=summary.get("signal"),
            technical_score=summary.get("technical_score"),
            trend_status=summary.get("trend_status"),
            momentum_status=summary.get("momentum_status"),
            signal_strength=summary.get("signal_strength"),
            summary_json=json.dumps(data),
            indicators_json=json.dumps(data.get("indicators", {})),
            expires_at=expires,
        )

        with SessionLocal() as db:
            db.add(row)
            db.commit()
            # Append to score history
            score = summary.get("technical_score")
            if score is not None:
                db.add(ScoreHistory(
                    ticker=symbol,
                    analysis_type="technical",
                    score=score,
                    signal=summary.get("signal"),
                ))
                db.commit()

        print(f"[TECH-DB-CACHE] Stored {symbol} (TTL {self.TTL}s)")

    def invalidate(self, ticker: str) -> bool:
        symbol = ticker.upper()
        with SessionLocal() as db:
            deleted = (
                db.query(TechnicalAnalysis)
                .filter(TechnicalAnalysis.ticker == symbol)
                .delete()
            )
            db.commit()
        return deleted > 0

    def status(self) -> list[dict]:
        now = time.time()
        with SessionLocal() as db:
            rows = (
                db.query(TechnicalAnalysis)
                .filter(TechnicalAnalysis.expires_at > now)
                .all()
            )
            return [
                {
                    "ticker": r.ticker,
                    "signal": r.signal,
                    "score": r.technical_score,
                    "age_s": round(now - r.analyzed_at.timestamp()) if r.analyzed_at else None,
                    "expires_in_s": round(r.expires_at - now),
                }
                for r in rows
            ]


# ─── Score History Queries ────────────────────────────────────────────────────

def get_score_history(ticker: str, analysis_type: str, limit: int = 90) -> list[dict]:
    """Return the last N score records for a ticker + analysis type."""
    symbol = ticker.upper()
    with SessionLocal() as db:
        rows = (
            db.query(ScoreHistory)
            .filter(
                ScoreHistory.ticker == symbol,
                ScoreHistory.analysis_type == analysis_type,
            )
            .order_by(ScoreHistory.recorded_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                "score": row.score,
                "signal": row.signal,
            }
            for row in reversed(rows)
        ]
