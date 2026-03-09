"""
src/engines/rl_optimisation/models.py — RL portfolio optimisation contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class RLConfig(BaseModel):
    episodes: int = 500
    gamma: float = 0.99          # discount factor
    learning_rate: float = 0.01
    lookback: int = 20           # observation window
    risk_penalty: float = 0.5    # penalty on variance
    transaction_cost: float = 0.001  # fraction
    hidden_size: int = 32


class RLState(BaseModel):
    """Environment observation."""
    returns: list[float] = Field(default_factory=list)       # recent returns per asset
    volatilities: list[float] = Field(default_factory=list)  # recent vol per asset
    current_weights: list[float] = Field(default_factory=list)


class RLAction(BaseModel):
    """Agent action: target portfolio weights."""
    weights: list[float] = Field(default_factory=list)


class EpisodeLog(BaseModel):
    episode: int = 0
    total_reward: float = 0.0
    final_return: float = 0.0
    avg_sharpe: float = 0.0


class RLResult(BaseModel):
    optimal_weights: dict[str, float] = Field(default_factory=dict)
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    episodes_trained: int = 0
    final_reward: float = 0.0
    training_curve: list[float] = Field(default_factory=list)  # rewards per episode
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
