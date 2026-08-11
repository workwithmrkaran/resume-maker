"""Every template, held to the same contract.

Adding a template means adding a `.tex.j2` and a registry entry — these tests
then apply to it automatically, so a new layout cannot quietly break escaping,
drop a section, or fail to compile.
"""

import pytest

from app import compile as compiler
from app.sample import SAMPLE_RESUME
from app.schema import (Contact, Education, Experience, Link, Project,
                        Publication, Resume, SkillGroup)
from app.templates_registry import TEMPLATES, render_resume

TEMPLATE_IDS = sorted(TEMPLATES)

needs_latex = pytest.mark.skipif(
    not compiler.engine_available(), reason="no LaTeX engine available"
)

# Every LaTeX metacharacter, in every field a user can type into.
HOSTILE = Resume(
    contact=Contact(
        full_name=r"Bobby \write18{id} Tables & Sons 100%",
        headline=r"C# dev — $100k_year ^2 ~tilde~",
        email="bobby@example.com",
        phone="+1 (555) 000-0000",
        location=r"Somewhere {braces} & co",
        links=[Link(label=r"my_site & more", url="https://example.com/a?b=1&c=2~d")],
    ),
    summary=r"Saved \$1M & cut costs 30%. \end{document} \input{/etc/passwd}",
    experience=[Experience(
        title=r"\textbf{Engineer}", company=r"A&B_Corp #1",
        location=r"100% remote", start_date="2020", end_date="Present",
        bullets=[r"Grew revenue 50% & shipped $2M", r"Used C++ & C#"],
    )],
    education=[Education(
        degree=r"B.S. #1", institution=r"University of {X} & Y",
        grade=r"3.8/4.0 ~ top 5%", details=r"Thesis on \LaTeX & typography",
        start_date="2015", end_date="2019",
    )],
    skills=[SkillGroup(category=r"Languages & tools", skills=["C#", "F#", "100%"])],
    projects=[Project(
        name=r"proj_name #2", role=r"Author & maintainer",
        url="https://example.com/p?x=1&y=2",
        description=r"Does 100% of the thing & more",
        bullets=[r"Handles $ & % correctly"],
    )],
    publications=[Publication(
        title=r"On \write18 and Other Hazards", authors=r"A. B. & C. D.",
        venue=r"Journal of {Things} & Stuff", year="2024",
        url="https://example.com/paper?id=1&v=2",
    )],
)


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_renders_the_full_sample(template_id):
    tex = render_resume(SAMPLE_RESUME, template_id)
    assert tex.strip().endswith(r"\end{document}")
    assert "Alex Rivera" in tex
    assert "Northwind Data" in tex          # experience
    assert "University of Texas" in tex     # education
    assert "queuelite" in tex               # projects
    assert "Backpressure Without Tears" in tex  # publications
    assert "Kubernetes" in tex              # skills


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_renders_a_minimal_resume(template_id):
    """A name and nothing else must not produce a broken document."""
    tex = render_resume(Resume(contact=Contact(full_name="Sam Doe")), template_id)
    assert "Sam Doe" in tex
    assert tex.strip().endswith(r"\end{document}")


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_hostile_input_is_escaped(template_id):
    tex = render_resume(HOSTILE, template_id)
    # The document body must contain no live command from user input. The
    # preamble legitimately uses these, so only check after \begin{document}.
    body = tex.split(r"\begin{document}", 1)[1]
    assert r"\write18" not in body
    assert r"\input{" not in body
    assert r"\end{document}\documentclass" not in body
    assert r"A\&B\_Corp \#1" in body


@needs_latex
@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_sample_compiles(template_id):
    pdf = compiler.compile_pdf(render_resume(SAMPLE_RESUME, template_id)).pdf_bytes
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


@needs_latex
@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_hostile_input_compiles(template_id):
    """Escaping is the security boundary: it must hold in every template."""
    pdf = compiler.compile_pdf(render_resume(HOSTILE, template_id)).pdf_bytes
    assert pdf.startswith(b"%PDF")


@needs_latex
@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_minimal_resume_compiles(template_id):
    resume = Resume(contact=Contact(full_name="Sam Doe"))
    assert compiler.compile_pdf(render_resume(resume, template_id)).pdf_bytes


@pytest.mark.parametrize("template_id", TEMPLATE_IDS)
def test_shipped_preview_assets_exist(template_id):
    """The gallery serves these, so a new template must ship them too."""
    from app.main import PREVIEW_DIR

    assert (PREVIEW_DIR / f"{template_id}.pdf").exists(), (
        f"run scripts/build_previews.py and commit {template_id}.pdf"
    )
    assert (PREVIEW_DIR / f"{template_id}.png").exists()


def test_catalogue_is_described_for_users():
    for template in TEMPLATES.values():
        assert template.name and template.description and template.best_for
