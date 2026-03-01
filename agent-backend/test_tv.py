from tradingview_ta import TA_Handler, Interval, Exchange
import sys

def test_tv(symbol, exchange):
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="america",
            exchange=exchange,
            interval=Interval.INTERVAL_1_DAY
        )
        analysis = handler.get_analysis()
        print(f"SUCCESS: {symbol} on {exchange}")
        for k in sorted(analysis.indicators.keys()):
            print(f"KEY: {k}")
    except Exception as e:
        print(f"FAILED: {symbol} on {exchange} - {e}")

if __name__ == "__main__":
    test_tv("MSFT", "NASDAQ")
    test_tv("AAPL", "NASDAQ")
    test_tv("TSLA", "NASDAQ")
    test_tv("KO", "NYSE")
