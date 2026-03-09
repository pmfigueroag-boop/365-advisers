"""src/routes/oms.py — API for Order Management System."""
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.engines.oms.engine import OMSEngine

logger = logging.getLogger("365advisers.routes.oms")
router = APIRouter(prefix="/alpha/oms", tags=["Alpha: OMS"])
_oms = OMSEngine()

class PlaceOrderRequest(BaseModel):
    ticker: str
    side: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    order_type: str = "market"

class FillRequest(BaseModel):
    order_id: str
    fill_price: float = Field(gt=0)

@router.post("/orders")
async def place_order(req: PlaceOrderRequest):
    return _oms.place_order(req.ticker, req.side, req.quantity, req.price, order_type=req.order_type)

@router.get("/orders")
async def get_orders():
    return {"open_orders": _oms.get_open_orders()}

@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    if _oms.order_manager.cancel_order(order_id):
        return {"status": "cancelled", "order_id": order_id}
    raise HTTPException(404, "Order not found or already filled")

@router.post("/fill")
async def simulate_fill(req: FillRequest):
    result = _oms.simulate_fill(req.order_id, req.fill_price)
    if not result:
        raise HTTPException(404, "Order not found or not fillable")
    return result

@router.get("/account")
async def get_account():
    return _oms.get_account()
