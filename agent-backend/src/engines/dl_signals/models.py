"""
src/engines/dl_signals/models.py — Deep learning signal contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class DLModelType(str, Enum):
    LSTM = "lstm"
    TRANSFORMER = "transformer"
    GRU = "gru"
    TCN = "tcn"


class DLSignalConfig(BaseModel):
    model_type: DLModelType = DLModelType.LSTM
    lookback: int = 60     # input sequence length
    horizon: int = 5       # prediction horizon (days)
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.2
    learning_rate: float = 0.001
    epochs: int = 50
    batch_size: int = 32
    features: list[str] = Field(
        default_factory=lambda: ["returns", "volume", "volatility", "momentum"],
    )


class DLPrediction(BaseModel):
    ticker: str
    model_type: str
    signal: float = 0.0         # -1.0 (bearish) to +1.0 (bullish)
    predicted_return: float = 0.0
    confidence: float = 0.0     # 0-1
    horizon: int = 5
    features_used: list[str] = Field(default_factory=list)
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DLModelInfo(BaseModel):
    model_type: DLModelType
    architecture: str = ""
    total_params: int = 0
    training_loss: float = 0.0
    validation_loss: float = 0.0
    r_squared: float = 0.0
    directional_accuracy: float = 0.0
    lookback: int = 60
    horizon: int = 5
