"""
src/routes/market_feed.py — Real-Time Market Data API with SSE streaming.
"""
from __future__ import annotations
import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from src.engines.market_feed.models import FeedConfig, FeedType
from src.engines.market_feed.engine import MarketFeedEngine

logger = logging.getLogger("365advisers.routes.feed")
router = APIRouter(prefix="/alpha/feed", tags=["Alpha: Market Feed"])
_engine = MarketFeedEngine()


class SubscribeRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1)

class FeedStartRequest(BaseModel):
    feed_type: FeedType = FeedType.SIMULATED
    api_key: str = ""
    api_secret: str = ""
    symbols: list[str] = Field(default_factory=list)
    tick_interval_ms: int = 1000


@router.post("/start")
async def start_feed(req: FeedStartRequest):
    """Start the market data feed."""
    config = FeedConfig(
        feed_type=req.feed_type,
        api_key=req.api_key, api_secret=req.api_secret,
        symbols=req.symbols, tick_interval_ms=req.tick_interval_ms,
    )
    return await _engine.start(config)


@router.post("/stop")
async def stop_feed():
    """Stop the market data feed."""
    await _engine.stop()
    return {"status": "stopped"}


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest):
    return await _engine.subscribe(req.tickers)


@router.post("/unsubscribe")
async def unsubscribe(req: SubscribeRequest):
    return await _engine.unsubscribe(req.tickers)


@router.get("/quotes/{ticker}")
async def get_quote(ticker: str):
    quote = _engine.get_quote(ticker)
    if not quote:
        return {"ticker": ticker, "error": "No data"}
    return quote


@router.get("/quotes")
async def get_all_quotes():
    return _engine.get_all_quotes()


@router.get("/bars/{ticker}")
async def get_bars(ticker: str, limit: int = 60):
    return {"ticker": ticker, "bars": _engine.get_bars(ticker, limit)}


@router.get("/status")
async def feed_status():
    return _engine.health().model_dump()


@router.get("/stream")
async def sse_stream(request: Request):
    """
    Server-Sent Events stream for real-time market data.

    Connect from frontend:
        const sse = new EventSource('/alpha/feed/stream');
        sse.onmessage = (e) => console.log(JSON.parse(e.data));
    """
    queue = asyncio.Queue(maxsize=100)
    _engine.register_sse_client(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            _engine.unregister_sse_client(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
