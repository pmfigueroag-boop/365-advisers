"""
src/data/external/adapters/stubs.py
──────────────────────────────────────────────────────────────────────────────
Commercial API Stubs — pre-wired adapters for providers that require
enterprise licenses or commercial agreements.

Each stub:
  - Declares full capabilities so the registry knows what it COULD provide
  - Returns a clear error response explaining the commercial requirement
  - Is ready for activation when a license is obtained

Providers stubbed:
  - Morningstar (fundamentals — enterprise API only)
  - Similarweb (alternative data — enterprise API, $10K+/yr)
  - Thinknum (alternative data — commercial contract required)
  - OptionMetrics (volatility — academic/enterprise, $5K+/yr)
"""

from __future__ import annotations

from src.data.external.base import (
    DataDomain, HealthStatus, ProviderAdapter, ProviderCapability,
    ProviderRequest, ProviderResponse, ProviderStatus,
)


class _CommercialStub(ProviderAdapter):
    """Base class for commercial API stubs."""

    _name: str = ""
    _domain: DataDomain = DataDomain.FUNDAMENTAL
    _caps: set[ProviderCapability] = set()
    _msg: str = "Commercial API — not activated"

    @property
    def name(self) -> str:
        return self._name

    @property
    def domain(self) -> DataDomain:
        return self._domain

    def get_capabilities(self) -> set[ProviderCapability]:
        return self._caps

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        return self._error_response(self._msg)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            provider_name=self.name, domain=self.domain,
            status=ProviderStatus.DISABLED, message=self._msg,
        )


class MorningstarAdapter(_CommercialStub):
    """
    Morningstar — enterprise fundamental data API.

    Requires: Enterprise license agreement with Morningstar.
    Would provide: Premium fundamental data, star ratings, style box,
    economic moat assessment, fair value estimates, analyst reports.

    To activate: Obtain API credentials from Morningstar Direct or
    Morningstar Data services, then implement fetch() with their
    REST/SOAP endpoints.
    """
    _name = "morningstar"
    _domain = DataDomain.FUNDAMENTAL
    _caps = {
        ProviderCapability.FINANCIAL_STATEMENTS,
        ProviderCapability.FINANCIAL_RATIOS,
        ProviderCapability.ANALYST_ESTIMATES,
        ProviderCapability.COMPANY_PROFILE,
    }
    _msg = "Morningstar requires enterprise license — stub only"


class SimilarwebAdapter(_CommercialStub):
    """
    Similarweb — web traffic and digital intelligence API.

    Requires: Enterprise API subscription ($10K+/year).
    Would provide: Monthly visits, traffic sources, audience demographics,
    competitor analysis, app analytics.

    To activate: Sign enterprise agreement with Similarweb, obtain
    API key, then implement fetch() with their REST v1/v2 endpoints.
    """
    _name = "similarweb"
    _domain = DataDomain.ALTERNATIVE
    _caps = {ProviderCapability.WEB_TRAFFIC, ProviderCapability.ALT_DATASETS}
    _msg = "Similarweb requires enterprise subscription ($10K+/yr) — stub only"


class ThinknumAdapter(_CommercialStub):
    """
    Thinknum — alternative data platform.

    Requires: Commercial contract with Thinknum.
    Would provide: Job postings, store counts, app ratings, social
    followers, web traffic, pricing, product catalog data.

    To activate: Negotiate data license with Thinknum, obtain credentials,
    then implement fetch() with their REST API.
    """
    _name = "thinknum"
    _domain = DataDomain.ALTERNATIVE
    _caps = {ProviderCapability.ALT_DATASETS, ProviderCapability.WEB_TRAFFIC}
    _msg = "Thinknum requires commercial contract — stub only"


class OptionMetricsAdapter(_CommercialStub):
    """
    OptionMetrics — academic-grade options analytics.

    Requires: Academic or enterprise subscription ($5K+/year).
    Would provide: IvyDB (implied volatility surfaces, option pricing,
    greeks, term structure), historical options data back to 1996.

    To activate: Obtain OptionMetrics IvyDB license, then implement
    fetch() with their data delivery mechanism (typically bulk files
    or API access).
    """
    _name = "optionmetrics"
    _domain = DataDomain.VOLATILITY
    _caps = {
        ProviderCapability.VOLATILITY_SURFACE,
        ProviderCapability.OPTIONS_CHAIN_FULL,
        ProviderCapability.IMPLIED_VOLATILITY,
    }
    _msg = "OptionMetrics requires academic/enterprise license ($5K+/yr) — stub only"
