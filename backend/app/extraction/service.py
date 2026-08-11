"""Turn resume text into a validated :class:`Resume`.

The contract is deliberately narrow: the model transcribes, it does not write.
Everything it returns is validated against the same schema the manual form
produces, and the user reviews it before anything is compiled — the product
plan makes that review step mandatory, so this layer never has to be perfect,
only honest about how sure it is.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ..llm import LlmClient, LlmError, get_client
from ..schema import Contact, Resume
from .text import ExtractedText, extract_text

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You extract structured data from resumes. You are a transcriber, not a writer.

Rules:
- Return ONE JSON object and nothing else. No markdown fences, no commentary.
- Copy the candidate's own wording. Never invent, embellish, translate or
  summarise. If a fact is not in the text, leave the field empty ("") or the
  list empty ([]).
- Dates stay exactly as written ("Mar 2022", "2019", "Summer 2021",
  "Present"). Do not reformat or infer them.
- Split each role's responsibilities into separate bullet strings, without
  leading dashes or bullet characters.
- Skills: group them under the headings the resume itself uses (e.g.
  "Languages"). If it has no headings, use one group with an empty category.
- `headline` is a short professional title line if the resume has one under
  the name; otherwise "".
- Put the most recent experience and education first.

The JSON must match this schema exactly, with no extra keys:

{schema}
"""

USER_PROMPT = """\
Extract the resume below into the JSON object.

--- RESUME TEXT START ---
{text}
--- RESUME TEXT END ---
"""

REPAIR_PROMPT = """\
Your previous reply was not valid against the schema. The errors were:

{errors}

Return the corrected JSON object only.
"""

# Enough to notice a resume came back near-empty, without pretending to be a
# calibrated probability.
CONFIDENCE_LOW = 0.45


@dataclass
class ExtractionResult:
    resume: Resume
    confidence: float
    provider: str
    warnings: List[str] = field(default_factory=list)

    @property
    def low_confidence(self) -> bool:
        return self.confidence < CONFIDENCE_LOW


class ExtractionFailed(Exception):
    """Extraction could not produce usable data. Message is user-facing."""


def _schema_for_prompt() -> str:
    """A trimmed JSON Schema — descriptions and defaults are noise here."""
    schema = Resume.model_json_schema()
    return json.dumps(schema, separators=(",", ":"))


def _strip_wrappers(text: str) -> str:
    """Recover the JSON object from a chatty or fenced reply."""
    # Reasoning models sometimes emit their scratchpad inline.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    return text.strip()


def parse_resume_json(raw: str) -> Dict[str, Any]:
    payload = json.loads(_strip_wrappers(raw))
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload


def coerce(payload: Dict[str, Any]) -> Resume:
    """Validate, after smoothing over the shapes models habitually get wrong.

    The schema forbids unknown keys, so a single invented field would otherwise
    throw away an entire good extraction.
    """
    return Resume.model_validate(_normalise(payload))


def _normalise(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = {k: v for k, v in payload.items() if k in Resume.model_fields}

    contact = {k: v for k, v in dict(data.get("contact") or {}).items()
               if k in Contact.model_fields}
    if not contact.get("full_name"):
        contact["full_name"] = "Unknown"  # the review screen will fix this
    # Models write "" for a missing email; the schema wants null.
    if isinstance(contact.get("email"), str) and not contact["email"].strip():
        contact["email"] = None
    links = []
    for link in contact.get("links") or []:
        if isinstance(link, str):
            link = {"label": "", "url": link}
        if isinstance(link, dict) and (link.get("url") or "").strip():
            links.append({"label": link.get("label") or "", "url": link["url"]})
    contact["links"] = links
    data["contact"] = contact

    # Models sometimes return a flat list of skill strings instead of groups.
    skills = data.get("skills")
    if isinstance(skills, list) and skills and all(isinstance(s, str) for s in skills):
        data["skills"] = [{"category": "", "skills": skills}]

    for section in ("experience", "projects"):
        for entry in data.get(section) or []:
            if isinstance(entry, dict) and isinstance(entry.get("bullets"), str):
                entry["bullets"] = [entry["bullets"]]
    return data


def score_confidence(resume: Resume, source: ExtractedText) -> float:
    """A rough "did we get most of it?" signal, not a probability.

    It drives one thing: whether the review screen says "check this carefully"
    a bit louder.
    """
    signals = [
        bool(resume.contact.full_name and resume.contact.full_name != "Unknown"),
        bool(resume.contact.email or resume.contact.phone or resume.contact.links),
        bool(resume.experience),
        bool(resume.education or resume.projects),
        bool(resume.skills),
        bool(resume.summary),
    ]
    score = sum(signals) / len(signals)

    # A long source that produced very little structure means we missed things
    # — a two-column layout, say, or an unusual section order.
    captured = sum(len(b) for job in resume.experience for b in job.bullets)
    captured += len(resume.summary)
    if len(source.text) > 1500 and captured < len(source.text) * 0.15:
        score *= 0.6
    return round(min(score, 1.0), 2)


def extract_resume(data: bytes, filename: str,
                   client: Optional[LlmClient] = None) -> ExtractionResult:
    """Full pipeline: bytes → text → model → validated resume."""
    source = extract_text(data, filename)
    client = client or get_client()

    system = SYSTEM_PROMPT.format(schema=_schema_for_prompt())
    user = USER_PROMPT.format(text=source.text)

    try:
        raw, provider = client.complete_json(system, user, Resume.model_json_schema())
    except LlmError as exc:
        log.warning("extraction: all providers failed: %s", exc)
        raise ExtractionFailed(
            "Our reader is unavailable right now. You can still fill the form "
            "in yourself — everything else works."
        ) from None

    try:
        resume = coerce(parse_resume_json(raw))
    except (ValueError, ValidationError) as first_error:
        # One repair round. Models fix their own schema violations reliably
        # when told exactly what broke; a second round rarely adds anything.
        log.info("extraction: invalid payload from %s, requesting repair",
                 provider.name)
        try:
            repair = user + "\n" + REPAIR_PROMPT.format(
                errors=_error_summary(first_error))
            raw, provider = client.complete_json(
                system, repair, Resume.model_json_schema())
            resume = coerce(parse_resume_json(raw))
        except (ValueError, ValidationError, LlmError) as second_error:
            log.warning("extraction: repair failed (%s)", type(second_error).__name__)
            raise ExtractionFailed(
                "We couldn't make sense of that resume. Please fill the form "
                "in yourself — your details are safer typed than guessed."
            ) from None

    confidence = score_confidence(resume, source)
    warnings = list(source.warnings)
    if confidence < CONFIDENCE_LOW:
        warnings.append(
            "We filled in what we could, but some sections look incomplete — "
            "please check every field carefully."
        )
    return ExtractionResult(resume=resume, confidence=confidence,
                            provider=provider.name, warnings=warnings)


def _error_summary(error: Exception, limit: int = 12) -> str:
    """Field-level errors for the repair prompt — no resume values included."""
    if isinstance(error, ValidationError):
        lines = [
            f"- {'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in error.errors()[:limit]
        ]
        return "\n".join(lines)
    return f"- The reply was not valid JSON ({error})"
