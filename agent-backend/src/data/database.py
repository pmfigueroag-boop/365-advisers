"""
src/data/database.py
─────────────────────────────────────────────────────────────────────────────
Persistence layer using SQLAlchemy (sync engine).
Supports PostgreSQL (recommended) and SQLite (dev fallback).

Tables:
  fundamental_analyses  — full snapshots, 24h cache backing
  technical_analyses    — full snapshots, 15min cache backing
  score_history         — time-series of scores for charts
  (+ 13 more tables for engines, backtesting, signals, etc.)

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
    Boolean, Column, Integer, Float, String, Text, DateTime,
    Index, create_engine, text, ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, relationship


# ─── Database setup ───────────────────────────────────────────────────────────

def _build_engine():
    """Create the SQLAlchemy engine from DATABASE_URL config.

    For PostgreSQL: enables connection pooling for multi-user concurrency.
    For SQLite: uses NullPool (no pooling, as SQLite is single-writer).
    """
    from src.config import get_settings
    url = get_settings().DATABASE_URL

    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        # SQLite fallback for local dev
        return create_engine(
            url, echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL with connection pool
        return create_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
        )


ENGINE = _build_engine()
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# ─── Models ───────────────────────────────────────────────────────────────────

class FundamentalAnalysis(Base):
    __tablename__ = "fundamental_analyses"
    __table_args__ = (
        Index("idx_fund_ticker_date", "ticker", "analyzed_at"),
    )

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
    __table_args__ = (
        Index("idx_tech_ticker_date", "ticker", "interval", "analyzed_at"),
    )

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
    __table_args__ = (
        Index("idx_score_history", "ticker", "analysis_type", "recorded_at"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    ticker          = Column(String(16), nullable=False, index=True)
    analysis_type   = Column(String(15), nullable=False)  # fundamental | technical
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
    __table_args__ = (
        Index("idx_ideas_status_priority", "status", "priority"),
        Index("idx_ideas_ticker", "ticker", "generated_at"),
    )

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
    __table_args__ = (
        Index("idx_signal_snapshots_ticker", "ticker", "evaluated_at"),
        Index("idx_signal_snapshots_category", "ticker", "category", "evaluated_at"),
    )

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
    __table_args__ = (
        Index("idx_composite_alpha_ticker", "ticker", "evaluated_at"),
    )

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
    __table_args__ = (
        Index("idx_signal_activations_ticker", "ticker", "is_expired"),
        Index("idx_signal_activations_signal", "signal_id", "ticker", "is_expired"),
    )

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    signal_id          = Column(String(64), nullable=False)
    ticker             = Column(String(16), nullable=False, index=True)
    activated_at       = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    deactivated_at     = Column(DateTime, nullable=True)
    initial_strength   = Column(String(10), default="weak")
    initial_confidence = Column(Float, default=0.0)
    category           = Column(String(20), nullable=False)
    half_life_days     = Column(Float, nullable=False, default=30.0)
    is_expired         = Column(Boolean, default=False)


# ─── Backtesting Tables ──────────────────────────────────────────────────────

class BacktestRun(Base):
    """Persisted metadata for a single backtesting run."""
    __tablename__ = "backtest_runs"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    run_id           = Column(String(36), nullable=False, unique=True, index=True)
    universe_json    = Column(Text, nullable=False)           # JSON list of tickers
    start_date       = Column(String(10), nullable=False)     # ISO date
    end_date         = Column(String(10), nullable=False)
    signal_count     = Column(Integer, default=0)
    status           = Column(String(20), default="pending")  # pending|running|completed|failed
    execution_time_s = Column(Float, default=0.0)
    config_json      = Column(Text, default="{}")             # Full BacktestConfig
    calibration_json = Column(Text, default="[]")             # CalibrationSuggestion list
    error_message    = Column(Text)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to results
    results          = relationship("BacktestResult", back_populates="run", cascade="all, delete-orphan")


class BacktestResult(Base):
    """Persisted per-signal performance results from a backtest run."""
    __tablename__ = "backtest_results"
    __table_args__ = (
        Index("idx_backtest_results_run", "run_id", "signal_id"),
        Index("idx_backtest_results_signal", "signal_id", "created_at"),
    )

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    run_id                   = Column(String(36), ForeignKey("backtest_runs.run_id"), nullable=False, index=True)
    signal_id                = Column(String(50), nullable=False)
    signal_name              = Column(String(100))
    category                 = Column(String(20))
    total_firings            = Column(Integer, default=0)
    hit_rate_json            = Column(Text, default="{}")     # {window: rate}
    avg_return_json          = Column(Text, default="{}")
    avg_excess_return_json   = Column(Text, default="{}")
    median_return_json       = Column(Text, default="{}")
    sharpe_json              = Column(Text, default="{}")
    sortino_json             = Column(Text, default="{}")
    max_drawdown             = Column(Float, default=0.0)
    empirical_half_life      = Column(Float)
    optimal_hold_period      = Column(Integer)
    alpha_decay_curve_json   = Column(Text, default="[]")     # 60-element array
    t_statistic_json         = Column(Text, default="{}")
    p_value_json             = Column(Text, default="{}")
    confidence_level         = Column(String(10), default="LOW")
    sample_size              = Column(Integer, default=0)
    universe_size            = Column(Integer, default=0)
    date_range               = Column(String(50))
    created_at               = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship back to run
    run                      = relationship("BacktestRun", back_populates="results")


class SignalPerformanceEventRecord(Base):
    """Persisted individual signal firing with forward returns."""
    __tablename__ = "signal_performance_events"
    __table_args__ = (
        Index("idx_perf_events_signal_ticker", "signal_id", "ticker", "fired_date"),
        Index("idx_perf_events_ticker", "ticker", "fired_date"),
    )

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    signal_id             = Column(String(50), nullable=False, index=True)
    signal_name           = Column(String(100))
    ticker                = Column(String(16), nullable=False, index=True)
    fired_date            = Column(String(10), nullable=False)         # ISO date
    strength              = Column(String(10), nullable=False)         # strong|moderate|weak
    confidence            = Column(Float, default=0.0)                 # 0.0–1.0
    value                 = Column(Float)                              # Feature value at fire
    price_at_fire         = Column(Float)
    forward_returns_json  = Column(Text, default="{}")                 # {window: return}
    benchmark_returns_json= Column(Text, default="{}")
    excess_returns_json   = Column(Text, default="{}")
    run_id                = Column(String(36), ForeignKey("backtest_runs.run_id"), index=True)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SignalCalibrationHistoryRecord(Base):
    """Audit trail for signal parameter recalibrations."""
    __tablename__ = "signal_calibration_history"
    __table_args__ = (
        Index("idx_calibration_signal", "signal_id", "applied_at"),
    )

    id            = Column(Integer, primary_key=True, autoincrement=True)
    signal_id     = Column(String(50), nullable=False, index=True)
    parameter     = Column(String(20), nullable=False)    # threshold|weight|half_life
    old_value     = Column(Float, nullable=False)
    new_value     = Column(Float, nullable=False)
    evidence      = Column(Text)
    run_id        = Column(String(36))                    # Backtest run that produced this
    applied_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    applied_by    = Column(String(20), default="auto")    # auto|manual



class OpportunityAlertRecord(Base):
    """Persistent store for opportunity monitoring alerts."""
    __tablename__ = "opportunity_alerts"
    __table_args__ = (
        Index("idx_opp_alerts_ticker", "ticker", "created_at"),
        Index("idx_opp_alerts_severity", "severity", "read", "created_at"),
    )

    id          = Column(String(64), primary_key=True)
    ticker      = Column(String(16), nullable=False, index=True)
    alert_type  = Column(String(30), nullable=False)
    severity    = Column(String(20), nullable=False)
    title       = Column(String(200))
    description = Column(Text)
    prev_value  = Column(Float)
    curr_value  = Column(Float)
    delta       = Column(Float)
    new_signals = Column(Text)          # JSON list
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    read        = Column(Boolean, default=False)


# ─── Create tables ────────────────────────────────────────────────────────────

def init_db():
    """Call once at startup to create all tables and declarative indexes."""
    Base.metadata.create_all(ENGINE)
    db_type = "PostgreSQL" if "postgresql" in str(ENGINE.url) else "SQLite"
    print(f"[DB] Database initialised ({db_type}) — {ENGINE.url.database}")


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
