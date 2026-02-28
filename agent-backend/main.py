from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph import app_graph, sanitize_data

app = FastAPI(title="365 Advisers API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    ticker: str

@app.get("/")
def read_root():
    return {"message": "365 Advisers API is running"}

@app.post("/analyze")
async def analyze_stock(request: AnalysisRequest):
    try:
        print(f"Starting analysis for ticker: {request.ticker}")
        # Initialize state
        initial_state = {
            "ticker": request.ticker,
            "financial_data": {},
            "macro_data": {},
            "agent_responses": [],
            "final_verdict": ""
        }
        
        # Run graph
        result = await app_graph.ainvoke(initial_state)
        print(f"Analysis completed for {request.ticker}")
        
        return sanitize_data({
            "ticker": result.get("ticker", request.ticker),
            "agent_responses": result.get("agent_responses", []),
            "final_verdict": result.get("final_verdict", "No final verdict generated."),
            "chart_data": result.get("chart_data", {"prices": [], "cashflow": []})
        })
    except Exception as e:
        print(f"CRITICAL ERROR in /analyze for {request.ticker}: {str(e)}")
        import traceback
        traceback.print_exc()
        return sanitize_data({
            "ticker": request.ticker,
            "agent_responses": [],
            "final_verdict": f"Error during analysis: {str(e)}",
            "chart_data": {"prices": [], "cashflow": []}
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
