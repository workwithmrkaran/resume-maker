"""Background job queue.

Both slow paths run here: LaTeX compilation (seconds of CPU) and AI extraction
(seconds of network). Neither may run inline in a request handler. This is a
small in-process queue with a fixed pool of worker threads — enough for MVP
volumes, and deliberately shaped like a task queue (submit → poll status →
fetch result) so moving to Celery/RQ later is a swap of this module rather
than a redesign of the API.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .compile import CompileError, compile_pdf
from .extraction.service import ExtractionFailed, extract_resume
from .extraction.text import UnsupportedFile
from .schema import Resume
from .storage import store
from .templates_registry import render_resume

log = logging.getLogger(__name__)

MAX_WORKERS = int(os.getenv("COMPILE_WORKERS", "2"))
MAX_QUEUE_DEPTH = int(os.getenv("COMPILE_QUEUE_DEPTH", "50"))
JOB_RETENTION_SECONDS = int(os.getenv("JOB_RETENTION_SECONDS", "3600"))

QUEUED, RUNNING, DONE, ERROR = "queued", "running", "done", "error"

COMPILE, EXTRACT = "compile", "extract"

# User-facing copy. Raw compiler output never reaches the client.
MESSAGES = {
    COMPILE: {
        QUEUED: "Queued — waiting for a free compiler.",
        RUNNING: "Typesetting your resume…",
        DONE: "Your resume is ready.",
        ERROR: "Something went wrong generating your PDF. Please try again.",
    },
    EXTRACT: {
        QUEUED: "Queued — waiting to read your resume.",
        RUNNING: "Reading your resume…",
        DONE: "We've read your resume.",
        ERROR: "We couldn't read that resume. Please try another file, or "
               "fill the form in yourself.",
    },
}


class QueueFull(Exception):
    pass


@dataclass
class Job:
    id: str
    kind: str = COMPILE
    status: str = QUEUED
    message: str = ""
    token: Optional[str] = None              # compile jobs: download token
    filename: str = "resume.pdf"
    result: Optional[Dict[str, Any]] = None  # extract jobs: the resume payload
    warnings: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.message:
            self.message = MESSAGES[self.kind][QUEUED]


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

    async def _enqueue(self, kind: str, filename: str) -> Job:
        async with self._lock:
            self._reap()
            if self._in_flight >= MAX_QUEUE_DEPTH:
                raise QueueFull()
            job = Job(id=secrets.token_urlsafe(12), kind=kind, filename=filename)
            self._jobs[job.id] = job
            self._in_flight += 1
        return job

    async def submit(self, resume: Resume, template_id: str) -> Job:
        job = await self._enqueue(COMPILE, _filename_for(resume))
        asyncio.create_task(self._run_compile(job, resume, template_id))
        return job

    async def submit_extraction(self, data: bytes, filename: str) -> Job:
        job = await self._enqueue(EXTRACT, filename)
        asyncio.create_task(self._run_extraction(job, data, filename))
        return job

    async def _run_compile(self, job: Job, resume: Resume, template_id: str) -> None:
        loop = asyncio.get_running_loop()
        async with self._running(job):
            try:
                tex = render_resume(resume, template_id)
                result = await loop.run_in_executor(self._executor(), compile_pdf, tex)
                entry = store.put(result.pdf_bytes, job.filename)
                job.token = entry.token
                self._succeed(job)
            except CompileError as exc:
                # Log the failure for debugging, but never the resume content.
                log.warning("compile failed job=%s template=%s reason=%s\n%s",
                            job.id, template_id, exc, exc.log_excerpt)
                self._fail(job)
            except Exception:  # noqa: BLE001 - last line of defence
                log.exception("unexpected compile error job=%s", job.id)
                self._fail(job)

    async def _run_extraction(self, job: Job, data: bytes, filename: str) -> None:
        loop = asyncio.get_running_loop()
        async with self._running(job):
            try:
                result = await loop.run_in_executor(
                    self._executor(), extract_resume, data, filename)
                job.result = {
                    "resume": result.resume,
                    "confidence": result.confidence,
                    "low_confidence": result.low_confidence,
                }
                job.warnings = result.warnings
                self._succeed(job)
            except (UnsupportedFile, ExtractionFailed) as exc:
                # These carry plain-language, user-safe text by construction.
                log.info("extraction rejected job=%s: %s", job.id, exc)
                self._fail(job, str(exc))
            except Exception:  # noqa: BLE001 - last line of defence
                log.exception("unexpected extraction error job=%s", job.id)
                self._fail(job)

    @asynccontextmanager
    async def _running(self, job: Job):
        job.status = RUNNING
        job.message = MESSAGES[job.kind][RUNNING]
        try:
            yield
        finally:
            job.finished_at = time.time()
            async with self._lock:
                self._in_flight -= 1

    @staticmethod
    def _succeed(job: Job) -> None:
        job.status = DONE
        job.message = MESSAGES[job.kind][DONE]

    @staticmethod
    def _fail(job: Job, message: str = "") -> None:
        job.status = ERROR
        job.message = message or MESSAGES[job.kind][ERROR]

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
