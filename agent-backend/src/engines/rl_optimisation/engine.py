"""
src/engines/rl_optimisation/engine.py — RL Optimisation Engine.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.rl_optimisation.models import RLConfig, RLResult
from src.engines.rl_optimisation.environment import PortfolioEnv
from src.engines.rl_optimisation.agent import PolicyGradientAgent

logger = logging.getLogger("365advisers.rl.engine")


class RLOptimisationEngine:
    """RL-based portfolio optimisation."""

    @classmethod
    def optimise(
        cls,
        returns_dict: dict[str, list[float]],
        config: RLConfig | None = None,
    ) -> RLResult:
        """
        Train RL agent to find optimal portfolio weights.

        Args:
            returns_dict: ticker → daily returns
            config: RL hyperparameters
        """
        cfg = config or RLConfig()
        tickers = sorted(returns_dict.keys())
        n = len(tickers)
        min_len = min(len(returns_dict[t]) for t in tickers)
        data = np.array([returns_dict[t][:min_len] for t in tickers]).T

        env = PortfolioEnv(data, cfg.lookback, cfg.risk_penalty, cfg.transaction_cost)
        agent = PolicyGradientAgent(env.state_dim, env.action_dim, cfg.learning_rate, cfg.hidden_size)

        training_curve = []
        best_reward = float("-inf")
        best_weights = np.ones(n) / n

        for ep in range(cfg.episodes):
            state = env.reset()
            total_reward = 0

            while True:
                action = agent.act(state)
                next_state, reward, done = env.step(action)
                agent.store_reward(reward)
                total_reward += reward
                state = next_state
                if done:
                    break

            agent.update(cfg.gamma)
            training_curve.append(total_reward)

            if total_reward > best_reward:
                best_reward = total_reward
                # Get final weights
                final_state = env.reset()
                best_weights = agent.get_weights(final_state)

        # Compute metrics
        final_weights = best_weights / np.sum(best_weights)
        port_returns = data @ final_weights
        exp_ret = float(np.mean(port_returns) * 252)
        exp_vol = float(np.std(port_returns) * np.sqrt(252))
        sharpe = exp_ret / exp_vol if exp_vol > 0 else 0

        return RLResult(
            optimal_weights={t: round(float(w), 6) for t, w in zip(tickers, final_weights)},
            expected_return=round(exp_ret, 6),
            expected_volatility=round(exp_vol, 6),
            sharpe_ratio=round(sharpe, 4),
            episodes_trained=cfg.episodes,
            final_reward=round(best_reward, 6),
            training_curve=training_curve[-100:],
        )
