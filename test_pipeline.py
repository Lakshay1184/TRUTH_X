import asyncio
import os
from dotenv import load_dotenv

from backend.pipelines.main_pipeline import DeepfakeDetectionPipeline

load_dotenv("backend/.env")

def test_pipeline():
    print("Testing ML Pipeline End-to-End...")
    pipeline = DeepfakeDetectionPipeline()
    
    # 1. Test Text Analysis + News Verification + Explainability
    print("\n--- Testing Text Modality ---")
    text_query = "The moon landing was faked using advanced holograms in a Hollywood studio."
    def progress_cb(msg):
        print(f"[Status] {msg}")
        
    result = pipeline.process(query=text_query, status_callback=progress_cb)
    
    print("\n--- Pipeline Result ---")
    print(f"Overall Label: {result.get('overall_label')}")
    print(f"Confidence: {result.get('combined_confidence')}")
    
    # Check if intelligence report is there
    if 'explainability' in result:
        print(f"Intelligence Report: {result['explainability'].get('intelligence_report')[:100]}...")
    
    if 'credibility' in result and 'provenance' in result['credibility']:
        print(f"Provenance: {result['credibility']['provenance']}")

if __name__ == "__main__":
    test_pipeline()
