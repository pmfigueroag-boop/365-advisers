import requests

r = requests.post("http://localhost:8000/backtest/run", json={
    "universe": ["AAPL"],
    "start_date": "2024-03-19",
})
d = r.json()
rid = d["run_id"]
print(f"POST: {d['status']} - {d['message']}")

r2 = requests.get(f"http://localhost:8000/backtest/runs/{rid}")
d2 = r2.json()
sr = d2.get("signal_results", [])
print(f"GET: {len(sr)} signals\n")

for s in sr[:5]:
    print(f"{s.get('signal_name', '?')}")
    print(f"  N={s.get('total_firings')} WR={s.get('win_rate'):.1f}%")
    print(f"  avg_return_flat={s.get('avg_return_flat')}")
    print(f"  sharpe_flat={s.get('sharpe_ratio_flat')}")
    print(f"  PF={s.get('profit_factor')}")
    print()
