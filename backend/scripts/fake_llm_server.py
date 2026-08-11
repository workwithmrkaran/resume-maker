#!/usr/bin/env python
"""A stand-in for the model API, for local development and the browser e2e run.

    python scripts/fake_llm_server.py &            # listens on :9001
    LLM_PROVIDER_1_MODEL=fake \\
    LLM_PROVIDER_1_API_KEY=fake \\
    LLM_PROVIDER_1_BASE_URL=http://127.0.0.1:9001/v1 \\
    uvicorn app.main:app --port 8000

It speaks enough of the OpenAI chat-completions API for the real SDK to talk to
it, so the upload path can be exercised without spending quota — and without
the flow silently passing because a mock was too generous.

`FAKE_LLM_STATUS` makes it fail instead (e.g. 429), which is how you watch the
provider chain fail over to the next key for real.
"""

from __future__ import annotations

import json
import os
import re

from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

FAIL_STATUS = int(os.getenv("FAKE_LLM_STATUS", "0"))


def _guess(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


def _build_resume(prompt: str) -> dict:
    """Pull a few obvious things out of the prompt.

    Just enough that the response reflects the uploaded document rather than a
    fixed fixture — otherwise an e2e run proves nothing about the plumbing.
    """
    lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
    body = [ln for ln in lines if not ln.startswith("---")]
    name = next((ln for ln in body if 2 <= len(ln.split()) <= 4
                 and ln[:1].isupper() and "@" not in ln), "Unknown")
    email = _guess(r"([\w.+-]+@[\w-]+\.[\w.]+)", prompt)
    return {
        "contact": {
            "full_name": name,
            "headline": "",
            "email": email or None,
            "phone": _guess(r"((?:\+\d[\d\s().-]{7,})|\d{3}-\d{4})", prompt),
            "location": "",
            "links": [],
        },
        "summary": _guess(r"SUMMARY\s*\n(.+)", prompt),
        "experience": [{
            "title": _guess(r"\n([A-Z][\w /]+Engineer[\w ]*)", prompt, "Engineer"),
            "company": _guess(r"Engineer,?\s+([A-Z][\w &]+)", prompt, "Unknown"),
            "location": "",
            "start_date": _guess(r"\(([A-Za-z]{3} \d{4})", prompt),
            "end_date": "Present" if "Present" in prompt else "",
            "bullets": [ln.lstrip("-• ").strip() for ln in body
                        if ln.startswith(("-", "•"))][:6],
        }],
        "education": [],
        "skills": [],
        "projects": [],
        "publications": [],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    if FAIL_STATUS:
        raise HTTPException(status_code=FAIL_STATUS, detail="simulated failure")

    payload = await request.json()
    # Only the user turn: the system prompt's own bullet list would otherwise
    # be scraped as if it were resume content.
    prompt = "\n".join(m.get("content", "") for m in payload.get("messages", [])
                       if m.get("role") == "user")
    return {
        "id": "fake-1",
        "object": "chat.completion",
        "model": payload.get("model", "fake"),
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant",
                        "content": json.dumps(_build_resume(prompt))},
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("FAKE_LLM_PORT", "9001")))
