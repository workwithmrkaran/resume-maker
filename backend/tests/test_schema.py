"""Validation rules that keep bad input away from the compiler."""

import pytest
from pydantic import ValidationError

from app.schema import Contact, Experience, Link, Resume, SkillGroup


def test_name_is_required():
    with pytest.raises(ValidationError):
        Resume(contact=Contact(full_name=""))


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        Contact(full_name="Sam", nickname="Sammy")


def test_field_length_is_capped():
    with pytest.raises(ValidationError):
        Contact(full_name="x" * 500)


def test_bullet_count_is_capped():
    with pytest.raises(ValidationError):
        Experience(title="A", company="B", bullets=[f"b{i}" for i in range(50)])


def test_blank_bullets_dropped():
    exp = Experience(title="A", company="B", bullets=["real", "  ", ""])
    assert exp.bullets == ["real"]


def test_empty_skill_groups_dropped():
    resume = Resume(
        contact=Contact(full_name="Sam"),
        skills=[SkillGroup(category="Empty", skills=[]),
                SkillGroup(category="Real", skills=["Python"])],
    )
    assert [g.category for g in resume.skills] == ["Real"]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd",
                                 "data:text/html,<script>"])
def test_dangerous_link_schemes_rejected(url):
    with pytest.raises(ValidationError):
        Link(label="x", url=url)


def test_bare_domain_gets_https():
    assert Link(label="x", url="github.com/sam").url == "https://github.com/sam"


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        Contact(full_name="Sam", email="not-an-email")


def test_whitespace_is_stripped():
    assert Contact(full_name="  Sam Doe  ").full_name == "Sam Doe"
