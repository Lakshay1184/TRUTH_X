"""truth.x — Async Job Manager for background ML tasks.

Extracted from api.py for cleaner separation of concerns.
Handles job lifecycle: creation, status tracking, cleanup.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional

from backend.utils.logger import logger

# Maximum number of completed jobs to retain before cleanup
_MAX_COMPLETED_JOBS = 100
_JOB_TTL_SECONDS = 3600  # 1 hour
_ACTIVE_JOB_TIMEOUT_SECONDS = 30 * 60


class JobManager:
    """Thread-safe job queue for managing background analysis tasks."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        logger.info("JobManager initialized")

    def create_job(self) -> str:
        """Create a new pending job and return its ID."""
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "status": "pending",
                "status_message": "Queued",
                "result": None,
                "error": None,
                "created_at": time.time(),
                "updated_at": time.time(),
                "completed_at": None,
                "progress": 0,
            }
        logger.info("Job created: %s", job_id)
        self._cleanup_stale_jobs()
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and result."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if (
                job["status"] in ("pending", "running")
                and (time.time() - job.get("created_at", time.time())) > _ACTIVE_JOB_TIMEOUT_SECONDS
            ):
                job["status"] = "failed"
                job["error"] = "Analysis exceeded the backend job timeout."
                job["completed_at"] = time.time()
                job["updated_at"] = time.time()
                job["status_message"] = "Analysis timed out"
                logger.error("Job timed out: %s", job_id)
            return dict(job)

    def update_progress(self, job_id: str, progress: int, message: str = "Processing...") -> None:
        """Update job progress (0-100)."""
        with self._lock:
            if job_id in self._jobs:
                if self._jobs[job_id]["status"] in ("pending", "processing"):
                    self._jobs[job_id]["status"] = "running"
                self._jobs[job_id]["status_message"] = message
                self._jobs[job_id]["progress"] = min(100, max(0, progress))
                self._jobs[job_id]["updated_at"] = time.time()

    def complete_job(self, job_id: str, result: Dict[str, Any]) -> None:
        """Mark a job as complete with its result."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "complete"
                self._jobs[job_id]["status_message"] = "Analysis complete"
                self._jobs[job_id]["result"] = result
                self._jobs[job_id]["completed_at"] = time.time()
                self._jobs[job_id]["updated_at"] = time.time()
                self._jobs[job_id]["progress"] = 100
        logger.info("Job completed: %s", job_id)

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed with an error message."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["status_message"] = "Analysis failed"
                self._jobs[job_id]["error"] = error
                self._jobs[job_id]["completed_at"] = time.time()
                self._jobs[job_id]["updated_at"] = time.time()
        logger.error("Job failed: %s — %s", job_id, error)

    def _cleanup_stale_jobs(self) -> None:
        """Remove old completed/failed jobs to prevent memory leaks."""
        now = time.time()
        with self._lock:
            stale = [
                jid for jid, j in self._jobs.items()
                if j["status"] in ("complete", "error", "failed", "cancelled")
                and j.get("completed_at")
                and (now - j["completed_at"]) > _JOB_TTL_SECONDS
            ]
            for jid in stale:
                del self._jobs[jid]

            # Hard cap
            completed = [
                (jid, j) for jid, j in self._jobs.items()
                if j["status"] in ("complete", "error", "failed", "cancelled")
            ]
            if len(completed) > _MAX_COMPLETED_JOBS:
                completed.sort(key=lambda x: x[1].get("completed_at", 0))
                for jid, _ in completed[:len(completed) - _MAX_COMPLETED_JOBS]:
                    del self._jobs[jid]

        if stale:
            logger.info("Cleaned up %d stale jobs", len(stale))

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j["status"] in ("pending", "running", "processing"))

    @property
    def total_count(self) -> int:
        with self._lock:
            return len(self._jobs)
