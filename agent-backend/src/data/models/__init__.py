"""
src/data/models/__init__.py
─────────────────────────────────────────────────────────────────────────────
Re-export all models from domain-grouped submodules.
This enables both new-style and legacy imports to work:

    from src.data.models import FundamentalAnalysis      # new
    from src.data.models.analysis import FundamentalAnalysis  # also works
"""

# Core
from src.data.models.base import Base, ENGINE, SessionLocal, init_db  # noqa: F401

# Analysis
from src.data.models.analysis import (  # noqa: F401
    FundamentalAnalysis,
    TechnicalAnalysis,
    ScoreHistory,
    OpportunityScoreHistory,
)

# Portfolio & Ideas
from src.data.models.portfolio import (  # noqa: F401
    Portfolio,
    PortfolioPosition,
    IdeaRecord,
    OpportunityAlertRecord,
)

# Signals
from src.data.models.signals import (  # noqa: F401
    SignalSnapshot,
    CompositeAlphaHistory,
    SignalActivationRecord,
    SignalPerformanceEventRecord,
    SignalCalibrationHistoryRecord,
    LiveSignalTrackingRecord,
    SignalCandidateRecord,
    SignalVersionRecord,
)

# Backtesting & Validation
from src.data.models.backtesting import (  # noqa: F401
    BacktestRun,
    BacktestResult,
    RollingPerformanceRecord,
    OpportunityPerformanceRecord,
    DegradationAlertRecord,
    WalkForwardRunRecord,
    WalkForwardFoldRecord,
    WalkForwardSignalResultRecord,
    CostModelProfileRecord,
    BenchmarkFactorProfileRecord,
    SignalRedundancyRecord,
    RegimeWeightRecord,
    SignalEnsembleRecord,
)

# Governance
from src.data.models.governance import (  # noqa: F401
    ExperimentRecord,
    ExperimentArtifactRecord,
    GovernanceAuditRecord,
    MetaLearningRecord,
    ConceptDriftRecord,
    OnlineLearningRecord,
    AllocationLearningRecord,
)

# Operations
from src.data.models.operations import (  # noqa: F401
    ShadowPortfolioRecord,
    ShadowPositionRecord,
    ShadowSnapshotRecord,
    StrategyRecord,
    LiquidityProfileRecord,
    PilotRunRecord,
    PilotDailySnapshotRecord,
    PilotAlertRecord,
    PilotMetricRecord,
)

# Cache
from src.data.models.cache import (  # noqa: F401
    FundamentalDBCache,
    TechnicalDBCache,
)

# Queries
from src.data.models.queries import get_score_history  # noqa: F401
