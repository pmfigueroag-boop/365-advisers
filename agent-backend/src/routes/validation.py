"""
src/routes/validation.py
─────────────────────────────────────────────────────────────────────────────
BACKWARD-COMPATIBLE RE-EXPORT SHIM.

This file was the original 1607-line monolith containing all QVF endpoints.
It has been split into domain-grouped sub-modules under
src/routes/validation_pkg/. This shim re-exports the combined router so
that the main.py import continues to work unchanged.

New code should import from src.routes.validation_pkg directly.
"""

from src.routes.validation_pkg import router  # noqa: F401
