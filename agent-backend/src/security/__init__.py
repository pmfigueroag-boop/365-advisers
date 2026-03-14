"""
src/security — Security layer for 365 Advisers

Public API:
    validate_ticker          — Validate and normalize ticker inputs
    sanitize_text_for_llm    — Clean text before LLM prompt inclusion
    sanitize_data_for_prompt — Deep-clean data dicts for prompts
"""

from src.security.sanitizer import (
    validate_ticker,
    sanitize_text_for_llm,
    sanitize_data_for_prompt,
    validate_investment_position,
)
from src.security.password import (
    hash_password,
    verify_password,
    needs_rehash,
    get_hashing_info,
)
from src.security.secrets import secrets_manager, SecretsManager

__all__ = [
    "validate_ticker",
    "sanitize_text_for_llm",
    "sanitize_data_for_prompt",
    "validate_investment_position",
    "hash_password",
    "verify_password",
    "needs_rehash",
    "get_hashing_info",
    "secrets_manager",
    "SecretsManager",
]
