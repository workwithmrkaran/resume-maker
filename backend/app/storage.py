"""Short-lived storage for generated PDFs.

Generated resumes are personal data, so they live on disk only long enough for
the user to download them (``PDF_TTL_SECONDS``, default 1 hour) and are swept
on every access plus by a periodic task. Swapping this for S3 with a lifecycle
rule means reimplementing :class:`PdfStore` — nothing above it changes.
"""

from __future__ import annotations

import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PDF_TTL_SECONDS = int(os.getenv("PDF_TTL_SECONDS", str(60 * 60)))
# Default under the OS temp dir so this works on Windows too, where "/tmp"
# would land in a surprising place like C:\tmp.
STORE_DIR = Path(os.getenv("PDF_STORE_DIR")
                 or Path(tempfile.gettempdir()) / "resume-maker-pdfs")


@dataclass
class StoredPdf:
    token: str
    path: Path
    filename: str
    created_at: float


class PdfStore:
    def __init__(self, directory: Path = STORE_DIR, ttl: int = PDF_TTL_SECONDS):
        self.directory = directory
        self.ttl = ttl
        self.directory.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, StoredPdf] = {}

    def put(self, pdf_bytes: bytes, filename: str) -> StoredPdf:
        token = secrets.token_urlsafe(24)
        path = self.directory / f"{token}.pdf"
        path.write_bytes(pdf_bytes)
        path.chmod(0o600)
        entry = StoredPdf(token=token, path=path, filename=filename,
                          created_at=time.time())
        self._entries[token] = entry
        self.sweep()
        return entry

    def get(self, token: str) -> Optional[StoredPdf]:
        self.sweep()
        entry = self._entries.get(token)
        if entry is None or not entry.path.exists():
            return None
        return entry

    def sweep(self) -> int:
        """Delete expired PDFs. Returns how many were removed."""
        cutoff = time.time() - self.ttl
        removed = 0
        for token, entry in list(self._entries.items()):
            if entry.created_at < cutoff:
                entry.path.unlink(missing_ok=True)
                self._entries.pop(token, None)
                removed += 1
        # Also catch files left behind by a previous process.
        for stray in self.directory.glob("*.pdf"):
            try:
                if stray.stat().st_mtime < cutoff:
                    stray.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                pass
        return removed


store = PdfStore()
