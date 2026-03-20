"""
tests/test_models_import.py
─────────────────────────────────────────────────────────────────────────────
Smoke tests to verify all model submodules import correctly.
Catches circular imports, missing dependencies, or broken re-exports.
"""

import pytest


class TestModelSubmoduleImports:
    """Verify each domain submodule imports without errors."""

    def test_import_base(self):
        from src.data.models.base import Base, init_db
        assert Base is not None

    def test_import_analysis(self):
        from src.data.models.analysis import FundamentalAnalysis, TechnicalAnalysis
        assert FundamentalAnalysis is not None
        assert TechnicalAnalysis is not None

    def test_import_portfolio(self):
        from src.data.models.portfolio import Portfolio, PortfolioPosition
        assert Portfolio is not None

    def test_import_signals(self):
        from src.data.models.signals import SignalSnapshot
        assert SignalSnapshot is not None

    def test_import_backtesting(self):
        from src.data.models.backtesting import BacktestRun
        assert BacktestRun is not None

    def test_import_governance(self):
        from src.data.models.governance import ExperimentRecord
        assert ExperimentRecord is not None

    def test_import_operations(self):
        from src.data.models.operations import PilotRunRecord
        assert PilotRunRecord is not None

    def test_import_cache(self):
        from src.data.models.cache import FundamentalDBCache, TechnicalDBCache
        assert FundamentalDBCache is not None

    def test_import_queries(self):
        from src.data.models.queries import get_score_history
        assert callable(get_score_history)


class TestLegacyImports:
    """Verify backward-compatible imports via the re-export shim."""

    def test_legacy_database_import_base(self):
        from src.data.database import Base
        assert Base is not None

    def test_legacy_database_import_init_db(self):
        from src.data.database import init_db
        assert callable(init_db)

    def test_legacy_database_import_fundamental(self):
        from src.data.database import FundamentalAnalysis
        assert FundamentalAnalysis is not None

    def test_legacy_database_import_cache(self):
        from src.data.database import FundamentalDBCache, TechnicalDBCache
        assert FundamentalDBCache is not None
        assert TechnicalDBCache is not None

    def test_legacy_database_import_query(self):
        from src.data.database import get_score_history
        assert callable(get_score_history)


class TestModelPackageReExport:
    """Verify the models __init__.py re-exports everything."""

    def test_models_init_exports_base(self):
        from src.data.models import Base
        assert Base is not None

    def test_models_init_exports_analysis(self):
        from src.data.models import FundamentalAnalysis, TechnicalAnalysis
        assert FundamentalAnalysis is not None

    def test_models_init_exports_signals(self):
        from src.data.models import SignalSnapshot
        assert SignalSnapshot is not None

    def test_models_init_exports_operations(self):
        from src.data.models import PilotRunRecord
        assert PilotRunRecord is not None


class TestValidationRouteImport:
    """Verify the validation route package imports correctly."""

    def test_validation_shim_import(self):
        from src.routes.validation import router
        assert router is not None

    def test_validation_pkg_import(self):
        from src.routes.validation_pkg import router
        assert router is not None
        assert len(router.routes) > 0


class TestLLMProviderImport:
    """Verify the LLM provider service imports correctly."""

    def test_llm_provider_import(self):
        from src.services.llm_provider import LLMProvider
        assert LLMProvider is not None

    def test_get_llm_provider(self):
        from src.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        assert provider is not None
        assert provider.primary_name.startswith("gemini/")
