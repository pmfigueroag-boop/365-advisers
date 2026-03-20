import requests

r = requests.get("http://localhost:8000/signals/AAPL")
d = r.json()

signals = d.get("signals", [])
fired = [s for s in signals if s.get("fired")]

lines = []
lines.append(f"Total: {len(signals)}, Fired: {len(fired)}")
lines.append("")
lines.append("=== FIRED SIGNALS ===")
for s in fired:
    lines.append(f"  [{s['category']:12}] {s['signal_name']:35} v={s.get('value')}")

lines.append("")
lines.append("=== QUALITY SIGNALS ===")
for s in signals:
    if s.get("category") == "quality":
        st = "FIRE" if s["fired"] else "----"
        lines.append(f"  {st} {s['signal_name']:35} v={s.get('value', 'N/A')} thr={s.get('threshold')}")

lines.append("")
lines.append("=== VALUE SIGNALS ===")
for s in signals:
    if s.get("category") == "value":
        st = "FIRE" if s["fired"] else "----"
        lines.append(f"  {st} {s['signal_name']:35} v={s.get('value', 'N/A')} thr={s.get('threshold')}")

lines.append("")
lines.append("=== GROWTH SIGNALS ===")
for s in signals:
    if s.get("category") == "growth":
        st = "FIRE" if s["fired"] else "----"
        lines.append(f"  {st} {s['signal_name']:35} v={s.get('value', 'N/A')} thr={s.get('threshold')}")

with open("thesis_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Done - see thesis_result.txt")
