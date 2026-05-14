"""Quick HF token validation test."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv("backend/.env")

from backend.services.hf_inference import run_hf_inference

print("Testing HF API with new token...")
result = run_hf_inference(
    "facebook/bart-large-mnli",
    {
        "inputs": "Scientists say vaccines are safe and effective.",
        "parameters": {
            "candidate_labels": ["health", "politics", "science"],
        },
    },
)

if result:
    print("HF API SUCCESS!")
    import json
    print(json.dumps(result, indent=2))
else:
    print("HF API returned None (token may be invalid or model loading)")
