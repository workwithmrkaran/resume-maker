"""End-to-end API tests, including a real LaTeX compile.

The compile tests are skipped automatically when no TeX engine is installed,
so the suite stays runnable outside the Docker image.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

from app import compile as compiler
from app.main import app
from app.ratelimit import limiter

needs_latex = pytest.mark.skipif(
    not compiler.engine_available(), reason="no LaTeX engine available"
)


@pytest.fixture
def client():
    limiter._events.clear()  # each test gets a fresh rate-limit budget
    with TestClient(app) as c:
        yield c


MINIMAL = {
    "template_id": "classic",
    "resume": {
        "contact": {"full_name": "Sam Doe", "email": "sam@example.com"},
        "summary": "Engineer with 50% more & signs than usual.",
        "experience": [{
            "title": "Engineer", "company": "Acme",
            "start_date": "2020", "end_date": "Present",
            "bullets": ["Shipped things"],
        }],
    },
}


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_templates_listed(client):
    templates = client.get("/api/templates").json()["templates"]
    assert any(t["id"] == "classic" for t in templates)
    assert all({"id", "name", "description", "preview_url"} <= t.keys()
               for t in templates)


def test_compile_rejects_unknown_template(client):
    payload = {**MINIMAL, "template_id": "nope"}
    assert client.post("/api/compile", json=payload).status_code == 400


def test_compile_rejects_invalid_payload(client):
    assert client.post("/api/compile", json={"resume": {}}).status_code == 422


def _await_job(client, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.2)
    raise AssertionError("job did not finish in time")


@needs_latex
def test_full_compile_and_download(client):
    started = client.post("/api/compile", json=MINIMAL)
    assert started.status_code == 202
    job = _await_job(client, started.json()["job_id"])
    assert job["status"] == "done", job

    pdf = client.get(job["download_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert "sam-doe-resume.pdf" in pdf.headers["content-disposition"]


@needs_latex
def test_hostile_input_still_compiles(client):
    payload = {
        "template_id": "classic",
        "resume": {
            "contact": {"full_name": r"Bobby \write18{id} Tables & Sons"},
            "summary": r"100% \input{/etc/passwd} $x^2$ #hashtag _under_ ~tilde~",
            "experience": [{
                "title": r"\end{document}", "company": r"{Braces}",
                "bullets": [r"Saved \$1M & cut costs 30%"],
            }],
        },
    }
    started = client.post("/api/compile", json=payload)
    job = _await_job(client, started.json()["job_id"])
    assert job["status"] == "done", job


@needs_latex
def test_template_preview_is_a_pdf(client):
    resp = client.get("/api/templates/classic/preview.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_unknown_job_returns_404(client):
    assert client.get("/api/jobs/nope").status_code == 404


def test_expired_download_token_returns_404(client):
    body = client.get("/api/download/not-a-real-token").json()
    assert "expired" in body["error"].lower()


def test_compile_rate_limit_enforced(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main.COMPILE_LIMIT, "max_events", 3, raising=False)
    codes = [client.post("/api/compile", json=MINIMAL).status_code
             for _ in range(5)]
    assert 429 in codes
    assert codes.count(202) <= 3


def test_error_response_shape(client):
    body = client.get("/api/jobs/missing").json()
    assert set(body) == {"error"}


# --------------------------------------------------------------- portability

def test_sandbox_status_reports_limits_on_this_platform():
    status = compiler.sandbox_status()
    assert status["shell_escape_disabled"] is True
    assert status["timeout_seconds"] > 0
    assert status["resource_limits"] is (compiler.sys.platform != "win32")


def test_windows_path_skips_posix_only_options(monkeypatch, tmp_path):
    """On Windows there is no fork, so `preexec_fn` must not be passed.

    Exercised here on any platform by flipping the flag: passing preexec_fn on
    Windows raises ValueError before the engine ever runs.
    """
    captured = {}

    class FakeProc:
        returncode = 0
        stdout = b""

    def fake_run(argv, **kwargs):
        captured.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(compiler, "IS_WINDOWS", True)
    monkeypatch.setattr(compiler.subprocess, "run", fake_run)
    compiler._run_subprocess(tmp_path)

    assert "preexec_fn" not in captured
    assert "creationflags" in captured
    # The engine still needs to find its own installation.
    assert "SYSTEMROOT" in captured["env"] or "SYSTEMROOT" not in os.environ


def test_posix_path_still_applies_limits(monkeypatch, tmp_path):
    if compiler.IS_WINDOWS:  # pragma: no cover - not the CI platform
        pytest.skip("POSIX only")
    captured = {}

    class FakeProc:
        returncode = 0
        stdout = b""

    def fake_run(argv, **kwargs):
        captured.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(compiler.subprocess, "run", fake_run)
    compiler._run_subprocess(tmp_path)
    assert captured["preexec_fn"] is compiler._limits


def test_api_root_signposts_instead_of_404(client):
    body = client.get("/").json()
    assert body["health"] == "/api/health"
    assert "5173" in body["web_ui"]


def test_favicon_is_quietly_empty(client):
    assert client.get("/favicon.ico").status_code == 204


def test_validation_errors_name_fields_without_quoting_values(client):
    payload = {
        "template_id": "classic",
        "resume": {"contact": {"full_name": "Sam", "email": "definitely-not-email"}},
    }
    response = client.post("/api/compile", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["fields"] == ["Contact, email"]
    # The bad value itself must not come back to the client.
    assert "definitely-not-email" not in response.text


def test_gallery_preview_needs_no_latex_engine(client, monkeypatch):
    """The shipped sample assets must be served without touching the compiler.

    Browsing templates is the first thing a visitor does; it must not depend on
    a TeX installation being present and warm.
    """
    def explode(*args, **kwargs):
        raise AssertionError("compile_pdf must not be called for the gallery")

    monkeypatch.setattr(compiler, "compile_pdf", explode)
    from app import main

    main._preview_cache.clear()
    main._thumbnail_cache.clear()

    pdf = client.get("/api/templates/classic/preview.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    png = client.get("/api/templates/classic/preview.png")
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")


def test_validation_fields_are_named_the_way_the_form_names_them():
    """"resume.projects.0.url" means nothing to someone filling in a form."""
    from app.main import _human_field

    assert _human_field(("body", "resume", "projects", 0, "url")) == \
        "Projects, entry 1, link"
    assert _human_field(("body", "resume", "contact", "full_name")) == \
        "Contact, full name"
    assert _human_field(("body", "resume", "experience", 2, "company")) == \
        "Work experience, entry 3, company"
