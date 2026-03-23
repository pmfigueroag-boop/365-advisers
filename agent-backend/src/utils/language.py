"""
src/utils/language.py
─────────────────────────────────────────────────────────────────────────────
Language helpers for LLM prompt construction.

Reads APP_LANGUAGE from config and provides prompt-ready strings.
"""

from __future__ import annotations

from functools import lru_cache


_LANG_MAP = {
    "es": "Spanish",
    "en": "English",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
}


@lru_cache
def get_output_language() -> str:
    """Return the full language name for LLM prompts (e.g. 'Spanish')."""
    from src.config import get_settings
    code = get_settings().APP_LANGUAGE.lower().strip()
    return _LANG_MAP.get(code, "English")


def lang_instruction() -> str:
    """Return a prompt instruction like 'ALL text in Spanish.'"""
    return f"ALL text in {get_output_language()}."


def lang_field_hint(field_desc: str) -> str:
    """Return a field hint like '<2-3 sentence memo in Spanish>'."""
    return f"<{field_desc} in {get_output_language()}>"
