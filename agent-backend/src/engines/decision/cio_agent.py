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

_llm_cio = ChatGoogleGenerativeAI(
    model=_settings.LLM_MODEL,
    google_api_key=_settings.GOOGLE_API_KEY,
)

def synthesize_investment_memo(
    ticker: str,
    investment_position: str,
    fundamental_verdict: dict,
    technical_summary: dict,
    opportunity_data: dict = {},
    position_data: dict = {}
) -> CIOMemoOutput:
    """
    Acts as the Chief Investment Officer synthesizing the final Investment Memo
    based strictly on the deterministically derived investment_position.
    """
    
    # Extract context safely
    fund_score = fundamental_verdict.get("score", 0.0)
    fund_narrative = fundamental_verdict.get("consensus_narrative", "")
    fund_risks = fundamental_verdict.get("key_risks", [])
    fund_catalysts = fundamental_verdict.get("key_catalysts", [])
    
    tech_score = technical_summary.get("technical_score", 0.0)
    tech_signal = technical_summary.get("signal", "")

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

OUTPUT REQUIREMENTS:
Respond ONLY with valid JSON (NO markdown code blocks, strict JSON) containing these fields in SPANISH:
{{
  "thesis_summary": "<One very strong, executive paragraph explaining the primary reason for the {investment_position} posture and the allocation % size. Cite the Opportunity Score and Conviction.>",
  "valuation_view": "<Short analysis on the intrinsic valuation and business quality.>",
  "technical_context": "<Short analysis on the timing, momentum, and technical setup.>",
  "key_catalysts": ["<catalyst1>", "<catalyst2>", ...],
  "key_risks": ["<risk1>", "<risk2>", ...]
}}
"""

    fallback: CIOMemoOutput = {
        "thesis_summary": f"Postura asignada: {investment_position}. Resumen ejecutivo no disponible.",
        "valuation_view": "Análisis fundamental no disponible.",
        "technical_context": "Análisis técnico no disponible.",
        "key_catalysts": fund_catalysts,
        "key_risks": fund_risks
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
            "key_risks": list(parsed.get("key_risks", fund_risks))
        }
    except Exception as exc:
        logger.error(f"CIO Agent error for {ticker}: {exc}")
        return fallback
