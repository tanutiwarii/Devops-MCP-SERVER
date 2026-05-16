from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"

@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    kind: str
    created_at: str
    updated_at: str
    detail: str | None = None
    result: dict[str, Any] | None = None
    request_summary: dict[str, Any] = field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._jobs: dict[str, JobRecord] = {}

    async def create(self, kind: str, request_summary: dict[str, Any]) -> JobRecord:
        job_id = str(uuid.uuid4())
        now = _now_iso()
        rec = JobRecord(
            job_id=job_id,
            status=JobStatus.queued,
            kind=kind,
            created_at=now,
            updated_at=now,
            request_summary=request_summary,
        )
        async with self._lock:
            self._jobs[job_id] = rec
        return rec

    async def set_running(self, job_id: str) -> None:
        async with self._lock:
            rec = self._jobs[job_id]
            rec.status = JobStatus.running
            rec.updated_at = _now_iso()

    async def succeed(self, job_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            rec = self._jobs[job_id]
            rec.status = JobStatus.succeeded
            rec.result = result
            rec.updated_at = _now_iso()

    async def fail(self, job_id: str, detail: str) -> None:
        async with self._lock:
            rec = self._jobs[job_id]
            rec.status = JobStatus.failed
            rec.detail = detail
            rec.updated_at = _now_iso()

    async def get(self, job_id: str) -> JobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)


JOBS = JobStore()
