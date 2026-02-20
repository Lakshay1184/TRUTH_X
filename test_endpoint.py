
import requests
import os
import sys

def test_endpoint():
    url = "http://127.0.0.1:8000/extract-metadata"
    video_path = "d:/truth.x/data/samples/yes1.mp4"
    
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return

    print(f"Sending request to {url} with {video_path}...")
    try:
        with open(video_path, "rb") as f:
            files = {"file": (os.path.basename(video_path), f, "video/mp4")}
            response = requests.post(url, files=files)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response JSON:")
            import json
            print(json.dumps(response.json(), indent=2))
        else:
            print("Error Response:")
            print(response.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Ensure requests is installed
    try:
        import requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
        
    test_endpoint()
