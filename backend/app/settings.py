"""Environment loading.

Import this before anything reads `os.environ`, so a local `.env` (API keys,
overrides) is in place. In Docker the environment comes from compose and there
is no `.env` file — `load_dotenv` is then a no-op.
"""

from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is declared
        return
    # Real environment variables win: compose and CI must be able to override
    # whatever a developer left in .env.
    load_dotenv(ENV_FILE, override=False)


load_env()
