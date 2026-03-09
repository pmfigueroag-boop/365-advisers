"""
src/engines/ml_signals/
──────────────────────────────────────────────────────────────────────────────
ML Signal Factory — train, deploy, and manage ML-based alpha signals.

Provides:
  • Feature engineering from Fundamental + Technical feature sets
  • sklearn-based model training (RF, GBM, Logistic, Linear, Lasso)
  • Model inference with calibrated confidence scoring
  • Model lifecycle registry (register, deploy, retire, compare)
  • Factory orchestrator for end-to-end signal generation
"""

from src.engines.ml_signals.models import (
    ModelType,
    ModelStatus,
    SignalDirection,
    MLModelConfig,
    FeatureImportance,
    MLSignalOutput,
    ModelCard,
    ModelRegistryEntry,
)
from src.engines.ml_signals.feature_engineering import build_feature_vector
from src.engines.ml_signals.trainer import MLTrainer
from src.engines.ml_signals.predictor import MLPredictor
from src.engines.ml_signals.model_registry import ModelRegistry
from src.engines.ml_signals.engine import MLSignalFactory

__all__ = [
    "ModelType", "ModelStatus", "SignalDirection",
    "MLModelConfig", "FeatureImportance", "MLSignalOutput",
    "ModelCard", "ModelRegistryEntry",
    "build_feature_vector",
    "MLTrainer", "MLPredictor", "ModelRegistry", "MLSignalFactory",
]
