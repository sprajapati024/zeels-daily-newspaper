"""Safe inline markup for newspaper prose.

Every input string is HTML-escaped first, so no tag, attribute or entity
from research/story input can ever reach the output as live markup. A tiny,
fixed set of emphasis is then re-enabled on top of the *escaped* text:

    **bold text**   -> <b>bold text</b>
    *italic text*   -> <i>italic text</i>
    _italic text_   -> <i>italic text</i>

Because escaping runs before the emphasis substitution, an attacker who
writes literal `<b>` in a story field sees `&lt;b&gt;` in the output, not a
real bold tag -- there is no way to smuggle arbitrary HTML through these
fields.
"""
from __future__ import annotations

import re
from html import escape
from urllib.parse import urlsplit

ALLOWED_LINK_SCHEMES = {"http", "https"}

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = re.compile(r"_(.+?)_")


def render_inline(text: str) -> str:
    """Escape ``text`` and re-enable controlled **bold**/*italic* emphasis."""
    out = escape(text)
    out = _BOLD_RE.sub(r"<b>\1</b>", out)
    out = _ITALIC_STAR_RE.sub(r"<i>\1</i>", out)
    out = _ITALIC_UNDERSCORE_RE.sub(r"<i>\1</i>", out)
    return out


def render_paragraphs(paragraphs: list[str], *, css_class: str | None = None) -> str:
    cls = f' class="{css_class}"' if css_class else ""
    return "\n".join(f"<p{cls}>{render_inline(p)}</p>" for p in paragraphs)


class UnsafeUrlError(ValueError):
    """Raised when a URL is not a direct http(s) link."""


def validate_url(url: str) -> str:
    """Return ``url`` unchanged if it is a direct http(s) link, else raise."""
    scheme = urlsplit(url).scheme.lower()
    if scheme not in ALLOWED_LINK_SCHEMES:
        raise UnsafeUrlError(f"link must be http(s): {url!r}")
    return url


def render_link(label: str, url: str) -> str:
    """Render a single ``<a>`` tag. ``url`` must already be validated."""
    safe_href = escape(url, quote=True)
    return f'<a href="{safe_href}">{render_inline(label)}</a>'
