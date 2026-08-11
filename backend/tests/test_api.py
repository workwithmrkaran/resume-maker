"""End-to-end API tests, including a real LaTeX compile.

The compile tests are skipped automatically when no TeX engine is installed,
so the suite stays runnable outside the Docker image.
"""

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
