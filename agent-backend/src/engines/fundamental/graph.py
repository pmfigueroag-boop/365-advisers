"""
src/engines/fundamental/graph.py
─────────────────────────────────────────────────────────────────────────────
Fundamental Analysis Engine — LangGraph multi-agent system.

Architecture:
  FundamentalDataFetcher → [Value, Quality, Capital, Risk] (parallel) → Committee → Formatter

Four agents, each with a distinct institutional framework:
  1. Value & Margin of Safety  (Graham / Buffett)
  2. Quality & Moat            (Munger / Fisher)
  3. Capital Allocation        (Icahn / activist)
  4. Risk & Macro Stress       (Marks / Dalio risk)

Committee Supervisor: synthesises 4 memos → 0–10 score + Research Memo.

This module is completely independent from graph.py (the legacy graph).
The legacy /analyze/stream endpoint continues to function unchanged.
"""

from __future__ import annotations

import asyncio
import operator
import os
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph

import logging

from src.data.market_data import fetch_fundamental_data
from src.utils.helpers import extract_json, sanitize_data

load_dotenv()

logger = logging.getLogger("365advisers.engines.fundamental")

# ─── LLM Configuration ────────────────────────────────────────────────────────

_llm_agent = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)
_llm_supervisor = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)
_tavily = TavilySearchResults(max_results=3)

# ─── State Schema ─────────────────────────────────────────────────────────────


class AgentMemo(TypedDict):
    agent: str
    framework: str
    signal: str               # BUY | SELL | HOLD | AVOID
    conviction: float         # 0.0–1.0
    memo: str
    key_metrics_used: list[str]
    metric_insights: list[dict]
    catalysts: list[str]
    risks: list[str]


class CommitteeOutput(TypedDict):
    signal: str               # BUY | SELL | HOLD
    score: float              # 0–10
    confidence: float         # 0.0–1.0
    risk_adjusted_score: float
    consensus_narrative: str
    key_catalysts: list[str]
    key_risks: list[str]
    allocation_recommendation: str


class FundamentalState(TypedDict):
    ticker: str
    fundamental_data: dict
    web_context: list[dict]
    agent_memos: Annotated[list[AgentMemo], operator.add]
    committee_output: CommitteeOutput
    research_memo: str


# ─── Utility: safe agent call ─────────────────────────────────────────────────

def _agent_prompt(
    ticker: str,
    agent_name: str,
    framework: str,
    focus: str,
    data: dict,
    extra_context: str = "",
) -> str:
    return f"""You are a world-class institutional investor acting as {agent_name}.
Your framework: {framework}
Your focus: {focus}

COMPANY: {ticker}
FINANCIAL DATA:
{data}
{f"ADDITIONAL CONTEXT:{extra_context}" if extra_context else ""}

IMPORTANT: Write ALL text fields (memo, catalysts, risks) in SPANISH. Do not use English.

Respond ONLY with valid JSON (no markdown, no prose outside JSON):
{{
  "agent": "{agent_name}",
  "framework": "{framework}",
  "signal": "BUY|SELL|HOLD|AVOID",
  "conviction": <float 0.0-1.0>,
  "memo": "<memo de 2-3 oraciones en español>",
  "key_metrics_used": ["<metrica1>", "<metrica2>"],
  "metric_insights": [
    {{
      "metric": "<nombre de la métrica clave>",
      "definition": "<explicación breve y didáctica de qué mide la métrica en la realidad>",
      "interpretation": "<tu interpretación de este valor numérico para esta empresa>"
    }}
  ],
  "catalysts": ["<catalizador1>"],
  "risks": ["<riesgo1>"]
}}"""


def _safe_agent_call(ticker: str, agent_name: str, framework: str, focus: str, data: dict, extra: str = "") -> AgentMemo:
    fallback: AgentMemo = {
        "agent": agent_name,
        "framework": framework,
        "signal": "HOLD",
        "conviction": 0.5,
        "memo": f"{agent_name} analysis unavailable.",
        "key_metrics_used": [],
        "metric_insights": [],
        "catalysts": [],
        "risks": [],
        "is_fallback": True,
    }
    try:
        from src.observability import traced_llm_call
        prompt = _agent_prompt(ticker, agent_name, framework, focus, data, extra)
        result = traced_llm_call("gemini-2.5-flash", prompt, _llm_agent.invoke)
        raw = result.content
        parsed = extract_json(raw)
        if not parsed:
            return fallback
        return {
            "agent":            str(parsed.get("agent", agent_name)),
            "framework":        str(parsed.get("framework", framework)),
            "signal":           str(parsed.get("signal", "HOLD")).upper(),
            "conviction":       min(1.0, max(0.0, float(parsed.get("conviction", 0.5)))),
            "memo":             str(parsed.get("memo", "")),
            "key_metrics_used": list(parsed.get("key_metrics_used", [])),
            "metric_insights":  list(parsed.get("metric_insights", [])),
            "catalysts":        list(parsed.get("catalysts", [])),
            "risks":            list(parsed.get("risks", [])),
            "is_fallback":      False,
        }
    except Exception as exc:
        logger.error(f"Agent {agent_name} failed: {exc}")
        return fallback


# ─── Graph Nodes ──────────────────────────────────────────────────────────────

def node_fetch_data(state: FundamentalState) -> dict:
    """Fetches fundamental data + web context for the ticker."""
    import concurrent.futures
    ticker = state["ticker"]
    logger.info(f"Fetching data for {ticker}")

    # Run blocking data fetches with a hard timeout to prevent hanging
    def _fetch_all():
        fund_data = fetch_fundamental_data(ticker)
        try:
            web_results = _tavily.invoke(f"{ticker} stock fundamental analysis recent earnings")
            web_context = [{"title": r.get("url", ""), "content": r.get("content", "")} for r in (web_results or [])]
        except Exception as exc:
            logger.warning(f"Tavily search failed: {exc}")
            web_context = []
        return fund_data, web_context

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_all)
            fund_data, web_context = future.result(timeout=25)
    except concurrent.futures.TimeoutError:
        logger.error(f"Data fetch TIMEOUT for {ticker} (25s)")
        fund_data = {"name": ticker, "sector": "", "industry": "", "ratios": {}, "cashflow_series": []}
        web_context = []
    except Exception as exc:
        logger.error(f"Data fetch error for {ticker}: {exc}")
        fund_data = {"name": ticker, "sector": "", "industry": "", "ratios": {}, "cashflow_series": []}
        web_context = []

    return {"fundamental_data": fund_data, "web_context": web_context}


def node_value_agent(state: FundamentalState) -> dict:
    """Agent 1: Value & Margin of Safety (Graham / Buffett framework)."""
    logger.info(f"Value Agent running for {state['ticker']}")
    data = state["fundamental_data"]
    memo = _safe_agent_call(
        ticker=state["ticker"],
        agent_name="Value & Margin of Safety",
        framework="Benjamin Graham / Warren Buffett — Intrinsic Value, DCF, MoS",
        focus=(
            "Assess intrinsic value vs current price. Focus on P/E, P/B, FCF yield, "
            "earnings power, and whether a margin of safety exists. Penalise overvalued "
            "growth stories without earnings support."
        ),
        data={
            "ratios": data.get("ratios", {}),
            "name": data.get("name"),
            "sector": data.get("sector"),
        },
    )
    return {"agent_memos": [memo]}


def node_quality_agent(state: FundamentalState) -> dict:
    """Agent 2: Quality & Moat (Munger / Fisher framework)."""
    logger.info(f"Quality Agent running for {state['ticker']}")
    data = state["fundamental_data"]
    memo = _safe_agent_call(
        ticker=state["ticker"],
        agent_name="Quality & Moat",
        framework="Charlie Munger / Phil Fisher — Durable Competitive Advantage, ROIC",
        focus=(
            "Assess business quality: ROIC, gross margin stability, revenue growth "
            "consistency, pricing power, switching costs, and management track record. "
            "Only recommend companies with defensible moats."
        ),
        data={
            "ratios": data.get("ratios", {}),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
        },
    )
    return {"agent_memos": [memo]}


def node_capital_agent(state: FundamentalState) -> dict:
    """Agent 3: Capital Allocation (Icahn / activist framework)."""
    logger.info(f"Capital Allocation Agent running for {state['ticker']}")
    data = state["fundamental_data"]
    memo = _safe_agent_call(
        ticker=state["ticker"],
        agent_name="Capital Allocation",
        framework="Carl Icahn / Activist — FCF deployment, buybacks, dividends, leverage",
        focus=(
            "Evaluate how management allocates capital: buyback yield, dividend policy, "
            "debt levels, acquisitions vs organic growth. Reward disciplined capital "
            "allocation and flag empire-building or over-levered balance sheets."
        ),
        data={
            "ratios": data.get("ratios", {}),
            "cashflow_series": data.get("cashflow_series", []),
        },
    )
    return {"agent_memos": [memo]}


def node_risk_agent(state: FundamentalState) -> dict:
    """Agent 4: Risk & Macro Stress (Marks / Dalio framework)."""
    logger.info(f"Risk Agent running for {state['ticker']}")
    data = state["fundamental_data"]
    web_ctx = "\n".join(c.get("content", "")[:400] for c in state.get("web_context", []))
    memo = _safe_agent_call(
        ticker=state["ticker"],
        agent_name="Risk & Macro Stress",
        framework="Howard Marks / Ray Dalio — Cycle position, tail risk, leverage stress",
        focus=(
            "Identify macro and idiosyncratic risks: leverage stress under rate hikes, "
            "sector cyclicality, geopolitical exposure, liquidity risk, and narrative risk. "
            "Produce a conservative downside case and flag non-consensus risks."
        ),
        data={
            "ratios": {
                "leverage": data.get("ratios", {}).get("leverage", {}),
                "valuation": data.get("ratios", {}).get("valuation", {}),
                "quality": data.get("ratios", {}).get("quality", {}),
            },
        },
        extra=web_ctx[:1500],
    )
    return {"agent_memos": [memo]}


def node_committee(state: FundamentalState) -> dict:
    """Committee Supervisor: synthesises 4 memos into a structured verdict."""
    logger.info(f"Committee Supervisor running for {state['ticker']}")
    memos = state["agent_memos"]
    ticker = state["ticker"]

    memo_summary = "\n".join(
        f"[{m['agent']}] Signal: {m['signal']}, Conviction: {m['conviction']:.0%}\n"
        f"  Memo: {m['memo']}\n"
        f"  Catalysts: {', '.join(m['catalysts'])}\n"
        f"  Risks: {', '.join(m['risks'])}"
        for m in memos
    )

    prompt = f"""You are the Chief Investment Officer of a top-tier institutional fund.
You have just received research memos from 4 specialist analysts on {ticker}.

ANALYST MEMOS:
{memo_summary}

TASK: Synthesise these 4 memos into a final Investment Committee verdict.
IMPORTANT: Write ALL text fields (consensus_narrative, key_catalysts, key_risks, allocation_recommendation) in SPANISH.

Respond ONLY with valid JSON:
{{
  "signal": "BUY|SELL|HOLD",
  "score": <float 0-10, where 10 is exceptionally attractive>,
  "confidence": <float 0.0-1.0>,
  "risk_adjusted_score": <float 0-10, discounted for risks>,
  "consensus_narrative": "<narrativa institucional de 3-4 oraciones en español>",
  "key_catalysts": ["<catalizador1>", "<catalizador2>"],
  "key_risks": ["<riesgo1>", "<riesgo2>"],
  "allocation_recommendation": "Sobreponderar|Ponderar en línea|Subponderar|Evitar"
}}"""

    fallback: CommitteeOutput = {
        "signal": "HOLD",
        "score": 5.0,
        "confidence": 0.5,
        "risk_adjusted_score": 4.5,
        "consensus_narrative": "Committee consensus unavailable.",
        "key_catalysts": [],
        "key_risks": [],
        "allocation_recommendation": "Market Weight",
    }

    try:
        from src.observability import traced_llm_call
        result = traced_llm_call("gemini-2.5-pro", prompt, _llm_supervisor.invoke)
        raw = result.content
        parsed = extract_json(raw)
        if not parsed:
            return {"committee_output": fallback}
        verdict: CommitteeOutput = {
            "signal":                   str(parsed.get("signal", "HOLD")).upper(),
            "score":                    round(min(10.0, max(0.0, float(parsed.get("score", 5.0)))), 2),
            "confidence":               round(min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))), 2),
            "risk_adjusted_score":      round(min(10.0, max(0.0, float(parsed.get("risk_adjusted_score", 4.5)))), 2),
            "consensus_narrative":      str(parsed.get("consensus_narrative", "")),
            "key_catalysts":            list(parsed.get("key_catalysts", [])),
            "key_risks":                list(parsed.get("key_risks", [])),
            "allocation_recommendation":str(parsed.get("allocation_recommendation", "Market Weight")),
        }
        return {"committee_output": verdict}
    except Exception as exc:
        logger.error(f"Committee synthesis failed: {exc}")
        return {"committee_output": fallback}


def node_formatter(state: FundamentalState) -> dict:
    """
    No-LLM formatter. Builds the Research Memo 1-pager as a structured
    markdown string from the committee output and agent memos.
    """
    ticker = state["ticker"]
    fund = state["fundamental_data"]
    committee = state["committee_output"]
    memos = state["agent_memos"]

    signal_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(committee["signal"], "⚪")

    agent_section = "\n".join(
        f"**{m['agent']}** ({m['framework'].split('—')[0].strip()})\n"
        f"Señal: **{m['signal']}** | Convicción: **{m['conviction']:.0%}**\n"
        f"{m['memo']}\n"
        for m in memos
    )

    catalysts = "\n".join(f"- {c}" for c in committee["key_catalysts"]) or "- N/A"
    risks = "\n".join(f"- {r}" for r in committee["key_risks"]) or "- N/A"

    ratios = fund.get("ratios", {})
    val = ratios.get("valuation", {})
    prof = ratios.get("profitability", {})

    def fmt(v):
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)

    memo = f"""# {fund.get('name', ticker)} ({ticker}) — Memo de Investigación
**Fecha:** {datetime.now(tz=timezone.utc).strftime('%d de %B de %Y')} | **Sector:** {fund.get('sector', 'N/D')} | **Industria:** {fund.get('industry', 'N/D')}

---

## Veredicto del Comité {signal_emoji}

| Métrica | Valor |
|---------|-------|
| **Señal** | {committee['signal']} |
| **Puntaje** | {committee['score']}/10 |
| **Puntaje Ajustado por Riesgo** | {committee['risk_adjusted_score']}/10 |
| **Confianza** | {committee['confidence']:.0%} |
| **Asignación Recomendada** | {committee['allocation_recommendation']} |

{committee['consensus_narrative']}

---

## Métricas de Valoración Clave

| Métrica | Valor |
|---------|-------|
| Ratio P/E | {fmt(val.get('pe_ratio', 'N/D'))} |
| Ratio P/B | {fmt(val.get('pb_ratio', 'N/D'))} |
| EV/EBITDA | {fmt(val.get('ev_ebitda', 'N/D'))} |
| Rendimiento FCF | {fmt(val.get('fcf_yield', 'N/D'))} |
| Margen Bruto | {fmt(prof.get('gross_margin', 'N/D'))} |
| Margen Neto | {fmt(prof.get('net_margin', 'N/D'))} |
| ROIC | {fmt(prof.get('roic', 'N/D'))} |

---

## Memos de Analistas

{agent_section}

---

## Catalizadores
{catalysts}

## Riesgos Clave
{risks}

---
*Generado por 365 Advisers Fundamental Engine · {datetime.now(tz=timezone.utc).isoformat()}*
"""
    return {"research_memo": memo}


# ─── Build the LangGraph ──────────────────────────────────────────────────────

_fund_workflow = StateGraph(FundamentalState)

_fund_workflow.add_node("FundamentalDataFetcher", node_fetch_data)
_fund_workflow.add_node("ValueAgent",    node_value_agent)
_fund_workflow.add_node("QualityAgent",  node_quality_agent)
_fund_workflow.add_node("CapitalAgent",  node_capital_agent)
_fund_workflow.add_node("RiskAgent",     node_risk_agent)
_fund_workflow.add_node("Committee",     node_committee)
_fund_workflow.add_node("Formatter",     node_formatter)

_fund_workflow.set_entry_point("FundamentalDataFetcher")

# Fan-out: DataFetcher → all 4 agents in parallel
for agent in ["ValueAgent", "QualityAgent", "CapitalAgent", "RiskAgent"]:
    _fund_workflow.add_edge("FundamentalDataFetcher", agent)
    _fund_workflow.add_edge(agent, "Committee")

_fund_workflow.add_edge("Committee", "Formatter")
_fund_workflow.add_edge("Formatter", END)

fundamental_graph = _fund_workflow.compile()


# ─── Streaming runner ─────────────────────────────────────────────────────────

AGENT_NODES = {"ValueAgent", "QualityAgent", "CapitalAgent", "RiskAgent"}


async def run_fundamental_stream(ticker: str):
    """
    Async generator for SSE streaming of fundamental analysis.

    Events (in order):
      data_ready       → fundamental ratios + company info
      agent_memo       → one per analyst (×4)
      committee_verdict→ final score + signal
      research_memo    → full 1-pager markdown
      done             → stream end
      error            → on failure
    """
    import time as _time
    start_ms = _time.monotonic_ns() / 1e6

    initial_state: FundamentalState = {
        "ticker":           ticker,
        "fundamental_data": {},
        "web_context":      [],
        "agent_memos":      [],
        "committee_output": {},  # type: ignore
        "research_memo":    "",
    }

    try:
        async for chunk in fundamental_graph.astream(initial_state):
            for node_name, node_output in chunk.items():

                if node_name == "FundamentalDataFetcher":
                    fund = node_output.get("fundamental_data", {})
                    yield {
                        "event": "data_ready",
                        "data": sanitize_data({
                            "ticker":   ticker,
                            "name":     fund.get("name", ticker),
                            "sector":   fund.get("sector", ""),
                            "industry": fund.get("industry", ""),
                            "ratios":   fund.get("ratios", {}),
                            "cashflow_series": fund.get("cashflow_series", []),
                        }),
                    }

                elif node_name in AGENT_NODES:
                    memos = node_output.get("agent_memos", [])
                    for memo in memos:
                        yield {
                            "event": "agent_memo",
                            "data":  sanitize_data(memo),
                        }

                elif node_name == "Committee":
                    elapsed = round(_time.monotonic_ns() / 1e6 - start_ms)
                    committee = node_output.get("committee_output", {})
                    yield {
                        "event": "committee_verdict",
                        "data":  sanitize_data({**committee, "elapsed_ms": elapsed}),
                    }

                elif node_name == "Formatter":
                    yield {
                        "event": "research_memo",
                        "data":  {"memo": node_output.get("research_memo", "")},
                    }

        yield {"event": "done", "data": {}}

    except Exception as exc:
        logger.error(f"Fundamental stream failed for {ticker}: {exc}", exc_info=True)
        yield {"event": "error", "data": {"message": str(exc)}}
