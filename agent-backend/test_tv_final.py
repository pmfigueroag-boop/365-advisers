from tradingview_ta import TA_Handler, Interval, Exchange
import json

def test_tv():
    try:
        handler = TA_Handler(
            symbol="MSFT",
            exchange="NASDAQ",
            screener="america",
            interval=Interval.INTERVAL_1_DAY
        )
        analysis = handler.get_analysis()
        print("SUMMARY:", analysis.summary)
        print("ALL INDICATOR KEYS:")
        for k in sorted(list(analysis.indicators.keys())):
            print(k)
        print("SUCCESS")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_tv()
