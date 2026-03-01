import json
import time
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from graph import app_graph, sanitize_data, run_analysis_stream

app = FastAPI(title="365 Advisers API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory TTL Cache ─────────────────────────────────────────────────────

class AnalysisCache:
    """
    Simple in-memory cache with per-entry TTL.
    Thread-safe for asyncio (single-threaded event loop).

    Cache structure per ticker:
    {
        "data_ready": { ...DataFetcher payload... },
        "agents":     [ ...8 agent dicts... ],
        "dalio":      { final_verdict, dalio_response },
        "cached_at":  <ISO UTC string>,
        "ts":         <unix float>
    }
    """
    TTL_ANALYSIS = 300   # 5 minutes
    TTL_TICKER   = 900   # 15 minutes (price changes more slowly)

    def __init__(self):
        self._store: dict[str, dict] = {}
        self._ticker_store: dict[str, dict] = {}

    # ---- Analysis cache ----

    def get(self, ticker: str) -> dict | None:
        entry = self._store.get(ticker.upper())
        if entry and (time.time() - entry["ts"]) < self.TTL_ANALYSIS:
            return entry
        if entry:
            del self._store[ticker.upper()]  # expired — evict
        return None

    def set(self, ticker: str, data_ready: dict, agents: list, dalio: dict):
        now = time.time()
        self._store[ticker.upper()] = {
            "data_ready": data_ready,
            "agents": agents,
            "dalio": dalio,
            "cached_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "ts": now,
        }
        print(f"[CACHE] Stored analysis for {ticker.upper()} (TTL {self.TTL_ANALYSIS}s)")

    def invalidate(self, ticker: str) -> bool:
        return self._store.pop(ticker.upper(), None) is not None

    def status(self) -> list[dict]:
        now = time.time()
        result = []
        for t, entry in list(self._store.items()):
            age = now - entry["ts"]
            if age < self.TTL_ANALYSIS:
                result.append({
                    "ticker": t,
                    "cached_at": entry["cached_at"],
                    "age_s": round(age),
                    "expires_in_s": round(self.TTL_ANALYSIS - age),
                })
            else:
                del self._store[t]  # lazy eviction
        return result

    # ---- Ticker-info cache ----

    def get_ticker_info(self, ticker: str) -> dict | None:
        entry = self._ticker_store.get(ticker.upper())
        if entry and (time.time() - entry["ts"]) < self.TTL_TICKER:
            return entry["data"]
        if entry:
            del self._ticker_store[ticker.upper()]
        return None

    def set_ticker_info(self, ticker: str, data: dict):
        self._ticker_store[ticker.upper()] = {"data": data, "ts": time.time()}


cache = AnalysisCache()


# ─── SSE helpers ─────────────────────────────────────────────────────────────

def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_from_cache(ticker: str, entry: dict):
    """Replay a cached analysis as SSE events — nearly instant."""
    print(f"[CACHE] HIT for {ticker} — replaying from cache")

    # Inject cache metadata into data_ready
    data_ready = dict(entry["data_ready"])
    data_ready["from_cache"] = True
    data_ready["cached_at"] = entry["cached_at"]

    yield sse("data_ready", data_ready)
    await asyncio.sleep(0)  # yield control to event loop

    for agent in entry["agents"]:
        yield sse("agent_update", agent)
        await asyncio.sleep(0.05)  # tiny stagger for smooth UI render

    yield sse("dalio_verdict", entry["dalio"])
    await asyncio.sleep(0)
    yield sse("done", {})


async def stream_live_and_cache(ticker: str):
    """Run the full LangGraph and cache the result while streaming."""
    collected_data_ready = {}
    collected_agents = []
    collected_dalio = {}

    async for event in run_analysis_stream(ticker):
        event_name = event.get("event")
        data = event.get("data", {})

        if event_name == "data_ready":
            # Add cache metadata (miss)
            data = dict(data)
            data["from_cache"] = False
            data["cached_at"] = None
            collected_data_ready = data
            yield sse("data_ready", data)

        elif event_name == "agent_update":
            collected_agents.append(data)
            yield sse("agent_update", data)

        elif event_name == "dalio_verdict":
            collected_dalio = data
            yield sse("dalio_verdict", data)

        elif event_name == "done":
            # Only cache when we have a complete result
            if collected_data_ready and collected_agents and collected_dalio:
                cache.set(ticker, collected_data_ready, collected_agents, collected_dalio)
            yield sse("done", {})

        elif event_name == "error":
            yield sse("error", data)


# ─── Routes ──────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    ticker: str


@app.get("/")
def read_root():
    return {"message": "365 Advisers API is running"}


# ---- Quick Ticker Info ----
@app.get("/ticker-info")
async def ticker_info(ticker: str):
    """Fast endpoint: name + price. Used when adding to watchlist."""
    import yfinance as yf
    symbol = ticker.upper().strip()

    # Check cache first
    cached = cache.get_ticker_info(symbol)
    if cached:
        return cached

    try:
        info = yf.Ticker(symbol).info or {}
        result = {
            "ticker": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "exchange": info.get("exchange", ""),
        }
        cache.set_ticker_info(symbol, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch ticker info: {e}")


# ---- SSE Streaming Endpoint (cache-aware) ----
@app.get("/analyze/stream")
async def analyze_stream(ticker: str, force: bool = False):
    """
    Server-Sent Events endpoint. Serves from cache when available.
    Add ?force=true to bypass cache and run fresh analysis.
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    symbol = ticker.upper().strip()

    # Check cache (unless force refresh requested)
    if not force:
        entry = cache.get(symbol)
        if entry:
            return StreamingResponse(
                stream_from_cache(symbol, entry),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
            )

    # Cache miss (or force) → run live
    return StreamingResponse(
        stream_live_and_cache(symbol),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ---- Comparison Endpoint ----
async def _run_single_for_compare(symbol: str) -> dict:
    """
    Fetch analysis for one ticker, using the cache when available.
    Returns a normalised dict ready for the compare grid.
    """
    entry = cache.get(symbol)
    if entry:
        return {
            "ticker": symbol,
            "name": entry["data_ready"].get("name", symbol),
            "price": entry["data_ready"].get("price"),
            "from_cache": True,
            "agents": entry["agents"],
            "fundamental_metrics": entry["data_ready"].get("fundamental_metrics", {}),
            "dalio": entry["dalio"],
            "error": None,
        }

    # Cache miss — run the full graph
    try:
        initial_state = {
            "ticker": symbol,
            "financial_data": {},
            "macro_data": {},
            "chart_data": {"prices": [], "cashflow": []},
            "agent_responses": [],
            "final_verdict": "",
            "dalio_response": {},
        }
        result = await app_graph.ainvoke(initial_state)
        f_data = result.get("financial_data", {})
        fundamentals = f_data.get("fundamental_engine", {})
        info = f_data.get("info", {})

        agents = [
            sanitize_data({
                "agent_name": r.get("agent_name", ""),
                "signal": r.get("signal", ""),
                "confidence": r.get("confidence", 0),
                "analysis": r.get("analysis", ""),
                "selected_metrics": r.get("selected_metrics", []),
            })
            for r in result.get("agent_responses", [])
        ]
        dalio = sanitize_data({
            "final_verdict": result.get("final_verdict", ""),
            "dalio_response": result.get("dalio_response", {}),
        })

        data_ready = sanitize_data({
            "ticker": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "fundamental_metrics": fundamentals,
            "tech_indicators": f_data.get("tech_indicators", {}),
            "tradingview": f_data.get("tradingview", {}),
            "from_cache": False,
            "cached_at": None,
        })

        # Persist to cache for future single-ticker lookups
        cache.set(symbol, data_ready, agents, dalio)

        return {
            "ticker": symbol,
            "name": data_ready.get("name", symbol),
            "price": data_ready.get("price"),
            "from_cache": False,
            "agents": agents,
            "fundamental_metrics": fundamentals,
            "dalio": dalio,
            "error": None,
        }
    except Exception as e:
        return {"ticker": symbol, "error": str(e), "agents": [], "dalio": {}, "fundamental_metrics": {}}


@app.get("/compare")
async def compare_tickers(tickers: str):
    """
    Run analysis for up to 3 tickers in parallel (using cache when available).
    Usage: GET /compare?tickers=AAPL,MSFT,NVDA
    """
    raw = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not raw:
        raise HTTPException(status_code=400, detail="Provide at least one ticker")
    symbols = raw[:3]  # hard cap at 3

    results = await asyncio.gather(*[_run_single_for_compare(s) for s in symbols])
    return sanitize_data({"results": list(results)})


# ---- Cache Management ----
@app.delete("/cache/{ticker}")
def invalidate_cache(ticker: str):
    """Manually invalidate cache for a specific ticker."""
    removed = cache.invalidate(ticker)
    return {"ticker": ticker.upper(), "invalidated": removed}


@app.get("/cache/status")
def cache_status():
    """List all tickers currently in cache with TTL info."""
    return {"entries": cache.status(), "ttl_analysis_s": AnalysisCache.TTL_ANALYSIS}


# ---- Legacy Blocking Endpoint ----
@app.post("/analyze")
async def analyze_stock(request: AnalysisRequest):
    try:
        print(f"Starting analysis for ticker: {request.ticker}")
        initial_state = {
            "ticker": request.ticker,
            "financial_data": {},
            "macro_data": {},
            "chart_data": {"prices": [], "cashflow": []},
            "agent_responses": [],
            "final_verdict": "",
            "dalio_response": {}
        }
        result = await app_graph.ainvoke(initial_state)
        f_engine = result.get("financial_data", {}).get("fundamental_engine", {})
        return sanitize_data({
            "ticker": result.get("ticker", request.ticker),
            "agent_responses": result.get("agent_responses", []),
            "final_verdict": result.get("final_verdict", "No final verdict generated."),
            "chart_data": result.get("chart_data", {"prices": [], "cashflow": []}),
            "fundamental_metrics": f_engine,
            "dalio_response": result.get("dalio_response", {}),
            "tradingview": result.get("financial_data", {}).get("tradingview", {})
        })
    except Exception as e:
        print(f"CRITICAL ERROR in /analyze for {request.ticker}: {str(e)}")
        import traceback
        traceback.print_exc()
        return sanitize_data({
            "ticker": request.ticker,
            "agent_responses": [],
            "final_verdict": f"Error during analysis: {str(e)}",
            "chart_data": {"prices": [], "cashflow": []}
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
