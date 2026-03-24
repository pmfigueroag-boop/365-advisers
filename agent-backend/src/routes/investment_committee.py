"""
src/routes/investment_committee.py
──────────────────────────────────────────────────────────────────────────────
Investment Committee API — SSE streaming and synchronous endpoints.

GET  /api/investment-committee/{ticker}/stream  — SSE stream of IC session
POST /api/investment-committee/{ticker}/run     — Complete IC transcript
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.auth.dependencies import get_current_user
from src.data.market_data import fetch_fundamental_data
from src.engines.fundamental.committee.debate import InvestmentCommitteeDebate
from src.utils.helpers import sanitize_data

logger = logging.getLogger("365advisers.routes.investment_committee")

router = APIRouter(
    prefix="/api/investment-committee",
    tags=["Investment Committee"],
    dependencies=[Depends(get_current_user)],
)


async def _sse_generator(ticker: str):
    """Wrap IC stream events into SSE text format."""
    try:
        fund_data = await asyncio.to_thread(fetch_fundamental_data, ticker)
        if not fund_data or "error" in fund_data:
            yield f"event: error\ndata: {json.dumps({'message': f'Failed to fetch data for {ticker}'})}\n\n"
            return

        debate = InvestmentCommitteeDebate()
        async for event in debate.run_stream(ticker, fund_data):
            event_name = event.get("event", "ic_update")
            data = sanitize_data(event.get("data", {}))
            yield f"event: {event_name}\ndata: {json.dumps(data, default=str)}\n\n"

    except Exception as exc:
        logger.error(f"IC stream error for {ticker}: {exc}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"


@router.get("/{ticker}/stream")
async def stream_ic_session(ticker: str):
    """
    SSE stream of a full Investment Committee session.

    Events (in order):
      ic_members         — committee member identities
      ic_round_present   — each agent's initial memo (×6)
      ic_round_challenge — each challenge (×6)
      ic_round_rebuttal  — each rebuttal
      ic_round_vote      — each final vote (×6)
      ic_verdict         — chairman's final synthesis
      ic_done            — session complete
    """
    symbol = ticker.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    return StreamingResponse(
        _sse_generator(symbol),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{ticker}/run")
async def run_ic_session(ticker: str):
    """
    Run a complete IC session synchronously.

    Returns the full ICTranscript including all rounds and the final verdict.
    """
    symbol = ticker.upper().strip()
    if not symbol or len(symbol) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    try:
        fund_data = await asyncio.to_thread(fetch_fundamental_data, symbol)
        if not fund_data or "error" in fund_data:
            raise HTTPException(
                status_code=502, detail=f"Failed to fetch data for {symbol}"
            )

        debate = InvestmentCommitteeDebate()
        transcript = await debate.run_full(symbol, fund_data)
        return sanitize_data(transcript.model_dump(mode="json"))

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"IC run error for {symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
