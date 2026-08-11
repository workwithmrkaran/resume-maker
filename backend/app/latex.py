"""LaTeX escaping and Jinja2 rendering.

Two rules govern this module:

1. No user-supplied string reaches the `.tex` file without going through
   :func:`escape_latex`. The Jinja2 environment enforces this by installing
   the escaper as the environment-wide finalizer, so a template author cannot
   forget it.
2. Jinja2's default delimiters collide with LaTeX syntax, so we use
   `\\VAR{...}`, `\\BLOCK{...}` and `\\#{...}` instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent / "templates"

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# One pass over the input, so that the replacements themselves — which contain
# backslashes and braces — are never re-escaped. Doing this as a sequence of
# str.replace calls is subtly wrong in either order.
_SPECIAL = re.compile("|".join(re.escape(c) for c in _ESCAPES))

# Control characters (other than newline/tab) have no meaning in a resume and
# can confuse the TeX engine.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")


def escape_latex(value: Any) -> str:
    """Escape a value for safe interpolation into a LaTeX document.

    ``None`` becomes an empty string so optional fields render as nothing
    rather than the literal text "None".
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)

    value = _CONTROL_CHARS.sub("", value)
    value = _SPECIAL.sub(lambda m: _ESCAPES[m.group()], value)
    # A blank line inside a field would start a new LaTeX paragraph in the
    # middle of, say, a bullet point. Collapse them to single line breaks.
    value = re.sub(r"\n{2,}", r"\\\\ ", value)
    value = value.replace("\n", " ")
    return value


def escape_url(value: Any) -> str:
    r"""Escape a URL for use inside ``\href{...}``.

    Narrower than the text escaper: the URL has to survive as a working link,
    so only what TeX cannot swallow raw is escaped.

    ``&`` matters more than it looks. Raw, it is a cell separator, and a query
    string inside a ``tabular`` cell derails \href's argument scanning with
    "Forbidden control sequence found" — a compile failure from an ordinary
    ``?a=1&b=2`` link. ``\&`` reaches hyperref as a plain ``&``.

    ``~`` is deliberately left alone: ``\~{}`` would land in the link target
    literally and break the URL.
    """
    if not value:
        return ""
    value = _CONTROL_CHARS.sub("", str(value)).strip()
    for char in ("\\", "{", "}", "%", "#", "&"):
        value = value.replace(char, "\\" + char)
    return value


def link_display(url: str) -> str:
    """Human-friendly form of a URL for the visible link text."""
    text = re.sub(r"^(https?://)?(www\.)?", "", (url or "").strip())
    return text.rstrip("/")


def _finalize(value: Any) -> str:
    """Environment-wide finalizer: everything is escaped by default.

    Values that a template has *deliberately* marked safe (via the ``url``
    filter, or literal LaTeX produced inside the template) are wrapped in
    :class:`_Raw` and pass through untouched.
    """
    if isinstance(value, _Raw):
        return str(value)
    return escape_latex(value)


class _Raw(str):
    """A string that has already been escaped appropriately."""


def _url_filter(value: Any) -> _Raw:
    return _Raw(escape_url(value))


def _display_filter(value: Any) -> str:
    return link_display(str(value or ""))


def build_environment(template_dir: Path | None = None) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir or TEMPLATE_DIR)),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        line_statement_prefix="%%",
        line_comment_prefix="%#",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,  # we escape via `finalize` instead — LaTeX, not HTML
        finalize=_finalize,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


_env: Environment | None = None


def get_environment() -> Environment:
    global _env
    if _env is None:
        env = build_environment()
        env.filters["url"] = _url_filter
        env.filters["display"] = _display_filter
        _env = env
    return _env


def render(template_name: str, data: dict) -> str:
    """Render a resume dict into LaTeX source."""
    return get_environment().get_template(template_name).render(**data)
