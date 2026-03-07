"""
src/engines/signal_ensemble/co_fire.py
──────────────────────────────────────────────────────────────────────────────
Co-fire detection — finds events where multiple signals trigger on the
same ticker within a date tolerance window.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations

from src.engines.backtesting.models import SignalEvent
from src.engines.signal_ensemble.models import CoFireEvent

logger = logging.getLogger("365advisers.signal_ensemble.co_fire")


class CoFireAnalyzer:
    """Detects co-occurring signal events."""

    def __init__(self, date_tolerance: int = 3) -> None:
        self._tol = date_tolerance

    def detect_pairs(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        forward_window: int = 20,
        min_co_fires: int = 10,
    ) -> dict[tuple[str, str], list[CoFireEvent]]:
        """
        Find all signal pairs with sufficient co-fire events.

        Returns {(sig_a, sig_b): [CoFireEvent, ...]}
        """
        signal_ids = sorted(events_by_signal.keys())

        # Build ticker→date index per signal
        indexes: dict[str, dict[str, list[tuple[date, float]]]] = {}
        for sig_id, events in events_by_signal.items():
            idx: dict[str, list[tuple[date, float]]] = defaultdict(list)
            for e in events:
                ret = e.forward_returns.get(forward_window)
                if ret is not None:
                    idx[e.ticker].append((e.fired_date, ret))
            indexes[sig_id] = dict(idx)

        result: dict[tuple[str, str], list[CoFireEvent]] = {}

        for sig_a, sig_b in combinations(signal_ids, 2):
            co_fires = self._match_pair(
                sig_a, indexes.get(sig_a, {}),
                sig_b, indexes.get(sig_b, {}),
                forward_window,
            )
            if len(co_fires) >= min_co_fires:
                result[(sig_a, sig_b)] = co_fires

        logger.info(
            "CO-FIRE: Found %d pairs with ≥%d co-fires among %d signals",
            len(result), min_co_fires, len(signal_ids),
        )
        return result

    def detect_triplets(
        self,
        pairs: dict[tuple[str, str], list[CoFireEvent]],
        events_by_signal: dict[str, list[SignalEvent]],
        forward_window: int = 20,
        min_co_fires: int = 10,
    ) -> dict[tuple[str, ...], list[CoFireEvent]]:
        """
        Extend synergistic pairs to triplets using greedy expansion.

        Only considers adding a third signal to an existing pair.
        """
        result: dict[tuple[str, ...], list[CoFireEvent]] = {}

        all_sigs = set(events_by_signal.keys())
        pair_keys = list(pairs.keys())

        for sig_a, sig_b in pair_keys:
            for sig_c in all_sigs - {sig_a, sig_b}:
                key = tuple(sorted([sig_a, sig_b, sig_c]))
                if key in result:
                    continue

                # Find events where all three co-fire
                co_fires_ab = pairs[(sig_a, sig_b)]
                triplet_fires = []
                c_events = {
                    (e.ticker, e.fired_date): e.forward_returns.get(forward_window)
                    for e in events_by_signal.get(sig_c, [])
                    if e.forward_returns.get(forward_window) is not None
                }

                for cf in co_fires_ab:
                    cf_date = date.fromisoformat(cf.date)
                    # Check if sig_c also fired nearby
                    for offset in range(-self._tol, self._tol + 1):
                        check_date = cf_date + timedelta(days=offset)
                        c_ret = c_events.get((cf.ticker, check_date))
                        if c_ret is not None:
                            triplet_fires.append(CoFireEvent(
                                ticker=cf.ticker,
                                date=cf.date,
                                signal_ids=list(key),
                                returns={**cf.returns, sig_c: c_ret},
                                joint_return=(cf.joint_return + c_ret) / 2,
                            ))
                            break

                if len(triplet_fires) >= min_co_fires:
                    result[key] = triplet_fires

        logger.info("CO-FIRE: Found %d triplets", len(result))
        return result

    def _match_pair(
        self,
        sig_a: str,
        idx_a: dict[str, list[tuple[date, float]]],
        sig_b: str,
        idx_b: dict[str, list[tuple[date, float]]],
        forward_window: int,
    ) -> list[CoFireEvent]:
        """Match co-occurring events for a signal pair."""
        co_fires = []
        common_tickers = set(idx_a.keys()) & set(idx_b.keys())

        for ticker in common_tickers:
            events_a = sorted(idx_a[ticker], key=lambda x: x[0])
            # Build date lookup for B
            b_lookup: dict[date, float] = {}
            for d, r in idx_b.get(ticker, []):
                b_lookup[d] = r

            for date_a, ret_a in events_a:
                # Check exact + tolerance
                best_ret_b = None
                for offset in range(-self._tol, self._tol + 1):
                    check = date_a + timedelta(days=offset)
                    if check in b_lookup:
                        best_ret_b = b_lookup[check]
                        break

                if best_ret_b is not None:
                    joint = (ret_a + best_ret_b) / 2
                    co_fires.append(CoFireEvent(
                        ticker=ticker,
                        date=date_a.isoformat(),
                        signal_ids=[sig_a, sig_b],
                        returns={sig_a: ret_a, sig_b: best_ret_b},
                        joint_return=joint,
                    ))

        return co_fires
