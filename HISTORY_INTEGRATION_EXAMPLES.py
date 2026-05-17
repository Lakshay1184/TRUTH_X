"""
Example: Integrating History Saving into Intel Analysis Engine

This shows how to add automatic history saving to your analysis pipelines.
Copy this pattern for other analysis types (video, image, text, AI detection, etc.)

Integration points:
1. Import history helpers at top of file
2. Track processing time
3. After analysis completes, call the auto-save function
4. Pass user_id from authentication context
"""

# ============================================================================
# EXAMPLE 1: Intel Engine Integration
# ============================================================================

import time
from typing import Optional

# At the top of backend/intel/engine.py, add these imports:
from backend.services.history_helpers import save_intel_analysis_history


class IntelEngine:
    """
    Main analysis orchestration engine.
    Now with automatic history saving.
    """

    def __init__(self):
        # ... existing initialization code ...
        pass

    async def analyze(
        self,
        content: str,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Analyze content for fact-checking and verification.
        
        UPDATED: Now auto-saves history if user_id provided.
        
        Args:
            content: Text content to analyze
            user_id: Authenticated user UUID (for history saving)
        
        Returns:
            Analysis result dict with verdict, evidence, sources, etc.
        """
        start_time = time.time()  # Track processing time
        
        try:
            # ... existing analysis pipeline code ...
            result = {
                "verdict": {"label": "Supported", "confidence": 95},
                "evidence": [{"title": "...", "source": "..."}],
                "sources_analyzed": 25,
                "claims_found": 3,
                "pipeline_stage": "complete",
                "summary": "Analysis complete...",
            }
            # ... rest of existing code ...
            
            # AFTER analysis completes, auto-save to history
            if user_id:
                end_time = time.time()
                processing_time_ms = int((end_time - start_time) * 1000)
                
                success = await save_intel_analysis_history(
                    user_id=user_id,
                    input_content=content,
                    analysis_result=result,
                    processing_time_ms=processing_time_ms,
                )
                
                if success:
                    print(f"✅ History saved for user {user_id}")
                else:
                    print(f"⚠️ Failed to save history for user {user_id}")
            
            return result
        
        except Exception as e:
            print(f"Error in analysis: {e}")
            raise


# ============================================================================
# EXAMPLE 2: FastAPI Endpoint Integration
# ============================================================================

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional

router = APIRouter(prefix="/api/analyze", tags=["analysis"])


def get_current_user_id(request: Request) -> Optional[str]:
    """
    Extract user ID from JWT token or authentication header.
    
    Implement based on your auth system.
    """
    # Example: extract from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Decode JWT and extract user_id
        # return decoded_user_id
        pass
    return None


@router.post("/intel")
async def analyze_intel(
    content: str,
    request: Request,
):
    """
    Analyze content using Intel engine.
    
    Automatically saves history for authenticated users.
    """
    user_id = get_current_user_id(request)
    
    engine = IntelEngine()
    result = await engine.analyze(
        content=content,
        user_id=user_id,  # Pass user_id for auto-history saving
    )
    
    return {
        "success": True,
        "result": result,
        "saved_to_history": user_id is not None,
    }


# ============================================================================
# EXAMPLE 3: Video Analysis Integration
# ============================================================================

from backend.services.history_helpers import save_video_analysis_history


async def analyze_video(video_file_path: str, user_id: Optional[str] = None):
    """
    Analyze video for deepfakes, manipulation, etc.
    """
    start_time = time.time()
    
    try:
        # Your video analysis pipeline
        result = {
            "classification": "Authentic",
            "confidence": 92,
            "duration": 125,
            "frames_analyzed": 250,
            "model": "LSTM-3D-CNN v2",
        }
        
        # AUTO-SAVE HISTORY
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_video_analysis_history(
                user_id=user_id,
                video_filename=video_file_path.split("/")[-1],
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    
    except Exception as e:
        print(f"Error in video analysis: {e}")
        raise


# ============================================================================
# EXAMPLE 4: Image Analysis Integration
# ============================================================================

from backend.services.history_helpers import save_image_analysis_history


async def analyze_image(image_file_path: str, user_id: Optional[str] = None):
    """
    Analyze image for manipulations, deepfakes, etc.
    """
    start_time = time.time()
    
    try:
        # Your image analysis pipeline
        result = {
            "classification": "Authentic",
            "confidence": 87,
            "resolution": "1920x1080",
            "manipulations": [],
            "model": "ResNet-101 + ManipDetect",
        }
        
        # AUTO-SAVE HISTORY
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_image_analysis_history(
                user_id=user_id,
                image_filename=image_file_path.split("/")[-1],
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    
    except Exception as e:
        print(f"Error in image analysis: {e}")
        raise


# ============================================================================
# EXAMPLE 5: Text Analysis Integration
# ============================================================================

from backend.services.history_helpers import save_text_analysis_history


async def analyze_text(text_content: str, user_id: Optional[str] = None):
    """
    Analyze text for AI generation, misinformation, etc.
    """
    start_time = time.time()
    
    try:
        # Your text analysis pipeline
        result = {
            "classification": "Human-Written",
            "confidence": 94,
            "sentences_analyzed": 15,
            "model": "RoBERTa-AI-Detector v3",
        }
        
        # AUTO-SAVE HISTORY
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_text_analysis_history(
                user_id=user_id,
                text_content=text_content,
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    
    except Exception as e:
        print(f"Error in text analysis: {e}")
        raise


# ============================================================================
# EXAMPLE 6: AI Detection Integration
# ============================================================================

from backend.services.history_helpers import save_ai_detection_history


async def detect_ai(content_file_path: str, user_id: Optional[str] = None):
    """
    Detect if content is AI-generated.
    """
    start_time = time.time()
    
    try:
        # Your AI detection pipeline
        result = {
            "ai_detection_label": "Human-Generated",
            "ai_score": 8,  # 0-100, lower = more human
            "type": "text",
            "model": "GPT-2 Detector",
            "artifacts_found": [],
        }
        
        # AUTO-SAVE HISTORY
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_ai_detection_history(
                user_id=user_id,
                content_filename=content_file_path.split("/")[-1],
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    
    except Exception as e:
        print(f"Error in AI detection: {e}")
        raise


# ============================================================================
# EXAMPLE 7: Fake News Check Integration
# ============================================================================

from backend.services.history_helpers import save_fake_news_check_history


async def check_fake_news(article_text: str, user_id: Optional[str] = None):
    """
    Check if article contains misinformation.
    """
    start_time = time.time()
    
    try:
        # Your fake news detection pipeline
        result = {
            "misinformation_label": "Fact-Checked",
            "misinformation_confidence": 89,
            "fact_checks": 5,
            "source_credibility": 7.8,
            "analysis_summary": "Article references credible sources...",
        }
        
        # AUTO-SAVE HISTORY
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_fake_news_check_history(
                user_id=user_id,
                article_title=article_text[:50],
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    
    except Exception as e:
        print(f"Error in fake news check: {e}")
        raise


# ============================================================================
# EXAMPLE 8: URL Verification Integration
# ============================================================================

from backend.services.history_helpers import save_url_verification_history


async def verify_url(url: str, user_id: Optional[str] = None):
    """
    Verify if URL is safe/malicious/phishing.
    """
    start_time = time.time()
    
    try:
        # Your URL safety pipeline
        result = {
            "url_verdict": "Safe",
            "safety_score": 98,  # 0-100, higher = safer
            "domain": "github.com",
            "phishing_detected": False,
            "malware_detected": False,
        }
        
        # AUTO-SAVE HISTORY
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_url_verification_history(
                user_id=user_id,
                url=url,
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    
    except Exception as e:
        print(f"Error in URL verification: {e}")
        raise


# ============================================================================
# INTEGRATION CHECKLIST
# ============================================================================

"""
To integrate history saving into your pipelines:

✅ Step 1: Import the appropriate history helper
   from backend.services.history_helpers import save_*_history

✅ Step 2: Track processing time
   start_time = time.time()
   # ... analysis code ...
   end_time = time.time()
   processing_time_ms = int((end_time - start_time) * 1000)

✅ Step 3: Call auto-save after analysis completes
   if user_id:
       await save_*_history(
           user_id=user_id,
           ... other parameters ...
           processing_time_ms=processing_time_ms,
       )

✅ Step 4: Update API endpoints to accept and pass user_id
   @router.post("/analyze")
   async def analyze(content: str, request: Request):
       user_id = extract_user_id_from_request(request)
       result = await analyze_pipeline(content, user_id)
       return result

✅ Step 5: Frontend: Extract user_id from auth context
   const { user } = useAuth();
   const response = await fetch("/api/analyze", {
       body: JSON.stringify({
           content: data,
           user_id: user.id,
       })
   });

✅ Step 6: Test
   - Sign in as user
   - Run analysis
   - Check /history page
   - Should see new entry with correct metadata

✅ Step 7: Monitor
   - Check backend logs for "History saved" messages
   - Check Supabase for new entries in analysis_history table
   - Verify RLS policies working (users only see own data)
"""

# ============================================================================
# QUICK COPY-PASTE TEMPLATE
# ============================================================================

"""
Here's the minimal template to add history saving to any analysis:

---

from backend.services.history_helpers import save_*_analysis_history

async def your_analysis_function(input_data, user_id=None):
    start_time = time.time()
    
    try:
        # Your analysis code here
        result = {
            "verdict": "...",
            "score": 0,
            # ... other fields ...
        }
        
        # Auto-save history
        if user_id:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            await save_*_analysis_history(
                user_id=user_id,
                # ... parameters ...
                analysis_result=result,
                processing_time_ms=processing_time_ms,
            )
        
        return result
    except Exception as e:
        raise

---
"""
