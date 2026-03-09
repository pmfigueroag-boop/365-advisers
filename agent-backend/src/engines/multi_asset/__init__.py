"""src/engines/multi_asset/ — Cross-asset data normalisation and correlation."""
from src.engines.multi_asset.models import AssetClass, AssetProfile, CorrelationMatrix, MultiAssetUniverse
from src.engines.multi_asset.normaliser import ReturnNormaliser
from src.engines.multi_asset.correlation import CorrelationEngine
from src.engines.multi_asset.engine import MultiAssetEngine
__all__ = ["AssetClass", "AssetProfile", "CorrelationMatrix", "MultiAssetUniverse",
           "ReturnNormaliser", "CorrelationEngine", "MultiAssetEngine"]
