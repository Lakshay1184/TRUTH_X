"""truth.x — Celery Worker App.

Handles asynchronous, long-running tasks for social media intelligence,
network graph scraping, and intensive background inference jobs.
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Use Redis if available, otherwise fallback to filesystem for Windows local testing
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Setup filesystem broker fallback
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
broker_dir = os.path.join(project_root, "celery_broker")
os.makedirs(os.path.join(broker_dir, "out"), exist_ok=True)
os.makedirs(os.path.join(broker_dir, "processed"), exist_ok=True)

try:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    s.connect(("localhost", 6379))
    s.close()
    broker_url = REDIS_URL
    transport_options = {}
    logger_msg = "Celery using Redis broker"
except (ConnectionRefusedError, TimeoutError, socket.timeout, OSError):
    broker_url = "filesystem://"
    transport_options = {
        "data_folder_in": os.path.join(broker_dir, "out"),
        "data_folder_out": os.path.join(broker_dir, "out"),
        "data_folder_processed": os.path.join(broker_dir, "processed")
    }
    logger_msg = "Celery using Filesystem broker (Redis not found)"

print(logger_msg)

celery_app = Celery(
    "truth_x_workers",
    broker=broker_url,
    include=["backend.workers.social_scanner"]
)

celery_app.conf.update(
    broker_transport_options=transport_options,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "backend.workers.social_scanner.*": {"queue": "social_queue"},
    },
)

if __name__ == "__main__":
    celery_app.start()
