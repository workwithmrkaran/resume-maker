"""Resume Maker API (Phase 1 — manual fill, single template).

Endpoints:
    GET  /api/health
    GET  /api/templates
    GET  /api/templates/{id}/preview.pdf   sample resume, cached
    POST /api/compile                      → { job_id }
    GET  /api/jobs/{job_id}                → status + download_url
    GET  /api/download/{token}             → the PDF
    POST /api/extract                      upload a resume → { job_id }
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import (Depends, FastAPI, File, HTTPException, Request,
                     Response, UploadFile)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import compile as compiler
from .compile import render_first_page_png
from .extraction.text import MAX_UPLOAD_BYTES
from .jobs import EXTRACT, QueueFull, queue
from .llm import get_client
from .ratelimit import (COMPILE_LIMIT, EXTRACT_LIMIT, POLL_LIMIT, client_key,
                        limiter)
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

# Sample previews are committed to the repo (see scripts/build_previews.py),
# so browsing templates works with no LaTeX installed at all. Compiling one on
# demand is only the fallback for a template whose assets are missing.
PREVIEW_DIR = Path(__file__).parent / "static" / "previews"

_preview_cache: dict[str, bytes] = {}
_thumbnail_cache: dict[str, bytes] = {}


def _shipped(template_id: str, suffix: str) -> Optional[bytes]:
    path = PREVIEW_DIR / f"{template_id}.{suffix}"
    return path.read_bytes() if path.exists() else None


PREWARM = os.getenv("PREWARM_COMPILE", "1") not in ("0", "false", "no")


def _prewarm() -> None:
    """Compile the sample once at boot, off the request path.

    A cold TeX install downloads packages and builds format files on its first
    run — tens of seconds on MiKTeX. Paying that at startup means no user ever
    waits for it, and the log says plainly whether the engine works at all.
    """
    import time

    started = time.time()
    try:
        compiler.compile_pdf(render_resume(SAMPLE_RESUME))
        log.info("compiler ready (warm-up took %.1fs)", time.time() - started)
    except Exception as exc:  # noqa: BLE001 - diagnostic only, never fatal
        log.warning("compiler warm-up failed after %.1fs: %s — the first real "
                    "compile may be slow or fail", time.time() - started, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.sweep()
    if not compiler.sandbox_status()["resource_limits"]:
        # Loud on purpose: this is the one platform difference that matters,
        # and it must not be discovered in production.
        log.warning(
            "Running without per-compile resource limits (%s). Fine for local "
            "development; use the Docker image or COMPILE_BACKEND=docker for "
            "anything reachable from the internet.",
            compiler.sandbox_status()["platform"],
        )
    if not compiler.engine_available():
        log.warning("LaTeX engine '%s' not found on PATH — compiles will fail.",
                    compiler.LATEX_ENGINE)
    elif PREWARM:
        threading.Thread(target=_prewarm, name="prewarm", daemon=True).start()
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


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Signpost, so hitting the API root isn't a bare 404.

    People land here expecting the app; the web UI is a separate service.
    """
    return {
        "service": "Resume Maker API",
        "web_ui": "the frontend runs separately — http://localhost:5173 in dev",
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Browsers ask for this on every visit; 204 keeps the logs readable."""
    return Response(status_code=204)


@app.get("/api/health")
async def health() -> dict:
    llm = get_client()
    return {
        "status": "ok",
        "engine": compiler.LATEX_ENGINE,
        "backend": compiler.COMPILE_BACKEND,
        "engine_available": compiler.engine_available(),
        "sandbox": compiler.sandbox_status(),
        # Which providers are loaded, and in what order they will be tried.
        # Keys are redacted — this endpoint is public.
        "extraction_enabled": llm.configured,
        "llm_providers": llm.describe(),
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
        shipped = _shipped(template_id, "pdf")
        if shipped is not None:
            _preview_cache[template_id] = shipped
        else:
            try:
                tex = render_resume(SAMPLE_RESUME, template_id)
                _preview_cache[template_id] = compiler.compile_pdf(tex).pdf_bytes
            except compiler.CompileError as exc:
                log.error("preview compile failed template=%s: %s\n%s",
                          template_id, exc, exc.log_excerpt)
                raise HTTPException(
                    status_code=503,
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
        png = _shipped(template_id, "png")
        if png is None:
            # No shipped thumbnail: rasterise, which needs poppler.
            png = render_first_page_png((await template_preview(template_id)).body)
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


@app.post("/api/extract", status_code=202,
          dependencies=[Depends(rate_limit(EXTRACT_LIMIT))])
async def start_extraction(file: UploadFile = File(...)) -> JobStatus:
    """Read an uploaded resume into the same schema the manual form produces.

    The upload is held in memory for the length of the job and never written to
    disk: it is somebody's full employment history and home address.
    """
    if not get_client().configured:
        raise HTTPException(
            status_code=503,
            detail="Resume reading is switched off right now — please fill "
                   "the form in yourself.",
        )

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413,
                            detail="That file is too large — the limit is 5 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="That file is empty.")

    try:
        job = await queue.submit_extraction(data, file.filename or "resume")
    except QueueFull:
        raise HTTPException(
            status_code=503,
            detail="We're reading a lot of resumes right now — try again in a moment.",
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
    status = JobStatus(job_id=job.id, kind=job.kind, status=job.status,
                       message=job.message, download_url=url,
                       warnings=job.warnings)
    if job.kind == EXTRACT and job.result:
        status.resume = job.result["resume"]
        status.confidence = job.result["confidence"]
        status.low_confidence = job.result["low_confidence"]
    return status


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request,
                                       exc: RequestValidationError):
    """Make a 422 diagnosable without echoing resume content back.

    FastAPI's default body quotes the offending values, which here means
    somebody's phone number in a log or an error panel. Field paths go to the
    server log; the client gets plain language and the list of fields.
    """
    fields = [".".join(str(p) for p in error["loc"][1:]) or "(body)"
              for error in exc.errors()]
    log.warning("rejected %s: invalid fields: %s", request.url.path,
                ", ".join(f"{f} ({e['type']})"
                          for f, e in zip(fields, exc.errors())))
    return JSONResponse(
        status_code=422,
        content={
            "error": "Some of these details couldn't be accepted — please "
                     "check the highlighted fields.",
            "fields": fields,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Uniform error shape, and never leak internals into `detail`."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=exc.headers or {},
    )
