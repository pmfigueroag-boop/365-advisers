"""
src/engines/walk_forward/window_generator.py
──────────────────────────────────────────────────────────────────────────────
Generates temporal fold splits for walk-forward validation.

Supports two modes:
  - ROLLING:  Fixed-size train window slides forward each fold.
  - ANCHORED: Train start is fixed; the window grows each fold.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.engines.walk_forward.models import (
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardMode,
)

logger = logging.getLogger("365advisers.walk_forward.window_generator")

# Approximate calendar days per trading day (for conversion)
_CALENDAR_PER_TRADING = 365.25 / 252


class WindowGenerator:
    """
    Generate train/test fold splits from a date range.

    Usage::

        gen = WindowGenerator()
        folds = gen.generate(config)
    """

    def generate(self, config: WalkForwardConfig) -> list[WalkForwardFold]:
        """
        Build the list of temporal folds.

        Parameters
        ----------
        config : WalkForwardConfig
            Walk-forward configuration with date range, window sizes, and mode.

        Returns
        -------
        list[WalkForwardFold]
            Ordered list of folds covering [start_date, end_date].
        """
        train_cal = int(config.train_days * _CALENDAR_PER_TRADING)
        test_cal = int(config.test_days * _CALENDAR_PER_TRADING)
        step_cal = int(config.effective_step_days * _CALENDAR_PER_TRADING)

        folds: list[WalkForwardFold] = []
        fold_idx = 0

        if config.mode == WalkForwardMode.ROLLING:
            # ── Rolling: fixed-size train window ──────────────────────────
            train_start = config.start_date

            while True:
                train_end = train_start + timedelta(days=train_cal)
                test_start = train_end + timedelta(days=1)
                test_end = test_start + timedelta(days=test_cal)

                # Stop if test window exceeds the dataset
                if test_end > config.end_date:
                    # Allow partial last fold if at least half the test window fits
                    if test_start + timedelta(days=test_cal // 2) <= config.end_date:
                        test_end = config.end_date
                    else:
                        break

                folds.append(WalkForwardFold(
                    fold_index=fold_idx,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                ))
                fold_idx += 1
                train_start = train_start + timedelta(days=step_cal)

        elif config.mode == WalkForwardMode.ANCHORED:
            # ── Anchored: start fixed, train window grows ─────────────────
            anchor_start = config.start_date
            train_end = anchor_start + timedelta(days=train_cal)

            while True:
                test_start = train_end + timedelta(days=1)
                test_end = test_start + timedelta(days=test_cal)

                if test_end > config.end_date:
                    if test_start + timedelta(days=test_cal // 2) <= config.end_date:
                        test_end = config.end_date
                    else:
                        break

                folds.append(WalkForwardFold(
                    fold_index=fold_idx,
                    train_start=anchor_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                ))
                fold_idx += 1
                train_end = train_end + timedelta(days=step_cal)

        logger.info(
            "WINDOW-GENERATOR: %d folds (%s mode) from %s to %s",
            len(folds), config.mode.value, config.start_date, config.end_date,
        )
        return folds
