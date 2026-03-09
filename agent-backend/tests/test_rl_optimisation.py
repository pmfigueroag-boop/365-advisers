"""
tests/test_rl_optimisation.py — RL portfolio optimisation tests.
"""
import numpy as np
import pytest
from src.engines.rl_optimisation.models import RLConfig
from src.engines.rl_optimisation.environment import PortfolioEnv
from src.engines.rl_optimisation.agent import PolicyGradientAgent
from src.engines.rl_optimisation.engine import RLOptimisationEngine


def _sample_returns(n_assets=3, n_obs=200, seed=42):
    np.random.seed(seed)
    return np.random.randn(n_obs, n_assets) * 0.01 + 0.0003


class TestPortfolioEnv:
    def test_reset(self):
        data = _sample_returns()
        env = PortfolioEnv(data, lookback=20)
        state = env.reset()
        assert len(state) == env.state_dim

    def test_step(self):
        data = _sample_returns()
        env = PortfolioEnv(data, lookback=20)
        env.reset()
        action = np.array([0.4, 0.3, 0.3])
        state, reward, done = env.step(action)
        assert len(state) == env.state_dim
        assert isinstance(reward, float)
        assert isinstance(done, bool)

    def test_episode(self):
        data = _sample_returns(3, 50)
        env = PortfolioEnv(data, lookback=10)
        env.reset()
        steps = 0
        while True:
            action = np.ones(3) / 3
            _, _, done = env.step(action)
            steps += 1
            if done:
                break
        assert steps == 50 - 10


class TestAgent:
    def test_act(self):
        agent = PolicyGradientAgent(9, 3, lr=0.01, hidden=16)
        state = np.random.randn(9)
        action = agent.act(state)
        assert len(action) == 3
        assert np.sum(action) == pytest.approx(1.0, abs=0.05)

    def test_weights_sum(self):
        agent = PolicyGradientAgent(9, 3)
        state = np.random.randn(9)
        weights = agent.get_weights(state)
        assert np.sum(weights) == pytest.approx(1.0, abs=0.01)

    def test_update(self):
        agent = PolicyGradientAgent(9, 3, lr=0.01, hidden=16)
        state = np.random.randn(9)
        for _ in range(5):
            agent.act(state)
            agent.store_reward(0.01)
        agent.update()  # Should not raise


class TestRLEngine:
    def test_optimise(self):
        np.random.seed(42)
        returns = {
            "A": (np.random.randn(150) * 0.01 + 0.0004).tolist(),
            "B": (np.random.randn(150) * 0.015 + 0.0003).tolist(),
            "C": (np.random.randn(150) * 0.02 + 0.0005).tolist(),
        }
        config = RLConfig(episodes=20, lookback=20, hidden_size=16)
        result = RLOptimisationEngine.optimise(returns, config)
        assert len(result.optimal_weights) == 3
        assert sum(result.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)
        assert result.episodes_trained == 20

    def test_training_curve(self):
        np.random.seed(42)
        returns = {
            "X": (np.random.randn(100) * 0.01).tolist(),
            "Y": (np.random.randn(100) * 0.01).tolist(),
        }
        config = RLConfig(episodes=10, lookback=10, hidden_size=8)
        result = RLOptimisationEngine.optimise(returns, config)
        assert len(result.training_curve) == 10

    def test_weights_positive(self):
        np.random.seed(42)
        returns = {
            "A": (np.random.randn(100) * 0.01).tolist(),
            "B": (np.random.randn(100) * 0.01).tolist(),
        }
        config = RLConfig(episodes=10, lookback=10, hidden_size=8)
        result = RLOptimisationEngine.optimise(returns, config)
        for w in result.optimal_weights.values():
            assert w >= 0  # softmax → positive
