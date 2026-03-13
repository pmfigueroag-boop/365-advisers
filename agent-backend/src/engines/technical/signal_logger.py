"""
src/engines/technical/signal_logger.py
──────────────────────────────────────────────────────────────────────────────
Signal Logger — records technical analysis signals for backtesting.

Stores SignalRecords in-memory and optionally to a JSON-lines file.
Enables historical signal retrieval for forward return analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import logging

logger = logging.getLogger("365advisers.engines.technical.signal_logger")


@dataclass
class SignalRecord:
    """A single technical analysis signal emission."""
    ticker: str
    timestamp: str                          # ISO-8601
    signal: str                             # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
    score: float                            # 0–10
    setup_quality: float                    # 0–1
    confidence: float                       # 0–1
    regime: str                             # TRENDING, RANGING, VOLATILE, TRANSITIONING
    module_scores: dict[str, float] = field(default_factory=dict)  # module → score
    price_at_signal: float = 0.0
    bias: str = "NEUTRAL"                   # BULLISH, BEARISH, NEUTRAL
    position_sizing_pct: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0


class SignalLogger:
    """
    In-memory signal logger with optional file persistence.

    Usage:
        logger = SignalLogger()
        logger.log(SignalRecord(...))
        history = logger.get_history("AAPL", lookback_days=90)
    """

    def __init__(self, persist_path: str | None = None) -> None:
        self._buffer: list[SignalRecord] = []
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: SignalRecord) -> None:
        """Record a signal emission."""
        self._buffer.append(record)

        if self._persist_path:
            try:
                with open(self._persist_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(record)) + "\n")
            except Exception as exc:
                logger.error(f"SIGNAL_LOGGER: Failed to persist: {exc}")

    def get_history(
        self,
        ticker: str | None = None,
        lookback_days: int = 90,
    ) -> list[SignalRecord]:
        """Retrieve signal history, optionally filtered by ticker and time window."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        cutoff_str = cutoff.isoformat()

        results = []
        for record in self._buffer:
            if ticker and record.ticker != ticker:
                continue
            if record.timestamp >= cutoff_str:
                results.append(record)

        return results

    def get_all(self) -> list[SignalRecord]:
        """Return all logged signals."""
        return list(self._buffer)

    @property
    def count(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        """Clear the in-memory buffer."""
        self._buffer.clear()

    def load_from_file(self) -> int:
        """Load signals from persist file into memory. Returns count loaded."""
        if not self._persist_path or not self._persist_path.exists():
            return 0

        count = 0
        with open(self._persist_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._buffer.append(SignalRecord(**data))
                    count += 1
                except Exception:
                    continue
        return count
