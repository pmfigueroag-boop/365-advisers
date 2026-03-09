"""
src/engines/event_backtester/engine.py — Event-driven backtesting engine.
"""
from __future__ import annotations
import numpy as np
import logging
from datetime import datetime, timezone
from src.engines.event_backtester.models import (
    MarketEvent, SignalEvent, OrderEvent, FillEvent,
    BacktestConfig, BacktestResult, TradeLog, EventType,
)
from src.engines.event_backtester.event_bus import EventBus
from src.engines.event_backtester.execution_sim import ExecutionSimulator

logger = logging.getLogger("365advisers.backtester.engine")


class EventBacktester:
    """
    Event-driven backtesting engine.

    Pipeline: market data → strategy signals → orders → execution → P&L
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.bus = EventBus()
        self.executor = ExecutionSimulator(self.config)

        # State
        self._cash = self.config.initial_capital
        self._positions: dict[str, float] = {}    # ticker → qty
        self._avg_costs: dict[str, float] = {}    # ticker → avg cost
        self._prices: dict[str, float] = {}       # ticker → last price
        self._equity_curve: list[float] = []
        self._trades: list[TradeLog] = []
        self._open_trades: dict[str, dict] = {}   # ticker → entry info
        self._events_processed = 0

        # Register handlers
        self.bus.register(EventType.MARKET, self._on_market)
        self.bus.register(EventType.ORDER, self._on_order)
        self.bus.register(EventType.FILL, self._on_fill)

    def run(
        self,
        prices: dict[str, list[float]],
        strategy_fn,
        timestamps: list[datetime] | None = None,
    ) -> BacktestResult:
        """
        Run backtest with tick-level data.

        Args:
            prices: ticker → list of prices (one per tick)
            strategy_fn: callable(ticker, price, positions, cash) → signal (-1 to +1) or None
            timestamps: optional timestamp per tick
        """
        tickers = sorted(prices.keys())
        n_ticks = min(len(prices[t]) for t in tickers)

        if not timestamps:
            from datetime import timedelta
            base = datetime.now(timezone.utc)
            timestamps = [base + timedelta(minutes=i) for i in range(n_ticks)]

        self._equity_curve = []

        for i in range(n_ticks):
            ts = timestamps[i]

            # Emit market events
            for ticker in tickers:
                price = prices[ticker][i]
                self._prices[ticker] = price
                event = MarketEvent(timestamp=ts, ticker=ticker, price=price)
                self.bus.emit(event)

            # Process market events
            self.bus.process_all()

            # Run strategy
            for ticker in tickers:
                signal = strategy_fn(ticker, prices[ticker][i], dict(self._positions), self._cash)
                if signal is not None and abs(signal) > 0.01:
                    self._process_signal(ticker, signal, prices[ticker][i], ts)

            # Process any resulting orders/fills
            self.bus.process_all()

            # Record equity
            equity = self._compute_equity()
            self._equity_curve.append(equity)

        # Close all open positions at last price
        self._close_all_positions(timestamps[-1] if timestamps else datetime.now(timezone.utc))

        return self._build_result()

    def _process_signal(self, ticker: str, signal: float, price: float, ts: datetime):
        """Convert signal to order."""
        equity = self._compute_equity()
        max_position_value = equity * self.config.max_position_pct
        current_qty = self._positions.get(ticker, 0)

        if signal > 0 and current_qty <= 0:
            # Buy signal
            qty = int(max_position_value / price)
            if qty > 0:
                self.bus.emit(OrderEvent(timestamp=ts, ticker=ticker, side="buy", quantity=qty))
        elif signal < 0 and current_qty >= 0:
            # Sell or short signal
            if current_qty > 0:
                self.bus.emit(OrderEvent(timestamp=ts, ticker=ticker, side="sell", quantity=current_qty))
            elif self.config.enable_shorting:
                qty = int(max_position_value / price)
                if qty > 0:
                    self.bus.emit(OrderEvent(timestamp=ts, ticker=ticker, side="sell", quantity=qty))

    def _on_market(self, event: MarketEvent):
        self._prices[event.ticker] = event.price
        self._events_processed += 1

    def _on_order(self, event: OrderEvent):
        price = self._prices.get(event.ticker, 0)
        if price <= 0:
            return
        fill = self.executor.execute(event, price)
        self.bus.emit(fill)
        self._events_processed += 1

    def _on_fill(self, event: FillEvent):
        ticker = event.ticker
        self._cash -= event.commission

        if event.side == "buy":
            old_qty = self._positions.get(ticker, 0)
            old_cost = self._avg_costs.get(ticker, 0)
            total_cost = old_cost * old_qty + event.fill_price * event.quantity
            new_qty = old_qty + event.quantity
            self._positions[ticker] = new_qty
            self._avg_costs[ticker] = total_cost / new_qty if new_qty > 0 else 0
            self._cash -= event.quantity * event.fill_price

            if ticker not in self._open_trades:
                self._open_trades[ticker] = {"entry_time": event.timestamp, "entry_price": event.fill_price, "quantity": event.quantity, "side": "buy"}
        else:
            old_qty = self._positions.get(ticker, 0)
            self._positions[ticker] = old_qty - event.quantity
            self._cash += event.quantity * event.fill_price

            if ticker in self._open_trades:
                ot = self._open_trades.pop(ticker)
                pnl = (event.fill_price - ot["entry_price"]) * ot["quantity"] - event.commission
                self._trades.append(TradeLog(
                    entry_time=ot["entry_time"], exit_time=event.timestamp,
                    ticker=ticker, side=ot["side"], quantity=ot["quantity"],
                    entry_price=ot["entry_price"], exit_price=event.fill_price,
                    pnl=round(pnl, 2), commission=event.commission,
                ))

            if self._positions.get(ticker, 0) == 0:
                self._positions.pop(ticker, None)
                self._avg_costs.pop(ticker, None)

        self._events_processed += 1

    def _close_all_positions(self, ts: datetime):
        for ticker, qty in list(self._positions.items()):
            if qty != 0:
                side = "sell" if qty > 0 else "buy"
                self.bus.emit(OrderEvent(timestamp=ts, ticker=ticker, side=side, quantity=abs(qty)))
        self.bus.process_all()

    def _compute_equity(self) -> float:
        position_value = sum(
            qty * self._prices.get(t, 0) for t, qty in self._positions.items()
        )
        return self._cash + position_value

    def _build_result(self) -> BacktestResult:
        ec = self._equity_curve
        if not ec:
            return BacktestResult()

        total_ret = (ec[-1] / ec[0] - 1) if ec[0] > 0 else 0
        returns = np.diff(ec) / np.array(ec[:-1]) if len(ec) > 1 else []
        vol = float(np.std(returns) * np.sqrt(252)) if len(returns) > 1 else 0
        sharpe = total_ret / vol if vol > 0 else 0

        # Max drawdown
        peak = ec[0]
        max_dd = 0
        for v in ec:
            peak = max(peak, v)
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

        # Trade stats
        wins = [t for t in self._trades if t.pnl > 0]
        losses = [t for t in self._trades if t.pnl <= 0]
        win_rate = len(wins) / len(self._trades) if self._trades else 0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

        return BacktestResult(
            total_return=round(total_ret, 6),
            annualised_return=round(total_ret * (252 / max(len(ec), 1)), 6),
            volatility=round(vol, 6),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 6),
            win_rate=round(win_rate, 4),
            profit_factor=round(pf, 4) if pf != float('inf') else 999.0,
            total_trades=len(self._trades),
            avg_trade_pnl=round(np.mean([t.pnl for t in self._trades]), 2) if self._trades else 0,
            final_equity=round(ec[-1], 2),
            equity_curve=ec,
            trade_log=self._trades,
            events_processed=self._events_processed,
        )
