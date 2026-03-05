"""
src/contracts/
──────────────────────────────────────────────────────────────────────────────
Typed data contracts for the 365 Advisers analytical pipeline.

Each module defines Pydantic models that serve as the formal interface
between adjacent architectural layers.  Every engine receives and returns
typed objects — no more raw dicts crossing boundaries.
"""
