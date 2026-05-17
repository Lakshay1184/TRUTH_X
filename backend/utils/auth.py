import base64
import json
from typing import Optional

def extract_user_id_from_token(token: Optional[str]) -> Optional[str]:
    """Extract user_id (sub) from Supabase JWT token without verification."""
    if not token:
        return None
    
    try:
        # Handle Bearer prefix
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        payload_b64 = parts[1]
        # Add base64 padding
        missing_padding = len(payload_b64) % 4
        if missing_padding:
            payload_b64 += '=' * (4 - missing_padding)
            
        payload_json = base64.b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        
        return payload.get("sub")
    except Exception:
        return None
