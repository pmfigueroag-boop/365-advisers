"""src/engines/attribution/ — Brinson-Fachler performance attribution."""
from src.engines.attribution.models import (
    SectorAttribution, BrinsonResult, AttributionPeriod,
)
from src.engines.attribution.brinson import BrinsonFachler
from src.engines.attribution.engine import AttributionEngine
__all__ = ["SectorAttribution", "BrinsonResult", "AttributionPeriod",
           "BrinsonFachler", "AttributionEngine"]
