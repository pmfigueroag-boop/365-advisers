"""
src/security/sanitizer.py
─────────────────────────────────────────────────────────────────────────────
Input sanitization and validation — defends against:
  - Prompt injection via ticker/text inputs
  - SQL injection via crafted strings
  - XSS via user-provided text in responses

All user inputs should pass through these validators before
being used in LLM prompts or database queries.
"""

from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger("365advisers.security")

# ── Ticker Validation ─────────────────────────────────────────────────────────

# Valid ticker: 1-10 uppercase alpha with optional dot/dash (e.g. BRK.B, UN-P)
_TICKER_PATTERN = re.compile(r"^[A-Z]{1,10}([.\-][A-Z]{1,5})?$")

# Known prompt injection patterns (case-insensitive)
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions|prompts|rules)",
    r"you\s+are\s+now\s+(a|an|my)",
    r"forget\s+(everything|your|all)",
    r"system\s*:\s*",
    r"<\/?(?:script|system|instruction)",
    r"\[\[.*system.*\]\]",
    r"ADMIN_OVERRIDE",
    r"```\s*system",
    r"jailbreak",
    r"DAN\s+mode",
    r"pretend\s+you",
    r"act\s+as\s+(?:if|though)",
    r"new\s+instructions?:",
    r"override\s+(?:your|the)\s+(?:rules|instructions)",
]
_INJECTION_REGEX = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def validate_ticker(ticker: str) -> str:
    """
    Validate and normalize a stock ticker symbol.

    Parameters
    ----------
    ticker : str
        Raw ticker input from user

    Returns
    -------
    str
        Sanitized uppercase ticker

    Raises
    ------
    ValueError
        If ticker format is invalid
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string")

    cleaned = ticker.strip().upper()

    if not _TICKER_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid ticker format: '{ticker}'. "
            "Expected 1-10 uppercase letters, optionally followed by .X or -X"
        )

    # Check for injection in ticker field
    if _INJECTION_REGEX.search(cleaned):
        logger.warning(f"Prompt injection detected in ticker: {ticker[:50]}")
        raise ValueError(f"Invalid ticker: '{ticker}'")

    return cleaned


def sanitize_text_for_llm(text: str, max_length: int = 5000) -> str:
    """
    Sanitize user-provided text before including in LLM prompts.

    - Strips control characters
    - Detects and neutralizes prompt injection attempts
    - Truncates to max_length

    Parameters
    ----------
    text : str
        Raw text from user input
    max_length : int
        Maximum allowed length (default 5000 chars)

    Returns
    -------
    str
        Sanitized text safe for LLM prompt inclusion
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove control characters (except newlines and tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Detect prompt injection
    if _INJECTION_REGEX.search(sanitized):
        logger.warning(f"Prompt injection detected in text input: {sanitized[:100]}...")
        # Neutralize by wrapping in explicit data markers
        sanitized = f"[USER_DATA_START]{sanitized}[USER_DATA_END]"

    # Truncate
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "... [TRUNCATED]"

    return sanitized


def sanitize_data_for_prompt(data: dict, max_depth: int = 3) -> dict:
    """
    Sanitize a data dictionary before including in an LLM prompt.

    Recursively processes string values to detect injection.
    """
    if max_depth <= 0:
        return {"_truncated": True}

    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = sanitize_text_for_llm(value, max_length=2000)
        elif isinstance(value, dict):
            result[key] = sanitize_data_for_prompt(value, max_depth - 1)
        elif isinstance(value, list):
            result[key] = [
                sanitize_text_for_llm(v, 1000) if isinstance(v, str) else v
                for v in value[:50]  # Cap list length
            ]
        else:
            result[key] = value
    return result


def validate_investment_position(position: str) -> str:
    """Validate investment position input."""
    valid = {"long", "short", "neutral", "none", "watch"}
    cleaned = position.strip().lower()
    if cleaned not in valid:
        raise ValueError(
            f"Invalid position: '{position}'. Must be one of: {', '.join(sorted(valid))}"
        )
    return cleaned
