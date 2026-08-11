"""Resume Maker API (Phase 1 — manual fill, single template).

Endpoints:
    GET  /api/health
    GET  /api/templates
    GET  /api/templates/{id}/preview.pdf   sample resume, cached
    POST /api/compile                      → { job_id }
    GET  /api/jobs/{job_id}                → status + download_url
    GET  /api/download/{token}             → the PDF
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import compile as compiler
from .compile import render_first_page_png
from .jobs import QueueFull, queue
from .ratelimit import COMPILE_LIMIT, POLL_LIMIT, client_key, limiter
from .sample import SAMPLE_RESUME
from .schema import CompileRequest, JobStatus
from .storage import store
from .templates_registry import TEMPLATES, list_templates, render_resume

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if o.strip()
]

_preview_cache: dict[str, bytes] = {}
_thumbnail_cache: dict[str, bytes] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.sweep()
    yield
    queue.shutdown()


app = FastAPI(title="Resume Maker API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def rate_limit(limit):
    def dependency(request: Request) -> None:
        allowed, retry_after = limiter.check(client_key(request), limit)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="You've hit the limit for now — please try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
    return dependency


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "engine": compiler.LATEX_ENGINE,
        "backend": compiler.COMPILE_BACKEND,
        "engine_available": compiler.engine_available(),
    }


@app.get("/api/templates")
async def get_templates() -> dict:
    return {"templates": list_templates()}


@app.get("/api/templates/{template_id}/preview.pdf")
async def template_preview(template_id: str) -> Response:
    """A compiled sample resume, so users see the real output before starting."""
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")

    if template_id not in _preview_cache:
        try:
            tex = render_resume(SAMPLE_RESUME, template_id)
            _preview_cache[template_id] = compiler.compile_pdf(tex).pdf_bytes
        except compiler.CompileError as exc:
            log.error("preview compile failed template=%s: %s\n%s",
                      template_id, exc, exc.log_excerpt)
            raise HTTPException(status_code=503,
                                detail="Preview is unavailable right now.") from None

    return Response(
        content=_preview_cache[template_id],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{template_id}-preview.pdf"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.get("/api/templates/{template_id}/preview.png")
async def template_thumbnail(template_id: str) -> Response:
    """First page of the sample, as an image.

    Browsers render an embedded PDF inconsistently (and some not at all), so
    the gallery card shows this and links the PDF for a closer look.
    """
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")

    if template_id not in _thumbnail_cache:
        pdf = (await template_preview(template_id)).body
        png = render_first_page_png(pdf)
        if png is None:
            raise HTTPException(status_code=503,
                                detail="Preview image is unavailable right now.")
        _thumbnail_cache[template_id] = png

    return Response(
        content=_thumbnail_cache[template_id],
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.post("/api/compile", status_code=202,
          dependencies=[Depends(rate_limit(COMPILE_LIMIT))])
async def start_compile(payload: CompileRequest, request: Request) -> JobStatus:
    if payload.template_id not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template.")
    try:
        job = await queue.submit(payload.resume, payload.template_id)
    except QueueFull:
        raise HTTPException(
            status_code=503,
            detail="We're compiling a lot of resumes right now — try again in a moment.",
            headers={"Retry-After": "15"},
        ) from None
    return _job_status(job)


@app.get("/api/jobs/{job_id}", dependencies=[Depends(rate_limit(POLL_LIMIT))])
async def job_status(job_id: str) -> JobStatus:
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That job has expired.")
    return _job_status(job)


@app.get("/api/download/{token}", dependencies=[Depends(rate_limit(POLL_LIMIT))])
async def download(token: str, inline: bool = False) -> Response:
    entry = store.get(token)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="This download link has expired. Generate the PDF again.",
        )
    disposition = "inline" if inline else "attachment"
    return Response(
        content=entry.path.read_bytes(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{entry.filename}"',
            "Cache-Control": "private, no-store",
        },
    )


def _job_status(job) -> JobStatus:
    url: Optional[str] = f"/api/download/{job.token}" if job.token else None
    return JobStatus(job_id=job.id, status=job.status, message=job.message,
                     download_url=url)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Uniform error shape, and never leak internals into `detail`."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=exc.headers or {},
    )
