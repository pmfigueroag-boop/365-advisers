import requests
import json

def test_analyze():
    url = "http://localhost:8000/analyze"
    payload = {"ticker": "MSFT"}
    try:
        response = requests.post(url, json=payload, timeout=120)
        print(f"STATUS: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("KEYS:", sorted(list(data.keys())))
            print("FUNDAMENTAL KEYS:", sorted(list(data.get('fundamental_metrics', {}).keys())))
            print("TV SUMMARY:", data.get('tradingview', {}).get('summary'))
            # Check for technical agents data
            for agent in data.get('agent_responses', []):
                if agent['agent_name'] in ['RSI', 'MACD']:
                    print(f"AGENT {agent['agent_name']} ANALYSIS SAMPLE: {agent['analysis'][:100]}...")
        else:
            print("RESPONSE TEXT:", response.text)
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_analyze()
