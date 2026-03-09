"""
src/data/external/scheduler.py
──────────────────────────────────────────────────────────────────────────────
Configurable Sync Engine for external data providers.

Defines refresh schedules per data domain and provides a SyncManager
that can be integrated with APScheduler or Celery Beat.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("365advisers.external.scheduler")


class SyncFrequency(str, Enum):
    """Sync frequency presets."""
    REALTIME = "realtime"          # Every 1-5 minutes (market hours only)
    FREQUENT = "frequent"         # Every 15 minutes
    HOURLY = "hourly"             # Every hour
    DAILY = "daily"               # Once daily (e.g. 18:00 ET)
    WEEKLY = "weekly"             # Once per week
    ON_PUBLISH = "on_publish"     # When new data is published (event-driven)
    MANUAL = "manual"             # Only on explicit request


@dataclass(frozen=True)
class SyncSchedule:
    """Configuration for syncing a data type."""
    domain: str
    frequency: SyncFrequency
    cron_expression: str            # APScheduler-compatible cron
    market_hours_only: bool = False
    description: str = ""


# ── Default Schedules ─────────────────────────────────────────────────────────

DEFAULT_SCHEDULES: list[SyncSchedule] = [
    # Market Data
    SyncSchedule(
        domain="market_data",
        frequency=SyncFrequency.REALTIME,
        cron_expression="*/5 9-16 * * 1-5",  # Every 5 min, market hours, weekdays
        market_hours_only=True,
        description="Intraday OHLCV from Polygon, Alpha Vantage, Twelve Data",
    ),
    SyncSchedule(
        domain="market_data_eod",
        frequency=SyncFrequency.DAILY,
        cron_expression="0 18 * * 1-5",  # 6pm ET weekdays
        description="End-of-day prices and adjustments",
    ),

    # Fundamental Data
    SyncSchedule(
        domain="fundamental",
        frequency=SyncFrequency.DAILY,
        cron_expression="0 6 * * 1-5",  # 6am ET weekdays
        description="Financials, ratios, profiles from FMP, Alpha Vantage, Finnhub",
    ),

    # Macro Data
    SyncSchedule(
        domain="macro",
        frequency=SyncFrequency.ON_PUBLISH,
        cron_expression="0 8 * * 1-5",  # 8am ET check for new releases
        description="FRED, World Bank, IMF indicators",
    ),

    # Sentiment
    SyncSchedule(
        domain="sentiment",
        frequency=SyncFrequency.FREQUENT,
        cron_expression="*/15 * * * *",  # Every 15 min
        description="Stocktwits, Santiment social sentiment",
    ),

    # Filings
    SyncSchedule(
        domain="filing_events",
        frequency=SyncFrequency.FREQUENT,
        cron_expression="*/30 8-18 * * 1-5",  # Every 30 min during business hours
        description="SEC EDGAR filings",
    ),

    # Options / Volatility
    SyncSchedule(
        domain="options",
        frequency=SyncFrequency.FREQUENT,
        cron_expression="*/15 9-16 * * 1-5",  # Every 15 min, market hours
        market_hours_only=True,
        description="Options chains and unusual activity",
    ),
    SyncSchedule(
        domain="volatility",
        frequency=SyncFrequency.FREQUENT,
        cron_expression="*/15 9-16 * * 1-5",
        market_hours_only=True,
        description="VIX, term structure, historical vol from Cboe",
    ),

    # Alternative Data
    SyncSchedule(
        domain="alternative",
        frequency=SyncFrequency.DAILY,
        cron_expression="0 7 * * 1-5",  # 7am ET weekdays
        description="Web traffic, alt datasets (when commercial providers activated)",
    ),
]


class SyncManager:
    """
    Manages sync schedules for all data domains.

    Integration points:
      - APScheduler: Use get_schedules() to register cron jobs
      - Celery Beat: Export schedules as periodic tasks
      - Manual: Call trigger_sync(domain) for on-demand refresh
    """

    def __init__(self, schedules: list[SyncSchedule] | None = None) -> None:
        self._schedules = {s.domain: s for s in (schedules or DEFAULT_SCHEDULES)}

    def get_schedules(self) -> list[SyncSchedule]:
        """Return all configured sync schedules."""
        return list(self._schedules.values())

    def get_schedule(self, domain: str) -> SyncSchedule | None:
        """Get schedule for a specific domain."""
        return self._schedules.get(domain)

    def update_frequency(self, domain: str, frequency: SyncFrequency, cron: str) -> bool:
        """Update the sync frequency for a domain at runtime."""
        if domain not in self._schedules:
            return False
        old = self._schedules[domain]
        self._schedules[domain] = SyncSchedule(
            domain=domain,
            frequency=frequency,
            cron_expression=cron,
            market_hours_only=old.market_hours_only,
            description=old.description,
        )
        logger.info(f"Updated sync schedule for '{domain}': {frequency.value} ({cron})")
        return True

    def summary(self) -> list[dict]:
        """Serializable summary for API exposure."""
        return [
            {
                "domain": s.domain,
                "frequency": s.frequency.value,
                "cron": s.cron_expression,
                "market_hours_only": s.market_hours_only,
                "description": s.description,
            }
            for s in self._schedules.values()
        ]
