"""
src/engines/online_learning/engine.py
──────────────────────────────────────────────────────────────────────────────
Online Learning Engine — orchestrator.

Pipeline:
  1. Receive new observations (signal returns)
  2. Check warmup period
  3. For each signal: compute EMA delta → dampen → validate → apply
  4. Optionally normalize weights
  5. Decay learning rate
  6. Persist audit trail
"""

from __future__ import annotations

import logging
from copy import deepcopy

from src.engines.online_learning.dampener import ChangeDampener
from src.engines.online_learning.models import (
    LearningState,
    OnlineLearningConfig,
    OnlineLearningReport,
    SignalObservation,
    WeightUpdate,
)
from src.engines.online_learning.updater import EMAUpdater

logger = logging.getLogger("365advisers.online_learning.engine")


class OnlineLearningEngine:
    """
    Incrementally updates signal weights as new data arrives.

    Usage::

        engine = OnlineLearningEngine()
        report = engine.process_observations(observations, current_weights)
        # report.updates contains the weight changes
        # report.state contains the new learning state
    """

    def __init__(self, config: OnlineLearningConfig | None = None) -> None:
        self.config = config or OnlineLearningConfig()
        self._updater = EMAUpdater()
        self._dampener = ChangeDampener()

        # Internal state: per-signal tracking
        self._states: dict[str, LearningState] = {}
        self._current_lr: float = self.config.learning_rate

    # ── Public API ────────────────────────────────────────────────────────

    def process_observations(
        self,
        observations: list[SignalObservation],
        current_weights: dict[str, float] | None = None,
        config: OnlineLearningConfig | None = None,
    ) -> OnlineLearningReport:
        """
        Process a batch of new observations and update weights.

        Parameters
        ----------
        observations : list[SignalObservation]
            New data points, one per signal.
        current_weights : dict | None
            Current signal weights. If None, uses internal state.
        config : OnlineLearningConfig | None

        Returns
        -------
        OnlineLearningReport
        """
        cfg = config or self.config
        weights = dict(current_weights) if current_weights else {}

        updates: list[WeightUpdate] = []
        dampened_count = 0

        for obs in observations:
            # Initialize state if new signal
            if obs.signal_id not in self._states:
                self._states[obs.signal_id] = LearningState(
                    signal_id=obs.signal_id,
                    current_weight=weights.get(obs.signal_id, 1.0 / max(1, len(observations))),
                    current_learning_rate=self._current_lr,
                )

            state = self._states[obs.signal_id]
            state.observations_count += 1
            state.cumulative_return += obs.forward_return
            if obs.hit or obs.forward_return > 0:
                hits = state.hit_rate * (state.observations_count - 1) + 1
                state.hit_rate = hits / state.observations_count
            else:
                hits = state.hit_rate * (state.observations_count - 1)
                state.hit_rate = hits / state.observations_count

            current_w = weights.get(obs.signal_id, state.current_weight)

            # Check warmup
            if state.observations_count < cfg.warmup_observations:
                updates.append(WeightUpdate(
                    signal_id=obs.signal_id,
                    weight_before=current_w,
                    weight_after=current_w,
                    delta=0.0,
                    raw_delta=0.0,
                    dampened=False,
                    observation_return=obs.forward_return,
                    learning_rate_used=self._current_lr,
                ))
                continue

            # EMA update
            raw_delta = self._updater.compute_raw_delta(
                obs, current_w, self._current_lr, cfg,
            )

            # Dampen
            delta, was_dampened = self._dampener.dampen(
                raw_delta, current_w, cfg,
            )
            if was_dampened:
                dampened_count += 1

            # Apply
            new_w = current_w + delta
            weights[obs.signal_id] = new_w
            state.current_weight = new_w

            updates.append(WeightUpdate(
                signal_id=obs.signal_id,
                weight_before=round(current_w, 6),
                weight_after=round(new_w, 6),
                delta=round(delta, 6),
                raw_delta=round(raw_delta, 6),
                dampened=was_dampened,
                observation_return=obs.forward_return,
                learning_rate_used=round(self._current_lr, 6),
            ))

        # Normalize if configured
        if cfg.normalize_weights and weights:
            weights = self._dampener.normalize_weights(weights)
            for u in updates:
                if u.signal_id in weights:
                    u.weight_after = round(weights[u.signal_id], 6)

        # Decay learning rate
        if cfg.decay_learning_rate:
            self._current_lr = self._updater.decay_lr(
                self._current_lr, cfg.lr_decay_factor,
            )
        for state in self._states.values():
            state.current_learning_rate = self._current_lr

        warmed_up = all(
            s.observations_count >= cfg.warmup_observations
            for s in self._states.values()
        )

        report = OnlineLearningReport(
            config=cfg,
            updates=updates,
            state=list(self._states.values()),
            total_observations=sum(s.observations_count for s in self._states.values()),
            dampened_count=dampened_count,
            current_learning_rate=round(self._current_lr, 6),
            warmed_up=warmed_up,
        )

        logger.info(
            "ONLINE-LEARNING: %d observations, %d dampened, lr=%.4f, warmed_up=%s",
            len(observations), dampened_count, self._current_lr, warmed_up,
        )
        return report

    def get_current_weights(self) -> dict[str, float]:
        """Return the current weight state."""
        return {s.signal_id: s.current_weight for s in self._states.values()}

    def get_state(self) -> list[LearningState]:
        """Return current learning state for all signals."""
        return list(self._states.values())

    def reset(self) -> None:
        """Reset all internal state."""
        self._states.clear()
        self._current_lr = self.config.learning_rate
