"""
tests/test_brinson_attribution.py
--------------------------------------------------------------------------
Tests for Brinson-Fachler performance attribution model.
"""

from __future__ import annotations

import pytest

from src.engines.attribution.brinson import BrinsonFachler
from src.engines.attribution.models import BrinsonResult, SectorAttribution


# ─── Fixtures ────────────────────────────────────────────────────────────────

# Equal-weight portfolio overweighting Tech, underweighting Health
PORT_W = {"Tech": 0.40, "Health": 0.20, "Financials": 0.25, "Energy": 0.15}
BENCH_W = {"Tech": 0.25, "Health": 0.30, "Financials": 0.25, "Energy": 0.20}

# Portfolio outperformed in Tech, underperformed in Health
PORT_R = {"Tech": 0.08, "Health": 0.02, "Financials": 0.05, "Energy": 0.03}
BENCH_R = {"Tech": 0.06, "Health": 0.04, "Financials": 0.05, "Energy": 0.01}


def _attribute(**kw) -> BrinsonResult:
    return BrinsonFachler.attribute(
        portfolio_weights=kw.get("pw", PORT_W),
        benchmark_weights=kw.get("bw", BENCH_W),
        portfolio_returns=kw.get("pr", PORT_R),
        benchmark_returns=kw.get("br", BENCH_R),
    )


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestBrinsonDecomposition:

    def test_active_return_decomposition(self):
        """active_return ≈ allocation + selection + interaction."""
        result = _attribute()
        decomposed = result.total_allocation + result.total_selection + result.total_interaction
        assert abs(result.active_return - decomposed) < 1e-6

    def test_active_return_sign(self):
        """Portfolio outperforms → positive active return."""
        result = _attribute()
        r_p = sum(PORT_W[s] * PORT_R[s] for s in PORT_W)
        r_b = sum(BENCH_W[s] * BENCH_R[s] for s in BENCH_W)
        assert abs(result.active_return - (r_p - r_b)) < 1e-6
        assert result.active_return > 0  # We outperformed

    def test_allocation_effect(self):
        """Overweighting outperforming sectors → positive allocation."""
        result = _attribute()
        # Overweight Tech (+15%) which outperformed benchmark → positive allocation
        tech = next(s for s in result.sector_attribution if s.sector == "Tech")
        assert tech.allocation_effect > 0

    def test_selection_effect(self):
        """Stock selection in sectors where portfolio beat benchmark."""
        result = _attribute()
        tech = next(s for s in result.sector_attribution if s.sector == "Tech")
        # Tech: portfolio return 8% vs benchmark 6% → positive selection
        assert tech.selection_effect > 0

    def test_interaction_effect(self):
        """Interaction = (w_p - w_b) × (r_p - r_b)."""
        result = _attribute()
        tech = next(s for s in result.sector_attribution if s.sector == "Tech")
        # Overweight (+15%) × outperform (+2%) → positive interaction
        assert tech.interaction_effect > 0

    def test_per_sector_total(self):
        """Each sector: total = allocation + selection + interaction."""
        result = _attribute()
        for sa in result.sector_attribution:
            expected = sa.allocation_effect + sa.selection_effect + sa.interaction_effect
            assert abs(sa.total_effect - expected) < 1e-6

    def test_equal_weights_no_allocation(self):
        """If portfolio and benchmark have same weights → allocation = 0."""
        same = {"Tech": 0.50, "Health": 0.50}
        result = _attribute(pw=same, bw=same)
        assert abs(result.total_allocation) < 1e-6

    def test_equal_returns_no_selection(self):
        """If returns are same → selection = 0."""
        same_r = {"Tech": 0.05, "Health": 0.05}
        result = _attribute(pr=same_r, br=same_r)
        assert abs(result.total_selection) < 1e-6
        assert abs(result.total_interaction) < 1e-6

    def test_benchmark_only_sector(self):
        """Sector in benchmark but not portfolio → handled correctly."""
        pw = {"Tech": 0.60, "Health": 0.40}
        bw = {"Tech": 0.30, "Health": 0.30, "Utilities": 0.40}
        pr = {"Tech": 0.05, "Health": 0.03}
        br = {"Tech": 0.04, "Health": 0.02, "Utilities": 0.06}
        result = _attribute(pw=pw, bw=bw, pr=pr, br=br)
        # Portfolio has 0 weight in Utilities
        util = next(s for s in result.sector_attribution if s.sector == "Utilities")
        assert util.portfolio_weight == 0.0
        # Still decomposes correctly
        assert abs(result.active_return - (
            result.total_allocation + result.total_selection + result.total_interaction
        )) < 1e-6

    def test_top_contributors_detractors(self):
        """Top contributors and detractors populated."""
        result = _attribute()
        # Tech should be a top contributor (overweight + outperform)
        assert "Tech" in result.top_contributors or len(result.top_contributors) == 0
        assert isinstance(result.top_detractors, list)

    def test_result_contract(self):
        """Result is a proper BrinsonResult with all fields."""
        result = _attribute()
        assert isinstance(result, BrinsonResult)
        assert len(result.sector_attribution) == 4
        d = result.model_dump()
        assert "portfolio_return" in d
        assert "active_return" in d
        assert "sector_attribution" in d
