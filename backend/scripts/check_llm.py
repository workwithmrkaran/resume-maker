#!/usr/bin/env python
"""Live check against the configured providers.

    cd backend && python scripts/check_llm.py            # both providers
    python scripts/check_llm.py path/to/resume.pdf       # full extraction too

Calls each provider in `.env` individually, so you can see which keys still
have quota, then optionally runs a real extraction end to end. Nothing here is
part of the app — it exists because the failover path is the kind of thing you
want to have watched work at least once.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import LlmClient, load_providers  # noqa: E402
from app.extraction.service import extract_resume  # noqa: E402

PING_SYSTEM = "You reply with JSON only."
PING_USER = 'Reply with exactly {"ok": true} and nothing else.'


def check_providers() -> list[bool]:
    providers = load_providers()
    if not providers:
        print("No providers configured. Copy .env.example to .env and add keys.")
        return []

    results = []
    for provider in providers:
        label = f"{provider.name} [{provider.redacted_key}]"
        started = time.time()
        try:
            # One provider at a time, so a working fallback can't mask a dead
            # primary — which is the whole thing we're checking.
            text, _ = LlmClient([provider]).complete_json(PING_SYSTEM, PING_USER)
            elapsed = time.time() - started
            print(f"  OK    {label}  {elapsed:.1f}s  → {text.strip()[:60]}")
            results.append(True)
        except Exception as exc:  # noqa: BLE001 - this is a diagnostic
            status = getattr(exc, "status_code", None)
            detail = f" (HTTP {status})" if status else ""
            print(f"  FAIL  {label}{detail}: {type(exc).__name__}: {exc}")
            results.append(False)
    return results


def check_extraction(path: Path) -> bool:
    print(f"\nExtracting {path.name} …")
    started = time.time()
    try:
        result = extract_resume(path.read_bytes(), path.name)
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic
        print(f"  FAIL  {type(exc).__name__}: {exc}")
        return False

    print(f"  OK    {time.time() - started:.1f}s via {result.provider}, "
          f"confidence {result.confidence}")
    for warning in result.warnings:
        print(f"  note  {warning}")
    print(json.dumps(result.resume.model_dump(mode="json"), indent=2)[:2000])
    return True


def main() -> int:
    print("Checking providers in order:")
    results = check_providers()
    if not results:
        return 1

    ok = True
    if len(sys.argv) > 1:
        ok = check_extraction(Path(sys.argv[1]))

    if not any(results):
        print("\nNo provider answered — extraction will be unavailable.")
        return 1
    if not all(results):
        print("\nSome providers are down; the chain will fail over to the rest.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
