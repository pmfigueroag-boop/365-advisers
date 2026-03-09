"""src/routes/oms.py — Order Management System + Broker Integration API."""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.engines.oms.engine import OMSEngine
from src.engines.oms.brokers.base import BrokerConfig, BrokerType

logger = logging.getLogger("365advisers.routes.oms")
router = APIRouter(prefix="/alpha/oms", tags=["Alpha: OMS"])
_oms = OMSEngine()


# ── Request Models ───────────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    ticker: str
    side: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_id: str = ""

class FillRequest(BaseModel):
    order_id: str
    fill_price: float = Field(gt=0)

class BrokerConnectRequest(BaseModel):
    broker_type: BrokerType = BrokerType.PAPER
    api_key: str = ""
    api_secret: str = ""
    base_url: str = ""
    paper_mode: bool = True


# ── Order Endpoints ──────────────────────────────────────────────────────────

@router.post("/orders")
async def place_order(req: PlaceOrderRequest):
    """Place an order (sync — uses pre-trade risk checks)."""
    return _oms.place_order(
        req.ticker, req.side, req.quantity, req.price,
        order_type=req.order_type, limit_price=req.limit_price,
        stop_price=req.stop_price, strategy_id=req.strategy_id,
    )

@router.post("/orders/async")
async def place_order_async(req: PlaceOrderRequest):
    """Place an order via broker adapter (async)."""
    return await _oms.place_order_async(
        req.ticker, req.side, req.quantity, req.price,
        order_type=req.order_type, limit_price=req.limit_price,
        stop_price=req.stop_price, strategy_id=req.strategy_id,
    )

@router.get("/orders")
async def get_orders():
    return {"open_orders": _oms.get_open_orders()}

@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    result = await _oms.cancel_order_async(order_id)
    if result.get("success"):
        return result
    raise HTTPException(404, result.get("error", "Order not found"))

@router.post("/fill")
async def simulate_fill(req: FillRequest):
    result = _oms.simulate_fill(req.order_id, req.fill_price)
    if not result:
        raise HTTPException(404, "Order not found or not fillable")
    return result

@router.get("/orders/{order_id}/history")
async def order_history(order_id: str):
    order = _oms.order_manager.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    fills = _oms.order_manager.get_fills(order_id)
    return {"order": order.model_dump(), "fills": [f.model_dump() for f in fills]}


# ── Account Endpoints ────────────────────────────────────────────────────────

@router.get("/account")
async def get_account():
    return _oms.get_account()


# ── Broker Endpoints ────────────────────────────────────────────────────────

@router.post("/broker/connect")
async def connect_broker(req: BrokerConnectRequest):
    """Connect to a broker (paper, Alpaca, or IB)."""
    config = BrokerConfig(
        broker_type=req.broker_type,
        api_key=req.api_key,
        api_secret=req.api_secret,
        base_url=req.base_url,
        paper_mode=req.paper_mode,
    )
    result = await _oms.connect_broker(config)
    return result

@router.post("/broker/disconnect")
async def disconnect_broker():
    await _oms.disconnect_broker()
    return {"status": "disconnected"}

@router.get("/broker/status")
async def broker_status():
    """Get broker connection health."""
    return await _oms.broker_health()

@router.post("/broker/sync")
async def sync_positions():
    """Sync positions between local state and broker."""
    report = await _oms.sync_positions()
    return report.model_dump()

@router.post("/broker/sync-account")
async def sync_account():
    """Refresh account state from broker."""
    return await _oms.sync_account()

@router.get("/broker/quotes/{ticker}")
async def get_quote(ticker: str):
    """Get current price from broker."""
    try:
        price = await _oms.get_quote(ticker)
        return {"ticker": ticker, "price": price}
    except Exception as e:
        raise HTTPException(500, str(e))
