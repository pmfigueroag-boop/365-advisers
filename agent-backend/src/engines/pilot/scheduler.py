"""
src/engines/pilot/scheduler.py
─────────────────────────────────────────────────────────────────────────────
PilotScheduler — Automated daily cycle execution.

Uses APScheduler to trigger PilotRunner.run_daily_cycle() at 17:00 ET
on market days (Mon-Fri, excluding US market holidays).

Integrates with FastAPI via lifespan context manager.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("365advisers.pilot.scheduler")

# ── Market holiday list (2026 US market holidays) ──────────────────────────

_US_MARKET_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}


def is_market_day(dt: datetime | None = None) -> bool:
    """Check if a given date is a US market trading day."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    # Weekend check
    if dt.weekday() >= 5:
        return False
    # Holiday check
    date_str = dt.strftime("%Y-%m-%d")
    return date_str not in _US_MARKET_HOLIDAYS_2026


class PilotScheduler:
    """
    Manages automated daily execution of the pilot cycle.

    Usage:
        scheduler = PilotScheduler()
        scheduler.start()        # Begin scheduled execution
        scheduler.stop()         # Stop scheduler
        scheduler.run_now()      # Manually trigger a cycle
    """

    def __init__(self) -> None:
        self._scheduler: Any = None
        self._running = False
        self._last_run: datetime | None = None
        self._last_result: dict | None = None

    def start(self) -> None:
        """Start the APScheduler with a daily trigger at 17:00 ET."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.warning(
                "APScheduler not installed. Run: pip install apscheduler. "
                "Daily scheduler will not start — use manual /pilot/{id}/run endpoint."
            )
            return

        if self._running:
            logger.info("Pilot scheduler already running.")
            return

        self._scheduler = BackgroundScheduler(timezone="US/Eastern")
        self._scheduler.add_job(
            self._daily_job,
            trigger=CronTrigger(
                hour=17, minute=0,
                day_of_week="mon-fri",
                timezone="US/Eastern",
            ),
            id="pilot_daily_cycle",
            name="Pilot Daily Cycle",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("✅ Pilot scheduler started — daily cycle at 17:00 ET (Mon-Fri)")

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Pilot scheduler stopped.")

    def run_now(self) -> dict:
        """
        Manually trigger a daily cycle right now (bypasses schedule).
        Returns the cycle result dict.
        """
        return self._daily_job()

    def _daily_job(self) -> dict:
        """
        Execute the daily pilot cycle.
        Checks for market day, finds active pilot, runs cycle.
        """
        from .runner import PilotRunner

        now = datetime.now(timezone.utc)

        # Skip non-market days
        if not is_market_day(now):
            logger.info(f"Skipping pilot cycle — {now.strftime('%A %Y-%m-%d')} is not a market day.")
            return {"skipped": True, "reason": "non_market_day"}

        runner = PilotRunner()

        # Find active pilot
        active = runner.get_active_pilot()
        if not active:
            logger.warning("No active pilot found. Skipping daily cycle.")
            return {"skipped": True, "reason": "no_active_pilot"}

        pilot_id = active.pilot_id

        logger.info(f"🚀 Starting daily pilot cycle for {pilot_id} (phase: {active.phase})")
        start = datetime.now(timezone.utc)

        try:
            result = runner.run_daily_cycle(pilot_id)
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            self._last_run = now
            self._last_result = result

            logger.info(
                f"✅ Daily cycle completed in {duration:.1f}s — "
                f"signals: {result.get('signals_count', 0)}, "
                f"ideas: {result.get('ideas_count', 0)}, "
                f"alerts: {result.get('alerts_count', 0)}"
            )
            return result

        except Exception as e:
            logger.error(f"❌ Daily cycle failed: {e}", exc_info=True)
            return {"error": str(e)}

    @property
    def status(self) -> dict:
        """Return scheduler status for monitoring."""
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "last_result_summary": (
                {k: v for k, v in (self._last_result or {}).items()
                 if k in ("signals_count", "ideas_count", "alerts_count", "error", "skipped")}
            ),
            "next_run": (
                str(self._scheduler.get_job("pilot_daily_cycle").next_run_time)
                if self._scheduler and self._running
                else None
            ),
        }


# ── Singleton ──────────────────────────────────────────────────────────────

_scheduler_instance: PilotScheduler | None = None


def get_pilot_scheduler() -> PilotScheduler:
    """Get or create the singleton scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = PilotScheduler()
    return _scheduler_instance


# ── FastAPI Lifespan Integration ───────────────────────────────────────────

@asynccontextmanager
async def pilot_scheduler_lifespan(app: Any):
    """
    FastAPI lifespan context manager that starts/stops the pilot scheduler.

    Usage in main.py:
        from src.engines.pilot.scheduler import pilot_scheduler_lifespan
        app = FastAPI(lifespan=pilot_scheduler_lifespan)
    """
    scheduler = get_pilot_scheduler()
    scheduler.start()
    logger.info("Pilot scheduler integrated with FastAPI lifespan.")
    yield
    scheduler.stop()
    logger.info("Pilot scheduler shut down with FastAPI.")
