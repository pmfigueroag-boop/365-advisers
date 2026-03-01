from graph import app_graph
import asyncio
import sys

async def test_graph(symbol):
    initial_state = {
        "ticker": symbol,
        "financial_data": {},
        "macro_data": {},
        "chart_data": {"prices": [], "cashflow": []},
        "agent_responses": [],
        "final_verdict": "",
        "dalio_response": {}
    }
    await app_graph.ainvoke(initial_state)

if __name__ == "__main__":
    import os
    # Redirect stdout to a file
    with open("full_graph_debug.log", "w", encoding='utf-8') as f:
        sys.stdout = f
        asyncio.run(test_graph("MSFT"))
    sys.stdout = sys.__stdout__
    print("LOG_GENERATED")
