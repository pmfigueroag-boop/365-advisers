import httpx, json

r = httpx.get("http://localhost:8000/signals/AAPL", timeout=120)
d = r.json()

with open("aapl_alpha_signals.json", "w") as f:
    json.dump(d, f, indent=2)

signals = [s for s in d["signals"] if s["fired"]]
lines = []
lines.append(f"FIRED: {len(signals)}/{d['total_signals']}")
lines.append("")

for s in sorted(signals, key=lambda x: x["category"]):
    lines.append(f"  [{s['category']:10}] {s['signal_name']}")
    lines.append(f"              val={s['value']:.4f}  thr={s['threshold']:.4f}  str={s['strength']:8}  conf={s['confidence']:.2f}")
    lines.append(f"              {s['description'][:90]}")
    lines.append("")

lines.append("CATEGORY SUMMARY:")
for k, v in d["category_summary"].items():
    if v["fired"] > 0:
        lines.append(f"  {k:12} fired={v['fired']}/{v['total']}  strength={v['composite_strength']:.2f}  conf={v['confidence']}")

ca = d.get("composite_alpha", {})
lines.append(f"\nCASE Score: {ca.get('score', 'N/A')}")
lines.append(f"Environment: {ca.get('environment', 'N/A')}")

output = "\n".join(lines)
print(output)
with open("aapl_alpha_result.txt", "w") as f:
    f.write(output)
