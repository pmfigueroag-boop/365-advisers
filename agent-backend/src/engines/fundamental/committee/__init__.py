"""
src/engines/fundamental/committee/
──────────────────────────────────────────────────────────────────────────────
Multi-Agent Investment Committee Simulation.

Five-round structured debate:
  Round 1 — PRESENT:   6 agents state initial position memos (parallel)
  Round 2 — CHALLENGE: Each agent challenges their most-opposed peer (parallel)
  Round 3 — REBUT:     Challenged agents defend their positions (parallel)
  Round 4 — VOTE:      All agents cast final votes (parallel)
  Round 5 — SYNTHESIS: Chairman aggregates votes → ICVerdict
"""

from src.engines.fundamental.committee.models import (
    ICMember,
    PositionMemo,
    Challenge,
    Rebuttal,
    Vote,
    ICTranscript,
    ICVerdict,
)
from src.engines.fundamental.committee.debate import InvestmentCommitteeDebate
from src.engines.fundamental.committee.chairman import ChairmanSynthesizer

__all__ = [
    "ICMember",
    "PositionMemo",
    "Challenge",
    "Rebuttal",
    "Vote",
    "ICTranscript",
    "ICVerdict",
    "InvestmentCommitteeDebate",
    "ChairmanSynthesizer",
]
