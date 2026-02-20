
import sys
import os
import json
# Add parent directory to sys.path to import main_pipeline
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
# Also add the top-level directory where main_pipeline usually runs from
sys.path.append(os.path.abspath("d:/truth.x"))

try:
    from main_pipeline import extract_video_metadata, _find_ffprobe, _find_ffmpeg
except ImportError:
    # Try importing with the path adjustment
    sys.path.append("d:/truth.x")
    from main_pipeline import extract_video_metadata, _find_ffprobe, _find_ffmpeg

def test_extraction():
    video_path = "d:/truth.x/data/samples/yes1.mp4"
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return

    print(f"Testing metadata extraction on: {video_path}")
    
    # Check what tools we found
    print(f"FFprobe path: {_find_ffprobe()}")
    print(f"FFmpeg path: {_find_ffmpeg()}")

    try:
        metadata = extract_video_metadata(video_path, _find_ffprobe())
        print(json.dumps(metadata, indent=2, default=str))
    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()
