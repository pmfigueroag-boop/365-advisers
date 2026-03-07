"""
src/data/external/adapters/gdelt.py
──────────────────────────────────────────────────────────────────────────────
GDELT Adapter — geopolitical event monitoring and risk assessment.

Queries the GDELT 2.0 DOC API for geopolitical events, tone analysis,
and thematic risk monitoring.  Provides a composite risk index plus
country-level and theme-level breakdowns.

Registers as the sole adapter for DataDomain.GEOPOLITICAL.

Data sources:
  - GDELT DOC 2.0 API (api.gdeltproject.org/api/v2/doc/doc)
  - Fully open, no API key required
  - Unreliable/slow — aggressive timeout + limited retry

Retry policy:
  - 1 retry, 3s backoff
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

from src.config import get_settings
from src.data.external.base import (
    DataDomain,
    HealthStatus,
    ProviderAdapter,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from src.data.external.contracts.geopolitical import (
    CountryRisk,
    GeopoliticalEventData,
    ThemeRisk,
)

logger = logging.getLogger("365advisers.external.gdelt")

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Default themes to monitor
DEFAULT_THEMES = [
    "TAX_POLICY", "TRADE_WAR", "SANCTIONS", "MILITARY_CONFLICT",
    "CYBER_ATTACK", "ENERGY_CRISIS", "FINANCIAL_REGULATION",
    "POLITICAL_INSTABILITY", "PANDEMIC", "CLIMATE_POLICY",
]

# Country risk classification thresholds
COUNTRY_RISK_THRESHOLDS = {
    "critical": -5.0,  # tone < -5
    "high": -2.5,
    "medium": -0.5,
    "low": 0.0,
}


class GDELTAdapter(ProviderAdapter):
    """
    GDELT geopolitical event adapter.

    Queries the GDELT DOC API for thematic and geographic event analysis.
    Produces a composite risk index and structured event intelligence.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.EDPL_GDELT_TIMEOUT
        self._retry_delay = settings.EDPL_DEFAULT_RETRY_DELAY
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "gdelt"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.GEOPOLITICAL

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.GEOPOLITICAL_EVENTS,
            ProviderCapability.GEOPOLITICAL_TONE,
            ProviderCapability.COUNTRY_RISK,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch geopolitical intelligence from GDELT."""
        t0 = time.perf_counter()

        themes = request.params.get("themes", DEFAULT_THEMES)
        countries = request.params.get("countries", ["US", "CN", "EU", "RU"])
        hours_back = int(request.params.get("hours_back", 48))

        try:
            # Fetch theme-level and geographic tone data concurrently
            theme_data, country_data, timeline = await asyncio.gather(
                self._fetch_theme_tone(themes, hours_back),
                self._fetch_country_tone(countries, hours_back),
                self._fetch_timeline(hours_back),
                return_exceptions=True,
            )

            if isinstance(theme_data, Exception):
                logger.warning(f"GDELT theme fetch failed: {theme_data}")
                theme_data = []
            if isinstance(country_data, Exception):
                logger.warning(f"GDELT country fetch failed: {country_data}")
                country_data = []
            if isinstance(timeline, Exception):
                logger.warning(f"GDELT timeline fetch failed: {timeline}")
                timeline = {}

            # Compute aggregate metrics
            all_tones = [t.tone for t in theme_data] if theme_data else []
            tone_24h = sum(all_tones) / len(all_tones) if all_tones else None
            total_events = sum(t.event_count for t in theme_data) if theme_data else 0

            # Detect spikes
            spike = self._detect_spike(timeline) if isinstance(timeline, dict) else False

            # Compute composite risk index
            risk_index = self._compute_risk_index(theme_data, country_data, spike)

            data = GeopoliticalEventData(
                as_of=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                risk_index=risk_index,
                tone_avg_24h=round(tone_24h, 2) if tone_24h is not None else None,
                event_count_24h=total_events,
                top_themes=theme_data if isinstance(theme_data, list) else [],
                top_country_risks=country_data if isinstance(country_data, list) else [],
                spike_detected=spike,
                source="gdelt",
                sources_used=["gdelt"],
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"GDELT adapter error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Lightweight GDELT health probe."""
        try:
            resp = await self._client.get(
                GDELT_DOC_API,
                params={"query": "trade", "mode": "artlist", "maxrecords": 1, "format": "json"},
            )
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=status,
                last_success=datetime.now(timezone.utc) if resp.status_code == 200 else None,
                message=f"GDELT HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"Health check failed: {exc}",
            )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_theme_tone(
        self, themes: list[str], hours_back: int,
    ) -> list[ThemeRisk]:
        """Fetch tone analysis per geopolitical theme."""
        results: list[ThemeRisk] = []

        for theme in themes[:10]:  # limit to 10 themes
            data = await self._gdelt_query(
                query=theme.replace("_", " "),
                mode="tonechart",
                timespan=f"{hours_back}h",
            )

            if data and isinstance(data, dict):
                tone_entries = data.get("tonechart", [])
                if tone_entries:
                    avg_tone = sum(
                        float(e.get("tone", 0)) for e in tone_entries
                    ) / len(tone_entries)
                    event_count = sum(int(e.get("count", 0)) for e in tone_entries)

                    # Determine trend
                    if len(tone_entries) >= 2:
                        recent = float(tone_entries[-1].get("tone", 0))
                        earlier = float(tone_entries[0].get("tone", 0))
                        trend = "rising" if recent > earlier + 0.5 else (
                            "falling" if recent < earlier - 0.5 else "stable"
                        )
                    else:
                        trend = "stable"

                    results.append(ThemeRisk(
                        theme=theme,
                        tone=round(avg_tone, 2),
                        event_count=event_count,
                        trend=trend,
                    ))

        return results

    async def _fetch_country_tone(
        self, countries: list[str], hours_back: int,
    ) -> list[CountryRisk]:
        """Fetch tone analysis per country."""
        # Country name mapping
        country_names = {
            "US": "United States", "CN": "China", "EU": "European Union",
            "RU": "Russia", "UK": "United Kingdom", "JP": "Japan",
            "DE": "Germany", "IN": "India", "BR": "Brazil", "KR": "South Korea",
        }

        results: list[CountryRisk] = []

        for code in countries[:8]:
            name = country_names.get(code, code)
            data = await self._gdelt_query(
                query=name,
                mode="tonechart",
                timespan=f"{hours_back}h",
            )

            if data and isinstance(data, dict):
                tone_entries = data.get("tonechart", [])
                if tone_entries:
                    avg_tone = sum(
                        float(e.get("tone", 0)) for e in tone_entries
                    ) / len(tone_entries)
                    event_count = sum(int(e.get("count", 0)) for e in tone_entries)

                    risk_level = "low"
                    for level, threshold in sorted(
                        COUNTRY_RISK_THRESHOLDS.items(),
                        key=lambda x: x[1],
                    ):
                        if avg_tone <= threshold:
                            risk_level = level
                            break

                    results.append(CountryRisk(
                        country_code=code,
                        country_name=name,
                        risk_level=risk_level,
                        event_count=event_count,
                        tone=round(avg_tone, 2),
                    ))

        return results

    async def _fetch_timeline(self, hours_back: int) -> dict:
        """Fetch event timeline for spike detection."""
        data = await self._gdelt_query(
            query="geopolitical OR conflict OR sanctions",
            mode="timelinevol",
            timespan=f"{hours_back}h",
        )
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _detect_spike(timeline: dict) -> bool:
        """Detect event volume spikes (> 2σ above mean)."""
        vol_data = timeline.get("timeline", [])
        if not vol_data or not isinstance(vol_data, list):
            return False

        # Extract volumes from first series
        if vol_data and isinstance(vol_data[0], dict):
            series = vol_data[0].get("data", [])
            volumes = [float(p.get("value", 0)) for p in series if p.get("value")]
            if len(volumes) >= 5:
                mean = sum(volumes) / len(volumes)
                variance = sum((v - mean) ** 2 for v in volumes) / len(volumes)
                std = variance ** 0.5
                recent = volumes[-1]
                return recent > mean + 2 * std

        return False

    @staticmethod
    def _compute_risk_index(
        themes: list[ThemeRisk],
        countries: list[CountryRisk],
        spike: bool,
    ) -> float | None:
        """
        Compute composite geopolitical risk index (0–100).

        Components:
          - Average negative tone (40%)
          - High-risk country count (30%)
          - Event spike penalty (30%)
        """
        if not themes and not countries:
            return None

        score = 50.0  # baseline

        # Tone component: more negative = higher risk
        if themes:
            avg_tone = sum(t.tone for t in themes) / len(themes)
            # Tone ranges from -10 to +10; normalize to 0-40
            tone_risk = max(0, min(40, (-avg_tone + 5) * 4))
            score = tone_risk
        else:
            score = 20.0

        # Country component
        if countries:
            high_risk_count = sum(
                1 for c in countries if c.risk_level in ("high", "critical")
            )
            country_risk = min(30, high_risk_count * 10)
            score += country_risk

        # Spike penalty
        if spike:
            score += 30

        return round(min(100, max(0, score)), 1)

    async def _gdelt_query(
        self, query: str, mode: str, timespan: str,
    ) -> dict | None:
        """Make GDELT DOC API call with 1 retry."""
        for attempt in range(2):
            try:
                resp = await self._client.get(
                    GDELT_DOC_API,
                    params={
                        "query": query,
                        "mode": mode,
                        "timespan": timespan,
                        "format": "json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.debug(f"GDELT query '{query}' returned HTTP {resp.status_code}")
                return None
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == 0:
                    await asyncio.sleep(self._retry_delay * 3)
            except Exception as exc:
                logger.debug(f"GDELT query error: {exc}")
                break
        return None
