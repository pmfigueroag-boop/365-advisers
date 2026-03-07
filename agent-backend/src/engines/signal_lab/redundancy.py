"""
src/engines/signal_lab/redundancy.py
─────────────────────────────────────────────────────────────────────────────
RedundancyDetector — identify signals that provide overlapping information.

Uses co-fire analysis and coverage metrics to flag signals that are
redundant with others in the library, recommending which to keep.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from .comparator import SignalComparator

logger = logging.getLogger(__name__)


class RedundancyDetector:
    """Detect and report on signal redundancy in the signal library."""

    @staticmethod
    def analyze(
        signal_fires: dict[str, list[dict]],
        evaluations: dict[str, dict] | None = None,
        overlap_threshold: float = 0.7,
    ) -> dict:
        """Full redundancy analysis across all signals.

        Args:
            signal_fires: {signal_id: [fire_dicts]}
            evaluations: Optional {signal_id: evaluation_dict} from SignalEvaluator
            overlap_threshold: Min overlap fraction to flag redundancy

        Returns:
            {
                "redundant_pairs": [...],
                "clusters": [...],          # groups of correlated signals
                "recommendations": [...],   # keep/remove/merge suggestions
                "redundancy_score": float,  # 0–1, library-level
            }
        """
        # Step 1: Find redundant pairs
        pairs = SignalComparator.find_redundant_pairs(signal_fires, overlap_threshold)

        # Step 2: Cluster correlated signals
        clusters = _build_clusters(pairs, signal_fires.keys())

        # Step 3: Generate recommendations
        recommendations = _generate_recommendations(clusters, evaluations or {})

        # Step 4: Library-level redundancy score
        total_signals = len(signal_fires)
        redundant_signals = sum(1 for c in clusters if len(c["members"]) > 1)
        redundancy_score = redundant_signals / total_signals if total_signals > 0 else 0.0

        return {
            "redundant_pairs": pairs,
            "clusters": clusters,
            "recommendations": recommendations,
            "redundancy_score": round(redundancy_score, 4),
            "total_signals": total_signals,
            "unique_clusters": len(clusters),
        }


def _build_clusters(
    pairs: list[dict],
    all_signals: list[str] | set[str] | dict,
) -> list[dict]:
    """Group redundant signals into clusters using union-find."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: str, b: str):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Initialize all signals
    for sig in all_signals:
        find(sig)

    # Union redundant pairs
    for pair in pairs:
        union(pair["signal_a"], pair["signal_b"])

    # Build clusters
    cluster_map: dict[str, list[str]] = defaultdict(list)
    for sig in all_signals:
        root = find(sig)
        cluster_map[root].append(sig)

    clusters = []
    for root, members in cluster_map.items():
        clusters.append({
            "cluster_id": root,
            "members": sorted(members),
            "size": len(members),
            "is_redundant": len(members) > 1,
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


def _generate_recommendations(
    clusters: list[dict],
    evaluations: dict[str, dict],
) -> list[dict]:
    """Generate keep/remove/merge recommendations for each cluster."""
    recommendations = []

    for cluster in clusters:
        if cluster["size"] == 1:
            recommendations.append({
                "signal_id": cluster["members"][0],
                "action": "keep",
                "reason": "unique signal, no redundancy detected",
                "cluster_size": 1,
            })
            continue

        # For multi-member clusters, rank by performance
        ranked = []
        for member in cluster["members"]:
            ev = evaluations.get(member, {})
            score = ev.get("avg_confidence", 0.0) * ev.get("total_fires", 0)
            ranked.append((member, score))

        ranked.sort(key=lambda x: x[1], reverse=True)

        # Keep the best, recommend review for others
        for i, (member, score) in enumerate(ranked):
            if i == 0:
                recommendations.append({
                    "signal_id": member,
                    "action": "keep",
                    "reason": f"best performing in cluster of {cluster['size']}",
                    "cluster_size": cluster["size"],
                })
            else:
                recommendations.append({
                    "signal_id": member,
                    "action": "review",
                    "reason": f"overlaps with {ranked[0][0]} — consider merging or removing",
                    "cluster_size": cluster["size"],
                    "better_alternative": ranked[0][0],
                })

    return recommendations
