"""
src/data/database.py
─────────────────────────────────────────────────────────────────────────────
BACKWARD-COMPATIBLE RE-EXPORT SHIM.

This file was the original 1294-line monolith containing all 40+ SQLAlchemy
models. It has been split into domain-grouped submodules under
src/data/models/. This shim re-exports everything so that all existing
imports (50+ files) continue to work unchanged.

New code should import from src.data.models directly:
    from src.data.models import FundamentalAnalysis
    from src.data.models.analysis import FundamentalAnalysis
"""

# Re-export everything from the new models package
from src.data.models import *                    # noqa: F401, F403
from src.data.models.cache import (              # noqa: F401
    FundamentalDBCache,
    TechnicalDBCache,
)
from src.data.models.queries import (            # noqa: F401
    get_score_history,
)
