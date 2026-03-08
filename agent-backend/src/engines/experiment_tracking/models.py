"""
src/engines/experiment_tracking/models.py
─────────────────────────────────────────────────────────────────────────────
Extended experiment models for the Research Experiment Tracking System.

Extends the existing governance models with research-specific fields:
  - New ExperimentTypes (signal/strategy/portfolio research)
  - Tags, hypothesis, description
  - Data fingerprint for reproducibility
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


# ── Extended Experiment Types ─────────────────────────────────────────────────

class ResearchExperimentType(str, Enum):
    """Superset of governance ExperimentType with research-specific values."""
    # Existing types
    BACKTEST = "backtest"
    WALK_FORWARD = "walk_forward"
    DISCOVERY = "discovery"
    CALIBRATION = "calibration"
    ENSEMBLE = "ensemble"
    ONLINE_LEARNING = "online_learning"
    # New research types
    SIGNAL_RESEARCH = "signal_research"
    STRATEGY_RESEARCH = "strategy_research"
    PORTFOLIO_RESEARCH = "portfolio_research"


# ── Extended Experiment Create ────────────────────────────────────────────────

class ResearchExperimentCreate(BaseModel):
    """Enhanced experiment registration payload."""
    experiment_type: ResearchExperimentType
    name: str
    description: str = ""
    author: str = "system"
    hypothesis: str = ""
    tags: list[str] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    signal_versions: dict[str, Any] = Field(default_factory=dict)
    strategy_version: int | None = None
    data_fingerprint: str = ""
    parent_experiment_id: str | None = None


class ResearchExperimentSummary(BaseModel):
    """Enhanced experiment summary with research-specific fields."""
    experiment_id: str
    experiment_type: str
    name: str
    description: str = ""
    author: str = "system"
    hypothesis: str = ""
    tags: list[str] = Field(default_factory=list)
    status: str = "pending"
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    data_fingerprint: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    parent_experiment_id: str | None = None
    child_experiment_ids: list[str] = Field(default_factory=list)
    artifact_count: int = 0
    created_at: str | None = None
    completed_at: str | None = None


class ReproductionResult(BaseModel):
    """Result of reproducing an experiment."""
    original_experiment_id: str
    reproduction_experiment_id: str
    data_fingerprint_match: bool = False
    config_match: bool = False
    metric_drift: dict[str, float] = Field(default_factory=dict)
    reproduction_status: str = "unknown"  # exact_match | close_match | diverged


# ── Utility ───────────────────────────────────────────────────────────────────

def compute_data_fingerprint(data: dict) -> str:
    """Deterministic hash of input data for reproducibility."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
