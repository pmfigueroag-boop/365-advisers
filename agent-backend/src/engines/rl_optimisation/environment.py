"""
src/engines/rl_optimisation/environment.py — Portfolio gym environment.

State: [lookback returns × n_assets, lookback vols × n_assets, current weights]
Action: target weights (softmax over n_assets)
Reward: portfolio return - risk_penalty × variance - transaction_costs
"""
from __future__ import annotations
import numpy as np
import logging

logger = logging.getLogger("365advisers.rl.environment")


class PortfolioEnv:
    """
    Portfolio allocation environment for RL.

    At each step, the agent chooses portfolio weights.
    Reward = risk-adjusted return after costs.
    """

    def __init__(
        self,
        returns: np.ndarray,  # [T × n_assets]
        lookback: int = 20,
        risk_penalty: float = 0.5,
        transaction_cost: float = 0.001,
    ):
        self.returns = returns
        self.T, self.n_assets = returns.shape
        self.lookback = lookback
        self.risk_penalty = risk_penalty
        self.tc = transaction_cost

        self._t = lookback
        self._weights = np.ones(self.n_assets) / self.n_assets

    @property
    def state_dim(self) -> int:
        return self.n_assets * 3  # returns + vols + weights

    @property
    def action_dim(self) -> int:
        return self.n_assets

    def reset(self) -> np.ndarray:
        self._t = self.lookback
        self._weights = np.ones(self.n_assets) / self.n_assets
        return self._get_state()

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool]:
        """
        Args:
            action: target weights (must sum to 1)

        Returns:
            (next_state, reward, done)
        """
        new_weights = np.abs(action) / (np.sum(np.abs(action)) + 1e-8)

        # Transaction cost
        turnover = np.sum(np.abs(new_weights - self._weights))
        tc = turnover * self.tc

        # Portfolio return at time t
        port_return = float(self.returns[self._t] @ new_weights)

        # Risk: variance of recent portfolio returns
        recent = self.returns[self._t - self.lookback:self._t] @ new_weights
        port_var = float(np.var(recent))

        # Reward
        reward = port_return - self.risk_penalty * port_var - tc

        self._weights = new_weights
        self._t += 1
        done = self._t >= self.T

        return self._get_state(), reward, done

    def _get_state(self) -> np.ndarray:
        window = self.returns[self._t - self.lookback:self._t]
        avg_ret = np.mean(window, axis=0)
        vols = np.std(window, axis=0)
        return np.concatenate([avg_ret, vols, self._weights])
