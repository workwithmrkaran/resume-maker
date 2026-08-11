"""Compile job queue.

Compilation takes seconds and burns CPU, so it must not run inline in the
request handler. This is a small in-process queue with a fixed pool of worker
threads — enough for MVP volumes, and deliberately shaped like a task queue
(submit → poll status → fetch result) so moving to Celery/RQ later is a
swap of this module rather than a redesign of the API.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, Optional

from .compile import CompileError, compile_pdf
from .schema import Resume
from .storage import store
from .templates_registry import render_resume

log = logging.getLogger(__name__)

MAX_WORKERS = int(os.getenv("COMPILE_WORKERS", "2"))
MAX_QUEUE_DEPTH = int(os.getenv("COMPILE_QUEUE_DEPTH", "50"))
JOB_RETENTION_SECONDS = int(os.getenv("JOB_RETENTION_SECONDS", "3600"))

QUEUED, RUNNING, DONE, ERROR = "queued", "running", "done", "error"

# User-facing copy. Raw compiler output never reaches the client.
MESSAGES = {
    QUEUED: "Queued — waiting for a free compiler.",
    RUNNING: "Typesetting your resume…",
    DONE: "Your resume is ready.",
    ERROR: "Something went wrong generating your PDF. Please try again.",
}


class QueueFull(Exception):
    pass


@dataclass
class Job:
    id: str
    status: str = QUEUED
    message: str = MESSAGES[QUEUED]
    token: Optional[str] = None
    filename: str = "resume.pdf"
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


class JobQueue:
    def __init__(self, max_workers: int = MAX_WORKERS):
        self._max_workers = max_workers
        self._pool: Optional[ThreadPoolExecutor] = None
        self._jobs: Dict[str, Job] = {}
        self._in_flight = 0
        self._lock = asyncio.Lock()

    def _executor(self) -> ThreadPoolExecutor:
        """Create the pool on demand.

        Lazily, so that a shutdown (app teardown, or between tests) leaves the
        queue reusable rather than permanently broken.
        """
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=self._max_workers,
                                            thread_name_prefix="compile")
        return self._pool

    async def submit(self, resume: Resume, template_id: str) -> Job:
        async with self._lock:
            self._reap()
            if self._in_flight >= MAX_QUEUE_DEPTH:
                raise QueueFull()
            job = Job(id=secrets.token_urlsafe(12),
                      filename=_filename_for(resume))
            self._jobs[job.id] = job
            self._in_flight += 1

        asyncio.create_task(self._run(job, resume, template_id))
        return job

    async def _run(self, job: Job, resume: Resume, template_id: str) -> None:
        job.status = RUNNING
        job.message = MESSAGES[RUNNING]
        loop = asyncio.get_running_loop()
        try:
            tex = render_resume(resume, template_id)
            result = await loop.run_in_executor(self._executor(), compile_pdf, tex)
            entry = store.put(result.pdf_bytes, job.filename)
            job.token = entry.token
            job.status = DONE
            job.message = MESSAGES[DONE]
        except CompileError as exc:
            # Log the failure for debugging, but never the resume content.
            log.warning("compile failed job=%s template=%s reason=%s\n%s",
                        job.id, template_id, exc, exc.log_excerpt)
            job.status = ERROR
            job.message = MESSAGES[ERROR]
        except Exception:  # noqa: BLE001 - last line of defence
            log.exception("unexpected compile error job=%s", job.id)
            job.status = ERROR
            job.message = MESSAGES[ERROR]
        finally:
            job.finished_at = time.time()
            async with self._lock:
                self._in_flight -= 1

    def get(self, job_id: str) -> Optional[Job]:
        self._reap()
        return self._jobs.get(job_id)

    def _reap(self) -> None:
        cutoff = time.time() - JOB_RETENTION_SECONDS
        for job_id, job in list(self._jobs.items()):
            if job.created_at < cutoff:
                self._jobs.pop(job_id, None)

    def shutdown(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)


def _filename_for(resume: Resume) -> str:
    """A tidy download filename derived from the candidate's name."""
    raw = resume.contact.full_name.strip().lower()
    safe = "".join(ch if ch.isalnum() else "-" for ch in raw).strip("-")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return f"{safe or 'resume'}-resume.pdf"


queue = JobQueue()
