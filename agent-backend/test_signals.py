import urllib.request
import json

r = urllib.request.urlopen("http://localhost:8000/signals/MSFT")
p = json.loads(r.read())
print(f"MSFT: {p['fired_signals']}/{p['total_signals']}")
print(f"  Composite: {p['composite']['overall_strength']}")
print(f"  Dominant: {p['composite']['dominant_category']}")
print(f"  Active: {p['composite']['active_categories']}")
for cat, sc in sorted(p.get("category_summary", {}).items()):
    if sc["fired"] > 0:
        print(f"    {cat}: {sc['fired']}/{sc['total']} (str: {sc['composite_strength']:.2f})")
