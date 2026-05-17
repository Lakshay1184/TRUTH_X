"""truth.x — Pipeline audit helpers.

Provides a lightweight trace collector for observability across the
Intel verification pipeline.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional


class PipelineAuditTrail:
    """Collects stage timings, statuses, and failure reasons."""

    def __init__(self, trace_id: Optional[str] = None) -> None:
        self.trace_id = trace_id or f"intel-{int(time.time() * 1000)}"
        self._started_at = time.perf_counter()
        self._stages: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []

    def log_event(self, stage: str, message: str, **details: Any) -> None:
        self._events.append({
            "stage": stage,
            "message": message,
            "details": details,
            "timestamp": time.time(),
        })

    @contextmanager
    def stage(self, name: str) -> Iterator[Dict[str, Any]]:
        record: Dict[str, Any] = {
            "stage": name,
            "status": "running",
            "started_at": time.time(),
        }
        self._stages.append(record)
        start = time.perf_counter()
        try:
            yield record
            record["status"] = "success"
        except Exception as exc:
            record["status"] = "failed"
            record["failure_reason"] = str(exc)
            raise
        finally:
            record["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
            record["finished_at"] = time.time()

    def update_stage(self, name: str, **updates: Any) -> None:
        for record in reversed(self._stages):
            if record.get("stage") == name:
                record.update(updates)
                return

    def record_failure(self, stage: str, reason: str, **details: Any) -> None:
        self._events.append({
            "stage": stage,
            "message": reason,
            "details": details,
            "level": "error",
            "timestamp": time.time(),
        })
        self.update_stage(stage, status="failed", failure_reason=reason, details=details)

    def finish(self, status: str = "success") -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": status,
            "duration_ms": round((time.perf_counter() - self._started_at) * 1000, 2),
            "stages": self._stages,
            "events": self._events,
        }
