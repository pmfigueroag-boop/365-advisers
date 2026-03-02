import json
import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from graph import app_graph, sanitize_data, run_analysis_stream

# ── Phase 2: Technical Engine
from src.data.market_data import fetch_technical_data
from src.engines.technical.indicators import IndicatorEngine
from src.engines.technical.scoring import ScoringEngine
from src.engines.technical.formatter import build_technical_summary

# ── Phase 3: Fundamental Engine
from src.engines.fundamental.graph import run_fundamental_stream

# ── Phase 4: Database persistence
from src.data.database import (
    init_db,
    FundamentalDBCache,
    TechnicalDBCache,
    get_score_history,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the SQLite database on startup."""
    init_db()
    yield


app = FastAPI(title="365 Advisers API", lifespan=lifespan)
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


# ── Technical Cache (Phase 2) ───────────────────────────────────────────

tech_cache = TechnicalDBCache()


# ── Fundamental Cache (Phase 4 — DB-backed, was in-memory Phase 3) ──────────
fund_cache = FundamentalDBCache()





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


# ─── Technical Analysis Endpoint (Phase 2) ────────────────────────────────────

@app.get("/analysis/technical")
async def get_technical_analysis(ticker: str, force: bool = False):
    """
    Run the full Technical Engine for a given ticker.

    Returns a TechnicalSummary with:
      - 5 indicator module results (Trend, Momentum, Volatility, Volume, Structure)
      - Deterministic 0–10 score per module + aggregate
      - Signal (STRONG_BUY → STRONG_SELL) + Strength (Strong/Moderate/Weak)

    Cache TTL: 15 minutes (indicators change intraday).
    Use ?force=true to bypass cache.
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    symbol = ticker.upper().strip()

    # Cache check
    if not force:
        cached = tech_cache.get(symbol)
        if cached:
            print(f"[TECH-CACHE] HIT for {symbol}")
            return {**cached, "from_cache": True}

    # Run the Technical Engine
    import time as _time
    start = _time.monotonic_ns() / 1e6

    try:
        tech_data   = fetch_technical_data(symbol)
        indicators  = IndicatorEngine.compute(tech_data)
        score       = ScoringEngine.compute(indicators)
        summary     = build_technical_summary(
            ticker=symbol,
            tech_data=tech_data,
            result=indicators,
            score=score,
            processing_start_ms=start,
        )
        summary["from_cache"] = False
        tech_cache.set(symbol, summary)
        return summary

    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Technical analysis failed for {symbol}: {str(exc)}"
        )


@app.delete("/cache/technical/{ticker}")
def invalidate_technical_cache(ticker: str):
    """Invalidate the technical cache for a specific ticker."""
    removed = tech_cache.invalidate(ticker)
    return {"ticker": ticker.upper(), "invalidated": removed}


# ─── Score History + Cache Status (Phase 4) ───────────────────────────────────

@app.get("/score-history")
def score_history(ticker: str, type: str = "fundamental", limit: int = 90):
    """
    Return the last N score records for a ticker.

    type: 'fundamental' | 'technical'
    limit: max rows (default 90)
    """
    if type not in ("fundamental", "technical"):
        raise HTTPException(status_code=400, detail="type must be 'fundamental' or 'technical'")
    data = get_score_history(ticker, type, min(limit, 365))
    return {"ticker": ticker.upper(), "analysis_type": type, "history": data}


@app.get("/cache/status")
def cache_status():
    """Return what's currently in both caches."""
    return {
        "fundamental": fund_cache.status(),
        "technical":   tech_cache.status(),
    }




# ─── Fundamental Analysis Endpoint (Phase 3) ──────────────────────────────────

@app.get("/analysis/fundamental/stream")
async def fundamental_analysis_stream(ticker: str, force: bool = False):
    """
    SSE stream for the Fundamental Analysis Engine.

    Events (in order):
      data_ready       → ratios + company info (no LLM, fast)
      agent_memo       × 4 → Value, Quality, Capital, Risk analysts
      committee_verdict → 0-10 score + signal + narrative
      research_memo    → full 1-pager markdown
      done

    Cache TTL: 24 hours (fundamental data is stable intraday).
    Use ?force=true to bypass cache.
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    symbol = ticker.upper().strip()

    # Serve from cache if available
    if not force:
        cached = fund_cache.get(symbol)
        if cached:
            print(f"[FUND-CACHE] HIT for {symbol}")
            async def replay_cache():
                for event_dict in cached["events"]:
                    yield sse(event_dict["event"], event_dict["data"])
                yield sse("done", {"from_cache": True})
            return StreamingResponse(replay_cache(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Stream live analysis
    async def event_generator():
        collected_events = []
        try:
            async for event_dict in run_fundamental_stream(symbol):
                event_name = event_dict.get("event", "")
                data = event_dict.get("data", {})
                line = sse(event_name, data)
                yield line
                if event_name not in ("done", "error"):
                    collected_events.append({"event": event_name, "data": data})
            # Cache the full stream on success
            if collected_events:
                fund_cache.set(symbol, {"events": collected_events})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/cache/fundamental/{ticker}")
def invalidate_fundamental_cache(ticker: str):
    """Invalidate the fundamental cache for a specific ticker."""
    removed = fund_cache.invalidate(ticker)
    return {"ticker": ticker.upper(), "invalidated": removed}



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


# ─── Combined Analysis Endpoint (Phase 5) ─────────────────────────────────────

@app.get("/analysis/combined/stream")
async def combined_analysis_stream(ticker: str, force: bool = False):
    """
    SSE stream that orchestrates both the Fundamental and Technical engines.

    Event flow:
      1. data_ready          → fundamental ratios (no LLM)
      2. agent_memo × 4      → specialist analysts
      3. committee_verdict   → 0-10 score + narrative
      4. research_memo       → 1-pager markdown
      5. technical_ready     → full TechnicalSummary JSON
      6. done

    Cache strategy:
      - Fundamental: 24h DB cache
      - Technical:   15min DB cache
      Both engines use their own caches independently.
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker parameter is required")

    symbol = ticker.upper().strip()

    async def event_generator():
        fund_events: list[dict] = []
        tech_data: dict | None = None
        is_from_cache = False

        # ── Part 1: Fundamental Engine ──────────────────────────────────────
        cached_fund = fund_cache.get(symbol) if not force else None
        if cached_fund:
            print(f"[COMBINED] Fundamental HIT for {symbol}")
            is_from_cache = True
            for ev in cached_fund["events"]:
                yield sse(ev["event"], ev["data"])
                await asyncio.sleep(0.02)
        else:
            # Run live and capture events for caching
            async for ev_dict in run_fundamental_stream(symbol):
                event_name = ev_dict.get("event", "")
                data = ev_dict.get("data", {})
                if event_name not in ("done", "error"):
                    yield sse(event_name, data)
                    fund_events.append({"event": event_name, "data": data})
                elif event_name == "error":
                    yield sse("error", data)
                    return
            # Cache the fundamental result
            if fund_events:
                fund_cache.set(symbol, {"events": fund_events})

        # ── Part 2: Technical Engine ────────────────────────────────────────
        cached_tech = tech_cache.get(symbol) if not force else None
        if cached_tech:
            print(f"[COMBINED] Technical HIT for {symbol}")
            tech_data = cached_tech
        else:
            import time as _time
            start = _time.monotonic_ns() / 1e6
            try:
                from src.data.market_data import fetch_technical_data
                from src.engines.technical.indicators import IndicatorEngine
                from src.engines.technical.scoring import ScoringEngine
                from src.engines.technical.formatter import build_technical_summary

                raw = await asyncio.to_thread(fetch_technical_data, symbol)
                indicators = await asyncio.to_thread(IndicatorEngine(raw).run)
                scores = ScoringEngine(indicators).score()
                elapsed = (_time.monotonic_ns() / 1e6) - start
                tech_data = build_technical_summary(symbol, scores, indicators, elapsed_ms=elapsed)
                tech_cache.set(symbol, tech_data)
            except Exception as exc:
                import traceback; traceback.print_exc()
                # Non-fatal — emit error info but continue
                yield sse("technical_ready", {"error": str(exc)})
                yield sse("done", {"from_cache": is_from_cache})
                return

        yield sse("technical_ready", tech_data)
        await asyncio.sleep(0)
        yield sse("done", {"from_cache": is_from_cache})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
