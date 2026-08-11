"""Template catalogue.

Adding a template in Phase 3 means adding a `.tex.j2` file plus one entry
here — no changes to the schema, the form, or the compile pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .latex import escape_latex, link_display, render
from .schema import Resume


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    best_for: str
    source: str  # filename under app/templates/
    # Render-time knobs baked into the template file (not user-settable in
    # Phase 1, but they keep the .tex free of magic numbers).
    options: Dict[str, Any] = field(default_factory=dict)

    def as_public_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "best_for": self.best_for,
            "preview_url": f"/api/templates/{self.id}/preview.png",
            "preview_pdf_url": f"/api/templates/{self.id}/preview.pdf",
        }


TEMPLATES: Dict[str, Template] = {
    "classic": Template(
        id="classic",
        name="Classic",
        description="Clean single-column layout with clear section rules.",
        best_for="ATS-friendly; good for industry roles across most fields.",
        source="classic.tex.j2",
        options={"font_size": 11, "margin": "1.6cm"},
    ),
    "compact": Template(
        id="compact",
        name="Compact",
        description="Small-caps headings and a centred header with icons; fits "
                    "a lot on one page.",
        best_for="Long histories and academic CVs — publications sit naturally "
                 "alongside experience.",
        source="compact.tex.j2",
        options={"font_size": 11, "scale": 0.9},
    ),
    "modern": Template(
        id="modern",
        name="Modern",
        description="Sans-serif, with bold rules under each heading and the "
                    "employer leading each entry.",
        best_for="Tech and product roles; reads well when recruiters skim "
                 "company names first.",
        source="modern.tex.j2",
        options={"font_size": 11},
    ),
    "technical": Template(
        id="technical",
        name="Technical",
        description="Dense two-column header, education first, skills summary "
                    "near the top.",
        best_for="Students and early-career engineers, where coursework and "
                 "the skills list carry weight.",
        source="technical.tex.j2",
        options={"font_size": 11},
    ),
}

DEFAULT_TEMPLATE_ID = "classic"


def get_template(template_id: str) -> Template:
    try:
        return TEMPLATES[template_id]
    except KeyError:
        raise KeyError(f"Unknown template: {template_id}") from None


def _daterange(entry: Dict[str, Any]) -> str:
    """Join an entry's start/end dates for display.

    Returned pre-escaped because the dash between them is literal LaTeX.
    """
    start = escape_latex(entry.get("start_date", ""))
    end = escape_latex(entry.get("end_date", ""))
    if start and end:
        return f"{start} -- {end}"
    return start or end


def render_resume(resume: Resume, template_id: str = DEFAULT_TEMPLATE_ID) -> str:
    """Render a validated resume into LaTeX source for the given template."""
    from .latex import _Raw  # local import: internal marker type

    template = get_template(template_id)
    context: Dict[str, Any] = resume.model_dump()
    context.update(template.options)
    context["daterange"] = lambda entry: _Raw(_daterange(entry))
    context["link_display"] = link_display
    return render(template.source, context)


def list_templates() -> List[Dict[str, str]]:
    return [t.as_public_dict() for t in TEMPLATES.values()]
