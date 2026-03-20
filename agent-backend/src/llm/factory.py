"""
src/llm/factory.py
─────────────────────────────────────────────────────────────────────────────
Provider-agnostic model factory.

This is the ONLY module that imports concrete LLM SDKs.
Adding a new provider (Claude, Mistral, etc.) = one new elif branch here.
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm.types import LLMProviderName, LLMSelection

logger = logging.getLogger("365advisers.llm.factory")


def build_model(selection: LLMSelection, api_keys: dict[str, str]) -> Any:
    """
    Construct a LangChain BaseChatModel from a selection.

    Parameters
    ----------
    selection : LLMSelection
        Provider, model name, and temperature config.
    api_keys : dict
        Mapping of provider name → API key string.

    Returns
    -------
    BaseChatModel
        Ready-to-use LangChain chat model instance.

    Raises
    ------
    ValueError
        If provider is unknown or API key is missing.
    """
    provider = selection.provider
    key = api_keys.get(provider.value, "")

    if not key:
        raise ValueError(
            f"No API key configured for provider '{provider.value}'. "
            f"Set the appropriate key in .env or environment."
        )

    if provider == LLMProviderName.GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = ChatGoogleGenerativeAI(
            model=selection.model,
            google_api_key=key,
            temperature=selection.temperature,
        )
        logger.debug("Built Gemini model: %s (temp=%.1f)", selection.model, selection.temperature)
        return model

    if provider == LLMProviderName.OPENAI:
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(
            model=selection.model,
            api_key=key,
            temperature=selection.temperature,
        )
        logger.debug("Built OpenAI model: %s (temp=%.1f)", selection.model, selection.temperature)
        return model

    raise ValueError(f"Unsupported LLM provider: {provider.value}")
