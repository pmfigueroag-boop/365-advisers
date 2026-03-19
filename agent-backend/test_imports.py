"""Quick import verification for Phase 2 Alpha modules."""
import traceback
import sys

def test_import(module_path, names):
    try:
        mod = __import__(module_path, fromlist=names)
        for name in names:
            getattr(mod, name)
        print(f"  OK: {module_path}")
        return True
    except Exception:
        print(f"  FAIL: {module_path}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Phase 2 Module Import Verification ===\n")
    
    results = []
    
    print("[1] ML Signal Factory")
    results.append(test_import("src.engines.ml_signals.models",
        ["ModelType", "ModelStatus", "SignalDirection", "MLModelConfig", "MLSignalOutput", "ModelCard"]))
    results.append(test_import("src.engines.ml_signals.feature_engineering", ["build_feature_vector", "normalise_features"]))
    results.append(test_import("src.engines.ml_signals.trainer", ["MLTrainer"]))
    results.append(test_import("src.engines.ml_signals.predictor", ["MLPredictor"]))
    results.append(test_import("src.engines.ml_signals.model_registry", ["ModelRegistry"]))
    results.append(test_import("src.engines.ml_signals.engine", ["MLSignalFactory"]))
    
    print("\n[2] Valuation Engine")
    results.append(test_import("src.engines.valuation.models",
        ["DCFInput", "DCFResult", "ComparableInput", "ComparableResult", "MarginOfSafety", "ValuationReport"]))
    results.append(test_import("src.engines.valuation.dcf", ["DCFModel"]))
    results.append(test_import("src.engines.valuation.comparable", ["ComparableAnalysis"]))
    results.append(test_import("src.engines.valuation.margin_of_safety", ["MarginCalculator"]))
    results.append(test_import("src.engines.valuation.engine", ["ValuationEngine"]))
    
    print(f"\n=== Results: {sum(results)}/{len(results)} passed ===")
    sys.exit(0 if all(results) else 1)
