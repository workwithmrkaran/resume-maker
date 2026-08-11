#!/usr/bin/env python
"""Regenerate the shipped template preview assets.

    cd backend && python scripts/build_previews.py

The gallery serves `app/static/previews/<template>.{pdf,png}` — files committed
to the repo — so browsing templates needs no TeX installation at all. Run this
whenever a template's layout changes, and commit the result. Needs a working
LaTeX engine (and poppler, for the thumbnail).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.compile import CompileError, compile_pdf, render_first_page_png  # noqa: E402
from app.sample import SAMPLE_RESUME  # noqa: E402
from app.templates_registry import TEMPLATES, render_resume  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "previews"
THUMBNAIL_DPI = 140


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = False

    for template_id in TEMPLATES:
        try:
            pdf = compile_pdf(render_resume(SAMPLE_RESUME, template_id)).pdf_bytes
        except CompileError as exc:
            print(f"FAIL  {template_id}: {exc}\n{exc.log_excerpt}")
            failed = True
            continue

        (OUT_DIR / f"{template_id}.pdf").write_bytes(pdf)
        print(f"ok    {template_id}.pdf  ({len(pdf):,} bytes)")

        png = render_first_page_png(pdf, dpi=THUMBNAIL_DPI)
        if png is None:
            print(f"warn  {template_id}.png skipped — poppler (pdftoppm) not found")
            failed = True
            continue
        (OUT_DIR / f"{template_id}.png").write_bytes(png)
        print(f"ok    {template_id}.png  ({len(png):,} bytes)")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
