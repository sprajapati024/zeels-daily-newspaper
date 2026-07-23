"""JSON schema for a Zeel's Daily newspaper issue.

Validates ``/var/www/briefs/<date>.newspaper.json`` into a tree of frozen
dataclasses. Every required section named in the production spec is
enforced here: metadata, cover_image, page_one (lead + index), briefing,
research_desk (exactly two papers, each with a status, methods, result,
limitation and at least one direct paper/PDF/DOI link), wildcard_desk,
signals, for_zeel, from_hermys_desk, and source_ledger.

This module only validates structure and cross-references (e.g. every URL
cited elsewhere in the issue must also appear in the source ledger). Text
is not rendered here -- see ``newspaper_html.py`` for escaping/markup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COVER_IMAGE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.(jpe?g)$", re.IGNORECASE)
ALLOWED_LINK_SCHEMES = {"http", "https"}
RESEARCH_PAPER_COUNT = 2
RESEARCH_STATUSES = {"preprint", "peer-reviewed"}


class NewspaperSchemaError(ValueError):
    """Raised when an issue JSON document fails schema validation."""

    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path


def _require_dict(data, path: str) -> dict:
    if not isinstance(data, dict):
        raise NewspaperSchemaError(path, f"expected an object, got {type(data).__name__}")
    return data


def _require_list(data, path: str, *, min_len: int = 0) -> list:
    if not isinstance(data, list):
        raise NewspaperSchemaError(path, f"expected an array, got {type(data).__name__}")
    if len(data) < min_len:
        raise NewspaperSchemaError(path, f"expected at least {min_len} item(s), got {len(data)}")
    return data


def _require_str(data, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(data, str):
        raise NewspaperSchemaError(path, f"expected a string, got {type(data).__name__}")
    if not allow_empty and not data.strip():
        raise NewspaperSchemaError(path, "must not be empty")
    return data


def _get(d: dict, key: str, path: str):
    if key not in d:
        raise NewspaperSchemaError(path, f"missing required key {key!r}")
    return d[key]


def _require_url(data, path: str) -> str:
    url = _require_str(data, path)
    scheme = urlsplit(url).scheme.lower()
    if scheme not in ALLOWED_LINK_SCHEMES:
        raise NewspaperSchemaError(path, f"must be a direct http(s) link, got {url!r}")
    return url


@dataclass(frozen=True)
class LinkRef:
    label: str
    url: str


def _parse_link(data, path: str) -> LinkRef:
    d = _require_dict(data, path)
    label = _require_str(_get(d, "label", path), f"{path}.label")
    url = _require_url(_get(d, "url", path), f"{path}.url")
    return LinkRef(label=label, url=url)


def _parse_links(data, path: str, *, min_len: int = 1) -> tuple[LinkRef, ...]:
    items = _require_list(data, path, min_len=min_len)
    return tuple(_parse_link(item, f"{path}[{i}]") for i, item in enumerate(items))


@dataclass(frozen=True)
class Take:
    label: str
    text: str


def _parse_take(data, path: str) -> Take | None:
    if data is None:
        return None
    d = _require_dict(data, path)
    label = _require_str(_get(d, "label", path), f"{path}.label")
    text = _require_str(_get(d, "text", path), f"{path}.text")
    return Take(label=label, text=text)


def _parse_paragraphs(data, path: str) -> tuple[str, ...]:
    items = _require_list(data, path, min_len=1)
    return tuple(_require_str(item, f"{path}[{i}]") for i, item in enumerate(items))


@dataclass(frozen=True)
class Metadata:
    date: str
    title: str
    edition_label: str
    day_of_week_label: str
    volume: str
    edition: str


def _parse_metadata(data, path: str) -> Metadata:
    d = _require_dict(data, path)
    date = _require_str(_get(d, "date", path), f"{path}.date")
    if not DATE_RE.match(date):
        raise NewspaperSchemaError(f"{path}.date", f"must be YYYY-MM-DD, got {date!r}")
    title = _require_str(d.get("title", "Zeel’s Daily"), f"{path}.title")
    edition_label = _require_str(_get(d, "edition_label", path), f"{path}.edition_label")
    day_of_week_label = _require_str(_get(d, "day_of_week_label", path), f"{path}.day_of_week_label")
    volume = _require_str(_get(d, "volume", path), f"{path}.volume")
    edition = _require_str(_get(d, "edition", path), f"{path}.edition")
    return Metadata(
        date=date,
        title=title,
        edition_label=edition_label,
        day_of_week_label=day_of_week_label,
        volume=volume,
        edition=edition,
    )


@dataclass(frozen=True)
class IndexEntry:
    label: str
    text: str


def _parse_index_entry(data, path: str) -> IndexEntry:
    d = _require_dict(data, path)
    label = _require_str(_get(d, "label", path), f"{path}.label")
    text = _require_str(_get(d, "text", path), f"{path}.text")
    return IndexEntry(label=label, text=text)


@dataclass(frozen=True)
class PageOne:
    kicker: str
    headline: str
    deck: str
    lead_paragraphs: tuple[str, ...]
    source: LinkRef
    index: tuple[IndexEntry, ...]
    take: Take | None = None


def _parse_page_one(data, path: str) -> PageOne:
    d = _require_dict(data, path)
    kicker = _require_str(_get(d, "kicker", path), f"{path}.kicker")
    headline = _require_str(_get(d, "headline", path), f"{path}.headline")
    deck = _require_str(_get(d, "deck", path), f"{path}.deck")
    lead_paragraphs = _parse_paragraphs(_get(d, "lead_paragraphs", path), f"{path}.lead_paragraphs")
    source = _parse_link(_get(d, "source", path), f"{path}.source")
    index_items = _require_list(_get(d, "index", path), f"{path}.index", min_len=1)
    index = tuple(_parse_index_entry(item, f"{path}.index[{i}]") for i, item in enumerate(index_items))
    take = _parse_take(d.get("take"), f"{path}.take")
    return PageOne(
        kicker=kicker,
        headline=headline,
        deck=deck,
        lead_paragraphs=lead_paragraphs,
        source=source,
        index=index,
        take=take,
    )


@dataclass(frozen=True)
class Story:
    kicker: str
    headline: str
    paragraphs: tuple[str, ...]
    source: LinkRef
    take: Take | None = None


def _parse_story(data, path: str) -> Story:
    d = _require_dict(data, path)
    kicker = _require_str(_get(d, "kicker", path), f"{path}.kicker")
    headline = _require_str(_get(d, "headline", path), f"{path}.headline")
    paragraphs = _parse_paragraphs(_get(d, "paragraphs", path), f"{path}.paragraphs")
    source = _parse_link(_get(d, "source", path), f"{path}.source")
    take = _parse_take(d.get("take"), f"{path}.take")
    return Story(kicker=kicker, headline=headline, paragraphs=paragraphs, source=source, take=take)


@dataclass(frozen=True)
class Briefing:
    stories: tuple[Story, ...]


def _parse_briefing(data, path: str) -> Briefing:
    d = _require_dict(data, path)
    story_items = _require_list(_get(d, "stories", path), f"{path}.stories", min_len=1)
    stories = tuple(_parse_story(item, f"{path}.stories[{i}]") for i, item in enumerate(story_items))
    return Briefing(stories=stories)


@dataclass(frozen=True)
class ResearchPaper:
    field: str
    status: str
    title: str
    byline: str
    methods: str
    result: str
    limitation: str
    links: tuple[LinkRef, ...]
    why_it_matters: str | None = None


def _parse_research_paper(data, path: str) -> ResearchPaper:
    d = _require_dict(data, path)
    field_ = _require_str(_get(d, "field", path), f"{path}.field")
    status = _require_str(_get(d, "status", path), f"{path}.status")
    if status not in RESEARCH_STATUSES:
        raise NewspaperSchemaError(
            f"{path}.status", f"must be one of {sorted(RESEARCH_STATUSES)}, got {status!r}"
        )
    title = _require_str(_get(d, "title", path), f"{path}.title")
    byline = _require_str(_get(d, "byline", path), f"{path}.byline")
    methods = _require_str(_get(d, "methods", path), f"{path}.methods")
    result = _require_str(_get(d, "result", path), f"{path}.result")
    limitation = _require_str(_get(d, "limitation", path), f"{path}.limitation")
    links = _parse_links(_get(d, "links", path), f"{path}.links", min_len=1)
    why_raw = d.get("why_it_matters")
    why_it_matters = _require_str(why_raw, f"{path}.why_it_matters") if why_raw is not None else None
    return ResearchPaper(
        field=field_,
        status=status,
        title=title,
        byline=byline,
        methods=methods,
        result=result,
        limitation=limitation,
        links=links,
        why_it_matters=why_it_matters,
    )


@dataclass(frozen=True)
class ResearchDesk:
    intro: str
    papers: tuple[ResearchPaper, ResearchPaper]


def _parse_research_desk(data, path: str) -> ResearchDesk:
    d = _require_dict(data, path)
    intro = _require_str(_get(d, "intro", path), f"{path}.intro")
    paper_items = _require_list(_get(d, "papers", path), f"{path}.papers")
    if len(paper_items) != RESEARCH_PAPER_COUNT:
        raise NewspaperSchemaError(
            f"{path}.papers", f"must contain exactly {RESEARCH_PAPER_COUNT} papers, got {len(paper_items)}"
        )
    papers = tuple(_parse_research_paper(item, f"{path}.papers[{i}]") for i, item in enumerate(paper_items))
    return ResearchDesk(intro=intro, papers=papers)


@dataclass(frozen=True)
class WildcardDesk:
    desk_name: str
    kicker: str
    headline: str
    paragraphs: tuple[str, ...]
    sources: tuple[LinkRef, ...]
    take: Take | None = None


def _parse_wildcard_desk(data, path: str) -> WildcardDesk:
    d = _require_dict(data, path)
    desk_name = _require_str(d.get("desk_name", "The Wildcard Desk"), f"{path}.desk_name")
    kicker = _require_str(_get(d, "kicker", path), f"{path}.kicker")
    headline = _require_str(_get(d, "headline", path), f"{path}.headline")
    paragraphs = _parse_paragraphs(_get(d, "paragraphs", path), f"{path}.paragraphs")
    sources = _parse_links(_get(d, "sources", path), f"{path}.sources", min_len=1)
    take = _parse_take(d.get("take"), f"{path}.take")
    return WildcardDesk(
        desk_name=desk_name, kicker=kicker, headline=headline, paragraphs=paragraphs, sources=sources, take=take
    )


@dataclass(frozen=True)
class SignalItem:
    label: str
    headline: str
    body: str


def _parse_signal_item(data, path: str) -> SignalItem:
    d = _require_dict(data, path)
    label = _require_str(_get(d, "label", path), f"{path}.label")
    headline = _require_str(_get(d, "headline", path), f"{path}.headline")
    body = _require_str(_get(d, "body", path), f"{path}.body")
    return SignalItem(label=label, headline=headline, body=body)


@dataclass(frozen=True)
class Signals:
    items: tuple[SignalItem, ...]


def _parse_signals(data, path: str) -> Signals:
    d = _require_dict(data, path)
    item_data = _require_list(_get(d, "items", path), f"{path}.items", min_len=1)
    items = tuple(_parse_signal_item(item, f"{path}.items[{i}]") for i, item in enumerate(item_data))
    return Signals(items=items)


@dataclass(frozen=True)
class ForZeel:
    headline: str
    paragraphs: tuple[str, ...]
    idea_worth_stealing: str | None = None


def _parse_for_zeel(data, path: str) -> ForZeel:
    d = _require_dict(data, path)
    headline = _require_str(_get(d, "headline", path), f"{path}.headline")
    paragraphs = _parse_paragraphs(_get(d, "paragraphs", path), f"{path}.paragraphs")
    idea_raw = d.get("idea_worth_stealing")
    idea = _require_str(idea_raw, f"{path}.idea_worth_stealing") if idea_raw is not None else None
    return ForZeel(headline=headline, paragraphs=paragraphs, idea_worth_stealing=idea)


@dataclass(frozen=True)
class FromHermysDesk:
    paragraphs: tuple[str, ...]
    closing_note: str | None = None


def _parse_from_hermys_desk(data, path: str) -> FromHermysDesk:
    d = _require_dict(data, path)
    paragraphs = _parse_paragraphs(_get(d, "paragraphs", path), f"{path}.paragraphs")
    closing_raw = d.get("closing_note")
    closing_note = _require_str(closing_raw, f"{path}.closing_note") if closing_raw is not None else None
    return FromHermysDesk(paragraphs=paragraphs, closing_note=closing_note)


@dataclass(frozen=True)
class Issue:
    metadata: Metadata
    cover_image: str
    page_one: PageOne
    briefing: Briefing
    research_desk: ResearchDesk
    wildcard_desk: WildcardDesk
    signals: Signals
    for_zeel: ForZeel
    from_hermys_desk: FromHermysDesk
    source_ledger: tuple[LinkRef, ...]


def _cited_urls(issue_parts: dict) -> set[str]:
    urls: set[str] = set()
    page_one: PageOne = issue_parts["page_one"]
    urls.add(page_one.source.url)
    briefing: Briefing = issue_parts["briefing"]
    for story in briefing.stories:
        urls.add(story.source.url)
    research_desk: ResearchDesk = issue_parts["research_desk"]
    for paper in research_desk.papers:
        urls.update(link.url for link in paper.links)
    wildcard_desk: WildcardDesk = issue_parts["wildcard_desk"]
    urls.update(link.url for link in wildcard_desk.sources)
    return urls


def parse_issue(data: dict) -> Issue:
    """Validate a raw issue dict and return a fully-typed :class:`Issue`.

    Raises :class:`NewspaperSchemaError` (a ``ValueError``) with a path-
    qualified message on the first structural problem found.
    """
    root = _require_dict(data, "issue")

    metadata = _parse_metadata(_get(root, "metadata", "issue"), "issue.metadata")

    cover_image = _require_str(_get(root, "cover_image", "issue"), "issue.cover_image")
    if "/" in cover_image or "\\" in cover_image or ".." in cover_image:
        raise NewspaperSchemaError("issue.cover_image", f"must be a bare filename, got {cover_image!r}")
    if not COVER_IMAGE_NAME_RE.match(cover_image):
        raise NewspaperSchemaError("issue.cover_image", f"must be a .jpg/.jpeg filename, got {cover_image!r}")

    page_one = _parse_page_one(_get(root, "page_one", "issue"), "issue.page_one")
    briefing = _parse_briefing(_get(root, "briefing", "issue"), "issue.briefing")
    research_desk = _parse_research_desk(_get(root, "research_desk", "issue"), "issue.research_desk")
    wildcard_desk = _parse_wildcard_desk(_get(root, "wildcard_desk", "issue"), "issue.wildcard_desk")
    signals = _parse_signals(_get(root, "signals", "issue"), "issue.signals")
    for_zeel = _parse_for_zeel(_get(root, "for_zeel", "issue"), "issue.for_zeel")
    from_hermys_desk = _parse_from_hermys_desk(_get(root, "from_hermys_desk", "issue"), "issue.from_hermys_desk")

    ledger_items = _require_list(_get(root, "source_ledger", "issue"), "issue.source_ledger", min_len=1)
    source_ledger = tuple(_parse_link(item, f"issue.source_ledger[{i}]") for i, item in enumerate(ledger_items))

    cited = _cited_urls(
        {
            "page_one": page_one,
            "briefing": briefing,
            "research_desk": research_desk,
            "wildcard_desk": wildcard_desk,
        }
    )
    ledger_urls = {link.url for link in source_ledger}
    missing = cited - ledger_urls
    if missing:
        raise NewspaperSchemaError(
            "issue.source_ledger", f"missing {len(missing)} cited url(s) from the ledger: {sorted(missing)}"
        )

    return Issue(
        metadata=metadata,
        cover_image=cover_image,
        page_one=page_one,
        briefing=briefing,
        research_desk=research_desk,
        wildcard_desk=wildcard_desk,
        signals=signals,
        for_zeel=for_zeel,
        from_hermys_desk=from_hermys_desk,
        source_ledger=source_ledger,
    )
