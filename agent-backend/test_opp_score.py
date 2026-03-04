import asyncio
import json
import httpx

async def test_stream():
    """Test the combined analysis stream for the new Opportunity Score"""
    url = "http://localhost:8000/analysis/combined/stream?ticker=AAPL&force=true"
    
    print(f"Testing SSE stream for AAPL: {url}")
    print("-" * 50)
    
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("GET", url) as response:
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                    
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    print(f"\n[EVENT] {current_event}")
                elif line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str:
                        try:
                            data = json.loads(data_str)
                            if current_event in ["opportunity_score", "decision_ready", "error"]:
                                print(json.dumps(data, indent=2, ensure_ascii=False))
                            else:
                                print(f"  ... received payload for {current_event}")
                        except json.JSONDecodeError:
                            print(f"  Raw data: {data_str[:100]}...")

if __name__ == "__main__":
    asyncio.run(test_stream())
