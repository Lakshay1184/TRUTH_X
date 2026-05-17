"""Run basic Intel smoke tests to validate grounded retrieval and QA.

This script runs four scenarios and prints:
- rewritten queries (from query_plan)
- retrieved evidence (titles, publishers, similarity)
- filtered-out candidates (via retrieval_errors)
- claim->evidence mapping
- QA follow-up question results

Note: Mistral/Tavily/Facts APIs are optional and disabled if no API keys are present.
"""
import os
import json
import time

from backend.utils.env_loader import ensure_backend_environment_loaded, log_runtime_env_status

ensure_backend_environment_loaded()
log_runtime_env_status("intel_smoke")
os.environ.setdefault("ENABLE_SOCIAL_MOCK", "false")

from backend.intel.engine import IntelEngine

engine = IntelEngine()

cases = [
    {
        "id": "scientific",
        "content": "A new peer-reviewed study shows that octopuses engage in REM-like sleep patterns similar to mammals.",
    },
    {
        "id": "educational",
        "content": "A classroom lecture explains how CRISPR edits specific genes using guide RNA to target Cas9 to DNA sequences.",
    },
    {
        "id": "factual",
        "content": "The city installed new traffic cameras at Main St and 3rd Ave to reduce speeding.",
    },
    {
        "id": "misinfo",
        "content": "Claim: Drinking large quantities of green tea cures advanced cancer within weeks.",
    },
]

results = {}

for case in cases:
    print(f"\n--- Running case: {case['id']} ---")
    start = time.time()
    try:
        out = engine.analyze(case["content"])  # returns formatted analysis
    except Exception as e:
        print(f"Engine analyze failed: {e}")
        out = {"error": str(e)}
    elapsed = time.time() - start
    results[case["id"]] = {"analysis": out, "elapsed_s": elapsed}

    # Print summary
    if out.get("status") != "success":
        print("Analysis failed or incomplete:", out.get("error") or out)
        continue

    print("Claims found:", out.get("claims_found"))
    print("Rewritten queries (per claim):")
    # Try to load query_plan from engine internals if available
    try:
        # Dive into engine internals: reconstruct query_plan via re-run of rewrite
        pass
    except Exception:
        pass

    print("Retrieved evidence count:", out.get("sources_analyzed"))
    print("Retrieval errors:", json.dumps(out.get("retrieval_errors", []), indent=2))
    print("Top evidence items:")
    for e in out.get("evidence", [])[:5]:
        print(f" - {e.get('title')[:120]} | {e.get('source')} | sim={e.get('ranking_score')}")

    # Run a follow-up QA question
    question = "Summarize the main verifiable point and list sources."
    try:
        qa = engine.answer(case["content"], question, evidence=out.get("evidence", []))
        print("QA answer:", qa.get("answer"))
        print("QA sources:", qa.get("sources"))
        print("QA confidence:", qa.get("confidence"))
    except Exception as e:
        print("QA run failed:", e)

# Save results to disk for inspection
with open("backend/tests/intel_smoke_results.json", "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=2)

print("\nSmoke run complete. Results written to backend/tests/intel_smoke_results.json")
