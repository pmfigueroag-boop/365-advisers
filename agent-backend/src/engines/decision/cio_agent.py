import logging
from typing import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.helpers import extract_json
from src.config import get_settings

logger = logging.getLogger("365advisers.cio_agent")
_settings = get_settings()

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

_llm_cio = ChatGoogleGenerativeAI(
    model=_settings.LLM_MODEL,
    google_api_key=_settings.GOOGLE_API_KEY,
)


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
- Material 8-K in last 7 days: {"SI — EVENTO MATERIAL DETECTADO" if has_material else "No"}
- Último 10-K: {latest_10k}
- Último 10-Q: {latest_10q}
- Filings en últimos 90 días: {filing_count}
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
- Índice de Riesgo Geopolítico: {risk}/100
- Tono Promedio 24h: {tone}
- Spike de Eventos Detectado: {"SI — VOLATILIDAD ELEVADA" if spike else "No"}
- Tema Dominante: {top_theme}
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
    # ─── NEW: optional EDPL enrichment contexts ───
    filing_context: dict | None = None,
    geopolitical_context: dict | None = None,
    macro_extended: dict | None = None,
    sentiment_context: dict | None = None,
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

    # Build dynamic output schema
    extra_fields = ""
    if enrichment_output_fields:
        extra_fields = f",\n{enrichment_output_fields}"

    prompt = f"""You are the Chief Investment Officer (CIO) of a top-tier institutional fund.
Your Investment Committee and Technical Desk just analyzed {ticker}.
Based on our proprietary Decision Matrix, the EXACT institutional posture must be: **{investment_position}**.
We also calculated a structured target portfolio allocation based on risk and conviction.

YOUR TASK:
Write a compelling, institutional-grade summary justifying this final posture and target allocation.
Do NOT disagree with the posture '{investment_position}' or the Target Allocation. Your job is to articulate exactly WHY this posture and allocation size were chosen based on the tension between fundamental and technical realities, heavily weighting the new 12-factor Opportunity Score and the Risk Level.

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
{enrichment_str}

OUTPUT REQUIREMENTS:
Respond ONLY with valid JSON (NO markdown code blocks, strict JSON) containing these fields in SPANISH:
{{
  "thesis_summary": "<One very strong, executive paragraph explaining the primary reason for the {investment_position} posture and the allocation % size. Cite the Opportunity Score and Conviction.>",
  "valuation_view": "<Short analysis on the intrinsic valuation and business quality.>",
  "technical_context": "<Short analysis on the timing, momentum, and technical setup.>",
  "key_catalysts": ["<catalyst1>", "<catalyst2>", ...],
  "key_risks": ["<risk1>", "<risk2>", ...]{extra_fields}
}}
"""

    fallback: CIOMemoOutput = {
        "thesis_summary": f"Postura asignada: {investment_position}. Resumen ejecutivo no disponible.",
        "valuation_view": "Análisis fundamental no disponible.",
        "technical_context": "Análisis técnico no disponible.",
        "key_catalysts": fund_catalysts,
        "key_risks": fund_risks,
        "filing_context": "",
        "geopolitical_context": "",
        "macro_environment": "",
        "sentiment_context": "",
    }

    try:
        raw_response = _llm_cio.invoke(prompt).content
        parsed = extract_json(raw_response)
        
        if not parsed:
            return fallback
            
        return {
            "thesis_summary": str(parsed.get("thesis_summary", fallback["thesis_summary"])),
            "valuation_view": str(parsed.get("valuation_view", fallback["valuation_view"])),
            "technical_context": str(parsed.get("technical_context", fallback["technical_context"])),
            "key_catalysts": list(parsed.get("key_catalysts", fund_catalysts)),
            "key_risks": list(parsed.get("key_risks", fund_risks)),
            "filing_context": str(parsed.get("filing_context", "")),
            "geopolitical_context": str(parsed.get("geopolitical_context", "")),
            "macro_environment": str(parsed.get("macro_environment", "")),
            "sentiment_context": str(parsed.get("sentiment_context", "")),
        }
    except Exception as exc:
        logger.error(f"CIO Agent error for {ticker}: {exc}")
        return fallback

