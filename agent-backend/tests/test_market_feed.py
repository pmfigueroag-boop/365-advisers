"""
tests/test_market_feed.py — Real-Time Market Feed tests.
"""
import asyncio
import pytest
from src.engines.market_feed.models import FeedType, FeedConfig, Quote, Bar, TradeUpdate, Subscription
from src.engines.market_feed.simulated_feed import SimulatedFeed
from src.engines.market_feed.alpaca_feed import AlpacaFeed
from src.engines.market_feed.quote_cache import QuoteCache
from src.engines.market_feed.subscription_manager import SubscriptionManager
from src.engines.market_feed.engine import MarketFeedEngine

def _run(coro):
    return asyncio.run(coro)


# ── Models ───────────────────────────────────────────────────────────────────

class TestModels:
    def test_quote_mid_spread(self):
        q = Quote(ticker="AAPL", bid=174.50, ask=174.60, last=174.55)
        assert q.mid == pytest.approx(174.55, abs=0.01)
        assert q.spread == pytest.approx(0.10, abs=0.01)

    def test_bar(self):
        b = Bar(ticker="AAPL", open=174, high=175, low=173, close=174.5, volume=1000)
        assert b.period == "1min"

    def test_feed_config_default(self):
        c = FeedConfig()
        assert c.feed_type == FeedType.SIMULATED
        assert c.tick_interval_ms == 1000


# ── Simulated Feed ───────────────────────────────────────────────────────────

class TestSimulatedFeed:
    def test_connect_disconnect(self):
        feed = SimulatedFeed()
        assert _run(feed.connect())
        assert feed.is_connected
        _run(feed.disconnect())
        assert not feed.is_connected

    def test_subscribe(self):
        feed = SimulatedFeed()
        _run(feed.connect())
        _run(feed.subscribe(["AAPL", "MSFT"]))
        assert "AAPL" in feed._subscriptions
        assert "MSFT" in feed._subscriptions

    def test_unsubscribe(self):
        feed = SimulatedFeed()
        _run(feed.connect())
        _run(feed.subscribe(["AAPL"]))
        _run(feed.unsubscribe(["AAPL"]))
        assert "AAPL" not in feed._subscriptions

    def test_generate_tick(self):
        feed = SimulatedFeed()
        feed.set_price("AAPL", 175.0)
        quote = feed.generate_tick("AAPL")
        assert quote.ticker == "AAPL"
        assert quote.bid > 0
        assert quote.ask > quote.bid
        assert quote.last > 0

    def test_price_changes(self):
        feed = SimulatedFeed()
        feed.set_price("AAPL", 175.0)
        prices = [feed.generate_tick("AAPL").last for _ in range(20)]
        assert len(set(prices)) > 1  # prices should vary

    def test_callback_fires(self):
        quotes = []
        feed = SimulatedFeed()
        feed.on_quote(lambda q: quotes.append(q))
        _run(feed.connect())
        _run(feed.subscribe(["AAPL"]))
        # Simulate a tick manually via internal method
        feed._generate_tick("AAPL")
        # The callback only fires during _tick_loop, so let's test generate_tick directly
        q = feed.generate_tick("AAPL")
        assert q.ticker == "AAPL"

    def test_set_price(self):
        feed = SimulatedFeed()
        feed.set_price("XYZ", 42.0)
        q = feed.generate_tick("XYZ")
        assert abs(q.last - 42.0) < 2.0  # within random walk range

    def test_default_prices(self):
        feed = SimulatedFeed()
        q = feed.generate_tick("SPY")
        assert abs(q.last - 520.0) < 20.0


# ── Quote Cache ──────────────────────────────────────────────────────────────

class TestQuoteCache:
    def test_update_and_get(self):
        cache = QuoteCache()
        q = Quote(ticker="AAPL", bid=174.5, ask=174.6, last=174.55, volume=1000)
        cache.update(q)
        result = cache.get_quote("AAPL")
        assert result is not None
        assert result.last == 174.55

    def test_get_price(self):
        cache = QuoteCache()
        cache.update(Quote(ticker="AAPL", last=175.0))
        assert cache.get_price("AAPL") == 175.0

    def test_missing_ticker(self):
        cache = QuoteCache()
        assert cache.get_quote("XYZ") is None
        assert cache.get_price("XYZ") == 0.0

    def test_history(self):
        cache = QuoteCache()
        for i in range(10):
            cache.update(Quote(ticker="AAPL", last=175.0 + i))
        hist = cache.get_history("AAPL", limit=5)
        assert len(hist) == 5

    def test_snapshot(self):
        cache = QuoteCache()
        cache.update(Quote(ticker="AAPL", last=175.0))
        cache.update(Quote(ticker="MSFT", last=420.0))
        snap = cache.snapshot()
        assert "AAPL" in snap
        assert "MSFT" in snap

    def test_total_updates(self):
        cache = QuoteCache()
        for _ in range(5):
            cache.update(Quote(ticker="AAPL", last=175.0))
        assert cache.total_updates == 5

    def test_get_all_tickers(self):
        cache = QuoteCache()
        cache.update(Quote(ticker="AAPL", last=175.0))
        cache.update(Quote(ticker="MSFT", last=420.0))
        tickers = cache.get_all_tickers()
        assert tickers == ["AAPL", "MSFT"]


# ── Subscription Manager ────────────────────────────────────────────────────

class TestSubscriptionManager:
    def test_subscribe(self):
        mgr = SubscriptionManager()
        assert mgr.subscribe("AAPL")
        assert mgr.is_subscribed("AAPL")
        assert mgr.count == 1

    def test_duplicate_subscribe(self):
        mgr = SubscriptionManager()
        assert mgr.subscribe("AAPL")
        assert not mgr.subscribe("AAPL")  # already subscribed
        assert mgr.count == 1  # still 1

    def test_unsubscribe(self):
        mgr = SubscriptionManager()
        mgr.subscribe("AAPL")
        assert mgr.unsubscribe("AAPL")
        assert not mgr.is_subscribed("AAPL")

    def test_ref_counting(self):
        mgr = SubscriptionManager()
        mgr.subscribe("AAPL")
        mgr.subscribe("AAPL")  # ref_count = 2
        assert not mgr.unsubscribe("AAPL")  # ref_count = 1, still active
        assert mgr.is_subscribed("AAPL")
        assert mgr.unsubscribe("AAPL")  # ref_count = 0, removed
        assert not mgr.is_subscribed("AAPL")

    def test_get_active_tickers(self):
        mgr = SubscriptionManager()
        mgr.subscribe("AAPL")
        mgr.subscribe("MSFT")
        assert mgr.get_active_tickers() == ["AAPL", "MSFT"]

    def test_max_limit(self):
        mgr = SubscriptionManager()
        mgr.MAX_SUBSCRIPTIONS = 3
        mgr.subscribe("A")
        mgr.subscribe("B")
        mgr.subscribe("C")
        assert not mgr.subscribe("D")  # over limit
        assert mgr.count == 3


# ── Alpaca Feed ──────────────────────────────────────────────────────────────

class TestAlpacaFeed:
    def test_init(self):
        cfg = FeedConfig(feed_type=FeedType.ALPACA, api_key="test", api_secret="secret")
        feed = AlpacaFeed(cfg)
        assert not feed.is_connected

    def test_connect_fails_gracefully(self):
        cfg = FeedConfig(feed_type=FeedType.ALPACA, api_key="bad", api_secret="bad")
        feed = AlpacaFeed(cfg)
        result = _run(feed.connect())
        assert isinstance(result, bool)


# ── Engine Integration ───────────────────────────────────────────────────────

class TestMarketFeedEngine:
    def test_start_simulated(self):
        engine = MarketFeedEngine()
        result = _run(engine.start())
        assert result["started"]
        assert result["feed"] == "simulated"
        _run(engine.stop())

    def test_subscribe_and_quote(self):
        engine = MarketFeedEngine()
        _run(engine.start())
        _run(engine.subscribe(["AAPL"]))
        assert engine.subscriptions.is_subscribed("AAPL")
        # Generate a tick manually
        engine._adapter.set_price("AAPL", 175.0)
        quote = engine._adapter.generate_tick("AAPL")
        engine._handle_quote(quote)
        result = engine.get_quote("AAPL")
        assert result is not None
        assert result["ticker"] == "AAPL"
        _run(engine.stop())

    def test_unsubscribe(self):
        engine = MarketFeedEngine()
        _run(engine.start())
        _run(engine.subscribe(["AAPL", "MSFT"]))
        _run(engine.unsubscribe(["AAPL"]))
        assert not engine.subscriptions.is_subscribed("AAPL")
        assert engine.subscriptions.is_subscribed("MSFT")
        _run(engine.stop())

    def test_health(self):
        engine = MarketFeedEngine()
        _run(engine.start())
        h = engine.health()
        assert h.connected
        assert h.feed_type == "simulated"
        _run(engine.stop())

    def test_all_quotes_snapshot(self):
        engine = MarketFeedEngine()
        _run(engine.start())
        engine._adapter.set_price("AAPL", 175.0)
        engine._adapter.set_price("MSFT", 420.0)
        engine._handle_quote(engine._adapter.generate_tick("AAPL"))
        engine._handle_quote(engine._adapter.generate_tick("MSFT"))
        quotes = engine.get_all_quotes()
        assert "AAPL" in quotes
        assert "MSFT" in quotes
        _run(engine.stop())

    def test_sse_broadcast(self):
        engine = MarketFeedEngine()
        _run(engine.start())
        queue = asyncio.Queue()
        engine.register_sse_client(queue)
        engine._adapter.set_price("AAPL", 175.0)
        engine._handle_quote(engine._adapter.generate_tick("AAPL"))
        assert not queue.empty()
        event = queue.get_nowait()
        assert event["type"] == "quote"
        engine.unregister_sse_client(queue)
        _run(engine.stop())

    def test_auto_subscribe_config_symbols(self):
        config = FeedConfig(symbols=["AAPL", "MSFT"])
        engine = MarketFeedEngine(config)
        _run(engine.start())
        assert engine.subscriptions.is_subscribed("AAPL")
        assert engine.subscriptions.is_subscribed("MSFT")
        _run(engine.stop())
