"""Canonical resume data schema.

This is the single source of truth shared by:
  * the manual-fill form (Phase 1),
  * the AI extraction step (Phase 2 — must emit exactly this shape),
  * every template's Jinja2 render step.

Keeping templates downstream of this schema is what lets Phase 3 add new
templates without touching the data layer.
"""

from __future__ import annotations

import re
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Field length caps. These are deliberately generous but finite: unbounded text
# is both a compile hazard (a 5MB paragraph will blow the compile timeout) and
# an abuse vector on a free service.
SHORT = 120
MEDIUM = 300
LONG = 2000

MAX_EXPERIENCE = 15
MAX_EDUCATION = 10
MAX_PROJECTS = 15
MAX_PUBLICATIONS = 30
MAX_SKILL_GROUPS = 12
MAX_BULLETS = 12
MAX_LINKS = 8

ShortStr = Annotated[str, Field(max_length=SHORT)]
MediumStr = Annotated[str, Field(max_length=MEDIUM)]

# Dates are free text on purpose ("Jan 2023", "2023-01", "Present", "Summer
# 2024"). Resumes use wildly inconsistent date formats and forcing a picker
# makes the form worse, not better. We only bound the length.
DateStr = Annotated[str, Field(max_length=40)]


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Link(_Base):
    """A labelled contact link (LinkedIn, GitHub, portfolio, ...)."""

    label: ShortStr
    url: MediumStr

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: str) -> str:
        """Only allow http(s) and mailto.

        The template turns links into clickable `\\href` targets, so a
        `javascript:` or `file:` URL would be embedded in the PDF verbatim.
        """
        if not v:
            return v
        if re.match(r"^(https?://|mailto:)", v, re.IGNORECASE):
            return v
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", v, re.IGNORECASE):
            return f"https://{v}"  # bare domain typed by the user
        raise ValueError("Link must be an http(s) URL")


class Contact(_Base):
    full_name: Annotated[str, Field(min_length=1, max_length=SHORT)]
    headline: ShortStr = ""
    email: Optional[EmailStr] = None
    phone: ShortStr = ""
    location: ShortStr = ""
    links: Annotated[List[Link], Field(max_length=MAX_LINKS)] = []


class Experience(_Base):
    title: Annotated[str, Field(min_length=1, max_length=SHORT)]
    company: Annotated[str, Field(min_length=1, max_length=SHORT)]
    location: ShortStr = ""
    start_date: DateStr = ""
    end_date: DateStr = ""
    bullets: Annotated[List[Annotated[str, Field(max_length=LONG)]],
                       Field(max_length=MAX_BULLETS)] = []

    @field_validator("bullets")
    @classmethod
    def _drop_empty(cls, v: List[str]) -> List[str]:
        return [b for b in v if b.strip()]


class Education(_Base):
    degree: Annotated[str, Field(min_length=1, max_length=SHORT)]
    institution: Annotated[str, Field(min_length=1, max_length=SHORT)]
    location: ShortStr = ""
    start_date: DateStr = ""
    end_date: DateStr = ""
    grade: ShortStr = ""
    details: MediumStr = ""


class SkillGroup(_Base):
    """One labelled row of skills, e.g. "Languages: Python, Go, SQL"."""

    category: ShortStr = ""
    skills: Annotated[List[ShortStr], Field(max_length=40)] = []

    @field_validator("skills")
    @classmethod
    def _drop_empty(cls, v: List[str]) -> List[str]:
        return [s for s in v if s.strip()]


class Project(_Base):
    name: Annotated[str, Field(min_length=1, max_length=SHORT)]
    role: ShortStr = ""
    url: MediumStr = ""
    start_date: DateStr = ""
    end_date: DateStr = ""
    description: Annotated[str, Field(max_length=LONG)] = ""
    bullets: Annotated[List[Annotated[str, Field(max_length=LONG)]],
                       Field(max_length=MAX_BULLETS)] = []

    @field_validator("bullets")
    @classmethod
    def _drop_empty(cls, v: List[str]) -> List[str]:
        return [b for b in v if b.strip()]

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: str) -> str:
        return Link._safe_url(v) if v else v


class Publication(_Base):
    title: Annotated[str, Field(min_length=1, max_length=MEDIUM)]
    authors: MediumStr = ""
    venue: MediumStr = ""
    year: Annotated[str, Field(max_length=20)] = ""
    url: MediumStr = ""

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: str) -> str:
        return Link._safe_url(v) if v else v


class Resume(_Base):
    """The canonical resume document."""

    contact: Contact
    summary: Annotated[str, Field(max_length=LONG)] = ""
    experience: Annotated[List[Experience], Field(max_length=MAX_EXPERIENCE)] = []
    education: Annotated[List[Education], Field(max_length=MAX_EDUCATION)] = []
    skills: Annotated[List[SkillGroup], Field(max_length=MAX_SKILL_GROUPS)] = []
    projects: Annotated[List[Project], Field(max_length=MAX_PROJECTS)] = []
    publications: Annotated[List[Publication], Field(max_length=MAX_PUBLICATIONS)] = []

    @field_validator("skills")
    @classmethod
    def _drop_empty_groups(cls, v: List[SkillGroup]) -> List[SkillGroup]:
        return [g for g in v if g.skills]


class CompileRequest(_Base):
    template_id: Annotated[str, Field(max_length=64)] = "classic"
    resume: Resume


class JobStatus(_Base):
    job_id: str
    status: str  # queued | running | done | error
    kind: str = "compile"
    # Plain-language status line for the UI — never a raw compiler error.
    message: str = ""
    download_url: Optional[str] = None
    # Extraction jobs only:
    resume: Optional[Resume] = None
    confidence: Optional[float] = None
    low_confidence: bool = False
    warnings: List[str] = []
