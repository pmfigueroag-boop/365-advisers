"""
src/engines/alpha_decay/tracker.py
──────────────────────────────────────────────────────────────────────────────
Activation Tracker — persists signal activation timestamps in SQLite so
the Decay Engine can compute signal age across evaluations.

Activation logic:
  • Signal fires for the first time → INSERT new activation record
  • Signal continues firing → no action (preserve original activated_at)
  • Signal stops firing → mark deactivated_at
  • Signal re-fires after deactivation → INSERT new record (new life cycle)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal
from src.engines.alpha_signals.models import SignalProfile
from src.engines.alpha_decay.models import (
    DecayConfig,
    SignalActivation,
    DEFAULT_HALF_LIFE_DAYS,
)

logger = logging.getLogger("365advisers.alpha_decay.tracker")


class ActivationTracker:
    """
    SQLite-backed tracker for signal activation timestamps.

    Maintains an in-memory cache of active activations per ticker
    to avoid repeated DB queries during evaluation.

    Usage::

        tracker = ActivationTracker()
        tracker.update_activations(signal_profile)
        activation = tracker.get_activation("momentum.golden_cross", "MSFT")
    """

    def __init__(self, config: DecayConfig | None = None) -> None:
        self._config = config or DecayConfig()
        # In-memory cache: {(signal_id, ticker): SignalActivation}
        self._cache: dict[tuple[str, str], SignalActivation] = {}
        self._loaded_tickers: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────

    def get_activation(
        self,
        signal_id: str,
        ticker: str,
    ) -> SignalActivation | None:
        """
        Get the active activation record for a signal+ticker pair.

        Returns None if the signal has never fired for this ticker.
        """
        ticker = ticker.upper()
        key = (signal_id, ticker)

        # Ensure this ticker's activations are loaded
        if ticker not in self._loaded_tickers:
            self._load_ticker(ticker)

        return self._cache.get(key)

    def update_activations(self, profile: SignalProfile) -> None:
        """
        Update activation records based on a fresh SignalProfile evaluation.

        - New firings: create activation records
        - Continued firings: no action
        - Stopped firings: mark deactivated
        """
        ticker = profile.ticker.upper()

        # Ensure this ticker's activations are loaded
        if ticker not in self._loaded_tickers:
            self._load_ticker(ticker)

        now = datetime.now(timezone.utc)
        currently_fired = {
            sig.signal_id for sig in profile.signals if sig.fired
        }
        previously_active = {
            key[0] for key, act in self._cache.items()
            if key[1] == ticker and not act.is_expired
        }

        # ── Handle new firings ────────────────────────────────────────────
        new_signals = currently_fired - previously_active
        for signal_id in new_signals:
            sig = next(
                (s for s in profile.signals if s.signal_id == signal_id), None
            )
            if sig is None:
                continue

            hl = self._config.half_life_days.get(
                sig.category.value,
                DEFAULT_HALF_LIFE_DAYS.get(sig.category.value, 30.0),
            )

            activation = SignalActivation(
                signal_id=signal_id,
                ticker=ticker,
                activated_at=now,
                initial_strength=sig.strength,
                initial_confidence=sig.confidence,
                category=sig.category,
                half_life_days=hl,
                is_expired=False,
            )

            self._cache[(signal_id, ticker)] = activation
            self._persist_activation(activation)

            logger.debug(
                f"TRACKER: New activation {signal_id} for {ticker} "
                f"(hl={hl}d)"
            )

        # ── Handle deactivations ──────────────────────────────────────────
        deactivated = previously_active - currently_fired
        for signal_id in deactivated:
            key = (signal_id, ticker)
            if key in self._cache:
                self._cache[key].is_expired = True
                self._persist_deactivation(signal_id, ticker, now)

                logger.debug(
                    f"TRACKER: Deactivated {signal_id} for {ticker}"
                )

    def purge_expired(self, ticker: str, max_age_days: int = 30) -> int:
        """
        Remove expired activation records older than max_age_days.

        Returns the number of records purged.
        """
        ticker = ticker.upper()
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        purged = 0
        try:
            from src.data.database import SignalActivationRecord
            with SessionLocal() as db:
                purged = (
                    db.query(SignalActivationRecord)
                    .filter(
                        SignalActivationRecord.ticker == ticker,
                        SignalActivationRecord.is_expired == True,  # noqa: E712
                        SignalActivationRecord.activated_at < cutoff,
                    )
                    .delete()
                )
                db.commit()
        except Exception as e:
            logger.warning(f"TRACKER: Purge failed for {ticker}: {e}")

        # Clean in-memory cache
        to_remove = [
            key for key, act in self._cache.items()
            if key[1] == ticker and act.is_expired
            and act.activated_at < cutoff
        ]
        for key in to_remove:
            del self._cache[key]

        if purged > 0:
            logger.info(f"TRACKER: Purged {purged} expired activations for {ticker}")

        return purged

    def get_ticker_activations(self, ticker: str) -> list[SignalActivation]:
        """Get all active (non-expired) activations for a ticker."""
        ticker = ticker.upper()
        if ticker not in self._loaded_tickers:
            self._load_ticker(ticker)

        return [
            act for key, act in self._cache.items()
            if key[1] == ticker and not act.is_expired
        ]

    # ── Private helpers ───────────────────────────────────────────────────

    def _load_ticker(self, ticker: str) -> None:
        """Load all active activations for a ticker from the DB into cache."""
        try:
            from src.data.database import SignalActivationRecord
            with SessionLocal() as db:
                rows = (
                    db.query(SignalActivationRecord)
                    .filter(
                        SignalActivationRecord.ticker == ticker,
                        SignalActivationRecord.is_expired == False,  # noqa: E712
                    )
                    .all()
                )
                for row in rows:
                    activation = SignalActivation(
                        signal_id=row.signal_id,
                        ticker=row.ticker,
                        activated_at=row.activated_at,
                        initial_strength=row.initial_strength or "weak",
                        initial_confidence=row.initial_confidence or 0.0,
                        category=row.category,
                        half_life_days=row.half_life_days,
                        is_expired=row.is_expired,
                    )
                    self._cache[(row.signal_id, row.ticker)] = activation
        except Exception as e:
            logger.warning(f"TRACKER: Failed to load activations for {ticker}: {e}")

        self._loaded_tickers.add(ticker)

    def _persist_activation(self, activation: SignalActivation) -> None:
        """Persist a new activation record to the DB."""
        try:
            from src.data.database import SignalActivationRecord
            with SessionLocal() as db:
                record = SignalActivationRecord(
                    signal_id=activation.signal_id,
                    ticker=activation.ticker,
                    activated_at=activation.activated_at,
                    initial_strength=activation.initial_strength.value,
                    initial_confidence=activation.initial_confidence,
                    category=activation.category.value,
                    half_life_days=activation.half_life_days,
                    is_expired=False,
                )
                db.add(record)
                db.commit()
        except Exception as e:
            logger.warning(
                f"TRACKER: Failed to persist activation "
                f"{activation.signal_id}/{activation.ticker}: {e}"
            )

    def _persist_deactivation(
        self,
        signal_id: str,
        ticker: str,
        deactivated_at: datetime,
    ) -> None:
        """Mark a signal activation as deactivated in the DB."""
        try:
            from src.data.database import SignalActivationRecord
            with SessionLocal() as db:
                (
                    db.query(SignalActivationRecord)
                    .filter(
                        SignalActivationRecord.signal_id == signal_id,
                        SignalActivationRecord.ticker == ticker,
                        SignalActivationRecord.is_expired == False,  # noqa: E712
                    )
                    .update({
                        "is_expired": True,
                        "deactivated_at": deactivated_at,
                    })
                )
                db.commit()
        except Exception as e:
            logger.warning(
                f"TRACKER: Failed to deactivate {signal_id}/{ticker}: {e}"
            )
