"""
src/engines/ml_signals/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the ML Signal Factory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class ModelType(str, Enum):
    """Supported sklearn model families."""
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOST = "gradient_boost"
    LOGISTIC = "logistic"
    LINEAR = "linear"
    LASSO = "lasso"


class ModelStatus(str, Enum):
    """Model lifecycle status."""
    TRAINING = "training"
    READY = "ready"
    DEPLOYED = "deployed"
    RETIRED = "retired"
    FAILED = "failed"


class SignalDirection(str, Enum):
    """ML signal classification."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ── Configuration ────────────────────────────────────────────────────────────

class MLModelConfig(BaseModel):
    """Hyperparameters and training configuration for an ML model."""
    model_type: ModelType = ModelType.RANDOM_FOREST
    target_variable: str = Field(
        "forward_return_20d",
        description="Target to predict: forward_return_20d, forward_return_5d, etc.",
    )
    features: list[str] = Field(
        default_factory=list,
        description="Feature names to use; empty = use all available",
    )
    test_size: float = Field(0.20, ge=0.05, le=0.50)
    n_estimators: int = Field(100, ge=10, le=1000)
    max_depth: int | None = Field(8, ge=1, le=50)
    learning_rate: float = Field(0.1, gt=0.0, le=1.0)
    min_samples_leaf: int = Field(5, ge=1)
    random_state: int = 42
    class_threshold: float = Field(
        0.01,
        description="Return threshold for binary classification: >threshold=BULLISH",
    )


# ── Feature Importance ───────────────────────────────────────────────────────

class FeatureImportance(BaseModel):
    """Importance of a single feature in a trained model."""
    feature_name: str
    importance: float = Field(0.0, ge=0.0)
    rank: int = Field(0, ge=0)


# ── ML Signal Output ────────────────────────────────────────────────────────

class MLSignalOutput(BaseModel):
    """Prediction output for a single ticker."""
    ticker: str
    prediction: float = Field(
        0.0,
        description="Raw model output (probability for classifiers, value for regressors)",
    )
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    direction: SignalDirection = SignalDirection.NEUTRAL
    model_id: str = ""
    model_type: str = ""
    top_features: list[FeatureImportance] = Field(
        default_factory=list,
        description="Top contributing features for this prediction",
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Model Card ───────────────────────────────────────────────────────────────

class ModelCard(BaseModel):
    """Metadata and performance metrics for a trained model."""
    model_id: str = ""
    model_type: ModelType = ModelType.RANDOM_FOREST
    status: ModelStatus = ModelStatus.READY
    version: str = "1.0.0"

    # Training metadata
    trained_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    training_samples: int = 0
    test_samples: int = 0
    feature_count: int = 0
    feature_names: list[str] = Field(default_factory=list)

    # Performance metrics
    accuracy: float = Field(0.0, ge=0.0, le=1.0)
    precision: float = Field(0.0, ge=0.0, le=1.0)
    recall: float = Field(0.0, ge=0.0, le=1.0)
    f1_score: float = Field(0.0, ge=0.0, le=1.0)
    information_coefficient: float = Field(0.0, ge=-1.0, le=1.0)
    hit_rate: float = Field(0.0, ge=0.0, le=1.0)

    # Feature importances
    feature_importances: list[FeatureImportance] = Field(default_factory=list)

    # Config used
    config: MLModelConfig = Field(default_factory=MLModelConfig)


# ── Registry Entry ───────────────────────────────────────────────────────────

class ModelRegistryEntry(BaseModel):
    """A model stored in the registry (card + serialized bytes)."""
    card: ModelCard
    model_bytes_b64: str = Field(
        "",
        description="Base64-encoded pickled sklearn model",
    )
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
