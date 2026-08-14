# Project handoff — Resume Maker

Written so a fresh Claude session (or a new engineer) can pick this up cold,
with no access to the conversation that produced it. It covers what exists,
why it is built the way it is, what is verified and what is not, and what to
do next.

**Repository:** `https://github.com/workwithmrkaran/resume-maker`, branch `main`.
Everything described here is committed and pushed. Last commit at time of
writing: `0872b94`.

---

## 1. What this is

A free web app that turns a guided form into a professionally typeset PDF
resume, compiled from real LaTeX templates. No account, no paywall, no LaTeX
knowledge needed from the user.

It was built from three planning documents (product, technical architecture,
frontend/UX) that defined three phases:

| Phase | Scope | Status |
|---|---|---|
| 1 | Manual fill, single template, compile and download | **Done** |
| 2 | Upload an existing resume, AI extraction, review and edit | **Done** |
| 3 | Multiple templates, template switching, optional accounts | **Templates and switching done. Accounts not built.** |

Four templates ship. Accounts are the only significant unbuilt item from the
original plan.

---

## 2. The central design decision

One canonical resume schema (`backend/app/schema.py`, Pydantic) sits at the
middle of everything:

```
manual form ─┐
             ├──> canonical Resume ──> Jinja2 template ──> .tex ──> pdflatex ──> PDF
AI upload ───┘
```

- The guided form produces it.
- AI extraction must emit exactly it.
- Every template consumes it.

That is what makes "AI autofill" a pre-fill step rather than a second
pipeline, and what lets a user switch template without re-entering anything.
**Do not add per-template fields to this schema.** When a template needed a
section the schema lacks, the template was changed, not the schema — see §6.

---

## 3. Repository layout

```
backend/
  app/
    main.py               FastAPI app, all endpoints, lifespan, error handlers
    schema.py             Canonical Pydantic resume schema — the contract
    latex.py              LaTeX escaping + Jinja2 environment (custom delimiters)
    compile.py            Sandboxed pdflatex invocation, cross-platform
    jobs.py               In-process job queue (compile + extract)
    storage.py            Short-lived PDF store with TTL sweep
    ratelimit.py          Sliding-window per-client limits
    llm.py                LLM provider chain with failover
    settings.py           Loads backend/.env
    sample.py             Fictional sample resume (previews + tests)
    templates_registry.py Template catalogue; render entry point
    templates/            classic|compact|modern|technical .tex.j2
    static/previews/      Committed sample PDFs + PNGs per template
  scripts/
    build_previews.py     Regenerate static/previews (run after layout changes)
    check_llm.py          Ping each configured LLM provider; optional extraction
    fake_llm_server.py    OpenAI-compatible stub for dev/e2e (FAKE_LLM_STATUS=429)
  tests/                  138 tests
  Dockerfile              API + TeX Live; the image is the sandbox
frontend/
  src/
    App.tsx               Screen state machine
    api.ts                API client, error shaping
    schema mirror:        types.ts, validation.ts, steps.ts
    aiFilled.tsx/-Context Tracks which fields came from AI
    components/           fields.tsx, StepForms.tsx, ResumePreview.tsx, PdfViewer.tsx
    screens/              Landing, TemplateGallery, ChoosePath, UploadResume,
                          FormWizard, ReviewAndDownload
  e2e/                    flow.mjs, upload.mjs, templates.mjs (Playwright)
docker-compose.yml        Hardened API + nginx-served web
```

---

## 4. Backend

### API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Signpost (health, docs, where the UI lives) |
| `GET` | `/api/health` | Engine, sandbox status, LLM providers (keys redacted) |
| `GET` | `/api/templates` | Template catalogue |
| `GET` | `/api/templates/{id}/preview.png` | Sample thumbnail (shipped asset) |
| `GET` | `/api/templates/{id}/preview.pdf` | Full sample PDF (shipped asset) |
| `POST` | `/api/compile` | Enqueue a compile → `202 {job_id}` |
| `POST` | `/api/extract` | Upload a resume for AI extraction → `202 {job_id}` |
| `GET` | `/api/jobs/{job_id}` | `queued`/`running`/`done`/`error` |
| `GET` | `/api/download/{token}` | The generated PDF |

Compilation and extraction are asynchronous: both take seconds and must not
block the API. `jobs.py` is an in-process thread pool deliberately shaped like
a task queue (submit → poll → fetch), so moving to Celery/RQ + Redis replaces
that one module without touching the API surface.

### Escaping — the security boundary

The compiler runs on text supplied by untrusted users. `latex.py` installs
`escape_latex` as the Jinja2 environment's **finalizer**, so every `\VAR{}` is
escaped whether or not a template author remembers. Values that must stay
functional (URLs) go through the narrower `escape_url` via an explicit `|url`
filter that marks them safe.

Two non-obvious things, both discovered by tests, both worth preserving:

1. **Escaping is a single regex pass.** Doing it as sequential `str.replace`
   calls is wrong in either order: replacing `\` with `\textbackslash{}`
   introduces braces that the later brace rules then escape again.
2. **`escape_url` escapes `&` but deliberately not `~`.** Raw `&` inside a
   `tabular` cell is a column separator and derails `\href`'s argument
   scanner — an ordinary `?a=1&b=2` link fails the whole compile. But `\~{}`
   lands *literally* in the link target and breaks the URL. Verified by
   extracting the URI from a compiled PDF.

### Sandboxing

- `-no-shell-escape`, `shell_escape=f`, `openin_any=p`, `openout_any=p`
- Wall-clock timeout, `RLIMIT_AS`/`CPU`/`FSIZE`/`NPROC`, ephemeral workdir
- Optional `COMPILE_BACKEND=docker` for per-compile container isolation
- Compose runs read-only, unprivileged, all caps dropped

**Windows has no `RLIMIT_*`.** On Windows the engine runs with shell-escape
off and a timeout but *without* memory/CPU/file-size caps. This is stated
rather than hidden: `sandbox_status()` reports it, `/api/health` exposes it,
and the API logs a warning at startup. Windows is for development; deployment
should use the container.

### AI extraction (Phase 2)

`backend/app/extraction/`:

- `text.py` — PDF via pymupdf, DOCX via python-docx *including tables* (many
  resumes lay out work history in tables). File type is decided by **magic
  bytes**, not the filename. Image-only PDFs are detected and reported in
  plain language rather than silently returning an empty resume. Caps: 5 MB,
  10 pages, 40k chars.
- `service.py` — prompt, parsing, validation. Model replies are stripped of
  markdown fences and `<think>` scratchpads; unknown keys are dropped (the
  schema forbids extras, and one invented field would otherwise discard a good
  extraction); common shape mistakes are coerced (a flat skills list, a
  bullets string instead of a list, a bare URL string instead of a link
  object). Then Pydantic validates. On failure there is **exactly one** repair
  round that tells the model which fields broke — never quoting their values.
- A completeness heuristic drives whether the review screen says "check this
  carefully" more loudly. It is a heuristic, not a calibrated probability.

The uploaded file is held in memory for the job and never written to disk.

### LLM provider chain (`llm.py`)

Providers are numbered blocks in `backend/.env`, tried in order:

```
LLM_PROVIDER_1_MODEL=nvidia/nemotron-3-super-120b-a12b
LLM_PROVIDER_1_API_KEY=nvapi-…
LLM_PROVIDER_1_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_PROVIDER_1_THINKING=false

LLM_PROVIDER_2_MODEL=openai/gpt-oss-20b
LLM_PROVIDER_2_API_KEY=nvapi-…
```

The point is that free-tier keys run out. On 429/402/401/5xx or a connection
failure, the next provider serves the request and the user sees nothing.

**A 400 does not fail over** — that means *we* sent something malformed and
the next provider would reject it identically. A 400 specifically on the
structured-output options (`response_format`, guided decoding) retries the
same provider once without them, since support varies by model.

Endpoints are OpenAI-compatible, so a provider can point at Anthropic, OpenAI
or a local vLLM with no code change. Prompts, replies and keys never reach the
logs.

---

## 5. Frontend

React + TypeScript + Vite, no UI framework, no router (a screen state machine
in `App.tsx`).

Screens: Landing → Template gallery → Choose path (fill in / upload) →
[Upload] → 7-step guided form → Review → Download.

Notable behaviour:

- **Autosave to localStorage.** Resume data never touches the server until the
  user presses Generate (or uploads a file). A refresh mid-form loses nothing.
- **Inline validation** as the user types, only for steps they've tried to
  leave. `validation.ts` mirrors the server rules — including the URL rule, so
  a bad link is caught in the form rather than as a 422 after Generate.
- **AI-filled badges.** After an upload, each field that still holds exactly
  what the model produced shows a badge; editing it clears the badge. Tracked
  by comparing against a snapshot in `aiFilled.tsx`.
- **Two previews.** During editing, a structured HTML approximation of the
  layout. After generating, the **actual compiled PDF**, rendered in-page.
- **Format switcher** on the review screen — same data, any of four layouts.

### Why pdf.js instead of an `<object>` embed

An `<object type="application/pdf">` depends on the browser shipping a PDF
viewer; where one isn't present it renders as a black rectangle. Since the
whole point of that screen is "see exactly what you're about to download",
pdf.js draws to a canvas and looks identical everywhere.

`pdfjs-dist` is **pinned to the v4 line on purpose**: v5/v6 call
`Map.prototype.getOrInsertComputed`, a very new built-in that throws on
browsers a version or two old. It is lazy-loaded, so its ~330 kB only arrives
once a PDF exists; the initial bundle stays ~226 kB.

---

## 6. Templates

| Format | Source | Best for |
|---|---|---|
| **Classic** | written for this project | ATS-friendly, most industry roles |
| **Compact** | [autoCV](https://github.com/jitinnair1/autoCV), Jitin Nair (MIT) | Long histories, academic CVs |
| **Modern** | [Harshibar's](https://github.com/harshibar/common-intern) (MIT), after jakeryang/resume | Tech and product roles |
| **Technical** | [Anubhav Singh's](https://github.com/xprilion) (MIT) | Students, early career |

The three adapted templates keep their upstream MIT notices at the top of each
`.tex.j2`, and each file's header comment records what was changed and why.

Adaptations made, and the reasoning:

- **Compact** used biblatex with a `citations.bib`. Replaced by the schema's
  own publications list — no `.bib` to ship, no second escaping path.
- **Technical** had hardcoded Honours and Volunteering sections. Dropped:
  adding fields for one template would distort the schema every other template
  shares. That content belongs in Projects or Experience.
- **Modern** used `\myuline` for underlined links, which needs literal braces
  around text that arrives escaped. Plain `\href` instead — an ATS reads it
  identically. Its unused FiraMono dependency was removed rather than becoming
  a font every machine must have.

### Adding a fifth

1. Drop a `.tex.j2` in `backend/app/templates/` using `\VAR{}` / `\BLOCK{}`.
2. Add one entry to `TEMPLATES` in `templates_registry.py`.
3. Run `python scripts/build_previews.py` and commit the generated assets.

`tests/test_templates.py` parametrises over the registry, so the new template
automatically inherits: renders a full sample, renders a name-only resume,
escapes every LaTeX metacharacter in every field, compiles all three cases,
and has its preview assets committed.

### Previews do not need LaTeX

The gallery serves pre-rendered assets committed to the repo, so browsing
templates works with no TeX installed. Compiling on demand is only the
fallback for a template missing its assets. Separately, a **startup warm-up**
compiles the sample once at boot so no user's request pays for a cold engine
(`PREWARM_COMPILE=0` to disable).

---

## 7. Tests

```bash
cd backend  && python -m pytest        # 138 tests
cd frontend && npm test                # 18 tests
cd frontend && node e2e/flow.mjs       # manual path, real browser
cd frontend && node e2e/upload.mjs     # AI upload path, real browser
cd frontend && node e2e/templates.mjs  # 4 formats switched from one dataset
```

Compile tests skip themselves when no TeX engine is present — **a green run on
a machine without LaTeX does not mean the pipeline works.** Check
`/api/health` for `engine_available`.

The backend suite compiles deliberately hostile input (`\write18{}`,
`\end{document}`, `100% & $1M`, metacharacters in every field) all the way to
a PDF, in every template.

The e2e scripts take `CHROMIUM_PATH` (reuse an installed browser) and
`SHOT_DIR`. `templates.mjs` asserts the four formats produce genuinely
different rendered output, not just that each returns 200.

---

## 8. Running it

### Docker (Linux, full sandbox)

```bash
docker compose up --build     # web :8080, api :8000
```

Reads `backend/.env` for keys. **Never verified by me** — no Docker daemon was
available in the environment where this was built. It is the one part of the
setup that has not had a real first run.

### Locally

Needs a TeX install: `texlive-latex-{base,recommended,extra}`,
`texlive-fonts-{recommended,extra}`, `lmodern`, `tex-gyre`, `poppler-utils`
on Debian/Ubuntu; MiKTeX on Windows.

```bash
cd backend  && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
            && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```

**MiKTeX users:** set auto-install on, or the compile hangs waiting for a
dialog no background process can answer:

```cmd
initexmf --set-config-value=[MPM]AutoInstall=1
mpm --require=lm --require=titlesec --require=enumitem --require=geometry ^
    --require=hyperref --require=xcolor --require=tools --require=fontawesome5 ^
    --require=tex-gyre
```

For local development, raise the abuse limits — the defaults are sized for a
shared public instance:

```
RATE_LIMIT_COMPILES=200
RATE_LIMIT_EXTRACTIONS=100
COMPILE_TIMEOUT=120
```

---

## 9. Verified vs unverified — read this before trusting anything

**Verified, by running it:**
- Full manual flow in a real browser: form → compile → download, with
  autosave surviving a refresh.
- Full AI upload flow in a real browser, against a local OpenAI-compatible
  stub: upload → extraction → pre-filled form with badges → PDF.
- **Provider failover, over real HTTP**: provider 1 returning 429, provider 2
  answering, correct extraction returned.
- All four templates compiling — full sample, name-only, and hostile input.
- The format switcher producing four genuinely different layouts.
- On the user's Windows machine: the real NVIDIA endpoint returned 200 with
  `nvidia/nemotron-3-super-120b-a12b`, so **that key and model ID are valid**.

**Not verified:**
- **The Docker image has never been built.** No daemon was available.
- **Extraction quality on real resumes.** It returns valid, schema-correct
  data. Whether it gets a *particular* person's work history right is
  untested. Two-column PDFs are the likely weak point. This is the single
  biggest open risk.
- The second NVIDIA key (`openai/gpt-oss-20b`) has never served a live
  request — only the primary has.
- No deployment of any kind. It has only ever run on localhost.

---

## 10. Known gaps and what to do next

**In rough priority order:**

1. **Build an evaluation set for extraction.** Ten to twenty real resumes with
   hand-written expected JSON, scored field by field. Turns "seems okay" into
   a number and lets you compare the two configured models properly. Nothing
   else about Phase 2 should be trusted until this exists.
2. **Build and run the Docker image**, then deploy. The mission in the
   planning docs is a free public tool; it currently runs on one laptop.
   Deployment must be Linux (full sandbox), not Windows.
3. **Rotate the NVIDIA API keys.** They were pasted into a chat conversation.
4. **Optional accounts** — the only significant unbuilt item from Phase 3.

**Architectural limits to know about:**

- The job queue and rate limiter hold state in process memory. Correct for one
  API process; running several means moving both to Redis.
- Rate limiting is per client IP — shared by everyone behind one NAT.
- Scanned/image-only PDFs are detected and reported, not OCR'd. A
  vision-language model is the better answer than bolting on Tesseract, and
  it is a separate piece of work.
- `texlive-fonts-extra` is ~1 GB unpacked and is the largest layer in the
  Docker image. It exists for the FontAwesome glyphs in three templates. Drop
  it (and the `fontawesome5` usage) if image size matters more than icons.

---

## 11. Conventions worth keeping

- **Never let raw compiler output reach a user.** They get plain language; the
  TeX log goes to the server log, and resume content never goes to either.
- **Never log prompts, model replies or API keys.**
- `backend/.env` is git-ignored and must stay that way. `.env.example` carries
  the shape with placeholder keys.
- Validation errors name fields the way the *form* names them ("Projects,
  entry 1, link"), not by schema path — the path goes to the log.
- The frontend mirrors backend validation rules deliberately; if you change a
  rule in `schema.py`, change it in `validation.ts` too.
