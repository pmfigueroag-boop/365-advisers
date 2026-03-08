"""
src/engines/strategy/definition.py
─────────────────────────────────────────────────────────────────────────────
Strategy Definition Framework — declarative strategy models & CRUD.

Provides Pydantic models for every strategy component with YAML support
and backward-compatible serialization to JSON for database persistence.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator
from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.strategy.definition")


# ── Enums ─────────────────────────────────────────────────────────────────────

class StrategyCategory(str, Enum):
    """Strategy classification categories."""
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    MULTI_FACTOR = "multi_factor"
    EVENT_DRIVEN = "event_driven"
    THEMATIC = "thematic"
    LOW_VOL = "low_vol"


class Horizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class SizingMethod(str, Enum):
    EQUAL = "equal"
    VOL_PARITY = "vol_parity"
    RANK_WEIGHTED = "rank_weighted"
    RISK_BUDGET = "risk_budget"


class RebalanceFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class RebalanceTrigger(str, Enum):
    CALENDAR = "calendar"
    DRIFT_BASED = "drift_based"
    SIGNAL_BASED = "signal_based"


class LifecycleState(str, Enum):
    DRAFT = "draft"
    RESEARCH = "research"
    BACKTESTED = "backtested"
    VALIDATED = "validated"
    PAPER = "paper"
    LIVE = "live"
    PAUSED = "paused"
    RETIRED = "retired"


class CompositionLogic(str, Enum):
    ALL_REQUIRED = "all_required"
    ANY_REQUIRED = "any_required"
    WEIGHTED = "weighted"


# ── Sub-models ────────────────────────────────────────────────────────────────

class EntryRule(BaseModel):
    """Declarative entry condition beyond signal filters."""
    field: str              # Field to evaluate: "case_score", "crowding", "uos"
    operator: str           # "gt", "lt", "gte", "lte", "eq", "in", "not_in"
    value: float | str | list = 0
    priority: int = 0       # Evaluation order (lower = first)
    label: str = ""         # Human-readable description


class ExitRule(BaseModel):
    """Declarative exit condition."""
    rule_type: str           # "trailing_stop", "time_stop", "signal_reversal", "target_reached"
    params: dict[str, Any] = Field(default_factory=dict)
    # Examples:
    #   trailing_stop: {"pct": 0.15}
    #   time_stop: {"days": 60}
    #   signal_reversal: {"signal_categories": ["momentum"]}
    #   target_reached: {"return_pct": 0.30}


class RegimeAction(BaseModel):
    """Action to take for a specific market regime."""
    regime: str              # "bull", "bear", "high_vol", "low_vol", "range"
    action: str              # "full_exposure", "reduce_50", "no_new_entries", "exit_all"
    sizing_override: float | None = None  # Override max_single_position


class UniverseConfig(BaseModel):
    """Asset universe definition."""
    source: str = "all"                    # "all", "sp500", "nasdaq100", "russell2000", "custom"
    custom_tickers: list[str] = Field(default_factory=list)
    sector_filter: list[str] = Field(default_factory=list)
    sector_exclude: list[str] = Field(default_factory=list)
    min_market_cap: float | None = None
    min_adv: float | None = None           # Minimum average daily volume USD
    max_volatility: float | None = None    # Maximum annualized volatility


class StrategyMetadata(BaseModel):
    """Descriptive metadata for strategy classification."""
    strategy_type: str = "systematic"      # systematic | discretionary | hybrid
    category: str = "multi_factor"         # StrategyCategory value
    horizon: str = "medium"                # Horizon value
    expected_turnover: str = "medium"      # low | medium | high
    benchmark: str = "SPY"                 # Benchmark ticker
    tags: list[str] = Field(default_factory=list)


class SignalComposition(BaseModel):
    """How the strategy combines alpha signals."""
    required_categories: list[str] = Field(default_factory=list)
    preferred_signals: list[str] = Field(default_factory=list)
    min_signal_strength: float = 0.0
    min_confidence: str = "low"            # low | medium | high
    composition_logic: str = "all_required"  # CompositionLogic value
    min_active_signals: int = 1


class ScoreThresholds(BaseModel):
    """Score-based filtering thresholds."""
    min_case_score: float = 0
    min_opportunity_score: float = 0.0
    min_business_quality: float = 0.0
    min_uos: float = 0.0
    max_freshness_class: str = "stale"     # "fresh", "stale" (reject "expired")


class PortfolioRules(BaseModel):
    """Portfolio construction rules."""
    max_positions: int = 20
    max_single_position: float = 0.10      # 10% max per position
    max_sector_exposure: float = 0.25      # 25% sector cap
    sizing_method: str = "vol_parity"      # SizingMethod value
    max_turnover: float = 0.50             # Max turnover per rebalance
    risk_budget_pct: float = 100.0         # Pct of total portfolio risk


class RebalanceConfig(BaseModel):
    """Rebalancing schedule and triggers."""
    frequency: str = "weekly"              # RebalanceFrequency value
    trigger_type: str = "calendar"         # RebalanceTrigger value
    drift_threshold: float = 0.05          # 5% drift triggers rebalance


# ── Main Strategy Config ──────────────────────────────────────────────────────

class StrategyConfig(BaseModel):
    """Declarative strategy configuration — full framework model.

    Backward-compatible: legacy fields (signal_filters, score_filters,
    portfolio_rules as dicts) are still accepted and merged into the
    typed sub-models.
    """

    # ── Typed sub-models (new, preferred) ──
    signals: SignalComposition = Field(default_factory=SignalComposition)
    thresholds: ScoreThresholds = Field(default_factory=ScoreThresholds)
    portfolio: PortfolioRules = Field(default_factory=PortfolioRules)
    rebalance: RebalanceConfig = Field(default_factory=RebalanceConfig)

    # ── Legacy dict fields (backward-compatible, supported but deprecated) ──
    signal_filters: dict[str, Any] = Field(default_factory=lambda: {
        "required_categories": [],
        "min_signal_strength": 0.0,
        "min_confidence": "low",
    })
    score_filters: dict[str, Any] = Field(default_factory=lambda: {
        "min_case_score": 0,
        "min_business_quality": 0.0,
        "min_uos": 0.0,
    })
    portfolio_rules: dict[str, Any] = Field(default_factory=lambda: {
        "max_positions": 20,
        "sizing_method": "vol_parity",
        "rebalance_frequency": "weekly",
        "max_single_position": 0.10,
        "max_sector_exposure": 0.25,
    })

    # ── Strategy Research Lab extensions ──
    entry_rules: list[EntryRule] = Field(default_factory=list)
    exit_rules: list[ExitRule] = Field(default_factory=list)
    regime_rules: list[RegimeAction] = Field(default_factory=list)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    metadata: StrategyMetadata = Field(default_factory=StrategyMetadata)

    @model_validator(mode="after")
    def _sync_legacy_to_typed(self) -> "StrategyConfig":
        """Merge legacy dict fields into typed sub-models if they carry data."""
        sf = self.signal_filters
        if sf.get("required_categories"):
            self.signals.required_categories = sf["required_categories"]
        if sf.get("min_signal_strength", 0) > 0:
            self.signals.min_signal_strength = sf["min_signal_strength"]
        if sf.get("min_confidence", "low") != "low":
            self.signals.min_confidence = sf["min_confidence"]

        scf = self.score_filters
        if scf.get("min_case_score", 0) > 0:
            self.thresholds.min_case_score = scf["min_case_score"]
        if scf.get("min_business_quality", 0) > 0:
            self.thresholds.min_business_quality = scf["min_business_quality"]
        if scf.get("min_uos", 0) > 0:
            self.thresholds.min_uos = scf["min_uos"]

        pr = self.portfolio_rules
        if pr.get("max_positions", 20) != 20:
            self.portfolio.max_positions = pr["max_positions"]
        if pr.get("sizing_method", "vol_parity") != "vol_parity":
            self.portfolio.sizing_method = pr["sizing_method"]
        if pr.get("max_single_position", 0.10) != 0.10:
            self.portfolio.max_single_position = pr["max_single_position"]
        if pr.get("max_sector_exposure", 0.25) != 0.25:
            self.portfolio.max_sector_exposure = pr["max_sector_exposure"]
        if pr.get("rebalance_frequency", "weekly") != "weekly":
            self.rebalance.frequency = pr["rebalance_frequency"]

        return self

    def get_signal_filters(self) -> dict[str, Any]:
        """Merged signal filtering config (for StrategyComposer compat)."""
        return {
            "required_categories": self.signals.required_categories,
            "min_signal_strength": self.signals.min_signal_strength,
            "min_confidence": self.signals.min_confidence,
            **{k: v for k, v in self.signal_filters.items()
               if k not in ("required_categories", "min_signal_strength", "min_confidence")},
        }

    def get_score_filters(self) -> dict[str, Any]:
        """Merged score filtering config."""
        return {
            "min_case_score": self.thresholds.min_case_score,
            "min_business_quality": self.thresholds.min_business_quality,
            "min_uos": self.thresholds.min_uos,
            **{k: v for k, v in self.score_filters.items()
               if k not in ("min_case_score", "min_business_quality", "min_uos")},
        }

    def get_portfolio_rules(self) -> dict[str, Any]:
        """Merged portfolio rules config."""
        return {
            "max_positions": self.portfolio.max_positions,
            "sizing_method": self.portfolio.sizing_method,
            "max_single_position": self.portfolio.max_single_position,
            "max_sector_exposure": self.portfolio.max_sector_exposure,
            "rebalance_frequency": self.rebalance.frequency,
            **{k: v for k, v in self.portfolio_rules.items()
               if k not in (
                   "max_positions", "sizing_method", "max_single_position",
                   "max_sector_exposure", "rebalance_frequency",
               )},
        }


# ── YAML Support ──────────────────────────────────────────────────────────────

def load_strategy_yaml(path: str | Path) -> dict:
    """Load a strategy definition from a YAML file.

    Returns a dict that can be passed to StrategyConfig(**data).
    """
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for YAML support: pip install pyyaml")

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    logger.info("Loaded strategy from YAML: %s", path.name)
    return data


def save_strategy_yaml(config: StrategyConfig, path: str | Path, *, name: str = "", description: str = "", version: str = "1.0.0") -> Path:
    """Save a strategy configuration to a YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for YAML support: pip install pyyaml")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(exclude_defaults=False)
    if name:
        data["name"] = name
    if description:
        data["description"] = description
    data["version"] = version

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info("Saved strategy to YAML: %s", path.name)
    return path


def load_all_strategies_from_dir(directory: str | Path) -> list[dict]:
    """Load all .yaml strategy files from a directory."""
    directory = Path(directory)
    if not directory.exists():
        return []

    results = []
    for yaml_file in sorted(directory.glob("**/*.yaml")):
        try:
            data = load_strategy_yaml(yaml_file)
            data["_source_file"] = str(yaml_file)
            results.append(data)
        except Exception as e:
            logger.warning("Failed to load strategy %s: %s", yaml_file.name, e)

    return results


# ── API Models ────────────────────────────────────────────────────────────────

class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    config: StrategyConfig = Field(default_factory=StrategyConfig)
    created_by: str = "manual"


class StrategySummary(BaseModel):
    strategy_id: str
    name: str
    description: str
    version: str = "1.0.0"
    lifecycle_state: str = "draft"
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

class StrategyDefinition:
    """CRUD for named investment strategies."""

    def create(self, payload: StrategyCreate) -> str:
        from src.data.database import StrategyRecord

        strategy_id = uuid.uuid4().hex[:12]
        with SessionLocal() as db:
            record = StrategyRecord(
                strategy_id=strategy_id,
                name=payload.name,
                description=payload.description,
                config_json=payload.config.model_dump_json(),
                created_by=payload.created_by,
                version=payload.version,
                lifecycle_state="draft",
            )
            db.add(record)
            db.commit()

        logger.info("Strategy created: %s — %s", strategy_id, payload.name)
        return strategy_id

    def get(self, strategy_id: str) -> StrategySummary | None:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            return self._to_summary(row) if row else None

    def list_strategies(
        self,
        active_only: bool = True,
        category: str | None = None,
        lifecycle_state: str | None = None,
        tags: list[str] | None = None,
    ) -> list[StrategySummary]:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            q = db.query(StrategyRecord)
            if active_only:
                q = q.filter(StrategyRecord.is_active == True)  # noqa: E712
            if lifecycle_state:
                q = q.filter(StrategyRecord.lifecycle_state == lifecycle_state)
            rows = q.order_by(StrategyRecord.created_at.desc()).all()

        results = [self._to_summary(r) for r in rows]

        # Post-filter by category and tags (stored in config JSON)
        if category:
            results = [
                s for s in results
                if s.config.get("metadata", {}).get("category") == category
            ]
        if tags:
            tag_set = set(tags)
            results = [
                s for s in results
                if tag_set.issubset(set(s.config.get("metadata", {}).get("tags", [])))
            ]

        return results

    def update(self, strategy_id: str, config: StrategyConfig) -> bool:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            if not row:
                return False
            row.config_json = config.model_dump_json()
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        return True

    def set_lifecycle_state(self, strategy_id: str, state: str) -> bool:
        """Transition strategy to a new lifecycle state."""
        from src.data.database import StrategyRecord

        valid_states = {e.value for e in LifecycleState}
        if state not in valid_states:
            logger.warning("Invalid lifecycle state: %s", state)
            return False

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            if not row:
                return False
            row.lifecycle_state = state
            row.updated_at = datetime.now(timezone.utc)
            if state == "retired":
                row.is_active = False
            db.commit()

        logger.info("Strategy %s → %s", strategy_id, state)
        return True

    def deactivate(self, strategy_id: str) -> bool:
        from src.data.database import StrategyRecord

        with SessionLocal() as db:
            row = db.query(StrategyRecord).filter(
                StrategyRecord.strategy_id == strategy_id
            ).first()
            if not row:
                return False
            row.is_active = False
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        return True

    @staticmethod
    def _to_summary(row) -> StrategySummary:
        return StrategySummary(
            strategy_id=row.strategy_id,
            name=row.name,
            description=row.description or "",
            version=getattr(row, "version", "1.0.0") or "1.0.0",
            lifecycle_state=getattr(row, "lifecycle_state", "draft") or "draft",
            config=json.loads(row.config_json or "{}"),
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
