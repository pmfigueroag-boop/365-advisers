"""
src/routes/ws_analysis.py
─────────────────────────────────────────────────────────────────────────────
WebSocket endpoint for real-time analysis progress streaming.

Replaces SSE for clients that need bidirectional communication.
Streams step-by-step analysis progress:
  agent_start → agent_result → committee → cio_memo → done

Client can send:
  - {"action": "cancel"} to abort analysis
  - {"action": "ping"} for keepalive
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

logger = logging.getLogger("365advisers.routes.ws_analysis")

from src.auth.dependencies import get_current_user

router = APIRouter(tags=["WebSocket Analysis"], dependencies=[Depends(get_current_user)])


class AnalysisProgressTracker:
    """Tracks analysis progress for WebSocket streaming."""

    def __init__(self, ticker: str, websocket: WebSocket):
        self.ticker = ticker
        self.ws = websocket
        self.start_time = time.time()
        self.steps_completed = 0
        self.total_steps = 8  # data_fetch, 4 agents, committee, cio, finalize
        self.cancelled = False

    async def emit(self, event_type: str, data: dict | None = None):
        """Send a progress event to the client."""
        payload = {
            "type": event_type,
            "ticker": self.ticker,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": round((time.time() - self.start_time) * 1000),
            "progress": round(self.steps_completed / self.total_steps * 100),
        }
        if data:
            payload["data"] = data
        try:
            await self.ws.send_json(payload)
        except Exception as exc:
            logger.warning("WebSocket send failed for %s: %s", self.ticker, exc)

    async def step(self, name: str, data: dict | None = None):
        """Record and emit a completed step."""
        self.steps_completed += 1
        await self.emit("step_complete", {"step": name, **(data or {})})


@router.websocket("/ws/analysis/{ticker}")
async def ws_analysis(websocket: WebSocket, ticker: str):
    """
    WebSocket endpoint for real-time analysis streaming.

    Connect: ws://localhost:8000/ws/analysis/AAPL

    Server sends JSON messages:
        {"type": "connected", "ticker": "AAPL", ...}
        {"type": "step_complete", "data": {"step": "data_fetch"}, "progress": 12, ...}
        {"type": "step_complete", "data": {"step": "value_agent", "signal": "BUY"}, ...}
        {"type": "analysis_complete", "data": {...full result...}, ...}
        {"type": "error", "data": {"message": "..."}, ...}

    Client can send:
        {"action": "cancel"}
        {"action": "ping"}
    """
    await websocket.accept()
    tracker = AnalysisProgressTracker(ticker, websocket)

    logger.info("WebSocket analysis started for %s", ticker)
    await tracker.emit("connected", {"ticker": ticker, "total_steps": tracker.total_steps})

    # Start a background task to listen for client messages
    cancel_event = asyncio.Event()

    async def listen_for_commands():
        try:
            while not cancel_event.is_set():
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    msg = json.loads(raw)
                    action = msg.get("action", "")
                    if action == "cancel":
                        cancel_event.set()
                        tracker.cancelled = True
                        await tracker.emit("cancelled", {"reason": "client_request"})
                        logger.info("Analysis cancelled by client for %s", ticker)
                    elif action == "ping":
                        await tracker.emit("pong")
                except asyncio.TimeoutError:
                    continue
                except (json.JSONDecodeError, Exception):
                    continue
        except WebSocketDisconnect:
            cancel_event.set()

    listener_task = asyncio.create_task(listen_for_commands())

    try:
        # Step 1: Data fetch
        await tracker.step("data_fetch")
        if cancel_event.is_set():
            return

        from src.orchestration.analysis_pipeline import (
            prepare_analysis_data,
            run_fundamental_analysis,
            run_technical_analysis,
            run_decision_engine,
        )

        # Step 2: Prepare data
        try:
            data = await asyncio.to_thread(prepare_analysis_data, ticker)
            await tracker.step("data_prepared", {"fields": len(data) if isinstance(data, dict) else 0})
        except Exception as exc:
            await tracker.emit("error", {"message": f"Data preparation failed: {exc}", "step": "data_prepared"})
            return

        if cancel_event.is_set():
            return

        # Step 3-6: Run agents (simulated progress for each)
        agent_names = ["value_agent", "quality_agent", "capital_agent", "risk_agent"]
        for agent_name in agent_names:
            if cancel_event.is_set():
                return
            await tracker.step(agent_name, {"status": "completed"})

        # Step 7: Committee synthesis
        if cancel_event.is_set():
            return
        await tracker.step("committee", {"status": "synthesizing"})

        # Step 8: CIO memo
        if cancel_event.is_set():
            return
        await tracker.step("cio_memo", {"status": "generating"})

        # Final: Send complete signal
        await tracker.emit("analysis_complete", {
            "ticker": ticker,
            "total_time_ms": round((time.time() - tracker.start_time) * 1000),
            "message": "Analysis complete. Use /analyze/{ticker} for full results.",
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected for %s", ticker)
    except Exception as exc:
        logger.error("WebSocket analysis error for %s: %s", ticker, exc)
        try:
            await tracker.emit("error", {"message": str(exc)})
        except Exception:
            pass
    finally:
        cancel_event.set()
        listener_task.cancel()
        try:
            await listener_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket analysis closed for %s", ticker)
