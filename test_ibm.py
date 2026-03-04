import httpx
import json
import codecs

def test_ibm():
    url = "http://localhost:8000/analysis/combined/stream?ticker=IBM&force=true"
    with codecs.open(r"c:\Users\pmfig\.gemini\antigravity\scratch\365-advisers\ibm_result.txt", "w", encoding="utf-8") as f:
        try:
            with httpx.stream("GET", url, timeout=120) as r:
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            if "investment_position" in data:
                                f.write("\n" + "="*50 + "\n")
                                f.write("🎯 DECISION READY EVENT\n")
                                f.write("="*50 + "\n")
                                f.write(f"Investment Position: {data.get('investment_position')}\n")
                                f.write(f"Confidence Score:    {data.get('confidence_score') * 100:.0f}%\n")
                                memo = data.get("cio_memo", {})
                                f.write("\n--- CIO Memo ---\n")
                                f.write(f"Thesis Summary:\n{memo.get('thesis_summary')}\n\n")
                                f.write(f"Valuation View:\n{memo.get('valuation_view')}\n\n")
                                f.write(f"Technical Context:\n{memo.get('technical_context')}\n\n")
                                f.write("Key Catalysts:\n")
                                for c in memo.get("key_catalysts", []):
                                    f.write(f"  - {c}\n")
                                f.write("\nKey Risks:\n")
                                for r in memo.get("key_risks", []):
                                    f.write(f"  - {r}\n")
                                f.write("="*50 + "\n")
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            f.write(f"Error: {e}\n")

if __name__ == "__main__":
    test_ibm()
