import sys
import os
import uvicorn

if __name__ == "__main__":
    # Add the current directory (project root) to sys.path
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    print(f"Starting server from root: {root_dir}")
    print("Backend accessible at http://127.0.0.1:8000")
    
    try:
        # Run Uvicorn programmatically
        # Binding to 127.0.0.1 is often more reliable for local development on Windows
        uvicorn.run("TRUTH_Xx.backend.app:app", host="127.0.0.1", port=8000, reload=True)
    except Exception as e:
        print(f"Failed to start server: {e}")
        input("Press Enter to exit...")
