"""Rendering: the template must never emit unescaped user text."""

import pytest

from app.sample import SAMPLE_RESUME
from app.schema import Contact, Experience, Link, Publication, Resume, SkillGroup
from app.templates_registry import render_resume


def test_sample_renders_all_sections():
    tex = render_resume(SAMPLE_RESUME)
    for section in ("Summary", "Experience", "Education", "Skills",
                    "Projects", "Publications"):
        assert f"\\section{{{section}}}" in tex
    assert tex.strip().endswith(r"\end{document}")


def test_optional_sections_omitted_when_empty():
    tex = render_resume(Resume(contact=Contact(full_name="Sam Doe")))
    for section in ("Summary", "Experience", "Education", "Skills",
                    "Projects", "Publications"):
        assert f"\\section{{{section}}}" not in tex
    assert "Sam Doe" in tex


def test_user_text_is_escaped_in_output():
    resume = Resume(
        contact=Contact(full_name="A&B Corp $tester"),
        summary=r"Grew revenue 50% \write18{whoami}",
    )
    tex = render_resume(resume)
    assert r"A\&B Corp \$tester" in tex
    assert r"50\%" in tex
    assert r"\write18" not in tex


def test_repeating_sections_render_every_entry():
    resume = Resume(
        contact=Contact(full_name="Sam Doe"),
        experience=[
            Experience(title=f"Role {i}", company=f"Company {i}",
                       bullets=[f"Did thing {i}"])
            for i in range(5)
        ],
    )
    tex = render_resume(resume)
    for i in range(5):
        assert f"Role {i}" in tex
        assert f"Did thing {i}" in tex


def test_date_range_formats():
    resume = Resume(
        contact=Contact(full_name="Sam Doe"),
        experience=[
            Experience(title="A", company="X", start_date="2020", end_date="2024"),
            Experience(title="B", company="Y", start_date="2019"),
            Experience(title="C", company="Z"),
        ],
    )
    tex = render_resume(resume)
    assert "2020 -- 2024" in tex
    assert "2019" in tex


def test_links_render_as_href():
    resume = Resume(contact=Contact(
        full_name="Sam Doe",
        links=[Link(label="GitHub", url="https://github.com/sam")],
    ))
    tex = render_resume(resume)
    assert r"\href{https://github.com/sam}{GitHub}" in tex


def test_skills_joined_with_category():
    resume = Resume(
        contact=Contact(full_name="Sam Doe"),
        skills=[SkillGroup(category="Languages", skills=["Python", "C#"])],
    )
    tex = render_resume(resume)
    assert r"\textbf{Languages:} Python, C\#" in tex


def test_publication_fragments_are_space_separated():
    resume = Resume(
        contact=Contact(full_name="Sam Doe"),
        publications=[Publication(title="A Paper", authors="S. Doe",
                                  venue="ICML", year="2025")],
    )
    tex = render_resume(resume)
    line = next(ln for ln in tex.splitlines() if "A Paper" in ln)
    assert "}. ICML. 2025." in line


def test_unknown_template_rejected():
    with pytest.raises(KeyError):
        render_resume(SAMPLE_RESUME, "does-not-exist")
