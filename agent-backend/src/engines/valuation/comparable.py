"""
src/engines/valuation/comparable.py
──────────────────────────────────────────────────────────────────────────────
Comparable Company Analysis.

Computes implied fair value using peer median multiples (PE, EV/EBITDA,
P/FCF, PB) applied to the target's fundamentals.
"""

from __future__ import annotations

import logging
from statistics import median

from src.engines.valuation.models import (
    ComparableInput,
    ComparableResult,
    PeerMultiple,
)

logger = logging.getLogger("365advisers.valuation.comparable")


class ComparableAnalysis:
    """
    Compute fair value from comparable company multiples.

    Consensus = weighted average of implied values:
        PE: 30%  |  EV/EBITDA: 30%  |  P/FCF: 25%  |  PB: 15%
    """

    WEIGHTS = {
        "pe": 0.30,
        "ev_ebitda": 0.30,
        "p_fcf": 0.25,
        "pb": 0.15,
    }

    @classmethod
    def analyze(cls, inputs: ComparableInput) -> ComparableResult:
        """
        Run comparable company analysis.

        For each valuation multiple:
            1. Compute median across peers (excluding None)
            2. Apply median multiple to target's fundamentals → implied value
            3. Weight and blend into consensus fair value
        """
        peers = inputs.peers
        if not peers:
            return ComparableResult(target_ticker=inputs.target_ticker)

        # Compute medians
        pe_values = [p.pe_ratio for p in peers if p.pe_ratio is not None and p.pe_ratio > 0]
        ev_values = [p.ev_ebitda for p in peers if p.ev_ebitda is not None and p.ev_ebitda > 0]
        pfcf_values = [p.p_fcf for p in peers if p.p_fcf is not None and p.p_fcf > 0]
        pb_values = [p.pb_ratio for p in peers if p.pb_ratio is not None and p.pb_ratio > 0]

        median_pe = median(pe_values) if pe_values else None
        median_ev = median(ev_values) if ev_values else None
        median_pfcf = median(pfcf_values) if pfcf_values else None
        median_pb = median(pb_values) if pb_values else None

        # Implied values
        implied_pe = round(median_pe * inputs.target_eps, 2) if (
            median_pe and inputs.target_eps > 0
        ) else None

        implied_ev_ebitda = None
        if median_ev and inputs.target_ebitda > 0:
            # EV/EBITDA × EBITDA = EV → subtract net debt = equity → per share
            ev = median_ev * inputs.target_ebitda
            implied_ev_ebitda = round(ev - inputs.target_net_debt_per_share, 2)

        implied_pfcf = round(median_pfcf * inputs.target_fcf_per_share, 2) if (
            median_pfcf and inputs.target_fcf_per_share > 0
        ) else None

        implied_pb = round(median_pb * inputs.target_book_value, 2) if (
            median_pb and inputs.target_book_value > 0
        ) else None

        # Consensus (weighted average of available implied values)
        weighted_sum = 0.0
        total_weight = 0.0
        weights_used = {}

        for label, implied, weight_key in [
            ("pe", implied_pe, "pe"),
            ("ev_ebitda", implied_ev_ebitda, "ev_ebitda"),
            ("p_fcf", implied_pfcf, "p_fcf"),
            ("pb", implied_pb, "pb"),
        ]:
            if implied is not None and implied > 0:
                w = cls.WEIGHTS[weight_key]
                weighted_sum += implied * w
                total_weight += w
                weights_used[label] = w

        # Re-normalise weights
        consensus = weighted_sum / total_weight if total_weight > 0 else 0.0
        if total_weight > 0:
            weights_used = {k: round(v / total_weight, 3) for k, v in weights_used.items()}

        return ComparableResult(
            target_ticker=inputs.target_ticker,
            peer_count=len(peers),
            median_pe=round(median_pe, 2) if median_pe else None,
            median_ev_ebitda=round(median_ev, 2) if median_ev else None,
            median_p_fcf=round(median_pfcf, 2) if median_pfcf else None,
            median_pb=round(median_pb, 2) if median_pb else None,
            implied_value_pe=implied_pe,
            implied_value_ev_ebitda=implied_ev_ebitda,
            implied_value_p_fcf=implied_pfcf,
            implied_value_pb=implied_pb,
            consensus_fair_value=round(consensus, 2),
            weights_used=weights_used,
        )
