import asyncio
import os
import pandas as pd
from graph import app_graph

async def debug_analysis():
    print("Starting debug analysis for TSLA...")
    initial_state = {
        "ticker": "TSLA",
        "financial_data": {},
        "chart_data": {},
        "agent_responses": [],
        "final_verdict": ""
    }
    try:
        result = await app_graph.ainvoke(initial_state)
        print("Success!")
        print(f"Final Verdict: {result.get('final_verdict')}")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_analysis())
