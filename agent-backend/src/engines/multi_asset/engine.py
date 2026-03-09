"""src/engines/multi_asset/engine.py — Multi-asset orchestrator."""
from __future__ import annotations
from src.engines.multi_asset.models import AssetClass, AssetProfile, CorrelationMatrix, MultiAssetUniverse
from src.engines.multi_asset.normaliser import ReturnNormaliser
from src.engines.multi_asset.correlation import CorrelationEngine


class MultiAssetEngine:
    """Orchestrate cross-asset data normalisation and correlation."""

    def __init__(self):
        self._assets: dict[str, AssetProfile] = {}

    def register_asset(self, profile: AssetProfile):
        self._assets[profile.ticker] = profile

    def get_universe(self) -> MultiAssetUniverse:
        by_class: dict[str, list[str]] = {}
        for t, p in self._assets.items():
            by_class.setdefault(p.asset_class.value, []).append(t)
        return MultiAssetUniverse(
            assets=list(self._assets.values()),
            by_class=by_class,
            total_assets=len(self._assets),
        )

    @staticmethod
    def normalise_and_correlate(
        prices_dict: dict[str, list[float]], method: str = "pearson",
        return_type: str = "log",
    ) -> CorrelationMatrix:
        """Normalise prices to returns and compute correlation matrix."""
        returns = {}
        for ticker, prices in prices_dict.items():
            if return_type == "log":
                returns[ticker] = ReturnNormaliser.log_returns(prices)
            else:
                returns[ticker] = ReturnNormaliser.simple_returns(prices)
        aligned = ReturnNormaliser.align_series(returns)
        return CorrelationEngine.compute_matrix(aligned, method)
