# Resume Maker

A free web app that turns a guided form into a professionally typeset PDF
resume, compiled from a real LaTeX template. No account, no paywall, no LaTeX
knowledge required.

This repository implements **Phase 1** of the product plan: manual fill, a
single template, compile and download.

| Landing | Guided form | Compiled output |
|---|---|---|
| ![Landing page](docs/landing.png) | ![Guided form](docs/form.png) | ![Compiled PDF](docs/output.png) |

## How it works

```
form input → validate (Pydantic) → escape → render Jinja2 → .tex
           → queued compile job → sandboxed pdflatex → PDF → short-lived download link
```

The canonical resume schema (`backend/app/schema.py`) sits at the centre: the
form produces it, every template consumes it, and Phase 2's AI extraction will
have to emit it. That's what makes "AI autofill" a pre-fill step rather than a
second pipeline, and what will let Phase 3 re-render existing data into a new
template without retyping anything.

## Running it

### Docker (everything, including the TeX engine)

```bash
docker compose up --build
# web  → http://localhost:8080
# api  → http://localhost:8000
```

### Locally, for development

The backend needs a TeX installation. On Debian/Ubuntu:

```bash
sudo apt-get install -y --no-install-recommends \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended lmodern poppler-utils
```

`lmodern` is not optional — without it pdflatex falls back to bitmap fonts,
which look wrong and extract badly in ATS scanners. `poppler-utils` is used to
rasterise template thumbnails.

```bash
# API
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# Web
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## Tests

```bash
cd backend  && python -m pytest        # 53 tests; compile tests skip if TeX is missing
cd frontend && npm test                # form logic and validation
cd frontend && node e2e/flow.mjs       # full browser run-through (needs both servers up)
```

The backend suite compiles deliberately hostile input (`\write18{…}`,
`\end{document}`, `100% & $1M`) all the way to a PDF, because escaping is the
security boundary here, not a formatting nicety.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness plus which engine is configured |
| `GET` | `/api/templates` | Template catalogue |
| `GET` | `/api/templates/{id}/preview.png` | Sample resume thumbnail |
| `GET` | `/api/templates/{id}/preview.pdf` | Full sample PDF |
| `POST` | `/api/compile` | Enqueue a compile → `202 { job_id }` |
| `GET` | `/api/jobs/{job_id}` | `queued` / `running` / `done` / `error` |
| `GET` | `/api/download/{token}` | The generated PDF |

Compilation is asynchronous because it takes seconds and must not block the API
process. `JobQueue` (`backend/app/jobs.py`) is an in-process thread pool shaped
like a task queue; moving to Celery/RQ + Redis means replacing that one module,
not redesigning the API.

## Safety

Every compile runs LaTeX over text an untrusted user supplied, so:

- **Escaping.** Every value reaching a template goes through `escape_latex` —
  enforced by installing it as the Jinja2 environment's `finalize`, so a
  template author cannot forget it. URLs get a narrower escaper that keeps
  `&` and `~` functional inside `\href`.
- **No shell escape.** `-no-shell-escape`, `shell_escape=f`, and
  `openin_any`/`openout_any=p` so the engine cannot read or write outside its
  working directory.
- **Resource limits.** Wall-clock timeout, `RLIMIT_AS`/`CPU`/`FSIZE`/`NPROC`,
  and an ephemeral working directory removed after every job.
- **Container hardening.** The compose service runs read-only, unprivileged,
  with all capabilities dropped and `no-new-privileges`. Set
  `COMPILE_BACKEND=docker` to isolate each compile in its own `--network=none`
  container instead.
- **Validation before rendering.** Pydantic enforces types, field lengths and
  list caps, and rejects `javascript:`/`file:` URLs, before any text reaches
  the template.
- **No leaking internals.** Users see "something went wrong generating your
  PDF"; the TeX log goes to the server log only, and resume content never does.

## Privacy

Resume content stays in the browser (`localStorage` autosave) until the user
presses Generate. Generated PDFs live in a temp store keyed by an unguessable
token and are deleted after `PDF_TTL_SECONDS` (default one hour). Nothing is
persisted server-side beyond that, and there are no accounts to attach it to.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:5173,…` | CORS allow-list |
| `COMPILE_BACKEND` | `subprocess` | `subprocess` or `docker` |
| `LATEX_ENGINE` | `pdflatex` | `pdflatex`, `xelatex` or `tectonic` |
| `COMPILE_TIMEOUT` | `20` | Seconds per compile |
| `COMPILE_MEMORY_MB` | `512` | Address-space cap per compile |
| `COMPILE_WORKERS` | `2` | Concurrent compiles |
| `COMPILE_QUEUE_DEPTH` | `50` | Jobs in flight before returning 503 |
| `RATE_LIMIT_COMPILES` | `10` | Compiles per client per window |
| `RATE_LIMIT_WINDOW` | `600` | Rate-limit window, seconds |
| `PDF_TTL_SECONDS` | `3600` | How long a download link works |
| `TRUST_PROXY_HEADERS` | unset | Set to `1` only behind a proxy you control |
| `VITE_API_BASE_URL` | `http://localhost:8000` | API origin, baked into the web build |

## Adding a template (Phase 3)

1. Drop a `.tex.j2` file in `backend/app/templates/`, using `\VAR{}` / `\BLOCK{}`
   delimiters against the existing schema.
2. Add one entry to `TEMPLATES` in `backend/app/templates_registry.py`.

The gallery, the form, the compile pipeline and the data model need no changes.

## What's deliberately not here

Per the product plan, Phase 1 excludes accounts, saved drafts on the server,
AI resume upload, multiple templates and payments. The upload path is visible
in the UI as a disabled "coming soon" card so Phase 2 slots in without a
redesign.

Two implementation notes worth knowing before scaling up:

- The job queue and rate limiter hold state in process memory. They are correct
  for one API process; running several means moving both to Redis.
- Rate limiting is per client IP, which is the right MVP default but is shared
  by everyone behind one NAT.
