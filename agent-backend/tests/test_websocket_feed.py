"""
tests/test_websocket_feed.py — Tests for WebSocket feed infrastructure.
"""
from __future__ import annotations
import pytest
from src.engines.data.websocket_feed import (
    FeedConfig, FeedState, MarketTick, WebSocketFeed, FeedHealth,
)


class TestFeedState:

    def test_initial_disconnected(self):
        feed = WebSocketFeed()
        assert feed.get_health().state == FeedState.DISCONNECTED

    def test_connect_transitions(self):
        feed = WebSocketFeed()
        state = feed.connect()
        assert state == FeedState.CONNECTED

    def test_subscribe_transitions(self):
        feed = WebSocketFeed()
        feed.connect()
        state = feed.subscribe(["AAPL", "MSFT"])
        assert state == FeedState.SUBSCRIBED

    def test_disconnect(self):
        feed = WebSocketFeed()
        feed.connect()
        feed.subscribe(["AAPL"])
        feed.disconnect()
        assert feed.get_health().state == FeedState.DISCONNECTED


class TestTickPipeline:

    def test_push_and_consume(self):
        feed = WebSocketFeed()
        feed.connect()
        feed.subscribe(["AAPL"])
        tick = MarketTick(ticker="AAPL", price=185.50)
        feed.push_tick(tick)
        consumed = feed.consume()
        assert len(consumed) == 1
        assert consumed[0].ticker == "AAPL"

    def test_buffer_fifo(self):
        feed = WebSocketFeed()
        feed.push_tick(MarketTick(ticker="A", price=100))
        feed.push_tick(MarketTick(ticker="B", price=200))
        consumed = feed.consume(1)
        assert consumed[0].ticker == "A"

    def test_buffer_max_size(self):
        config = FeedConfig(max_buffer_size=100)
        feed = WebSocketFeed(config)
        for i in range(200):
            feed.push_tick(MarketTick(ticker=f"T{i}", price=float(i)))
        assert feed.get_health().buffer_size <= 100

    def test_get_latest(self):
        feed = WebSocketFeed()
        feed.push_tick(MarketTick(ticker="AAPL", price=180))
        feed.push_tick(MarketTick(ticker="MSFT", price=400))
        feed.push_tick(MarketTick(ticker="AAPL", price=185))
        latest = feed.get_latest("AAPL")
        assert latest is not None
        assert latest.price == 185


class TestHealth:

    def test_message_count(self):
        feed = WebSocketFeed()
        for _ in range(5):
            feed.push_tick(MarketTick(ticker="X", price=100))
        h = feed.get_health()
        assert h.messages_received == 5

    def test_subscriptions_tracked(self):
        feed = WebSocketFeed()
        feed.connect()
        feed.subscribe(["AAPL", "MSFT", "GOOGL"])
        h = feed.get_health()
        assert "AAPL" in h.subscribed_tickers
        assert len(h.subscribed_tickers) == 3

    def test_heartbeat_no_messages(self):
        feed = WebSocketFeed()
        assert feed.check_heartbeat() is False

    def test_heartbeat_after_tick(self):
        feed = WebSocketFeed()
        feed.push_tick(MarketTick(ticker="X", price=100))
        assert feed.check_heartbeat() is True


class TestReconnection:

    def test_reconnect_increments_count(self):
        feed = WebSocketFeed()
        feed.reconnect()
        assert feed.get_health().reconnect_count == 1

    def test_max_reconnect_exceeded(self):
        config = FeedConfig(max_reconnect_attempts=2)
        feed = WebSocketFeed(config)
        feed.reconnect()
        feed.reconnect()
        state = feed.reconnect()  # 3rd attempt, exceeds max
        assert state == FeedState.ERROR

    def test_is_active(self):
        feed = WebSocketFeed()
        assert feed.is_active is False
        feed.connect()
        assert feed.is_active is True


class TestUnsubscribe:

    def test_unsub_removes_tickers(self):
        feed = WebSocketFeed()
        feed.connect()
        feed.subscribe(["AAPL", "MSFT"])
        feed.unsubscribe(["AAPL"])
        h = feed.get_health()
        assert "AAPL" not in h.subscribed_tickers
        assert "MSFT" in h.subscribed_tickers
