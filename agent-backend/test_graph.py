from graph import app_graph
import asyncio
import json

async def test_graph(symbol):
    print(f"--- Testing LangGraph for {symbol} ---")
    initial_state = {
        "ticker": symbol,
        "financial_data": {},
        "macro_data": {},
        "chart_data": {"prices": [], "cashflow": []},
        "agent_responses": [],
        "final_verdict": "",
        "dalio_response": {}
    }
    try:
        result = await app_graph.ainvoke(initial_state)
        print("SUCCESS: Graph execution completed")
        print(f"Final Verdict: {result.get('final_verdict')[:100]}...")
        
        # Inspection
        print("\n--- STATE INSPECTION ---")
        fd = result.get('financial_data', {})
        print(f"Has tech_indicators: {'tech_indicators' in fd}")
        if 'tech_indicators' in fd:
            print(f"Sample Tech (RSI): {fd['tech_indicators'].get('rsi')}")
            print(f"Sample Tech (Price): {fd['tech_indicators'].get('current_price')}")
        
        print(f"Has fundamental_engine: {'fundamental_engine' in fd}")
        if 'fundamental_engine' in fd:
            fe = fd['fundamental_engine']
            print(f"Profitability Keys: {list(fe.get('profitability', {}).keys())}")
        
        ars = result.get('agent_responses', [])
        print(f"Number of Agent Responses: {len(ars)}")
        for agent in ars:
            print(f"  - {agent.get('agent_name')}: {agent.get('signal')} (Conf: {agent.get('confidence')})")
            
    except Exception as e:
        print(f"FAILED: Graph execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_graph("MSFT"))
