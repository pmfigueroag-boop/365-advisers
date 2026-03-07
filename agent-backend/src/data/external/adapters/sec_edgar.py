"""
src/data/external/adapters/sec_edgar.py
──────────────────────────────────────────────────────────────────────────────
SEC EDGAR Adapter — filing retrieval and material event detection.

Fetches recent filings (10-K, 10-Q, 8-K, DEF 14A, SC 13D/G) from the
SEC EDGAR FULL-TEXT SEARCH API.  Classifies filing urgency and detects
material events.

Registers as the sole adapter for DataDomain.FILING_EVENTS.

Data sources:
  - EDGAR FULL-TEXT SEARCH: efts.sec.gov/LATEST/search-index
  - EDGAR Submissions API: data.sec.gov/submissions/
  - Free; rate-limited (10 req/s with mandatory User-Agent)

Retry policy:
  - 3 retries with exponential backoff (1s, 2s, 4s)
  - Mandatory User-Agent header per SEC policy
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

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
from src.data.external.contracts.filing_event import (
    FilingEvent,
    FilingEventData,
    OwnershipFiling,
)

logger = logging.getLogger("365advisers.external.edgar")

EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"
EDGAR_EFTS = "https://efts.sec.gov/LATEST/search-index"

# 8-K item codes considered "material"
MATERIAL_ITEMS = {
    "1.01",  # Entry into Material Agreement
    "1.02",  # Termination of Material Agreement
    "2.01",  # Acquisition/Disposition of Assets
    "2.05",  # Costs Associated with Exit/Disposal
    "2.06",  # Material Impairments
    "4.01",  # Change in Auditor
    "4.02",  # Non-reliance on Financial Statements
    "5.01",  # Change in Control
    "5.02",  # Departure of Directors/Officers
    "8.01",  # Other Events (often material)
}


class SECEdgarAdapter(ProviderAdapter):
    """
    SEC EDGAR adapter for filing event intelligence.

    Detects material events, classifies filing urgency, and provides
    structured filing data for downstream signal generation.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._email = settings.SEC_EDGAR_EMAIL or "contact@365advisers.com"
        self._timeout = settings.EDPL_EDGAR_TIMEOUT
        self._max_retries = 3
        self._retry_delay = settings.EDPL_DEFAULT_RETRY_DELAY
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "User-Agent": f"365Advisers/1.0 ({self._email})",
                "Accept": "application/json",
            },
        )

    @property
    def name(self) -> str:
        return "sec_edgar"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.FILING_EVENTS

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.SEC_FILINGS,
            ProviderCapability.MATERIAL_EVENTS,
            ProviderCapability.OWNERSHIP_FILINGS,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch SEC filings for a ticker."""
        t0 = time.perf_counter()
        ticker = request.ticker or ""

        if not ticker:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                "ticker required for SEC EDGAR", latency_ms=elapsed,
            )

        days_back = int(request.params.get("days_back", 90))
        filing_types = request.params.get("filing_types", ["10-K", "10-Q", "8-K", "DEF14A"])

        try:
            # Step 1: Resolve CIK from ticker
            cik = await self._resolve_cik(ticker)
            if not cik:
                elapsed = (time.perf_counter() - t0) * 1000
                return self._error_response(
                    f"Could not resolve CIK for {ticker}", latency_ms=elapsed,
                )

            # Step 2: Fetch submissions
            submissions = await self._fetch_submissions(cik)
            if not submissions:
                elapsed = (time.perf_counter() - t0) * 1000
                return self._ok_response(
                    FilingEventData.empty(ticker), latency_ms=elapsed,
                )

            # Step 3: Parse and filter filings
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            filings = self._parse_filings(submissions, filing_types, cutoff)

            # Classify material events
            has_material = any(
                f.urgency in ("material", "critical")
                and f.filed_date >= (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
                for f in filings
            )

            # Find latest annual and quarterly
            latest_annual = next(
                (f.filed_date for f in filings if f.filing_type == "10-K"), None,
            )
            latest_quarterly = next(
                (f.filed_date for f in filings if f.filing_type == "10-Q"), None,
            )

            # Extract ownership filings
            ownership = [
                OwnershipFiling(
                    filer_name="",
                    filing_type=f.filing_type,
                    filed_date=f.filed_date,
                    purpose=f.description or "",
                )
                for f in filings
                if f.filing_type.startswith("SC")
            ]

            data = FilingEventData(
                ticker=ticker,
                filings=filings,
                has_material_event=has_material,
                latest_annual_filing=latest_annual,
                latest_quarterly_filing=latest_quarterly,
                ownership_filings=ownership,
                source="sec_edgar",
                sources_used=["sec_edgar"],
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"SEC EDGAR adapter error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Verify EDGAR API is reachable."""
        try:
            resp = await self._client.get(
                f"{EDGAR_SUBMISSIONS}/CIK0000320193.json",  # Apple CIK
            )
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=status,
                last_success=datetime.now(timezone.utc) if resp.status_code == 200 else None,
                message=f"EDGAR HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"Health check failed: {exc}",
            )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _resolve_cik(self, ticker: str) -> str | None:
        """Resolve ticker to SEC CIK number."""
        data = await self._api_get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={
                "action": "getcompany",
                "company": ticker,
                "type": "",
                "dateb": "",
                "owner": "include",
                "count": 1,
                "search_text": "",
                "output": "atom",
            },
        )
        # Fallback: try the company tickers JSON
        try:
            resp = await self._client.get("https://www.sec.gov/files/company_tickers.json")
            if resp.status_code == 200:
                tickers = resp.json()
                for entry in tickers.values():
                    if entry.get("ticker", "").upper() == ticker.upper():
                        cik = str(entry.get("cik_str", ""))
                        return cik.zfill(10)
        except Exception as exc:
            logger.debug(f"CIK resolution failed for {ticker}: {exc}")
        return None

    async def _fetch_submissions(self, cik: str) -> dict | None:
        """Fetch submission data for a CIK."""
        return await self._api_get_json(f"{EDGAR_SUBMISSIONS}/CIK{cik}.json")

    def _parse_filings(
        self,
        submissions: dict,
        filing_types: list[str],
        cutoff_date: str,
    ) -> list[FilingEvent]:
        """Parse EDGAR submissions into FilingEvent objects."""
        recent = submissions.get("filings", {}).get("recent", {})
        if not recent:
            return []

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        filings: list[FilingEvent] = []
        type_set = {t.upper() for t in filing_types}

        for i in range(min(len(forms), 100)):
            form = forms[i] if i < len(forms) else ""
            date = dates[i] if i < len(dates) else ""
            accession = accessions[i] if i < len(accessions) else ""
            doc = docs[i] if i < len(docs) else ""
            desc = descriptions[i] if i < len(descriptions) else ""

            # Filter by type and date
            if form.upper() not in type_set:
                continue
            if date < cutoff_date:
                continue

            # Classify urgency
            urgency = self._classify_urgency(form)

            accession_clean = accession.replace("-", "")
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{accession_clean}/{accession}/{doc}"
            ) if doc else None

            filings.append(FilingEvent(
                filing_type=form,
                filed_date=date,
                accession_number=accession,
                primary_document_url=doc_url,
                description=desc or None,
                urgency=urgency,
            ))

        return filings

    @staticmethod
    def _classify_urgency(form: str) -> str:
        """Classify filing urgency."""
        form_upper = form.upper()
        if form_upper == "8-K":
            return "material"
        if form_upper in ("SC 13D", "SC 13D/A"):
            return "material"
        if form_upper in ("4", "3", "5"):  # insider ownership changes
            return "routine"
        if form_upper in ("10-K", "10-Q"):
            return "routine"
        if form_upper.startswith("DEF"):
            return "routine"
        return "routine"

    async def _api_get(self, url: str, params: dict | None = None) -> dict | None:
        """Generic GET with retry and rate limiting."""
        for attempt in range(1 + self._max_retries):
            try:
                # SEC requires 100ms between requests
                await asyncio.sleep(0.15)
                resp = await self._client.get(url, params=params)
                if resp.status_code == 503:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    continue
                if resp.status_code == 200:
                    return resp.json() if "json" in resp.headers.get("content-type", "") else {}
                return None
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                else:
                    logger.debug(f"EDGAR exhausted retries: {exc}")
            except Exception as exc:
                logger.debug(f"EDGAR request error: {exc}")
                break
        return None

    async def _api_get_json(self, url: str) -> dict | None:
        """GET JSON with retry."""
        for attempt in range(1 + self._max_retries):
            try:
                await asyncio.sleep(0.15)  # SEC rate limit
                resp = await self._client.get(url)
                if resp.status_code == 503:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                    continue
                if resp.status_code == 200:
                    return resp.json()
                return None
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (2 ** attempt))
                else:
                    logger.debug(f"EDGAR JSON exhausted retries: {exc}")
            except Exception as exc:
                logger.debug(f"EDGAR JSON error: {exc}")
                break
        return None
