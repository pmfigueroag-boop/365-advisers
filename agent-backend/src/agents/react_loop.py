"""
src/agents/react_loop.py
─────────────────────────────────────────────────────────────────────────────
ReAct (Reason + Act) loop for autonomous agents.

Implements the tool-calling workflow:
  1. Send prompt + tool declarations to LLM
  2. If LLM requests a tool call → execute tool → return result
  3. Repeat until LLM produces final answer or max_iterations reached

This enables agents to autonomously request additional data
during analysis instead of working only with pre-fetched data.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

from src.agents.tools import TOOL_DECLARATIONS, execute_tool
from src.utils.helpers import extract_json

logger = logging.getLogger("365advisers.agents.react")


class ReActLoop:
    """
    Execute an LLM agent with autonomous tool-calling capability.

    Parameters
    ----------
    llm_invoke : Callable
        The LLM invoke function (e.g. ChatGoogleGenerativeAI.invoke)
    model_name : str
        Model identifier for tracing (e.g. "gemini-2.5-flash")
    max_iterations : int
        Maximum tool-call iterations before forcing final answer
    """

    def __init__(
        self,
        llm_invoke: Callable,
        model_name: str = "gemini-2.5-flash",
        max_iterations: int = 3,
    ):
        self.llm_invoke = llm_invoke
        self.model_name = model_name
        self.max_iterations = max_iterations
        self._tool_calls_made: list[dict] = []

    def run(self, system_prompt: str, user_message: str) -> dict:
        """
        Execute the ReAct loop.

        Returns
        -------
        dict
            The parsed JSON result from the LLM's final answer,
            plus "_react_metadata" with tool call history.
        """
        messages = []
        tool_call_history = []
        iteration = 0

        # Build initial prompt with tool instruction
        full_prompt = self._build_prompt_with_tools(system_prompt, user_message)

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"ReAct iteration {iteration}/{self.max_iterations}")

            try:
                from src.observability import traced_llm_call
                result = traced_llm_call(
                    self.model_name, full_prompt, self.llm_invoke
                )
                raw = result.content
            except Exception as exc:
                logger.error(f"ReAct LLM call failed: {exc}")
                break

            # Check if the response contains a tool call request
            tool_request = self._extract_tool_call(raw)

            if tool_request:
                tool_name = tool_request.get("tool_name", "")
                tool_args = tool_request.get("arguments", {})

                logger.info(f"ReAct: Agent requests tool '{tool_name}' with args {tool_args}")

                # Execute the tool
                t0 = time.perf_counter()
                tool_result = execute_tool(tool_name, tool_args)
                duration_ms = (time.perf_counter() - t0) * 1000

                tool_call_record = {
                    "iteration": iteration,
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result_keys": list(tool_result.keys()) if isinstance(tool_result, dict) else [],
                    "duration_ms": round(duration_ms, 1),
                    "success": "error" not in tool_result,
                }
                tool_call_history.append(tool_call_record)

                # Append tool result to prompt for next iteration
                full_prompt = self._append_tool_result(
                    full_prompt, tool_name, tool_args, tool_result
                )
                continue

            # No tool call — this is the final answer
            parsed = extract_json(raw)
            if parsed:
                parsed["_react_metadata"] = {
                    "iterations": iteration,
                    "tool_calls": tool_call_history,
                    "autonomous": len(tool_call_history) > 0,
                }
                return parsed
            else:
                # LLM returned non-JSON, try to use it anyway
                logger.warning("ReAct: Final answer is not valid JSON")
                return {
                    "raw_response": raw[:500],
                    "_react_metadata": {
                        "iterations": iteration,
                        "tool_calls": tool_call_history,
                        "autonomous": len(tool_call_history) > 0,
                        "parse_error": True,
                    },
                }

        # Max iterations reached — force extraction from last response
        logger.warning(f"ReAct: Max iterations ({self.max_iterations}) reached")
        return {
            "_react_metadata": {
                "iterations": iteration,
                "tool_calls": tool_call_history,
                "autonomous": len(tool_call_history) > 0,
                "max_iterations_reached": True,
            },
        }

    def _build_prompt_with_tools(self, system: str, user: str) -> str:
        """Build prompt with tool availability information."""
        tool_descriptions = []
        for tool in TOOL_DECLARATIONS:
            params = tool.get("parameters", {}).get("properties", {})
            param_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
            tool_descriptions.append(
                f"  - {tool['name']}({param_str}): {tool['description']}"
            )

        tools_section = "\n".join(tool_descriptions)

        return f"""{system}

AVAILABLE TOOLS:
You can request additional data by responding with a JSON tool call:
{tools_section}

To call a tool, respond with ONLY:
{{"_tool_call": true, "tool_name": "<name>", "arguments": {{...}}}}

When you have enough information, respond with your final analysis JSON (without _tool_call).

{user}"""

    def _append_tool_result(
        self, prompt: str, tool_name: str, args: dict, result: dict
    ) -> str:
        """Append tool execution result to the ongoing prompt."""
        return f"""{prompt}

TOOL RESULT ({tool_name}):
{json.dumps(result, default=str, indent=2)}

Now continue your analysis with this additional data. Either call another tool or provide your final answer JSON."""

    @staticmethod
    def _extract_tool_call(raw: str) -> dict | None:
        """
        Check if the LLM response is a tool call request.

        Returns the tool call dict if found, None otherwise.
        """
        try:
            parsed = extract_json(raw)
            if parsed and parsed.get("_tool_call") is True:
                return parsed
        except Exception:
            pass
        return None
