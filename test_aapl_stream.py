import asyncio, httpx, json

async def main():
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream('GET', 'http://localhost:8000/analysis/fundamental/stream?ticker=AAPL') as r:
            async for line in r.aiter_lines():
                if line.startswith('data:'):
                    try:
                        data = json.loads(line[5:])
                        if 'score' in data and 'confidence' in data:
                            with open('committee_aapl.json', 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2)
                    except: pass
    print("Done")

if __name__ == '__main__':
    asyncio.run(main())
