"""Render a validated newspaper :class:`~newspaper_schema.Issue` into one
XHTML fragment per desk, using only the controlled-emphasis escaping in
``newspaper_markup.py``. No section here ever emits raw HTML sourced from
issue content -- every user-supplied string passes through
:func:`newspaper_markup.render_inline` (escape, then re-enable **bold**/
*italic*) or :func:`newspaper_markup.render_link` (escaped label + a
schema-validated http(s) href).
"""
from __future__ import annotations

from zeels_daily_markup import render_inline, render_link
from zeels_daily_schema import Issue

CSS_CONTENT = """
body { font-family: Georgia, 'Iowan Old Style', serif; line-height: 1.55; margin: 5%; color: #111; }
h1 { font-size: 2em; line-height: 1.08; margin: 0 0 .25em; }
h2 { font-size: 1.45em; line-height: 1.15; margin: 1.4em 0 .35em; border-top: 3px solid #111; padding-top: .35em; }
h3 { font-size: 1.15em; line-height: 1.2; margin: 1.1em 0 .25em; }
p { margin: 0 0 .85em; }
a { color: #111; text-decoration: underline; }
.mast { text-align:center; border-top: 2px solid #111; border-bottom: 4px solid #111; padding: .45em 0 .55em; }
.mast h1 { font-size: 2.35em; letter-spacing: -.03em; }
.deck { font-style: italic; font-size: 1.08em; }
.edition { font-family: sans-serif; font-size: .72em; letter-spacing: .08em; text-transform: uppercase; }
.kicker { font-family: sans-serif; font-size: .72em; font-weight: bold; letter-spacing: .1em; text-transform: uppercase; }
.lead { font-size: 1.08em; }
.take { border-left: 4px solid #111; padding: .25em 0 .25em .75em; font-style: italic; }
.source { font-family: sans-serif; font-size: .78em; margin-top: .8em; }
.paper { border-top: 1px solid #777; padding-top: .65em; }
.stat { font-size: 1.55em; font-weight: bold; margin-bottom: .1em; }
.small { font-size: .85em; }
.center { text-align: center; }
ul { margin-top: .25em; }
""".strip()


def _take_html(take) -> str:
    return f'<p class="take"><b>{render_inline(take.label)}:</b> {render_inline(take.text)}</p>'


def render_page_one(issue: Issue) -> str:
    md = issue.metadata
    p1 = issue.page_one
    parts = [
        '<div class="mast">',
        f'<div class="edition">{render_inline(md.edition_label)}</div>',
        f'<h1>{render_inline(md.title)}</h1>',
        f'<div class="edition">{render_inline(md.day_of_week_label)} · '
        f'{render_inline(md.volume)} · {render_inline(md.edition)}</div>',
        "</div>",
        f'<p class="kicker">{render_inline(p1.kicker)}</p>',
        f'<h2 style="border-top:0">{render_inline(p1.headline)}</h2>',
        f'<p class="deck">{render_inline(p1.deck)}</p>',
    ]
    parts += [f'<p class="lead">{render_inline(para)}</p>' for para in p1.lead_paragraphs]
    if p1.take is not None:
        parts.append(_take_html(p1.take))
    parts.append(f'<p class="source">{render_link(p1.source.label, p1.source.url)}</p>')
    parts.append("<h2>Page-one index</h2>")
    parts.append("<ul>")
    parts += [f"<li><b>{render_inline(item.label)}:</b> {render_inline(item.text)}</li>" for item in p1.index]
    parts.append("</ul>")
    return "\n".join(parts)


def render_briefing(issue: Issue) -> str:
    parts = ["<h1>The Briefing</h1>"]
    for story in issue.briefing.stories:
        parts.append(f'<p class="kicker">{render_inline(story.kicker)}</p>')
        parts.append(f"<h2>{render_inline(story.headline)}</h2>")
        parts += [f"<p>{render_inline(para)}</p>" for para in story.paragraphs]
        if story.take is not None:
            parts.append(_take_html(story.take))
        parts.append(f'<p class="source">{render_link(story.source.label, story.source.url)}</p>')
    return "\n".join(parts)


def render_research_desk(issue: Issue) -> str:
    rd = issue.research_desk
    parts = ["<h1>The Research Desk</h1>", f'<p class="deck">{render_inline(rd.intro)}</p>']
    for paper in rd.papers:
        status_label = "peer reviewed" if paper.status == "peer-reviewed" else paper.status
        parts.append('<div class="paper">')
        parts.append(f'<p class="kicker">{render_inline(paper.field)} · {render_inline(status_label)}</p>')
        parts.append(f"<h2>{render_inline(paper.title)}</h2>")
        parts.append(f"<p><b>{render_inline(paper.byline)}</b></p>")
        parts.append(f"<p>{render_inline(paper.methods)}</p>")
        parts.append(f"<p>{render_inline(paper.result)}</p>")
        if paper.why_it_matters:
            parts.append(f'<p class="take"><b>Why it matters:</b> {render_inline(paper.why_it_matters)}</p>')
        parts.append(f"<p><b>Limitation:</b> {render_inline(paper.limitation)}</p>")
        link_html = "<br/>".join(render_link(link.label, link.url) for link in paper.links)
        parts.append(f'<p class="source">{link_html}</p>')
        parts.append("</div>")
    return "\n".join(parts)


def render_wildcard_desk(issue: Issue) -> str:
    wd = issue.wildcard_desk
    parts = [
        f"<h1>{render_inline(wd.desk_name)}</h1>",
        f'<p class="kicker">{render_inline(wd.kicker)}</p>',
        f"<h2>{render_inline(wd.headline)}</h2>",
    ]
    parts += [f"<p>{render_inline(para)}</p>" for para in wd.paragraphs]
    if wd.take is not None:
        parts.append(_take_html(wd.take))
    link_html = "<br/>".join(render_link(link.label, link.url) for link in wd.sources)
    parts.append(f'<p class="source">{link_html}</p>')
    return "\n".join(parts)


def render_signals(issue: Issue) -> str:
    parts = ["<h1>Signals</h1>"]
    for item in issue.signals.items:
        parts.append(f"<h2>{render_inline(item.label)}</h2>")
        parts.append(f'<p class="stat">{render_inline(item.headline)}</p>')
        parts.append(f"<p>{render_inline(item.body)}</p>")
    return "\n".join(parts)


def render_for_zeel(issue: Issue) -> str:
    fs = issue.for_zeel
    fh = issue.from_hermys_desk
    parts = ["<h1>For Zeel</h1>", f"<h2>{render_inline(fs.headline)}</h2>"]
    parts += [f"<p>{render_inline(para)}</p>" for para in fs.paragraphs]
    if fs.idea_worth_stealing:
        parts.append(f'<p class="take"><b>Idea worth stealing:</b> {render_inline(fs.idea_worth_stealing)}</p>')
    parts.append("<h2>From Hermy’s desk</h2>")
    parts += [f"<p>{render_inline(para)}</p>" for para in fh.paragraphs]
    if fh.closing_note:
        parts.append(f'<p class="center small">{render_inline(fh.closing_note)}</p>')
    return "\n".join(parts)


def render_source_ledger(issue: Issue) -> str:
    parts = [
        "<h1>Sources</h1>",
        '<p class="deck">Every direct link cited in this edition.</p>',
        "<ul>",
    ]
    parts += [f"<li>{render_link(link.label, link.url)}</li>" for link in issue.source_ledger]
    parts.append("</ul>")
    return "\n".join(parts)


def render_chapters(issue: Issue) -> list[tuple[str, str, str]]:
    """Return ``(title, file_name, xhtml_body)`` for every desk, in reading order."""
    return [
        ("Page One", "page-one.xhtml", render_page_one(issue)),
        ("The Briefing", "briefing.xhtml", render_briefing(issue)),
        ("The Research Desk", "research.xhtml", render_research_desk(issue)),
        (issue.wildcard_desk.desk_name, "wildcard.xhtml", render_wildcard_desk(issue)),
        ("Signals", "signals.xhtml", render_signals(issue)),
        ("For Zeel", "for-zeel.xhtml", render_for_zeel(issue)),
        ("Sources", "sources.xhtml", render_source_ledger(issue)),
    ]
