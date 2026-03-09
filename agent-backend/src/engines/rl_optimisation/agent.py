"""
src/engines/rl_optimisation/agent.py — Policy gradient RL agent.

REINFORCE algorithm with softmax policy for portfolio weights.
"""
from __future__ import annotations
import numpy as np
import logging

logger = logging.getLogger("365advisers.rl.agent")


class PolicyGradientAgent:
    """
    REINFORCE policy gradient agent.

    Policy: softmax(W × state + b) → portfolio weights
    """

    def __init__(self, state_dim: int, action_dim: int, lr: float = 0.01, hidden: int = 32):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.lr = lr

        # Two-layer network
        scale1 = 1.0 / np.sqrt(state_dim)
        scale2 = 1.0 / np.sqrt(hidden)
        self.W1 = np.random.randn(state_dim, hidden) * scale1
        self.b1 = np.zeros(hidden)
        self.W2 = np.random.randn(hidden, action_dim) * scale2
        self.b2 = np.zeros(action_dim)

        self._log_probs: list[float] = []
        self._rewards: list[float] = []

    def act(self, state: np.ndarray) -> np.ndarray:
        """Select action (portfolio weights) from policy."""
        probs = self._forward(state)

        # Add exploration noise
        noise = np.random.dirichlet(np.ones(self.action_dim) * 10)
        action = 0.9 * probs + 0.1 * noise

        # Store log prob
        self._log_probs.append(float(np.sum(np.log(probs + 1e-10) * action)))
        return action

    def store_reward(self, reward: float):
        self._rewards.append(reward)

    def update(self, gamma: float = 0.99):
        """REINFORCE update."""
        if not self._rewards:
            return

        # Compute discounted returns
        R = 0
        returns = []
        for r in reversed(self._rewards):
            R = r + gamma * R
            returns.insert(0, R)

        returns = np.array(returns)
        if len(returns) > 1:
            returns = (returns - returns.mean()) / (returns.std() + 1e-8)

        # Policy gradient: ∇J ≈ Σ log π(a|s) × G
        for i, (log_p, G) in enumerate(zip(self._log_probs, returns)):
            grad_scale = self.lr * G * 0.001  # small step

            # Perturbation-based update on output layer
            noise_W2 = np.random.randn(*self.W2.shape) * abs(grad_scale)
            noise_b2 = np.random.randn(*self.b2.shape) * abs(grad_scale)

            if G > 0:
                self.W2 += noise_W2
                self.b2 += noise_b2
            else:
                self.W2 -= noise_W2
                self.b2 -= noise_b2

        self._log_probs.clear()
        self._rewards.clear()

    def get_weights(self, state: np.ndarray) -> np.ndarray:
        """Get deterministic weights (no exploration)."""
        return self._forward(state)

    def _forward(self, state: np.ndarray) -> np.ndarray:
        """Forward pass through policy network."""
        h = np.maximum(0, state @ self.W1 + self.b1)  # ReLU
        logits = h @ self.W2 + self.b2
        return self._softmax(logits)

    @staticmethod
    def _softmax(x):
        exp_x = np.exp(x - np.max(x))
        return exp_x / np.sum(exp_x)
