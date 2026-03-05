"""
src/engines/composite_alpha/__init__.py
──────────────────────────────────────────────────────────────────────────────
Composite Alpha Score Engine — combines multiple Alpha Signals into a
single 0–100 institutional-grade score with category subscores.

Public API:
    from src.engines.composite_alpha import CompositeAlphaEngine, CompositeAlphaResult
"""

from src.engines.composite_alpha.models import (  # noqa: F401
    CategorySubscore,
    SignalEnvironment,
    CompositeAlphaResult,
    CASEWeightConfig,
)
from src.engines.composite_alpha.engine import CompositeAlphaEngine  # noqa: F401
