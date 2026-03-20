import json, urllib.request

url = "http://localhost:8000/backtest/runs/b35f1a7b-4abd-4927-90dc-37c3b5ac261e"
with urllib.request.urlopen(url) as resp:
    data = json.loads(resp.read())

srs = data.get("signal_results", [])
print(f"Total signal results: {len(srs)}")
if srs:
    s = srs[0]
    print(f"\nFirst signal: {s.get('signal_name', s.get('signal_id'))}")
    print(f"  hit_rate type: {type(s.get('hit_rate')).__name__}")
    print(f"  hit_rate value: {s.get('hit_rate')}")
    print(f"  avg_return type: {type(s.get('avg_return')).__name__}")
    print(f"  avg_return value: {s.get('avg_return')}")
    print(f"  sharpe_ratio type: {type(s.get('sharpe_ratio')).__name__}")
    print(f"  sharpe_ratio value: {s.get('sharpe_ratio')}")
    print(f"  total_firings: {s.get('total_firings')}")
    
    # Show what T+20 values should be:
    hr = s.get("hit_rate", {})
    ar = s.get("avg_return", {})
    if isinstance(hr, dict):
        print(f"\n  T+20 win_rate: {hr.get('20', hr.get(20, 'N/A'))}")
    if isinstance(ar, dict):
        print(f"  T+20 avg_return: {ar.get('20', ar.get(20, 'N/A'))}")
