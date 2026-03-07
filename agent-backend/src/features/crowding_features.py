"""
src/features/crowding_features.py
──────────────────────────────────────────────────────────────────────────────
Extracts crowding-relevant features from EDPL contracts and transforms
them into the parameter format expected by CrowdingEngine.assess().

This bridges:
  - ETFFlowData    → net_flows_5d, mean_flow_60d, std_flow_60d
  - OptionsIntelligence → implied_vol_30d, realized_vol_20d
  - InstitutionalFlowData → inst_ownership_change, sector_avg_change
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.external.contracts.etf_flows import ETFFlowData
from src.data.external.contracts.options import OptionsIntelligence
from src.data.external.contracts.institutional import InstitutionalFlowData

logger = logging.getLogger("365advisers.features.crowding")


def extract_etf_flow_params(
    etf_data: ETFFlowData,
    ticker_sector: str = "",
) -> dict[str, float]:
    """
    Extract CrowdingEngine EFC parameters from ETF flow data.

    Maps the sector-level flow data to the ticker's sector and returns
    the params expected by ``CrowdingEngine.assess()``:
      - net_flows_5d
      - mean_flow_60d
      - std_flow_60d

    If the ticker's sector is not found in the flow data, returns
    defaults that produce EFC = 0 (no crowding signal).
    """
    if not etf_data.sector_flows or not ticker_sector:
        return {
            "net_flows_5d": 0.0,
            "mean_flow_60d": 0.0,
            "std_flow_60d": 1.0,
        }

    # Find the matching sector
    sector_lower = ticker_sector.lower()
    matched = None
    for sf in etf_data.sector_flows:
        if sf.sector.lower() in sector_lower or sector_lower in sf.sector.lower():
            matched = sf
            break

    if not matched:
        return {
            "net_flows_5d": 0.0,
            "mean_flow_60d": 0.0,
            "std_flow_60d": 1.0,
        }

    # Use flow momentum as net_flows_5d,
    # net_flow_20d/4 as mean (weekly avg),
    # compute std from all sectors for cross-sector comparison
    all_5d = [sf.net_flow_5d for sf in etf_data.sector_flows]
    std_60d = 1.0
    if len(all_5d) > 1:
        mean = sum(all_5d) / len(all_5d)
        variance = sum((x - mean) ** 2 for x in all_5d) / len(all_5d)
        std_60d = max(variance ** 0.5, 0.01)

    return {
        "net_flows_5d": matched.net_flow_5d,
        "mean_flow_60d": matched.net_flow_20d / 4 if matched.net_flow_20d else 0.0,
        "std_flow_60d": std_60d,
    }


def extract_options_vol_params(
    options_data: OptionsIntelligence,
) -> dict[str, float | None]:
    """
    Extract CrowdingEngine Volatility Compression parameters.

    Returns params for ``CrowdingEngine.assess()``:
      - implied_vol_30d
      - realized_vol_20d (approximated from implied if not available separately)
    """
    if not options_data.snapshot:
        return {
            "implied_vol_30d": None,
            "realized_vol_20d": None,
        }

    snap = options_data.snapshot
    iv = snap.implied_vol_30d

    # Realized vol approximation: IV * 0.85 (options typically have slight premium)
    # This is overridden when the CrowdingEngine receives actual OHLCV data and
    # computes realized vol internally.
    rv = iv * 0.85 if iv is not None else None

    return {
        "implied_vol_30d": iv,
        "realized_vol_20d": rv,
    }


def extract_institutional_params(
    inst_data: InstitutionalFlowData,
    sector_avg_change: float = 0.0,
) -> dict[str, float]:
    """
    Extract CrowdingEngine IOH parameters from institutional flow data.

    Returns params for ``CrowdingEngine.assess()``:
      - inst_ownership_change
      - sector_avg_change
    """
    change = inst_data.inst_ownership_change_qoq or 0.0

    # If we don't have a pre-computed sector average, use a reasonable default
    # that produces a moderate IOH signal only for large changes
    effective_sector_avg = sector_avg_change if sector_avg_change > 0 else 0.02

    return {
        "inst_ownership_change": change,
        "sector_avg_change": effective_sector_avg,
    }


def build_crowding_params(
    etf_data: ETFFlowData | None = None,
    options_data: OptionsIntelligence | None = None,
    inst_data: InstitutionalFlowData | None = None,
    ticker_sector: str = "",
) -> dict[str, Any]:
    """
    Build a complete dict of CrowdingEngine.assess() parameters from
    all available EDPL data sources.

    This is the main entry point — call it with whatever data is available
    and it will produce sensible defaults for anything missing.
    """
    params: dict[str, Any] = {}

    # ETF Flow → EFC indicator
    if etf_data:
        params.update(extract_etf_flow_params(etf_data, ticker_sector))
    else:
        params.update({"net_flows_5d": 0.0, "mean_flow_60d": 0.0, "std_flow_60d": 1.0})

    # Options → VC indicator
    if options_data:
        params.update(extract_options_vol_params(options_data))
    else:
        params.update({"implied_vol_30d": None, "realized_vol_20d": None})

    # Institutional → IOH indicator
    if inst_data:
        params.update(extract_institutional_params(inst_data))
    else:
        params.update({"inst_ownership_change": 0.0, "sector_avg_change": 0.0})

    return params
