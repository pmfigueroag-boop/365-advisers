import asyncio
import json
from src.orchestration.analysis_pipeline import AnalysisPipeline
from src.services.cache_manager import cache_manager

async def main():
    try:
        pipeline = AnalysisPipeline(
            cache_manager.fundamental,
            cache_manager.technical,
            cache_manager.decision
        )
        print("Starting stream...")
        async for event in pipeline.run_combined_stream("AAPL", force=True):
            if isinstance(event, dict):
                evt_type = event.get("event")
                if evt_type in ["opportunity_score", "technical_ready", "dalio_verdict"]:
                    print(f"---{evt_type.upper()}---")
                    print(json.dumps(event.get("data", {}), indent=2))
        print("Done.")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
