import logging
from typing import TypedDict

from pydantic import BaseModel, Field

from src.utils.helpers import extract_json
from src.config import get_settings
from src.llm import get_llm, LLMTaskType

logger = logging.getLogger("365advisers.cio_agent")
_settings = get_settings()


class CIOMemoLLMOutput(BaseModel):
    """Pydantic validation schema for CIO memo LLM responses."""
    thesis_summary: str = ""
    valuation_view: str = ""
    technical_context: str = ""
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    filing_context: str = ""
    geopolitical_context: str = ""
    macro_environment: str = ""
    sentiment_context: str = ""


class CIOMemoOutput(TypedDict):
    thesis_summary: str
    valuation_view: str
    technical_context: str
    key_catalysts: list[str]
    key_risks: list[str]
    # Optional enrichment sections (only present when data available)
    filing_context: str
    geopolitical_context: str
    macro_environment: str
    sentiment_context: str

_llm_cio = get_llm(LLMTaskType.REASONING)


def _build_enrichment_blocks(
    filing_context: dict | None,
    geopolitical_context: dict | None,
    macro_extended: dict | None,
    sentiment_context: dict | None,
) -> str:
    """Build optional context sections for enriched CIO Memo."""
    blocks: list[str] = []

    if filing_context and filing_context.get("source") != "null":
        filings = filing_context.get("filings", [])
        has_material = filing_context.get("has_material_event", False)
        latest_10k = filing_context.get("latest_annual_filing", "N/A")
        latest_10q = filing_context.get("latest_quarterly_filing", "N/A")
        filing_count = len(filings)

        blocks.append(f"""
[CORPORATE FILINGS CONTEXT — SEC EDGAR]
- Material 8-K in last 7 days: {"YES — MATERIAL EVENT DETECTED" if has_material else "No"}
- Latest 10-K: {latest_10k}
- Latest 10-Q: {latest_10q}
- Filings in last 90 days: {filing_count}
- Ownership filings: {len(filing_context.get('ownership_filings', []))}
NOTE: If there is a material event, you MUST mention it in your thesis and key_risks.""")

    if geopolitical_context and geopolitical_context.get("source") != "null":
        risk = geopolitical_context.get("risk_index")
        tone = geopolitical_context.get("tone_avg_24h")
        spike = geopolitical_context.get("spike_detected", False)
        themes = geopolitical_context.get("top_themes", [])
        top_theme = themes[0].get("theme", "N/A") if themes else "N/A"

        blocks.append(f"""
[GEOPOLITICAL CONTEXT — GDELT]
- Geopolitical Risk Index: {risk}/100
- Average Tone 24h: {tone}
- Event Spike Detected: {"YES — ELEVATED VOLATILITY" if spike else "No"}
- Dominant Theme: {top_theme}
NOTE: If risk > 60 or spike detected, mention geopolitical risk in key_risks.""")

    if macro_extended and macro_extended.get("sources_used"):
        gdp = macro_extended.get("gdp_growth_annualized")
        nfp = macro_extended.get("nonfarm_payrolls_change")
        retail = macro_extended.get("retail_sales_mom")
        confidence = macro_extended.get("consumer_confidence")
        housing = macro_extended.get("housing_starts")
        leading = macro_extended.get("leading_indicators_index")

        macro_parts = []
        if gdp is not None: macro_parts.append(f"GDP Growth (ann.): {gdp}%")
        if nfp is not None: macro_parts.append(f"Nonfarm Payrolls Chg: {nfp}K")
        if retail is not None: macro_parts.append(f"Retail Sales MoM: {retail}%")
        if confidence is not None: macro_parts.append(f"Consumer Confidence: {confidence}")
        if housing is not None: macro_parts.append(f"Housing Starts: {housing}K")
        if leading is not None: macro_parts.append(f"Leading Indicators: {leading}")

        if macro_parts:
            blocks.append(f"""
[MACRO ENVIRONMENT — FRED Extended]
{chr(10).join('- ' + p for p in macro_parts)}
NOTE: Weave macro context into your valuation_view and mention relevant trends.""")

    if sentiment_context and sentiment_context.get("sources_used"):
        geo_tone = sentiment_context.get("geopolitical_tone")
        evt_count = sentiment_context.get("event_count_48h")
        dom_theme = sentiment_context.get("dominant_geopolitical_theme")

        if geo_tone is not None or evt_count is not None:
            blocks.append(f"""
[SENTIMENT CONTEXT — Enriched]
- Geopolitical Tone: {geo_tone or 'N/A'}
- Event Count 48h: {evt_count or 'N/A'}
- Dominant Theme: {dom_theme or 'N/A'}
NOTE: If sentiment is strongly negative, note it in your key_risks.""")

    return "\n".join(blocks)


def _build_enrichment_output_instructions(
    filing_context: dict | None,
    geopolitical_context: dict | None,
    macro_extended: dict | None,
    sentiment_context: dict | None,
) -> str:
    """Build output field instructions for available enrichment sections."""
    fields: list[str] = []

    if filing_context and filing_context.get("source") != "null":
        fields.append(
            '  "filing_context": "<Short paragraph about what SEC filings reveal about the company.>"'
        )
    if geopolitical_context and geopolitical_context.get("source") != "null":
        fields.append(
            '  "geopolitical_context": "<Short paragraph about geopolitical risk and its impact.>"'
        )
    if macro_extended and macro_extended.get("sources_used"):
        fields.append(
            '  "macro_environment": "<Short paragraph about the macro backdrop and its implications.>"'
        )
    if sentiment_context and sentiment_context.get("sources_used"):
        fields.append(
            '  "sentiment_context": "<Short paragraph about news sentiment signals.>"'
        )

    return ",\n".join(fields)


def synthesize_investment_memo(
    ticker: str,
    investment_position: str,
    fundamental_verdict: dict,
    technical_summary: dict,
    opportunity_data: dict | None = None,
    position_data: dict | None = None,
    # ─── EDPL enrichment contexts ───
    filing_context: dict | None = None,
    geopolitical_context: dict | None = None,
    macro_extended: dict | None = None,
    sentiment_context: dict | None = None,
    # ─── Alpha Stack conclusions (NEW) ───
    alpha_stack_context: dict | None = None,
) -> CIOMemoOutput:
    """
    Acts as the Chief Investment Officer synthesizing the final Investment Memo
    based strictly on the deterministically derived investment_position.

    Now enriched with optional context from SEC EDGAR, GDELT, FRED, and
    news/sentiment when available.
    """
    opportunity_data = opportunity_data or {}
    position_data = position_data or {}
    
    # Extract context safely
    fund_score = fundamental_verdict.get("score", 0.0)
    fund_narrative = fundamental_verdict.get("consensus_narrative", "")
    fund_risks = fundamental_verdict.get("key_risks", [])
    fund_catalysts = fundamental_verdict.get("key_catalysts", [])
    
    _summary = technical_summary.get("summary", {})
    tech_score = _summary.get("technical_score",
                    technical_summary.get("technical_score", 5.0))
    tech_signal = _summary.get("signal",
                    technical_summary.get("signal", ""))

    # Opportunity Matrix Context (if available)
    opp_score = opportunity_data.get("opportunity_score", "N/A")
    opp_dims = opportunity_data.get("dimensions", {})
    opp_str = f"""
- Opportunity Score: {opp_score}/10
- Business Quality: {opp_dims.get('business_quality', 'N/A')}/10
- Valuation: {opp_dims.get('valuation', 'N/A')}/10
- Financial Strength: {opp_dims.get('financial_strength', 'N/A')}/10
- Market Behavior: {opp_dims.get('market_behavior', 'N/A')}/10
    """ if opp_dims else ""
    
    if position_data:
        opp_str += f"""
[POSITION SIZING SUGGESTION]
- Conviction Level: {position_data.get('conviction_level', 'N/A')}
- Risk Level: {position_data.get('risk_level', 'N/A')}
- Target Allocation: {position_data.get('suggested_allocation', 'N/A')}%
- Recommended Action: {position_data.get('recommended_action', 'N/A')}
"""

    # Build enrichment sections
    enrichment_str = _build_enrichment_blocks(
        filing_context, geopolitical_context, macro_extended, sentiment_context,
    )
    enrichment_output_fields = _build_enrichment_output_instructions(
        filing_context, geopolitical_context, macro_extended, sentiment_context,
    )

    # ─── Alpha Stack Context Block ───────────────────────────────────────
    alpha_str = ""
    if alpha_stack_context:
        alpha_parts = []

        alpha_memo = alpha_stack_context.get("alpha_memo")
        if alpha_memo:
            alpha_parts.append(f"""[ALPHA SIGNALS ANALYSIS]
- Signal: {alpha_memo.get('signal', 'N/A')}
- Conviction: {alpha_memo.get('conviction', 'N/A')}
- Key conclusion: {alpha_memo.get('narrative', 'N/A')}
- Key data: {', '.join(alpha_memo.get('key_data', []))}
- Risks: {', '.join(alpha_memo.get('risk_factors', []))}""")

        evidence_memo = alpha_stack_context.get("evidence_memo")
        if evidence_memo:
            alpha_parts.append(f"""[CASE EVIDENCE ANALYSIS]
- Signal: {evidence_memo.get('signal', 'N/A')}
- Conviction: {evidence_memo.get('conviction', 'N/A')}
- Key conclusion: {evidence_memo.get('narrative', 'N/A')}
- Key data: {', '.join(evidence_memo.get('key_data', []))}
- Risks: {', '.join(evidence_memo.get('risk_factors', []))}""")

        signal_map_memo = alpha_stack_context.get("signal_map_memo")
        if signal_map_memo:
            alpha_parts.append(f"""[SIGNAL MAP ANALYSIS]
- Signal: {signal_map_memo.get('signal', 'N/A')}
- Conviction: {signal_map_memo.get('conviction', 'N/A')}
- Key conclusion: {signal_map_memo.get('narrative', 'N/A')}
- Key data: {', '.join(signal_map_memo.get('key_data', []))}
- Risks: {', '.join(signal_map_memo.get('risk_factors', []))}""")

        backtest_memo = alpha_stack_context.get("backtest_memo")
        if backtest_memo:
            alpha_parts.append(f"""[BACKTEST EVIDENCE]
- Signal: {backtest_memo.get('signal', 'N/A')}
- Conviction: {backtest_memo.get('conviction', 'N/A')}
- Key conclusion: {backtest_memo.get('narrative', 'N/A')}
- Key data: {', '.join(backtest_memo.get('key_data', []))}
- Risks: {', '.join(backtest_memo.get('risk_factors', []))}""")

        # Summary stats
        case_score = alpha_stack_context.get("case_score")
        fired = alpha_stack_context.get("fired_signals", 0)
        total = alpha_stack_context.get("total_signals", 0)
        environment = alpha_stack_context.get("environment", "N/A")

        if case_score is not None:
            alpha_parts.insert(0, f"""[ALPHA STACK SUMMARY — PROPRIETARY SIGNAL SYSTEM]
- CASE Composite Score: {case_score:.1f}/100
- Signal Environment: {environment}
- Active Signals: {fired}/{total}
NOTE: The Alpha Stack provides quantitative evidence of statistical edge.
You MUST reference Alpha Stack conclusions in your thesis_summary and use them
to strengthen or qualify your conviction. If Alpha signals conflict with
fundamental/technical, note the divergence explicitly.""")

        alpha_str = "\n\n".join(alpha_parts)

    # Build dynamic output schema
    extra_fields = ""
    if enrichment_output_fields:
        extra_fields = f",\n{enrichment_output_fields}"

    # ─── Enhanced Scoring Context Blocks ─────────────────────────────────
    enhanced_str = ""

    # Purified Technical Score (alpha-validated)
    purified_score = technical_summary.get("purified_score") or technical_summary.get("summary", {}).get("purified_score")
    purified_signal = technical_summary.get("purified_signal") or technical_summary.get("summary", {}).get("purified_signal")
    purified_evidence = technical_summary.get("purified_evidence", [])
    if purified_score is not None:
        evidence_lines = "\n".join(f"  - {e}" for e in (purified_evidence or [])[:5])
        enhanced_str += f"""
[PURIFIED TECHNICAL SCORE — ALPHA-VALIDATED INDICATORS]
- Score: {purified_score}/10
- Signal: {purified_signal or 'N/A'}
- Based on: Low volatility (ATR%, BB width), volume confirmation, regime (ADX, SMA spread)
- Eliminated noise: RSI, Stochastic, MACD, MFI (empirically proven non-predictive)
{evidence_lines}
NOTE: This score uses ONLY indicators with statistically validated predictive power (p<0.05).
Reference this score when discussing technical timing and conviction."""

    # Dynamic Fundamental Score V3 (sector-calibrated)
    dynamic_score = fundamental_verdict.get("dynamic_score")
    dynamic_signal = fundamental_verdict.get("dynamic_signal")
    dynamic_evidence = fundamental_verdict.get("dynamic_evidence", [])
    if dynamic_score is not None:
        evidence_lines = "\n".join(f"  - {e}" for e in (dynamic_evidence or [])[:5])
        enhanced_str += f"""

[DYNAMIC FUNDAMENTAL SCORE V3 — SECTOR-CALIBRATED]
- Score: {dynamic_score}/10
- Signal: {dynamic_signal or 'N/A'}
- Calibration: 3-layer (theoretical gates → sector-relative z-score → dispersion weights)
- Context: Metrics scored RELATIVE to sector peers, not absolute thresholds
{evidence_lines}
NOTE: This score adapts to the company's industry context automatically.
Reference this score when discussing fundamental quality and valuation."""

    prompt = f"""You are the Chief Investment Officer (CIO) of a top-tier institutional fund.
Your Investment Committee, Technical Desk, and Alpha Signal System just analyzed {ticker}.
Based on our proprietary Decision Matrix, the EXACT institutional posture must be: **{investment_position}**.
We also calculated a structured target portfolio allocation based on risk and conviction.

YOUR TASK:
Write a compelling, institutional-grade summary justifying this final posture and target allocation.
Do NOT disagree with the posture '{investment_position}' or the Target Allocation. Your job is to articulate exactly WHY this posture and allocation size were chosen based on the tension between fundamental, technical, AND Alpha Stack signal realities, heavily weighting the new 12-factor Opportunity Score and the Risk Level.

CONTEXT DATA:
- Ticker: {ticker}
- Determined Position by Matrix: {investment_position}
- Fundamental Score: {fund_score}/10
- Fundamental Narrative: "{fund_narrative}"
- Fundamental Catalysts: {fund_catalysts}
- Fundamental Risks: {fund_risks}
- Technical Score: {tech_score}/10
- Technical Signal: {tech_signal}
{opp_str}
{alpha_str}
{enhanced_str}
{enrichment_str}

OUTPUT REQUIREMENTS:
Respond ONLY with valid JSON (NO markdown code blocks, strict JSON) containing these fields in ENGLISH:
{{
  "thesis_summary": "<One very strong, executive paragraph explaining the primary reason for the {investment_position} posture and the allocation % size. Cite the Opportunity Score and Conviction.>",
  "valuation_view": "<Short analysis on the intrinsic valuation and business quality.>",
  "technical_context": "<Short analysis on the timing, momentum, and technical setup.>",
  "key_catalysts": ["<catalyst1>", "<catalyst2>", ...],
  "key_risks": ["<risk1>", "<risk2>", ...]{extra_fields}
}}
"""

    fallback: CIOMemoOutput = {
        "thesis_summary": f"Assigned posture: {investment_position}. Executive summary not available.",
        "valuation_view": "Fundamental analysis not available.",
        "technical_context": "Technical analysis not available.",
        "key_catalysts": fund_catalysts,
        "key_risks": fund_risks,
        "filing_context": "",
        "geopolitical_context": "",
        "macro_environment": "",
        "sentiment_context": "",
    }

    try:
        from src.observability import traced_llm_call
        result = traced_llm_call("gemini-2.5-pro", prompt, _llm_cio.invoke)
        raw_response = result.content
        parsed = extract_json(raw_response)
        
        if not parsed:
            return fallback

        # Validate LLM output with Pydantic schema
        validated = CIOMemoLLMOutput.model_validate(parsed)
        return {
            "thesis_summary": validated.thesis_summary or fallback["thesis_summary"],
            "valuation_view": validated.valuation_view or fallback["valuation_view"],
            "technical_context": validated.technical_context or fallback["technical_context"],
            "key_catalysts": validated.key_catalysts or fund_catalysts,
            "key_risks": validated.key_risks or fund_risks,
            "filing_context": validated.filing_context,
            "geopolitical_context": validated.geopolitical_context,
            "macro_environment": validated.macro_environment,
            "sentiment_context": validated.sentiment_context,
        }
    except Exception as exc:
        logger.error(f"CIO Agent error for {ticker}: {exc}")
        return fallback

