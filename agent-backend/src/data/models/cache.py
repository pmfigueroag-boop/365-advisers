"""
src/data/models/cache.py
─────────────────────────────────────────────────────────────────────────────
DB-backed cache classes for fundamental and technical analysis results.
Drop-in replacements for in-memory caches.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from src.data.models.base import SessionLocal
from src.data.models.analysis import (
    FundamentalAnalysis,
    TechnicalAnalysis,
    ScoreHistory,
)


class FundamentalDBCache:
    """
    Drop-in replacement for the in-memory FundamentalCache.
    Persists results to DB so they survive server restarts.
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
            ratios_json=json.dumps(data_ready),
            research_memo=research,
            expires_at=expires,
        )

        with SessionLocal() as db:
            db.add(row)
            db.commit()
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
            data_ready_payload = json.loads(row.ratios_json or "{}")
            if "ratios" not in data_ready_payload and data_ready_payload != {}:
                data_ready_payload = {"ticker": row.ticker, "ratios": data_ready_payload}
            elif "ticker" not in data_ready_payload:
                data_ready_payload["ticker"] = row.ticker
            events.append({"event": "data_ready", "data": data_ready_payload})
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
