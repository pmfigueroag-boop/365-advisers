"""
src/execution/broker_adapter.py
─────────────────────────────────────────────────────────────────────────────
Unified Abstraction for Broker Execution.
Provides a BaseBroker interface and a MockBrokerAdapter backed by SQLite.
"""

import sqlite3
import datetime
import logging
from typing import Dict, Any, List
from abc import ABC, abstractmethod

import yfinance as yf

logger = logging.getLogger("365advisers.broker")

class BaseBroker(ABC):
    """Abstract connection to any trading broker (Mock, Alpaca, IBKR)."""
    
    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """Returns {cash: float, equity: float, currency: str}"""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Returns list of {ticker: str, qty: float, current_price: float, market_value: float}"""
        pass

    @abstractmethod
    def submit_market_order(self, ticker: str, qty: float, side: str) -> Dict[str, Any]:
        """Submits an order and returns {order_id: str, status: str, filled_qty: float, filled_price: float}"""
        pass
        
    @abstractmethod
    def liquid_all_positions(self) -> Dict[str, Any]:
        """Closes all open positions at market price."""
        pass


class MockBrokerAdapter(BaseBroker):
    """
    A local, SQLite-backed Paper Trading engine.
    Uses yfinance to fetch real-time execution prices.
    """
    
    def __init__(self, db_path: str = "trading_db.sqlite", initial_capital: float = 100000.0):
        self.db_path = db_path
        self._init_db(initial_capital)
        
    def _init_db(self, initial_capital: float):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # Determine if we need to set initial capital
        cur.execute("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY, cash REAL)")
        cur.execute("SELECT cash FROM account WHERE id = 1")
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO account (id, cash) VALUES (1, ?)", (initial_capital,))
        elif row[0] <= 0:
            cur.execute("UPDATE account SET cash = ? WHERE id = 1", (initial_capital,))
            
        cur.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                ticker TEXT PRIMARY KEY,
                qty REAL,
                avg_entry_price REAL
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                ticker TEXT,
                side TEXT,
                qty REAL,
                price REAL
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _fetch_realtime_price(self, ticker: str) -> float:
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info
            if 'lastPrice' in info:
                return float(info['lastPrice'])
            return 0.0
        except Exception as e:
            logger.error(f"Failed to fetch real-time price for {ticker}: {e}")
            return 0.0

    def get_account(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT cash FROM account WHERE id = 1")
        cash = cur.fetchone()[0]
        
        cur.execute("SELECT ticker, qty FROM positions WHERE qty > 0")
        positions = cur.fetchall()
        
        portfolio_val = 0.0
        for ticker, qty in positions:
            price = self._fetch_realtime_price(ticker)
            portfolio_val += price * qty
            
        conn.close()
            
        return {
            "cash": round(cash, 2),
            "equity": round(cash + portfolio_val, 2),
            "currency": "USD"
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT ticker, qty, avg_entry_price FROM positions WHERE qty > 0")
        rows = cur.fetchall()
        conn.close()
        
        pos_list = []
        for ticker, qty, avg_entry in rows:
            price = self._fetch_realtime_price(ticker)
            pos_list.append({
                "ticker": ticker,
                "qty": qty,
                "avg_entry_price": avg_entry,
                "current_price": price,
                "market_value": round(price * qty, 2),
                "unrealized_pl": round((price - avg_entry) * qty, 2)
            })
            
        return pos_list

    def submit_market_order(self, ticker: str, qty: float, side: str) -> Dict[str, Any]:
        side = side.upper()
        if side not in ["BUY", "SELL"]:
            raise ValueError("Side must be BUY or SELL")
            
        price = self._fetch_realtime_price(ticker)
        if price <= 0:
            return {"status": "FAILED", "reason": f"Could not fetch live price for {ticker}"}
            
        cost = price * qty
        timestamp = datetime.datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        # 1. Check Cash/Position constraints
        cur.execute("SELECT cash FROM account WHERE id = 1")
        cash = cur.fetchone()[0]
        
        cur.execute("SELECT qty, avg_entry_price FROM positions WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        current_qty = row[0] if row else 0.0
        avg_price = row[1] if row else 0.0
        
        if side == "BUY":
            if cost > cash:
                conn.close()
                return {"status": "FAILED", "reason": f"Insufficient funds {cash} < {cost}"}
            
            new_cash = cash - cost
            new_qty = current_qty + qty
            # Compute new weighted average entry
            new_avg = ((current_qty * avg_price) + cost) / new_qty if new_qty > 0 else 0
            
            cur.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))
            cur.execute("INSERT OR REPLACE INTO positions (ticker, qty, avg_entry_price) VALUES (?, ?, ?)", 
                        (ticker, new_qty, new_avg))
                        
        elif side == "SELL":
            if qty > current_qty:
                conn.close()
                return {"status": "FAILED", "reason": f"Insufficient quantity {current_qty} < {qty}"}
                
            new_cash = cash + cost
            new_qty = current_qty - qty
            new_avg = avg_price if new_qty > 0 else 0.0
            
            cur.execute("UPDATE account SET cash = ? WHERE id = 1", (new_cash,))
            if new_qty > 0:
                cur.execute("UPDATE positions SET qty = ?, avg_entry_price = ? WHERE ticker = ?", 
                            (new_qty, new_avg, ticker))
            else:
                cur.execute("DELETE FROM positions WHERE ticker = ?", (ticker,))
                
        # 3. Log Trade
        cur.execute("INSERT INTO trade_history (timestamp, ticker, side, qty, price) VALUES (?, ?, ?, ?, ?)",
                   (timestamp, ticker, side, qty, price))
                   
        conn.commit()
        conn.close()
        
        logger.info(f"Mock Execution: {side} {qty:.4f} {ticker} @ ${price:.2f}")
        
        return {
            "order_id": f"mock_{int(datetime.datetime.now().timestamp())}",
            "status": "FILLED",
            "filled_qty": qty,
            "filled_price": price
        }
        
    def liquid_all_positions(self) -> Dict[str, Any]:
        positions = self.get_positions()
        results = []
        for p in positions:
            res = self.submit_market_order(p["ticker"], p["qty"], "SELL")
            results.append(res)
        return {"status": "LIQUIDATED", "trades": results}
