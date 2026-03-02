"""
src/utils/helpers.py
─────────────────────────────────────────────────────────────────────────────
Shared utilities extracted from the original graph.py monolith.
- sanitize_data(): recursively replace NaN / Infinity with None for JSON.
- extract_json():  parse LLM responses that may contain markdown fences.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


# ─── JSON Sanitizer ──────────────────────────────────────────────────────────

def sanitize_data(data: Any) -> Any:
    """Recursively replace NaN and Infinity with None for JSON compliance."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [sanitize_data(x) for x in data]
    if isinstance(data, float):
        try:
            if math.isnan(data) or math.isinf(data):
                return None
        except Exception:
            return None
    return data


# ─── LLM JSON Extractor ──────────────────────────────────────────────────────

def extract_json(text: str | None) -> dict | None:
    """
    Extract a JSON object from an LLM response that may contain markdown
    fences or surrounding prose.

    Strategy:
    1. Try direct JSON parse.
    2. Strip ```json ... ``` or ``` ... ``` fences.
    3. Fall back to first-brace / last-brace substring.
    Returns None on failure.
    """
    if not text:
        return None

    # 1. Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. Strip markdown fences
    cleaned = text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 3. First-brace / last-brace extraction
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        fragment = cleaned[start : end + 1]
        # Remove trailing commas that break strict JSON
        fragment = re.sub(r",\s*}", "}", fragment)
        fragment = re.sub(r",\s*]", "]", fragment)
        try:
            return json.loads(fragment)
        except Exception as exc:
            print(f"[extract_json] Failed to parse fragment: {exc}")

    return None
